#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 )); then
    printf 'Aufruf: %s AUSGABEPRAEFIX MODELL.gguf [llama-bench-Optionen]\n' "$0" >&2
    exit 2
fi
out=$1
model=$2
shift 2
[[ -r $model ]] || { printf 'Modell fehlt: %s\n' "$model" >&2; exit 1; }
for suffix in .json .gpu.csv .stderr; do
    if [[ -e $out$suffix || -L $out$suffix ]]; then
        printf 'Ausgabedatei existiert bereits: %s\n' "$out$suffix" >&2
        exit 1
    fi
done
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu,power.draw,temperature.gpu --format=csv -lms 500 > "$out.gpu.csv" &
sampler=$!
trap 'kill "$sampler" 2>/dev/null || true; wait "$sampler" 2>/dev/null || true' EXIT
/usr/bin/time -v "$HOME/.local/bin/llama-bench" --offline -m "$model" -dev CUDA0 \
    -fitt 1024 -b 512 -ub 256 -fa on -ctk q8_0 -ctv q8_0 "$@" -o json \
    > "$out.json" 2> "$out.stderr"
jq -c '.[] | {n_prompt,n_gen,n_depth,n_cpu_moe,n_threads,load_mode,avg_ts}' "$out.json"
