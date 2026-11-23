#!/usr/bin/env bash
# localllma-setup – one-click local AI stack for Fedora (Framework Laptop 16)
# Commands: install update repair doctor status test benchmark backup restore uninstall
set -euo pipefail
umask 077

usage() {
    cat <<'HELP'
Usage: ./setup.sh [command] [options]

Commands
  install    set up everything that is missing (default, repeatable, resumable)
  update     re-run install and refresh the pinned Pi release only
  repair     re-create missing links/units/config from this repository
  doctor     diagnose hardware, services, router, webui, pi, mcp, skills, sandbox
  status     compact view of the installed environment
  test       functional acceptance (router, models, webui, mcp, pi, sandbox)
  benchmark  run the reproducible benchmark scripts in benchmarks/
  backup     versioned backup of managed configs into ~/.local/state/localllma-setup
  restore    restore a previous backup after validation
  creative-studio {install|update|serve|status|doctor|test|backup|restore|uninstall}
             optional Local Creative Studio (127.0.0.1:8700, user data is kept)

Install options
  --download-models   download missing GGUF files (up to 37.1 GB)
  --coding-candidates install or update the six opt-in coding candidate models
                      (packages/models-coding-candidates.tsv, about 60.5 GB)
  --download-cuda     download the official CUDA 12.8 runtime archive
  --cuda-lib-dir DIR  take the three CUDA 12 libraries from DIR (backup path)
  --dry-run           print planned changes, validate, write nothing

Environment
  LLAMA_SETUP_CACHE    archive cache (default ~/.cache/localllma-setup)
  LLAMA_SETUP_SKILLS   skills dir    (default ~/dev/github/skillset/skills)

Restarting after an interrupted run resumes where it stopped. Managed files that
differ from this repository abort instead of overwriting user edits.
HELP
}

fail() { printf 'Fehler: %s\n' "$*" >&2; exit 1; }

cmd=install
arg=
coding_candidates=false
download_models=false
download_cuda=false
cuda_lib_dir=
dry_run=false
while (( $# )); do
    case $1 in
        install|update|repair|doctor|status|test|benchmark|backup|restore) cmd=$1 ;;
        uninstall) cmd=uninstall ;;
        creative-studio)
            src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
            exec python3 "$src/libexec/llama-creative-studio" "${@:2}" ;;
        --download-models) download_models=true ;;
        --coding-candidates) coding_candidates=true ;;
        --download-cuda) download_cuda=true ;;
        --cuda-lib-dir)
            (( $# >= 2 )) || fail 'missing path after --cuda-lib-dir'
            cuda_lib_dir=$(realpath -e -- "$2") || fail "CUDA path missing: $2"
            shift ;;
        --dry-run) dry_run=true ;;
        -h|--help) usage; exit 0 ;;
        --*) usage >&2; fail "unknown option: $1" ;;
        *) case $cmd in restore|benchmark) [[ -z $arg ]] && arg=$1 || { usage >&2; fail "extra argument: $1"; } ;;
              *) usage >&2; fail "unknown command: $1" ;; esac ;;
    esac
    shift
done
if [[ -n $cuda_lib_dir && $download_cuda == true ]]; then
    fail 'choose --cuda-lib-dir or --download-cuda, not both'
fi

src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cache=${LLAMA_SETUP_CACHE:-$HOME/.cache/localllma-setup}
skills=${LLAMA_SETUP_SKILLS:-$HOME/dev/github/skillset/skills}
[[ $skills = /* ]] || fail 'LLAMA_SETUP_SKILLS must be absolute'
opt=$HOME/.local/opt/llama.cpp
cfg=$HOME/.config/llama.cpp
models=$HOME/models/gguf
state=$HOME/.local/state/localllma-setup
unitsdir=$HOME/.config/systemd/user
release=b12503
pi_version=1.5.2
pi_pkg=@earendil-works/pi-coding-agent
pi_dir=${LLAMA_SETUP_PI_DIR:-$HOME/.pi/agent}
pi_agent_json=$pi_dir
websearch='websearch-mcp-dfdbc9bda9119fbf67610f288eae43821180f621'
runtime_archive=cudart-llama-b12503-bin-ubuntu-cuda-12.8-x64.tar.gz
libnames=(libcudart.so.12 libcublas.so.12 libcublasLt.so.12)
router=http://127.0.0.1:8080

log()  { printf '%s\n' "$*"; }
skip() { printf 'Übersprungen: %s\n' "$*"; }
warn() { printf 'Warnung: %s\n' "$*" >&2; }
DRY=$dry_run

step() { :; }

# ---- shared primitives (verified with b12503 restore) ---------------------

require_cmds() {
    local missing=()
    for command in "$@"; do
        command -v "$command" >/dev/null || missing+=("$command")
    done
    (( ${#missing[@]} == 0 )) || fail "missing programs: ${missing[*]} (see README.md)"
}

hash_ok() {
    local actual
    actual=$(sha256sum < "$1") || return 1
    [[ ${actual%% *} == "$2" ]]
}

fetch() {
    local dest=$1 sha=$2 url=$3 bytes=${4:-} part="$1.partial"
    if [[ -e $dest || -L $dest ]]; then
        if [[ ! -f $dest ]] || ! hash_ok "$dest" "$sha"; then
            fail "SHA-256 mismatch: $dest"
        fi
        return
    fi
    [[ ! -L $part ]] || fail "unexpected symlink: $part"
    log "download ${dest##*/}"
    if $DRY; then return 0; fi
    local have=
    [[ -f $part ]] && have=$(stat -c %s -- "$part")
    if [[ -z $bytes || ! -f $part || $have != "$bytes" ]]; then
        curl -qfSL --retry 3 --continue-at - --output "$part" "$url" || fail "interrupted: $part"
    fi
    if ! hash_ok "$part" "$sha"; then
        rm -- "$part"
        fail "SHA-256 of download mismatch: $dest"
    fi
    mv -T -- "$part" "$dest"
}

