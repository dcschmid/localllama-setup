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
  update     apply the reviewed package and configuration pins in this checkout
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
  --coding-candidates install or update the five opt-in coding candidate models
                      (packages/models-coding-candidates.tsv, about 70 GB)
  --download-cuda     download the official CUDA 12.8 runtime archive
  --cuda-lib-dir DIR  take the three CUDA 12 libraries from DIR (backup path)
  --pi-only           limit maintenance to Pi
  --dry-run           print planned changes without modifying the installation

Environment
  LLAMA_SETUP_CACHE    archive cache (default ~/.cache/localllma-setup)
  LLAMA_SETUP_SKILLS   skills dir    (default ~/dev/github/skillset/skills)

Restarting after an interrupted run resumes where it stopped. Managed files that
differ from this repository abort instead of overwriting user edits.
HELP
}

fail() { printf 'Fehler: %s\n' "$*" >&2; exit 1; }

if [[ ${1:-} == benchmark ]]; then
    src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    shift
    case "${1:-}" in
        pi|bench-pi.py) shift; exec python3 "$src/benchmarks/bench-pi.py" "$@" ;;
        pi-context|bench-pi-context.py) shift; exec python3 "$src/benchmarks/bench-pi-context.py" "$@" ;;
        bench-context.py|measure-router.py) runner=$1; shift; exec python3 "$src/benchmarks/$runner" "$@" ;;
        run-perf-case.sh|run.sh) runner=$1; shift; exec bash "$src/benchmarks/$runner" "$@" ;;
        --help|-h) printf 'Usage: ./setup.sh benchmark {pi|pi-context|bench-context.py|run-perf-case.sh|run.sh} [args]\n'; exit 0 ;;
        *) exec bash "$src/benchmarks/run.sh" "$@" ;;
    esac
fi

cmd=install
arg=
pi_only=false
coding_candidates=false
download_models=false
download_cuda=false
cuda_lib_dir=
dry_run=false
while (( $# )); do
    case $1 in
        install|update|repair|doctor|status|test|backup|restore) cmd=$1 ;;
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
        --pi-only) pi_only=true ;;
        -h|--help) usage; exit 0 ;;
        --*) usage >&2; fail "unknown option: $1" ;;
        *) case $cmd in restore) [[ -z $arg ]] && arg=$1 || { usage >&2; fail "extra argument: $1"; } ;;
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
release=b12628
pi_dir=${LLAMA_SETUP_PI_DIR:-$HOME/.pi/agent}
websearch='websearch-mcp-dfdbc9bda9119fbf67610f288eae43821180f621'
runtime_archive=cudart-llama-b12628-bin-ubuntu-cuda-12.8-x64.tar.gz
libnames=(libcudart.so.12 libcublas.so.12 libcublasLt.so.12)
router=http://127.0.0.1:8080

log()  { printf '%s\n' "$*"; }
skip() { printf 'Übersprungen: %s\n' "$*"; }
warn() { printf 'Warnung: %s\n' "$*" >&2; }
DRY=$dry_run

step() { :; }

# ---- shared primitives (verified with b12628 restore) ---------------------

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
        mkdir -p -- "${target%/*}"
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
    if [[ -e $target ]] && cmp -s -- "$source" "$target"; then return 0; fi
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
}

lock() {
    if $DRY; then return 0; fi
    mkdir -p -- "$opt"
    exec 9>"$opt/.setup.lock"
    flock -n 9 || fail 'another setup for this account is running'
}

