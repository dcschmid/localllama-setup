#!/usr/bin/env bash
set -euo pipefail
if (( $# < 5 )); then
    printf '%s\n' 'Aufruf: run-perf-case.sh AUSGABE ID ALIAS A|B prefix,48 [option=wert ...]' >&2
    exit 2
fi
run=$(realpath -ms -- "$1")
shift
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case_id=${1:?}
alias=${2:?}
thp=${3:?}
workload=${4:?}
shift 4
[[ $case_id =~ ^[a-z0-9-]+$ && $alias =~ ^[a-z0-9-]+$ && $thp =~ ^[AB]$ ]] || exit 2
unit="llama-perf-$case_id"
port=18083
out="$run/$case_id"
mkdir -p -- "$run"
exec 9>"${XDG_RUNTIME_DIR:?}/llama-perf-$port.lock"
if ! flock -n 9; then
    printf 'Am Benchmark-Port %s läuft bereits ein Vergleich\n' "$port" >&2
    exit 1
fi
if [[ -n $(ss -lntH "( sport = :$port )") ]]; then
    printf 'Benchmark-Port %s ist belegt\n' "$port" >&2
    exit 1
fi
mkdir -- "$out"
cleanup() { systemctl --user stop "$unit" >/dev/null 2>&1 || true; }
trap cleanup EXIT
if curl -qfsS --max-time 3 http://127.0.0.1:8080/models | jq -e 'any(.data[]; .status.value == "loaded" or .status.value == "loading")' >/dev/null; then
    printf 'Produktionsrouter benutzt gerade ein Modell. Abbruch.\n' >&2
    exit 1
fi
source_path=${LLAMA_PERF_PRESETS:-$HOME/.config/llama.cpp/models.ini}
python3 - "$source_path" "$alias" "$out/models.ini" "$@" <<'PY'
import re
import sys
from pathlib import Path

src, alias, output, *options = sys.argv[1:]
text=Path(src).read_text()
intro,*sections=re.split(r"(?m)(?=^\[[^\n\]]+\]\s*$)",text)
known={part.splitlines()[0].strip()[1:-1]:part for part in sections}
selected=known[alias].rstrip()
for option in options:
    key,value=option.split("=",1)
    assert re.fullmatch(r"[a-z][a-z0-9-]+",key)
    selected,n=re.subn(r"(?m)^"+key+r"\s*=.*$",f"{key} = {value}",selected,count=1)
    if not n:
        selected+=f"\n{key} = {value}"
Path(output).write_text(intro+known["*"]+selected+"\n")
PY
parent=$(systemctl --user show -P MainPID llama-cpp.service)
if [[ $parent == 0 ]]; then
    printf '%s\n' 'Starte zuerst den regulären llama.cpp-Benutzerdienst.' >&2
    exit 1
fi
tunables=$(python3 - "$parent" "$thp" <<'PY'
import sys
from pathlib import Path
data=Path(f"/proc/{sys.argv[1]}/environ").read_bytes()
old=next((line.decode().split("=",1)[1] for line in data.split(b"\0") if line.startswith(b"GLIBC_TUNABLES=")),"")
if sys.argv[2]=="B":
    active=[x for x in old.split(":") if x and x.split("=",1)[0]!="glibc.malloc.hugetlb"]
    active+=["glibc.malloc.hugetlb=1"]
    old=":".join(active)
print(old)
PY
)
date --iso-8601=seconds > "$out/start"
cat /sys/firmware/acpi/platform_profile > "$out/platform-profile"
sensors -j > "$out/sensors-start.json" 2>"$out/sensors-start.err" || :
systemd-run --user --quiet --unit="$unit" --collect --working-directory="$HOME/models/gguf" \
  --property=NoNewPrivileges=yes \
  --property='UnsetEnvironment=OPENAI_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN HF_TOKEN HUGGING_FACE_HUB_TOKEN GITHUB_TOKEN GH_TOKEN CONTEXT7_API_KEY OTEL_EXPORTER_OTLP_ENDPOINT' \
  --setenv="GLIBC_TUNABLES=$tunables" --property="StandardOutput=append:$out/server.log" \
  --property="StandardError=append:$out/server.log" "$HOME/.local/bin/llama-server" \
  --offline --host 127.0.0.1 --port "$port" --no-ui --models-max 1 --models-preset "$out/models.ini"
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu,temperature.gpu,power.draw,clocks.current.graphics --format=csv -lms 1000 > "$out/gpu.csv" 9>&- &
monitor=$!
(
  while systemctl --user is-active --quiet "$unit"; do
    if curl -qfsS --max-time 2 http://127.0.0.1:8080/models | jq -e 'any(.data[]; .status.value == "loaded" or .status.value == "loading")' >/dev/null; then
      printf 'Produktionsrouter ist belegt\n' > "$out/interrupted"
      cleanup
      exit
    fi
    available=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
    if (( available < 1048576 )); then
      printf 'Weniger als 1 GiB MemAvailable\n' > "$out/interrupted"
      cleanup
      exit
    fi
    sleep 2
  done
) 9>&- &
guard=$!
trap 'kill "$monitor" "$guard" 2>/dev/null || true; cleanup' EXIT
for _ in {1..50}; do
  if curl -qfsS --max-time 1 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then break; fi
  sleep .2
done
curl -qfsS --max-time 120 "http://127.0.0.1:$port/props?model=$alias" > "$out/props.json"
router=$(systemctl --user show -P MainPID "$unit")
mapfile -t children < <(pgrep -P "$router" -x llama-server)
[[ ${#children[@]} == 1 ]]
worker=${children[0]}
python3 - "$router" "$worker" "$tunables" <<'PY' > "$out/tunables.json"
import json
from pathlib import Path
import sys
pids=sys.argv[1:3]
values=[next((line.decode().split("=",1)[1] for line in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if line.startswith(b"GLIBC_TUNABLES=")),None) for pid in pids]
assert all(value==sys.argv[3] for value in values),values
print(json.dumps(dict(zip(("router","model_worker"),values))))
PY
if [[ $workload == 256k ]]; then
  python3 "$repo/benchmarks/bench-context.py" "$alias" 262144 --port "$port" --structured > "$out/rows.jsonl"
  python3 "$repo/benchmarks/bench-context.py" "$alias" 16384 32768 65536 131072 196608 \
    --port "$port" --structured --reuse-prefix > "$out/ladder.jsonl"
elif [[ $workload == context,* ]]; then
  python3 "$repo/benchmarks/bench-context.py" "$alias" "${workload#*,}" \
    --port "$port" --structured > "$out/rows.jsonl"
else
  IFS=, read -r flow modules <<< "$workload"
  python3 "$repo/benchmarks/measure-router.py" "$alias" --port "$port" --pid "$worker" --case "$case_id" --flow "$flow" --modules "$modules" > "$out/rows.jsonl"
fi
sensors -j > "$out/sensors-end.json" 2>"$out/sensors-end.err" || :
date --iso-8601=seconds > "$out/end"
printf 'PASS %s\n' "$case_id"