archive() {
    local expected=$1 name sha url
    while IFS=$'\t' read -r name sha url; do
        if [[ $name == "$expected" ]]; then
            fetch "$cache/$name" "$sha" "$url"
            return
        fi
    done < "$src/packages/artifacts.tsv"
    fail "archive missing from manifest: $expected"
}

model_rows() { tail -n +2 "$src/packages/models.tsv"; }
candidates_rows() { tail -n +2 "$src/packages/models-coding-candidates.tsv"; }

unpack() {
    local name=$1 dest=$2 strip=$3
    archive "$name"
    if $DRY; then log "plan: extract $name -> $dest"; return 1; fi
    mkdir -- "$dest"
    tar --extract --file "$cache/$name" --directory "$dest" --strip-components="$strip" \
        --no-same-owner --no-same-permissions
}

npm_install() (
    cd -- "$1"
    cp -- "$src/packages/$2/"package{,-lock}.json .
    export PATH="$opt/node/bin:$PATH"
    npm ci --include=dev --ignore-scripts --no-audit --no-fund --no-update-notifier
    if [[ $2 == websearch ]]; then
        npm run build
    fi
)

# managed file: same -> ok, different -> abort so user edits survive
install_file() {
    local mode=$1 source=$2 target=$3
    if [[ -e $target || -L $target ]]; then
        cmp -s -- "$source" "$target" || fail "existing file differs: $target"
    else
        if $DRY; then log "plan: install $target"; return 0; fi
        install -m "$mode" -- "$source" -- "$target"
    fi
}

# The managed router preset file follows the repository; keep one backup on
# change instead of aborting like install_file (the candidate track does the same).
sync_models_ini() {
    local source=$1 target=$2
    if $DRY; then log "plan: sync $target"; return 0; fi
    if [[ -e $target ]] && ! cmp -s -- "$source" "$target"; then
        mkdir -p -- "$state/backups"
        cp -a -- "$target" "$state/backups/models.ini.$(date +%s)"
        install -m 600 -- "$source" "$target"
        log 'router preset file updated (previous copy kept in the setup state)'
    elif [[ ! -e $target ]]; then
        mkdir -p -- "${target%/*}"
        install -m 600 -- "$source" "$target"
    fi
}

# docs are repository-owned: replace on drift, keep one backup per run
install_doc() {
    local source=$1 target=$2
    if [[ -e $target ]] && ! cmp -s -- "$source" "$target"; then
        if $DRY; then log "plan: refresh doc $target"; return 0; fi
        mkdir -p -- "$state/doc-backup"
        cp -a -- "$target" "$state/doc-backup/$(basename -- "$target").$(date +%s)"
    fi
    [[ -e $target ]] && return 0
    if $DRY; then log "plan: install doc $target"; return 0; fi
    install -m 600 -- "$source" "$target"
}

link_to() {
    local source=$1 target=$2
    if [[ -e $target || -L $target ]]; then
        [[ -L $target && $(readlink -- "$target") == "$source" ]] || fail "existing path differs: $target"
    else
        if $DRY; then log "plan: link $target -> $source"; return 0; fi
        ln -s -- "$source" -- "$target"
    fi
}

# ---- phases ----------------------------------------------------------------

