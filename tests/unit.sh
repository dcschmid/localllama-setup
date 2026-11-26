#!/usr/bin/env bash
# Platform-independent unit tests for setup internals (no GPU, no models).
set -eu
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$src"
pass=0 fail=0
ok()   { printf 'ok %s\n' "$1"; pass=$((pass+1)); }
no()   { printf 'FAIL %s\n' "$1"; fail=$((fail+1)); }

# 1. manifest shape
rows=$(awk -F'\t' 'NR>1 && NF==12 && $5~/^[0-9a-f]{64}$/ && $4~/^[0-9]+$/' packages/models.tsv | wc -l)
[[ $rows == 2 ]] && ok "models.tsv: 2 valid rows" || no "models.tsv rows=$rows"

# 2. dry-run works on a scratch HOME with stub binaries
home=$(mktemp -d); trap 'rm -rf "$home"' EXIT
mkdir -p "$home/bin"
for c in jq uv nvidia-smi socat bwrap pasta nft setpriv xdg-open gh; do
    printf '#!/bin/sh\nexit 0\n' > "$home/bin/$c"
done
printf '#!/bin/sh\necho NVIDIA GeForce RTX 5070 Laptop GPU\n' > "$home/bin/nvidia-smi"
printf '#!/bin/sh\nexec node "$@"\n' > "$home/bin/uv"
PATH="$home/bin:$PATH" HOME="$home" LLAMA_SETUP_CACHE="$home/cache" \
    bash setup.sh --dry-run --download-models --download-cuda > "$home/out.log" 2>&1 && rc=0 || rc=$?
[[ $rc == 0 ]] && ok "setup.sh --dry-run on empty HOME" || { cat "$home/out.log"; no "dry-run rc=$rc"; }
if [[ ! -e $home/.local && ! -e $home/.config && ! -e $home/.pi && ! -e $home/models && ! -e $home/cache ]]; then
    ok "setup dry-run writes no installation directories"
else
    no "setup dry-run modified HOME"
fi

# 3. unknown command fails
bash setup.sh bogus >/dev/null 2>&1 && no "unknown command accepted" || ok "unknown command rejected"

# 4. template placeholders resolve
out=$(sed "s|@HOME@|$home|g" config/models.ini.in | grep -c '@HOME@' || true)
[[ $out == 0 ]] && ok "models.ini.in renders" || no "models.ini.in left @HOME@"

# 5. renderer produces valid json subset for pi manifest
mkdir -p "$home/stage"
sed -e "s|@HOME@|$home|g" -e "s|@SKILLS@|$home/skills|g" config/pi.json.in > "$home/pi.json"
jq -e '.compaction.reserveTokens == 39322' "$home/pi.json" >/dev/null && ok "pi manifest compaction pinned" || no "pi manifest compaction"

# 5b. extension manifest shape + prompt templates for every active command
jq -e '(.packages|length>=4) and all(.packages[]; .name and .version and .status)' config/pi-manifest.json >/dev/null \
    && ok "pi-manifest.json shape" || no "pi-manifest.json shape"
jq -e --slurpfile manifest config/pi-manifest.json '
    $manifest[0] as $m |
    .packages[""].dependencies ==
      ([$m.packages[] | select(.status=="active") | {key:.name,value:.version}]
       + [{key:$m.pi.name,value:$m.pi.version}] | from_entries)
    ' packages/pi/package-lock.json >/dev/null \
    && ok "Pi npm lock agrees with the active manifest" || no "Pi npm lock drift"
jq -r '.promptTemplates[]' config/pi.json.in | while read -r t; do
    [[ -f config/prompts/$t.md ]] || exit 1
done && ok "prompt templates complete" || no "prompt templates missing"

# 5c. permission-mode template renders and carries the build-first policy
sed "s|@SKILLS@|$home/skills|g" config/permission-mode.json.in > "$home/pm.json"
jq -e '.defaultMode == "build" and .cycleOrder[0] == "default"
       and .modes.build.sandbox.enabled == true
       and (.modes.build.sandbox.denyRead | index("~/.ssh"))
       and (.modes.build.permission.bash | has("sudo*"))
       and (.modes.build.permission.external_directory
            | .["@SKILLS@"] == null and .["'"$home"'/skills"] == "allow")' \
    "$home/pm.json" >/dev/null \
    && ok "permission-mode template renders" || no "permission-mode template"

# 6. backup/restore roundtrip on scratch HOME
home2=$(mktemp -d); mkdir -p "$home2/.config/llama.cpp" "$home2/.pi/agent" "$home2/.config/systemd/user"
echo 'x=1' > "$home2/.config/llama.cpp/models.ini"; echo '{}' > "$home2/.pi/agent/settings.json"
out=$(HOME="$home2" bash setup.sh backup 2>/dev/null | tail -1)
[[ -f "$out" ]] && ok "backup archive" || no "backup archive"
rm -rf "$home2/.config/llama.cpp"; HOME="$home2" bash setup.sh restore "$out" >/dev/null 2>&1 &&
   [[ -f "$home2/.config/llama.cpp/models.ini" ]] && ok "restore redeploys" || no "restore"
rm -rf "$home2"

# 7. uninstall dry-run parses
bash uninstall.sh --dry-run >/dev/null 2>&1 && ok "uninstall --dry-run" || no "uninstall --dry-run"

printf '%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