backup_configs() {
    local out=$1
    local paths=() p
    if ! $pi_only; then
        [[ ! -d $cfg ]] || paths+=(".config/llama.cpp")
        [[ ! -d $unitsdir ]] || paths+=(".config/systemd/user")
    fi
    local relative=${pi_dir#"$HOME/"}
    [[ $relative != "$pi_dir" ]] || fail 'Pi configuration must be under HOME to back it up'
    for p in settings.json auth.json mcp.json models-store.json prompts permission-mode; do
        [[ ! -e $pi_dir/$p ]] || paths+=("$relative/$p")
    done
    for p in .local/bin/pi .local/bin/pi-sandbox .local/opt/llama.cpp/pi-harness; do
        [[ ! -e $HOME/$p && ! -L $HOME/$p ]] || paths+=("$p")
    done
    (( ${#paths[@]} )) || { printf 'nothing to back up\n'; return 0; }
    if $DRY; then log "plan: backup ${paths[*]} -> $out"; return 0; fi
    mkdir -p -- "$state/backups"
    tar -czf "$out" -C "$HOME" "${paths[@]}"
    printf '%s\n' "$out"
}

install_pi() {
    local stage=$1 nodebin=$2 manifest=$src/config/pi-manifest.json pin version version_actual digest release_dir
    local npm_dir=$src/packages/pi name want template
    pin=$(jq -er '.pi.name' "$manifest")
    version=$(jq -er '.pi.version' "$manifest")
    jq -e --slurpfile manifest "$manifest" '
        .packages[""].dependencies as $locked | $manifest[0] as $m |
        $locked == ([$m.packages[] | select(.status == "active") | {key:.name,value:.version}]
                    + [{key:$m.pi.name,value:$m.pi.version}] | from_entries)
        ' "$npm_dir/package-lock.json" >/dev/null || fail 'Pi manifest and lockfile disagree'
    cmp -s <(jq -S '.dependencies' "$npm_dir/package.json") \
           <(jq -S '.packages[""].dependencies' "$npm_dir/package-lock.json") ||
        fail 'Pi package.json and lockfile disagree'

    local rendered=$stage/pi-config.json
    jq --arg home "$HOME" --arg skills "$skills" --slurpfile manifest "$manifest" '
        .agentDir = ($home + "/.pi/agent") | .skills = $skills
        | .packages = [$manifest[0].packages[] | select(.status=="active") | "\(.source)@\(.version)"]
        | .piVersion = $manifest[0].pi.version | .package = $manifest[0].pi.name
        ' "$src/config/pi.json.in" > "$rendered"
    jq --arg skills "$skills" 'walk(if type=="string" then gsub("@SKILLS@"; $skills)
        elif type=="object" then with_entries(.key |= gsub("@SKILLS@"; $skills))
        else . end)' "$src/config/permission-mode.json.in" > "$stage/permission-mode.json"
    digest=$(sha256sum "$npm_dir/package.json" "$npm_dir/package-lock.json" \
        "$rendered" "$src/config/pi-workflow.md" "$src/libexec/pi-sandbox" "$src/libexec/pi-router.py" \
        | awk '{print $1}' | sha256sum)
    release_dir=$opt/pi-harness-${digest:0:16}

    if $DRY; then
        log "plan: pinned Pi $version and extensions from packages/pi (npm ci --ignore-scripts)"
        log "plan: project sandbox and coding relay at $release_dir"
        return
    fi
    local package_missing=false
    while IFS=$'\t' read -r name want; do
        if ! jq -e --arg want "$want" '.version == $want' "$release_dir/node_modules/$name/package.json" >/dev/null 2>&1; then
            package_missing=true
        fi
    done < <(jq -r '.packages[] | select(.status == "active") | [.name,.version] | @tsv' "$manifest")
    if $package_missing || [[ ! -x $release_dir/bin/pi || ! -x $release_dir/node_modules/.bin/pi ]] ||
       ! cmp -s "$rendered" "$release_dir/pi-config.json" ||
       ! cmp -s "$npm_dir/package-lock.json" "$release_dir/package-lock.json" ||
       ! jq -e --slurpfile manifest "$manifest" '
            $manifest[0].pi.version == .version' "$release_dir/node_modules/$pin/package.json" >/dev/null 2>&1; then
        mkdir -p "$stage/pi-harness/bin"
        cp -- "$npm_dir"/package{,-lock}.json "$stage/pi-harness/"
        (cd -- "$stage/pi-harness" &&
            PATH="${nodebin%/*}:$PATH" npm ci --ignore-scripts --no-audit --no-fund --no-update-notifier)
        version_actual=$(PI_OFFLINE=1 PI_CODING_AGENT_DIR="$stage/empty-agent" \
            "$nodebin" "$stage/pi-harness/node_modules/$pin/dist/bundle/cli.js" --version)
        [[ $version_actual == "$version" ]] || fail 'unexpected Pi package version'
        install -m 755 "$src/libexec/pi-sandbox" "$stage/pi-harness/bin/pi"
        install -m 644 "$src/libexec/pi-router.py" "$stage/pi-harness/bin/pi-router.py"
        install -m 644 "$rendered" "$src/config/pi-workflow.md" "$stage/pi-harness/"
        local damaged=
        if [[ -e $release_dir ]]; then
            damaged=$release_dir.damaged-$(date +%s%N)
            mv -T -- "$release_dir" "$damaged"
        fi
        if ! mv -T -- "$stage/pi-harness" "$release_dir"; then
            [[ -z $damaged ]] || mv -T -- "$damaged" "$release_dir"
            fail 'could not activate the repaired Pi release'
        fi
    fi
    if [[ ! -L $opt/pi-harness || $(readlink -- "$opt/pi-harness") != "$release_dir" ]]; then
        backup_configs "$state/backups/pi-before-$(date +%s%N).tar.gz" >/dev/null
    fi
    mkdir -p -- "$pi_dir/permission-mode" "$pi_dir/prompts" "$HOME/.local/bin"
    local pm=$pi_dir/permission-mode/permission-mode.json
    if [[ -e $pm ]]; then
        jq -e 'type == "object"' "$pm" >/dev/null || fail 'invalid existing permission-mode configuration'
    else
        install_file 600 "$stage/permission-mode.json" "$pm"
    fi
    for template in "$src"/config/prompts/*.md; do
        name=${template##*/}
        [[ -e $pi_dir/prompts/$name ]] || install_file 644 "$template" "$pi_dir/prompts/$name"
    done

    [[ ! -e $opt/pi-harness || -L $opt/pi-harness ]] || fail 'the Pi release link points at a directory'
    # Keep original launchers available for rollback. Use the release symlink as
    # the single switching point so an incomplete npm install leaves Pi usable.
    if [[ ! -L $opt/pi-harness || $(readlink -- "$opt/pi-harness") != "$release_dir" ]]; then
        ln -s -- "$release_dir" "$stage/pi-harness-link"
        mv -Tf -- "$stage/pi-harness-link" "$opt/pi-harness"
    fi
    local launcher=$opt/pi-harness/bin/pi path
    for name in pi pi-sandbox; do
        path=$HOME/.local/bin/$name
        if [[ -L $path && $(readlink -- "$path") == "$launcher" ]]; then continue; fi
        if [[ -e $path || -L $path ]]; then
            if [[ $name == pi && ! -L $path ]]; then
                warn "$path is an existing executable. Use pi-sandbox or move that launcher before repair."
                continue
            fi
            mkdir -p -- "$state/pi-launchers"
            [[ -e $state/pi-launchers/$name || -L $state/pi-launchers/$name ]] ||
                cp -a -- "$path" "$state/pi-launchers/$name"
        fi
        ln -s -- "$launcher" "$stage/$name"
        mv -Tf -- "$stage/$name" "$path"
    done
    log "Pi $version ready. Start pi from a project directory."
}

install_pi_only() {
    local stage nodebin=$opt/node/bin/node
    require_cmds curl sha256sum flock tar xz python3 jq npm bwrap socat node
    lock
    if ! $DRY; then mkdir -p -- "$cache"; fi
    if $DRY; then stage=$(mktemp -d); else stage=$(mktemp -d "$opt/.pi-setup.XXXXXXXX"); fi
    # shellcheck disable=SC2064
    trap "rm -rf -- '$stage'" EXIT
    if [[ ! -x $nodebin ]]; then
        if unpack node-v24.22.1-linux-x64.tar.xz "$stage/node" 1; then
            [[ $("$stage/node/bin/node" --version) == v24.22.1 ]] || fail 'Node version mismatch'
            mv -T -- "$stage/node" "$opt/node"
        elif $DRY; then nodebin=$(command -v node)
        else fail 'pinned Node installation failed'; fi
    fi
    install_pi "$stage" "$nodebin"
}

install_stack() {
    hardware_report
    if ! $DRY; then mkdir -p -- "$cache" "$models"; fi

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
    if $DRY; then
        stage=$(mktemp -d)
    else
        stage=$(mktemp -d "$opt/.setup.XXXXXXXX")
    fi
    # shellcheck disable=SC2064
    trap "rm -rf -- '$stage'" EXIT

    if [[ ! -d $opt/$release ]]; then
        unpack llama-b12628-bin-ubuntu-cuda-12.8-x64.tar.gz "$stage/$release" 1 || true
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

    if ! $DRY; then mkdir -p -- "$cfg" "$unitsdir" "$HOME/.local/bin" "$HOME/.local/libexec" "$HOME/.local/share/applications"; fi
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
    for n in llama-github-mcp llama-research; do
        install_file 755 "$src/libexec/$n" "$HOME/.local/libexec/$n"
    done
    install_file 755 "$src/libexec/llama-webui" "$HOME/.local/bin/llama-webui"
    install_file 644 "$stage/llama-cpp.desktop" "$HOME/.local/share/applications/llama-cpp.desktop"

    install_pi "$stage" "$nodebin"

    # repository docs own the installed copies (one drift backup each)
    install_doc "$src/docs/SETUP.md" "$cfg/SETUP.md"
    install_doc "$src/docs/QUICKSTART.md" "$cfg/QUICKSTART.md"
    install_doc "$src/docs/MODEL_BENCHMARKS.md" "$cfg/MODEL_BENCHMARKS.md"
    install_doc "$src/docs/PERFORMANCE_OPTIMIZATION.md" "$cfg/PERFORMANCE_OPTIMIZATION.md"
    install_doc "$src/docs/PI_CODING_AGENT.md" "$cfg/PI_CODING_AGENT.md"

    if ! $DRY; then
        systemctl --user daemon-reload
        systemctl --user add-wants default.target llama-cpp.service
        systemctl --user start llama-cpp.service llama-cpp-mcp.service llama-cpp-research.service
    fi
    if [[ -d $cfg/pi-legacy || -d $cfg/claude ]]; then : ; fi
    log 'install complete - run ./setup.sh test for acceptance'
}

# ---- coding candidates (opt-in evaluation profile, about 70 GB) -----------
# ./setup.sh install --coding-candidates is the only path that fetches these
# files; the default one-click install never touches them. Re-running reuses
# valid GGUF files and resumes interrupted downloads via fetch().

install_coding_candidates() {
    hardware_report
    if ! $DRY; then mkdir -p -- "$cache" "$models"; fi

    local name repo revision bytes sha _rest missing_candidates=0 want=0
    while IFS=$'\t' read -r name repo revision bytes sha _rest; do
        [[ $name == filename ]] && continue
        if [[ -f $models/$name ]]; then
            hash_ok "$models/$name" "$sha" || fail "SHA-256 mismatch: $models/$name"
            log "reuse $name"
            continue
        fi
        missing_candidates=$((missing_candidates + 1)); want=$((want + bytes))
    done < <(candidates_rows)

    if (( missing_candidates > 0 )) && ! $DRY; then
        local avail
        avail=$(df -kB --output=avail -- "$models" | tail -1 | tr -d ' ')
        (( avail * 1024 > want + 4294967296 )) ||
            fail "not enough space below ${avail} KiB for $missing_candidates candidate files (about $((want / 1073741824)) GiB plus 4 GiB headroom)"
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
    pi_doctor || rc=1
    candidates_doctor
    return "$rc"
}

pi_doctor() {
    local rc=0 manifest=$src/config/pi-manifest.json harness=$opt/pi-harness
    local want name version info settings=$pi_dir/settings.json
    printf '== Pi harness\n'
    if [[ -x $harness/bin/pi && -r $harness/pi-config.json ]]; then
        if [[ -L $HOME/.local/bin/pi && $(readlink -- "$HOME/.local/bin/pi") == "$harness/bin/pi" ]]; then
            printf 'PASS managed pi launcher\n'
        else
            printf 'WARN pi uses another launcher; use pi-sandbox or repair the PATH entry\n'
        fi
        if [[ -x $opt/node/bin/node ]]; then
            printf 'PASS managed Node %s\n' "$("$opt/node/bin/node" --version)"
        else
            printf 'FAIL managed Node missing; run setup.sh repair --pi-only\n'
            rc=1
        fi
        want=$(jq -r '.pi.version' "$manifest")
        version=$(jq -r '.version' "$harness/node_modules/@earendil-works/pi-coding-agent/package.json" 2>/dev/null || true)
        if [[ $version == "$want" ]]; then printf 'PASS pinned official Pi %s\n' "$version"
        else printf 'FAIL Pi version %s (expected %s); run repair --pi-only\n' "${version:-missing}" "$want"; rc=1; fi
        if jq -e '.defaultProvider == "llama.cpp" and .defaultModel == "research-code"
              and .routerUrl == "http://127.0.0.1:8080"
              and .contextTokens == 262144 and .outputTokens == 8192
              and .compaction.enabled == true' "$harness/pi-config.json" >/dev/null; then
            printf 'PASS installed Pi profile is local Coding Long 256K, native compaction\n'
        else
            printf 'FAIL Pi model/compaction configuration; run repair --pi-only\n'
            rc=1
        fi
        settings=$harness/pi-config.json
        if jq -e --slurpfile manifest "$manifest" '
            .packages == [$manifest[0].packages[] | select(.status == "active")
                            | "\(.source)@\(.version)"]' "$settings" >/dev/null; then
            printf 'PASS managed extension list matches the active package pins\n'
        else
            printf 'FAIL managed extension list differs from the package pins; run repair --pi-only\n'
            rc=1
        fi
    else
        printf 'FAIL managed Pi sandbox launcher missing; run setup.sh repair --pi-only\n'
        rc=1
        harness=$pi_dir/npm
    fi
    while IFS=$'\t' read -r name want info; do
        if [[ $info != active ]]; then
            printf 'DISABLED %s %s (%s)\n' "$name" "$want" "$info"
            continue
        fi
        version=$(jq -r '.version' "$harness/node_modules/$name/package.json" 2>/dev/null || true)
        if [[ $version == "$want" ]]; then
            printf 'PASS %s %s installed\n' "$name" "$version"
        else
            printf 'FAIL %s %s (expected %s); run repair --pi-only\n' "$name" "${version:-missing}" "$want"
            rc=1
        fi
    done < <(jq -r '.packages[] | [.name,.version,.status] | @tsv' "$manifest")
    local conflict scope
    for scope in "$settings" "$PWD/.pi/settings.json"; do
        [[ -r $scope ]] || continue
        if ! jq -e 'type == "object"' "$scope" >/dev/null 2>&1; then
            printf 'WARN invalid Pi settings in %s\n' "$scope"
            continue
        fi
        for conflict in 'context:pi-condense|better-compaction|@sting8k/pi-vcc|sol-pi' \
                        'edit:pi-hashline-edit-pro|sol-pi'; do
            if jq -e --arg names "${conflict#*:}" '
                any(.packages[]? | if type=="object" then .source else . end;
                type=="string" and test($names))' "$scope" >/dev/null; then
                printf 'WARN %s package overlaps the default tool or context engine in %s\n' "${conflict%%:*}" "$scope"
            fi
        done
    done
    if jq -e '.defaultMode == "build" and .modes.build.sandbox.enabled == true' \
            "$pi_dir/permission-mode/permission-mode.json" >/dev/null 2>&1; then
        printf 'PASS Build configured for new interactive sessions, shell sandbox enabled in policy\n'
    else
        printf 'WARN Build mode or its shell sandbox differs; review permission-mode.json\n'
    fi
    if [[ -d $skills ]]; then
        printf 'PASS shared skill files present (%s)\n' "$(find "$skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l)"
    else
        printf 'FAIL shared skill directory missing\n'
        rc=1
    fi
    local l
    for l in bwrap socat; do
        if command -v "$l" >/dev/null; then
            printf 'PASS sandbox dependency %s present\n' "$l"
        else
            printf 'FAIL sandbox dependency %s missing; install it before starting managed Pi\n' "$l"
            rc=1
        fi
    done
    for l in typescript-language-server pyright ruff shellcheck rust-analyzer fd rg; do
        command -v "$l" >/dev/null && printf 'PASS host tool %s present\n' "$l" \
            || printf 'OPTIONAL host tool %s missing\n' "$l"
    done
    local catalog
    if catalog=$(curl -qfsS --max-time 5 "$router/models") && jq -e '
        any(.data[] | select(.id=="research-code").status.args; . as $a |
            ($a|index("--ctx-size")) != null and $a[($a|index("--ctx-size"))+1]=="262144"
            and ($a|index("--n-predict")) != null and $a[($a|index("--n-predict"))+1]=="8192"
            and ($a|index("--parallel")) != null and $a[($a|index("--parallel"))+1]=="1"
            and ($a|index("--cache-ram")) != null and $a[($a|index("--cache-ram"))+1]=="512"
            and (($a|index("--offline")) != null)
            and all($a[]; (startswith("--spec-") | not))
            and any($a[]; contains("Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-Q4_K_M.gguf"))
        )' <<<"$catalog" >/dev/null; then
        printf 'PASS router preset matches Coding Long 256K, one slot and 512 MiB cache\n'
    else
        printf 'FAIL coding router preset unavailable or different; inspect settings with setup.sh status\n'
        rc=1
    fi
    printf 'OPTIONAL MCP via pi --with-mcp. Native footer and benchmark counters available.\n'
    printf 'NOT TESTED live tool and session workflows. Use test --pi-only for sandbox and inference checks.\n'
    return "$rc"
}

status() {
    printf 'llama.cpp: %s (release %s)\n' "$(unit_state llama-cpp.service)" "$release"
    printf 'gateway:   %s\n' "$(unit_state llama-cpp-mcp.service)"
    printf 'research:  %s\n' "$(unit_state llama-cpp-research.service)"
    curl -fsS --max-time 5 "$router/models" 2>/dev/null | jq -r '.data[].id' | sed 's/^/profile: /'
    if [[ -x $HOME/.local/bin/pi ]]; then
        printf 'pi: %s\n' "$("$HOME/.local/bin/pi" --version 2>/dev/null || echo present)"
    else
        printf 'pi: no launcher at ~/.local/bin/pi\n'
    fi
}

pi_acceptance_test() {
    local temp project launcher=$HOME/.local/bin/pi-sandbox out
    [[ -x $launcher ]] || fail 'Pi sandbox missing; run setup.sh repair --pi-only'
    temp=$(mktemp -d /tmp/pi-acceptance.XXXXXXXX)
    project=$temp/project
    # shellcheck disable=SC2064
    trap "rm -rf -- '$temp'" EXIT
    mkdir -p "$project" "$temp/skills/probe"
    printf '%s\n' test-only > "$temp/outside.txt"
    printf '%s\n' '---' 'name: probe' 'description: Sandbox test fixture.' '---' 'Read-only test.' \
        > "$temp/skills/probe/SKILL.md"
    cp "$src/tests/pi-sandbox.ts" "$project/"
    if ! out=$(cd "$project" && "$launcher" --list-models research-code) ||
       [[ $out != *262.1K* || $out != *8.2K* ]]; then
        fail 'model listing does not expose the pinned context and output limits'
    fi
    python3 "$src/tests/pi-router.py"
    (cd "$project" && printf '%s\n' '{"type":"get_state","id":"sandbox-test"}' |
        OPENAI_API_KEY=fixture LLAMA_SETUP_SKILLS="$temp/skills" timeout 45 "$launcher" \
            --mode rpc --no-session --perm build -e "$project/pi-sandbox.ts") > "$temp/rpc.jsonl"
    if ! jq -e 'type=="object" and length==11 and all(.[]; .==true)' "$project/sandbox-result.json" >/dev/null; then
        fail 'runtime sandbox probe failed'
    fi
    [[ ! -e $project/.pi-lens-probe-home ]] || fail 'Pi Lens wrote logs into the project'
    printf 'PASS project write, sibling isolation, read-only skills, credential and child isolation, coding-only relay\n'
    printf 'PASS Pi Lens logs outside the project\n'

    if ! curl -qfsS --max-time 5 "$router/models" | jq -e \
        'any(.data[]; .id=="research-code" and .status.value=="loaded")' >/dev/null ||
       ! curl -qfsS --max-time 5 "$router/slots?model=research-code" |
        jq -e 'length==1 and .[0].is_processing==false' >/dev/null; then
        printf 'NOT TESTED live inference. Coding Long 256K must be loaded and idle.\n'
        return 1
    fi
    out=$(cd "$project" && timeout 180 "$launcher" --no-session --perm build --thinking off \
        --no-skills --no-tools --no-context-files --no-lens-context -p \
        'Reply with exactly the text SETUP-OK.') || fail 'Pi inference failed'
    [[ $out == *SETUP-OK* ]] || fail 'Pi did not return the known smoke-test response'
    printf 'PASS Pi launcher, model limits and local inference\n'
}

acceptance_test() {
    local rc=0
    curl -qfsS --max-time 5 "$router/health" >/dev/null || { echo 'FAIL router'; rc=1; }
    curl -qfsS --max-time 5 "$router/models" |
        jq -e 'any(.data[]; .id=="research") and any(.data[]; .id=="creative-writing")' >/dev/null ||
        { echo 'FAIL research/writing profiles missing'; rc=1; }
    curl -qfsS --max-time 5 http://127.0.0.1:8642/healthz >/dev/null || { echo 'FAIL websearch'; rc=1; }
    curl -qfsS --max-time 5 http://127.0.0.1:8643/status >/dev/null || { echo 'FAIL gateway'; rc=1; }
    python3 "$src/tests/gemma4-profile-check.py" >/dev/null ||
        { echo 'FAIL two-model profile/hash validation'; rc=1; }
    pi_acceptance_test || rc=1
    return "$rc"
}

backup_cmd() {
    local out
    out=$state/backups/localllma-$(date +%Y%m%d-%H%M%S-%N).tar.gz
    backup_configs "$out"
}

restore_cmd() {
    local archive=${1:-} stage relative=${pi_dir#"$HOME/"} file
    if [[ -z $archive ]]; then
        archive=$(find "$state/backups" -maxdepth 1 -name 'localllma-*.tar.gz' -printf '%p\n' 2>/dev/null | sort | tail -1) || true
    fi
    [[ -n $archive && -f $archive ]] || fail 'no backup given and none found'
    [[ $relative != "$pi_dir" ]] || fail 'Pi configuration must be under HOME to restore it'
    stage=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf -- '$stage'" EXIT
    python3 - "$archive" "$stage" "$HOME" "$relative" "$pi_only" <<'PYTHON'
import os
from pathlib import Path
import shutil
import sys
import tarfile

archive, stage, home, agent, pi_only = sys.argv[1:]
home, stage = Path(home), Path(stage)
links = {".local/bin/pi", ".local/bin/pi-sandbox", ".local/opt/llama.cpp/pi-harness"}
pi_paths = {f"{agent}/{name}" for name in (
    "settings.json", "auth.json", "mcp.json", "models-store.json", "prompts", "permission-mode"
)} | links
roots = pi_paths if pi_only == "true" else pi_paths | {".config/llama.cpp", ".config/systemd/user"}
with tarfile.open(archive, "r:gz") as saved:
    members = []
    for member in saved:
        name = Path(member.name)
        if name.is_absolute() or ".." in name.parts:
            raise SystemExit("Invalid path in setup backup")
        if not any(str(name) == root or str(name).startswith(root + "/") for root in roots):
            if pi_only == "true" and str(name).startswith((".config/llama.cpp", ".config/systemd/user")):
                continue
            raise SystemExit(f"Unmanaged path in setup backup: {name}")
        if not (member.isfile() or member.isdir() or member.issym()):
            raise SystemExit(f"Unsupported entry in setup backup: {name}")
        if member.issym():
            target = Path(os.path.normpath(name.parent / member.linkname))
            if target.is_absolute():
                if not target.is_relative_to(home):
                    raise SystemExit(f"Link outside HOME in setup backup: {name}")
            elif ".." in target.parts:
                raise SystemExit(f"Link outside HOME in setup backup: {name}")
        members.append(member)

    if not members:
        raise SystemExit("Archive has no selected setup files")
    for member in members:
        path = stage / member.name
        parent = home / Path(member.name).parent
        if parent.resolve() != parent:
            raise SystemExit(f"Symlink in restore destination: {Path(member.name).parent}")
        if path.parent.resolve() != path.parent:
            raise SystemExit(f"Symlink in setup backup: {member.name}")
        if member.isfile():
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                raise SystemExit(f"Duplicate link and file in setup backup: {member.name}")
            with saved.extractfile(member) as src, path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            path.chmod(member.mode & 0o755)
        elif member.isdir():
            if path.is_symlink():
                raise SystemExit(f"Duplicate link and directory in setup backup: {member.name}")
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(member.linkname)
PYTHON
    for file in settings.json auth.json mcp.json permission-mode/permission-mode.json; do
        if [[ -f $stage/$relative/$file ]]; then
            jq -e 'type == "object"' "$stage/$relative/$file" >/dev/null || fail "invalid $file in backup"
        fi
    done
    if $DRY; then log "plan: restore validated files from $archive"; return; fi
    lock
    # A restore is itself reversible.
    backup_configs "$state/backups/before-restore-$(date +%s%N).tar.gz" >/dev/null
    while IFS= read -r -d '' file; do
        local target=$HOME/${file#"$stage/"}
        mkdir -p -- "${target%/*}"
        cp -a --remove-destination -- "$file" "$target"
    done < <(find "$stage" \( -type f -o -type l \) -print0)
    if ! $pi_only; then systemctl --user daemon-reload; fi
    printf 'restored from %s\n' "$archive"
}

# ---- dispatch ----------------------------------------------------------------

case $cmd in
    install|update|repair)
        if $coding_candidates; then install_coding_candidates
        elif $pi_only; then install_pi_only; else preflight; lock; install_stack; fi ;;
    doctor)    if $pi_only; then pi_doctor; else doctor; fi ;;
    status)    status ;;
    test)
        if $DRY; then log 'plan: run sandbox and model acceptance checks'
        elif $pi_only; then pi_acceptance_test
        else acceptance_test; fi ;;
    backup)    backup_cmd ;;
    restore)   shift 0; restore_cmd "${1:-}" ;;
    uninstall)
        options=()
        if $DRY; then options+=(--dry-run); fi
        if $pi_only; then options+=(--pi-only); fi
        exec bash "$src/uninstall.sh" "${options[@]}" ;;
esac