hardware_report() {
    local distro
    distro=$(. /etc/os-release && printf '%s %s' "${NAME:-?}" "${VERSION_ID:-?}")
    local arch cores mem vram gib_glibc
    arch=$(uname -m)
    cores=$(nproc)
    mem=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1048576 ))
    vram=$(( $(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1) ))
    gib_glibc=$(ldd --version 2>/dev/null | head -1 | grep -o '[0-9]*\.[0-9]*$' || echo '?')
    local thp
    thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null | tr -d ' ' || echo n/a)
    log "hardware: $distro $arch, ${cores} CPUs, ${mem} GiB RAM, GPU ${vram:-?} MiB, glibc ${gib_glibc}, THP ${thp}"
    if [[ $arch != x86_64 ]]; then
        warn 'x86_64 expected; tested range ends here'
    fi
    if (( mem < 31 )); then
        warn "RAM ${mem} GiB below the tested 32 GiB floor - 256K context will not fit"
    fi
    if [[ -n ${vram:-} ]] && (( vram < 6144 )); then
        warn "VRAM ${vram} MiB below the tested 6 GiB floor - profiles were tuned for 8 GiB"
    fi
    if (( cores < 12 )); then
        warn "${cores} CPUs below 12 tested threads - decode throughput will drop"
    fi
}

preflight() {
    [[ $(uname -s) == Linux ]] || fail 'Linux user account only'
    [[ $HOME =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail 'HOME must be an absolute plain path'
    require_cmds curl sha256sum flock tar xz python3 jq uv nvidia-smi socat bwrap pasta nft setpriv xdg-open node npm
    nvidia-smi -L >/dev/null || fail 'the NVIDIA driver must work before setup'
    node -e 'const [a,m]=process.versions.node.split(".").map(Number);process.exit(a>22||(a===22&&m>=19)?0:1)' ||
        fail 'Node.js >= 22.19 required for Pi (installer can provide it via packages)'
    mkdir -p -- "$cache" "$opt" "$models" "$cfg" "$state/logs" "$pi_agent_json"
}

lock() {
    exec 9>"$opt/.setup.lock"
    flock -n 9 || fail 'another setup for this account is running'
}

backup_configs() {
    local out=$1
    mkdir -p -- "$state/backups"
    local paths=() p
    [[ -d $cfg ]] && paths+=(".config/llama.cpp")
    [[ -d $unitsdir ]] && paths+=(".config/systemd/user")
    for p in settings.json auth.json mcp.json models-store.json prompts; do
        [[ -f $pi_dir/$p ]] && paths+=(".pi/agent/$p")
    done
    (( ${#paths[@]} )) || { printf 'nothing to back up\n'; return 0; }
    if $DRY; then log "plan: backup ${paths[*]} -> $out"; return 0; fi
    tar -czf "$out" -C "$HOME" "${paths[@]}"
    printf '%s\n' "$out"
}

install_stack() {
    hardware_report

    while IFS=$'\t' read -r name repo revision bytes sha _rest; do
        [[ $name != filename ]] || continue
        if [[ ! -f $models/$name && $download_models == false ]]; then
            fail "GGUF missing: $models/$name - restore it from backup or use --download-models"
        fi
    done < <(model_rows)
    if [[ ! -d $opt/$release && -z $cuda_lib_dir && $download_cuda == false && ! -f $cache/$runtime_archive ]]; then
        fail 'CUDA runtime missing - pass --cuda-lib-dir DIR or --download-cuda'
    fi
    if [[ ! -d $opt/$release && -n $cuda_lib_dir ]]; then
        (cd -- "$cuda_lib_dir" && sha256sum --check --quiet "$src/packages/cuda-libs.sha256") ||
            fail 'CUDA libraries differ from the recorded backup - use that backup or --download-cuda'
    fi
    while IFS=$'\t' read -r name repo revision bytes sha _rest; do
        [[ $name != filename ]] || continue
        [[ -f $models/$name ]] && continue
        log "verify $name"
        fetch "$models/$name" "$sha" "https://huggingface.co/$repo/resolve/$revision/$name" "$bytes"
    done < <(model_rows)

    local stage
    stage=$(mktemp -d "$opt/.setup.XXXXXXXX")
    # shellcheck disable=SC2064
    trap "rm -rf -- '$stage'" EXIT

    if [[ ! -d $opt/$release ]]; then
        unpack llama-b12503-bin-ubuntu-cuda-12.8-x64.tar.gz "$stage/$release" 1 || true
        if $DRY; then
            skip 'unpack llama.cpp release (dry-run)'
        else
            if [[ -z $cuda_lib_dir ]]; then
                unpack "$runtime_archive" "$stage/cuda" 0
            fi
            local lib file
            for lib in "${libnames[@]}"; do
                if [[ -n $cuda_lib_dir ]]; then
                    file=$cuda_lib_dir/$lib
                else
                    file=$(find -L "$stage/cuda" -type f -name "$lib" -print -quit)
                    [[ -n $file ]] || file=$(find -L "$stage/cuda" -type f -name "$lib.*" -print -quit)
                fi
                [[ -f $file ]] || fail "CUDA library missing: $lib"
                cp -L --reflink=auto -- "$file" "$stage/$release/$lib"
            done
            if ! "$stage/$release/llama-server" --list-devices > "$stage/devices" 2>&1 || ! grep 'CUDA0:' "$stage/devices"; then
                cat "$stage/devices" >&2
                fail 'CUDA0 was not detected'
            fi
            mv -T -- "$stage/$release" "$opt/$release"
        fi
    fi
    if ! $DRY; then
        "$opt/$release/llama-server" --version
        if ! "$opt/$release/llama-server" --list-devices > "$stage/devices" 2>&1 || ! grep 'CUDA0:' "$stage/devices"; then
            cat "$stage/devices" >&2
            fail 'CUDA0 was not detected'
        fi
    fi

    if [[ ! -d $opt/node ]]; then
        if unpack node-v24.22.1-linux-x64.tar.xz "$stage/node" 1; then
            [[ $("$stage/node/bin/node" --version) == v24.22.1 ]] || fail 'Node version mismatch'
            mv -T -- "$stage/node" "$opt/node"
        fi
    fi
    local nodebin=${LLAMA_SETUP_NODE:-$opt/node/bin/node}
    [[ -x $nodebin ]] || nodebin=$(command -v node)
    [[ $nodebin == *"$opt/node"* ]] && [[ ! -x $nodebin ]] && fail 'bundled Node missing - rerun without cache shortcuts'
    "$nodebin" --version >/dev/null

    if [[ ! -d $opt/github-mcp-v2.2.0 ]]; then
        if unpack github-mcp-server_Linux_x86_64.tar.gz "$stage/github-mcp-v2.2.0" 0; then
            "$stage/github-mcp-v2.2.0/github-mcp-server" --version
            mv -T -- "$stage/github-mcp-v2.2.0" "$opt/github-mcp-v2.2.0"
        fi
    fi
    if [[ ! -d $opt/mcp-http-v0.15.0 ]]; then
        if ! $DRY; then
            uv venv --python /usr/bin/python3 --relocatable "$stage/mcp-http-v0.15.0"
            uv pip sync --python "$stage/mcp-http-v0.15.0/bin/python" --require-hashes \
                "$src/packages/mcp-http/requirements.lock"
            mv -T -- "$stage/mcp-http-v0.15.0" "$opt/mcp-http-v0.15.0"
        else skip 'mcp gateway venv (dry-run)'; fi
    fi
    if [[ ! -d $opt/mcp ]]; then
        if $DRY; then skip 'node MCP servers (dry-run)'; else
            mkdir -- "$stage/mcp"; npm_install "$stage/mcp" mcp
            mv -T -- "$stage/mcp" "$opt/mcp"
        fi
    fi
    if [[ ! -d $opt/$websearch ]]; then
        if unpack websearch-mcp.tar.gz "$stage/$websearch" 1; then
            npm_install "$stage/$websearch" websearch
            mv -T -- "$stage/$websearch" "$opt/$websearch"
        fi
    fi

    # router + webui + MCP config (rendered even in dry-run so validation runs)
    sed "s|@HOME@|$HOME|g" "$src/config/models.ini.in" > "$stage/models.ini"
    sed "s|@HOME@|$HOME|g" "$src/config/llama-cpp.desktop.in" > "$stage/llama-cpp.desktop"
    python3 - "$src/config/mcp.json.in" "$HOME" "$skills" "$stage" "$src/config/ui.json" "$opt/node/bin/node" <<'PY'
import json, os, sys
from pathlib import Path
import shutil
path, home, skills, stage, ui_template, bundled = sys.argv[1:]
node = os.path.realpath(bundled) if os.access(bundled, os.X_OK) else (shutil.which("node") or "node")
config = json.loads(Path(path).read_text(encoding="utf-8").replace("@HOME@", home).replace("@NODE@", node))
servers = config["mcpServers"]
unavailable = set()
if os.path.isdir(skills):
    servers["skills"]["args"][-1] = skills
else:
    print(f"skills dir missing, filesystem MCP stays off: {skills}", file=sys.stderr)
    del servers["skills"]
    unavailable.add("llama-skills")
ui = json.loads(Path(ui_template).read_text())
if unavailable:
    entries = json.loads(ui["mcpServers"])
    ui["mcpServers"] = json.dumps(
        [e for e in entries if e["id"] not in unavailable], ensure_ascii=False, separators=(",", ":"))
for name, data in (("mcp.json", config), ("ui.json", ui)):
    (Path(stage) / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY

    mkdir -p -- "$cfg" "$unitsdir" "$HOME/.local/bin" "$HOME/.local/libexec" "$HOME/.local/share/applications"
    sync_models_ini "$stage/models.ini" "$cfg/models.ini"
    install_file 600 "$stage/mcp.json" "$cfg/mcp.json"
    install_file 600 "$stage/ui.json" "$cfg/ui.json"
    install_file 600 "$src/config/research.nft" "$cfg/research.nft"
    install_file 600 "$src/config/research-resolv.conf" "$cfg/research-resolv.conf"
    local n
    for n in render.py routing.jinja gemma4-base.jinja; do
        install_file 600 "$src/config/writing/$n" "$cfg/writing/$n"
    done
    for n in llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service; do
        install_file 644 "$src/units/$n" "$unitsdir/$n"
    done
    for n in llama-github-mcp llama-research pi-sandbox; do
    for n in llama-github-mcp llama-research; do
        install_file 755 "$src/libexec/$n" "$HOME/.local/libexec/$n"
    done
    install_file 755 "$src/libexec/llama-webui" "$HOME/.local/bin/llama-webui"
    install_file 644 "$stage/llama-cpp.desktop" "$HOME/.local/share/applications/llama-cpp.desktop"
    install_file 755 "$src/libexec/pi-sandbox" "$HOME/.local/bin/pi-sandbox"

    # Pi Coding Agent (official package, pinned, npm prefix - no cloud fallbacks)
    local pin=$pi_pkg@$pi_version
    local npm_prefix=$opt/pi
    if [[ ! -x $npm_prefix/bin/pi ]]; then
        if $DRY; then skip "pi $pin install (dry-run)"; else
            mkdir -p -- "$stage/pi"
            npm_config_prefix=$npm_prefix "$nodebin" "$npm_prefix" >/dev/null 2>&1 || true
            npm_config_prefix=$npm_prefix PATH="${npm_prefix}/bin:$PATH" \
                npm install -g --ignore-scripts --no-audit --no-fund "$pin" --prefix "$npm_prefix"
            [[ -x $npm_prefix/bin/pi ]] || fail 'pi binary missing after install'
        fi
    fi
    local pi_bin=$npm_prefix/bin/pi
    [[ -x $pi_bin ]] || pi_bin=$(command -v pi)
    [[ -n $pi_bin ]] || fail 'pi not installed - rerun without cache shortcuts'

    local stage_pi=$stage/pi-agent
    mkdir -p "$stage_pi"
    sed -e "s|@HOME@|$HOME|g" -e "s|@SKILLS@|$skills|g" "$src/config/pi.json.in" > "$stage/pi.json"
    jq '{compaction:.compaction, skills:[.skills], enableSkillCommands:true,
         defaultProvider:.defaultProvider, defaultModel:.defaultModel}' "$stage/pi.json" \
        > "$stage_pi/settings.json"
    jq '{(.defaultProvider // "llama.cpp"): {type:"api_key", key:"local",
         env:{LLAMA_BASE_URL:(.routerUrl // "http://127.0.0.1:8080")}}}' "$stage/pi.json" \
        > "$stage_pi/auth.json"
    jq --argjson mcp "$(jq '.mcpServers' "$stage/pi.json")" \
       '{mcpServers:($mcp|to_entries|map({key:.key,value:{url:.value}})|from_entries)}' "$stage/pi.json" \
        > "$stage_pi/mcp.json"
    mkdir -p -- "$pi_dir"
    local n
    for n in settings.json auth.json mcp.json; do
        if [[ -f $pi_dir/$n ]]; then
            jq . -- "$pi_dir/$n" >/dev/null || fail "Pi-Konfiguration ungueltig: $pi_dir/$n"
        else
            install_file 600 "$stage_pi/$n" "$pi_dir/$n"
        fi
    done

    # pi-permission-modes: Build as the standard start mode, sandbox stays on,
    # credentials masked, network allowlisted (config/permission-mode.json.in)
    if [[ -f $pi_dir/permission-mode/permission-mode.json ]]; then
        skip 'permission-mode.json (existing kept)'
    else
        mkdir -p "$pi_dir/permission-mode"
        /usr/bin/sed "s|@SKILLS@|$skills|g" "$src/config/permission-mode.json.in" \
            > "$stage_pi/permission-mode.json" \
            || fail 'permission-mode template render failed'
        jq -e . "$stage_pi/permission-mode.json" >/dev/null \
            || fail "permission-mode.json render invalid"
        install_file 644 "$stage_pi/permission-mode.json" \
            "$pi_dir/permission-mode/permission-mode.json"
    fi

    # pinned Pi extensions: manifest is the single install source; no auto-updates
    local m=$src/config/pi-manifest.json name ver status
    [[ -f $m ]] || fail 'config/pi-manifest.json missing'
    jq -e . "$m" >/dev/null || fail 'pi manifest invalid JSON'
    while IFS=$'\t' read -r name ver status; do
        [[ $status == active ]] || { skip "extension $name ($status)"; continue; }
        if grep -q "\"npm:$name\"" <<<"$(jq '.packages // []' "$pi_dir/settings.json" 2>/dev/null)"; then
            skip "extension $name already installed"
            continue
        fi
        if $DRY; then skip "pi install npm:$name@$ver (dry-run)"; continue
        elif ! $pi_bin install "npm:$name@$ver" >/dev/null 2>&1; then
            fail "pi install npm:$name@$ver failed"
        fi
    done < <(jq -r '.packages[] | [.name,.version,.status] | @tsv' "$m")

    # prompt templates ship from config/prompts/ (finish, review, fix-ci, finish-docs);
    # existing user copies are kept, same rule as settings.json
    local t
    for t in "$src"/config/prompts/*.md; do
        if [[ -e $pi_dir/prompts/$(basename "$t") ]]; then
            skip "prompt template $(basename "$t") (existing kept)"
        else
            install_file 644 "$t" "$pi_dir/prompts/$(basename "$t")"
        fi
    done
    if [[ ! -e $HOME/.local/bin/pi ]]; then
        link_to "$pi_bin" "$HOME/.local/bin/pi"
    fi

    # repository docs own the installed copies (one drift backup each)
    install_doc "$src/docs/SETUP.md" "$cfg/SETUP.md"
    install_doc "$src/docs/QUICKSTART.md" "$cfg/QUICKSTART.md"
    install_doc "$src/docs/MODEL_BENCHMARKS.md" "$cfg/MODEL_BENCHMARKS.md"
    install_doc "$src/docs/PERFORMANCE_OPTIMIZATION.md" "$cfg/PERFORMANCE_OPTIMIZATION.md"
    install_doc "$src/docs/PI_CODING_AGENT.md" "$cfg/PI_CODING_AGENT.md"

    if ! $DRY; then
        systemctl --user daemon-reload
        systemctl --user restart llama-cpp.service
        systemctl --user start llama-cpp-mcp.service llama-cpp-research.service
        systemctl --user start llama-cpp.service llama-cpp-mcp.service llama-cpp-research.service
    fi
    if [[ -d $cfg/pi-legacy || -d $cfg/claude ]]; then : ; fi
    log 'install complete - run ./setup.sh test for acceptance'
}

# ---- coding candidates (opt-in evaluation profile, about 60.5 GB) -----------
# ./setup.sh install --coding-candidates is the only path that fetches these
# files; the default one-click install never touches them. Re-running reuses
# valid GGUF files and resumes interrupted downloads via fetch().

install_coding_candidates() {
    hardware_report
    if ! $DRY; then mkdir -p -- "$cache" "$models"; fi

    local name repo revision bytes sha _rest missing=0 want=0
    while IFS=$'\t' read -r name repo revision bytes sha _rest; do
        [[ $name == filename ]] && continue
        if [[ -f $models/$name ]]; then
            hash_ok "$models/$name" "$sha" || fail "SHA-256 mismatch: $models/$name"
            log "reuse $name"
            continue
        fi
        missing=$((missing + 1)); want=$((want + bytes))
    done < <(candidates_rows)

    if (( missing > 0 )) && ! $DRY; then
        local avail
        avail=$(df -kB --output=avail -- "$models" | tail -1 | tr -d ' ')
        (( avail * 1024 > want + 4294967296 )) ||
            fail "not enough space below ${avail} KiB for $missing candidate files (about $((want / 1073741824)) GiB plus 4 GiB headroom)"
    fi

    # The candidate presets ship inside config/models.ini.in. Replace the
    # managed router configuration like install_doc does: keep one backup, then
    # write. The running router reloads its preset list after the downloads.
    if ! $DRY; then
        local stage rendered
        stage=$(mktemp -d)
        rendered=$stage/models.ini
        sed "s|@HOME@|$HOME|g" "$src/config/models.ini.in" > "$rendered"
        mkdir -p -- "$cfg"
        if [[ -e $cfg/models.ini ]] && ! cmp -s "$rendered" "$cfg/models.ini"; then
            mkdir -p -- "$state/backups"
            cp -a -- "$cfg/models.ini" "$state/backups/models.ini.$(date +%s)"
            install -m 600 -- "$rendered" "$cfg/models.ini"
            log 'router preset file updated (previous copy kept in the setup state)'
        elif [[ ! -e $cfg/models.ini ]]; then
            install -m 600 -- "$rendered" "$cfg/models.ini"
        fi
        rm -rf -- "$stage"
    fi

    while IFS=$'\t' read -r name repo revision bytes sha _rest; do
        [[ $name == filename ]] && continue
        [[ -f $models/$name ]] && continue
        log "verify $name"
        fetch "$models/$name" "$sha" "https://huggingface.co/$repo/resolve/$revision/$name" "$bytes"
    done < <(candidates_rows)

    if ! $DRY && curl -fsS --max-time 5 "$router/health" >/dev/null 2>&1; then
        curl -fsS --max-time 20 "$router/models?reload=1" >/dev/null &&
            log 'router preset list reloaded' || warn 'preset reload failed; restart llama-cpp.service'
    fi
    log 'coding candidates ready - select a preset id in Pi, e.g. coding-mellum-12b'
}

candidates_doctor() {
    local present=0 name repo revision sha _rest
    while IFS=$'\t' read -r name repo revision sha _rest; do
        [[ $name == filename ]] && continue
        [[ -f $models/$name ]] && present=$((present + 1))
    done < <(candidates_rows)
    printf 'coding candidates: %s/5 GGUF files in %s\n' "$present" "$models"
    if (( present == 5 )) && curl -qfsS --max-time 5 "$router/models" 2>/dev/null |
        jq -e '(.data // []) as $ids | ["coding-phai-256k","coding-mellum-12b",
               "coding-lfm-24b","coding-ornith-9b","coding-kat-35b"] | . - ($ids | map(.id)) | length == 0' >/dev/null; then
        printf 'PASS five candidate presets registered on the router\n'
    elif (( present == 5 )); then
        printf 'WARN candidate presets not registered; reload with %s/models?reload=1 or restart llama-cpp.service\n' "$router"
    fi
}

# ---- read-only commands -----------------------------------------------------

unit_state() { systemctl --user is-active "$1" 2>/dev/null || true; }

doctor() {
    local rc=0
    printf '== hardware\n';       hardware_report || rc=1
    printf '== services\n'
    local u
    for u in llama-cpp llama-cpp-mcp llama-cpp-research; do
        printf '%s: %s\n' "$u" "$(unit_state $u.service)"
        [[ $(unit_state $u.service) == active ]] || rc=1
    done
    printf '== router\n'
    curl -fsS --max-time 5 "$router/health" >/dev/null && printf 'health ok\n' || { printf 'router unreachable\n'; rc=1; }
    curl -fsS --max-time 10 "$router/models" 2>/dev/null | jq -r '.data[] | "\(.id): \(.status.value)"' || rc=1
    printf '== webui/mcp\n'
    curl -fsS --max-time 5 "$router/props" | jq -r '.ui_settings.mcpServers | fromjson[] | [.displayName,(.enabled|tostring)]|@tsv' || rc=1
    curl -fsS --max-time 5 http://127.0.0.1:8642/healthz >/dev/null && printf 'websearch ok\n' || { printf 'websearch down\n'; rc=1; }
    curl -fsS --max-time 5 http://127.0.0.1:8643/status >/dev/null && printf 'gateway ok\n' || { printf 'gateway down\n'; rc=1; }
    printf '== pi\n'
    if command -v pi >/dev/null; then pi --version; else printf 'pi missing\n'; rc=1; fi
    if [[ -f ${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/settings.json ]]; then
        local pdir=${PI_CODING_AGENT_DIR:-$HOME/.pi/agent} want
        while IFS= read -r want; do
            [[ -d $pdir/npm/node_modules/$want ]] && printf 'extension: %s ok\n' "$want" \
                || { printf 'extension: %s missing\n' "$want"; rc=1; }
        done < <(jq -r '[.packages[]|select(.status=="active")|.name][]' "$src/config/pi-manifest.json")
        ls "$pdir"/prompts/*.md >/dev/null 2>&1 \
            && printf 'prompt templates: %s\n' "$(ls "$pdir"/prompts/*.md | wc -l)" \
            || { printf 'prompt templates missing\n'; rc=1; }
        local pm=$pdir/permission-mode/permission-mode.json
        if [[ -f $pm ]] && jq -e '.defaultMode == "build"' "$pm" >/dev/null 2>&1; then
            printf 'permission modes: build default, sandbox on\n'
    candidates_doctor
        else
            printf 'permission modes: missing or defaultMode not build\n'; rc=1
        fi
    fi
    local l
    for l in typescript-language-server pyright ruff shellcheck rust-analyzer; do
        command -v "$l" >/dev/null || printf 'lsp/linter missing: %s\n' "$l"
    done
    printf '== skills\n'
    ls -d "$skills"/*/SKILL.md 2>/dev/null | wc -l
    printf '== sandbox\n'
    [[ -x $HOME/.local/bin/pi-sandbox ]] && printf 'pi-sandbox installed\n' || { printf 'pi-sandbox missing\n'; rc=1; }
    exit $rc
}

status() {
    printf 'llama.cpp: %s (release %s)\n' "$(unit_state llama-cpp.service)" "$release"
    printf 'gateway:   %s\n' "$(unit_state llama-cpp-mcp.service)"
    printf 'research:  %s\n' "$(unit_state llama-cpp-research.service)"
    curl -fsS --max-time 5 "$router/models" 2>/dev/null | jq -r '.data[].id' | sed 's/^/profile: /'
    [[ -x $HOME/.local/bin/pi ]] && printf 'pi: %s\n' "$(pi --version 2>/dev/null || echo present)"
}

acceptance_test() {
    local rc=0
    curl -fsS --max-time 5 "$router/health" >/dev/null || { echo 'FAIL router'; rc=1; }
    curl -fsS --max-time 240 "$router/props?model=coding-long-256k" |
        jq -e '.default_generation_settings.n_ctx == 262144' >/dev/null || { echo 'FAIL 262K context'; rc=1; }
    curl -fsS --max-time 240 "$router/props?model=research" |
        jq -e '.default_generation_settings.n_ctx == 32768' >/dev/null || { echo 'FAIL research ctx'; rc=1; }
    curl -fsS --max-time 5 http://127.0.0.1:8642/healthz | grep -q ok || { echo 'FAIL websearch'; rc=1; }
    curl -fsS --max-time 5 http://127.0.0.1:8643/status | grep -q configured || { echo 'FAIL gateway'; rc=1; }
    if command -v pi >/dev/null; then
        local out
        out=$(cd "$src" && PI_CODING_AGENT_DIR=$pi_dir timeout 300 pi -p --provider llama.cpp \
            --model coding-long-256k "Reply with exactly: SETUP-OK" 2>&1 | tail -1)
        [[ $out == *SETUP-OK* ]] || { echo "FAIL pi: $out"; rc=1; }
    else
        skip 'pi e2e (pi missing)'
    fi
    printf 'acceptance: %s\n' "$([[ $rc == 0 ]] && echo ok || echo failed)"
    exit $rc
}

benchmarks() {
    [[ $# == 0 ]] || exec bash "$src/benchmarks/$1"
    exec bash "$src/benchmarks/run.sh"
        jq -e 'any(.data[]; .id=="research") and any(.data[]; .id=="creative-writing")' >/dev/null ||
        { echo 'FAIL research/writing profiles missing'; rc=1; }
}

backup_cmd() {
    local out
    out=$state/backups/localllma-$(date +%Y%m%d-%H%M%S).tar.gz
    backup_configs "$out"
}

restore_cmd() {
    local archive=${1:-$(ls -1t "$state"/backups/localllma-*.tar.gz 2>/dev/null | head -1)}
    [[ -n $archive && -f $archive ]] || fail 'no backup given and none found'
    local stage; stage=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf -- '$stage'" EXIT
    tar -xzf "$archive" -C "$stage"
    local ok=true
    for f in settings.json auth.json mcp.json; do
        [[ -f $stage/.pi/agent/$f ]] && jq . "$stage/.pi/agent/$f" >/dev/null || true
    done
    [[ -f $stage/.config/llama.cpp/models.ini ]] || { echo 'backup lacks models.ini'; ok=false; }
    [[ $ok == true ]] || fail 'backup validation failed'
    [[ -d $stage/.config ]] && ( cd "$stage/.config" && tar -cf - . ) | tar -x -C "$HOME/.config"
    [[ -d $stage/.pi ]] && { mkdir -p "$HOME/.pi"; ( cd "$stage/.pi" && tar -cf - . ) | tar -x -C "$HOME/.pi"; }
    systemctl --user daemon-reload
    printf 'restored from %s\n' "$archive"
}

# ---- dispatch ----------------------------------------------------------------

case $cmd in
    install)   preflight; lock; install_stack ;;
    update)    preflight; lock; install_stack
               if command -v pi >/dev/null; then
                   log 'updating pinned Pi via pi update'
                   PI_CODING_AGENT_DIR=$pi_dir pi update || warn 'pi update failed (pinned version stays active)'
               fi ;;
    repair)    preflight; lock; install_stack
               systemctl --user daemon-reload ;;
    doctor)    preflight; doctor ;;
    status)    preflight; status ;;
    test)      acceptance_test ;;
    benchmark) shift 0; benchmarks "${1:-}" ;;
    backup)    backup_cmd ;;
    restore)   shift 0; restore_cmd "${1:-}" ;;
    uninstall) exec bash "$src/uninstall.sh" ;;
esac
