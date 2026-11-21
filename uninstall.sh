#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
    cat <<'HELP'
Aufruf: ./uninstall.sh [--dry-run] [--remove-models]

Entfernt die paketierten llama.cpp-Komponenten aus dem Benutzerkonto.
Konfiguration und CUDA-Bibliotheken werden unter ~/.local/state/localllma-setup gesichert.
Modelle, Download-Caches, Browserdaten und Medienexporte bleiben standardmäßig erhalten.

--dry-run        Geplante Schritte anzeigen.
--remove-models  Zusätzlich die Modellpfade aus packages/models.tsv entfernen.
--remove-candidates Nur die Coding-Kandidaten aus packages/models-coding-candidates.tsv
                   entfernen (Produktionsmodelle bleiben erhalten).
HELP
}

fail() { printf 'Fehler: %s\n' "$*" >&2; exit 1; }

dry_run=false
remove_models=false
remove_candidates=false
for option in "$@"; do
    case "$option" in
        --dry-run) dry_run=true ;;
        --remove-models) remove_models=true ;;
        --remove-candidates) remove_candidates=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; fail "Unbekannte Option: $option" ;;
    esac
done

(( EUID != 0 )) || fail 'Starte die Deinstallation im Benutzerkonto ohne sudo.'
[[ ${HOME:-} == /* ]] || fail 'HOME muss ein absoluter Pfad sein.'
home=$(realpath -e -- "$HOME")
[[ $home != / && -d $home && -O $home ]] || fail 'HOME muss dem ausführenden Benutzer gehören.'

src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
opt=$home/.local/opt/llama.cpp
cfg=$home/.config/llama.cpp
units_dir=$home/.config/systemd/user
applications=$home/.local/share/applications
bin=$home/.local/bin
libexec=$home/.local/libexec
state=$home/.local/state/localllma-setup
models=$home/models/gguf
release=b12503
websearch='websearch-mcp-dfdbc9bda9119fbf67610f288eae43821180f621'

dirs=("$opt" "${cfg%/*}" "$units_dir" "$applications" "$bin" "$libexec" "$state")
if $remove_models; then dirs+=("$models"); fi
for dir in "${dirs[@]}"; do
    [[ $(realpath -m -- "$dir") == "$dir" ]] || fail "Verzeichnispfad ist umgeleitet: $dir"
done

if ! $dry_run && [[ -d $opt ]]; then
    [[ ! -L $opt/.setup.lock ]] || fail "Unerwarteter Symlink: $opt/.setup.lock"
    exec 9>>"$opt/.setup.lock"
    flock -n 9 || fail 'Setup oder Deinstallation läuft bereits.'
fi

exists() { [[ -e $1 || -L $1 ]]; }

units=()
save=("$cfg" "$applications/llama-cpp.desktop" "$applications/pi-coding-agent.desktop" "$bin/llama-webui" "$bin/pi-sandbox" "$libexec/pi-sandbox")
for name in llama-cpp.service llama-cpp-research.service llama-cpp-mcp.service; do
    if exists "$units_dir/$name"; then
        units+=("$name")
    fi
    save+=("$units_dir/$name" "$units_dir/$name.d")
done
for name in llama-github-mcp llama-research pi-sandbox; do
    save+=("$libexec/$name")
done
save+=("$home/.pi/agent/settings.json" "$home/.pi/agent/auth.json" "$home/.pi/agent/mcp.json"
       "$home/.pi/agent/models-store.json" "$home/.pi/agent/prompts" "$home/.pi/agent/npm")
for name in libcudart.so.12 libcublas.so.12 libcublasLt.so.12; do
    if [[ ! -L $opt/$release && -f $opt/$release/$name && ! -L $opt/$release/$name ]]; then
        save+=("$opt/$release/$name")
    fi
done

links=()
add_link() {
    local path=$1 expected=$2 target
    if [[ -L $path ]]; then
        target=$(readlink -- "$path")
        if [[ $target != /* ]]; then target=${path%/*}/$target; fi
        if [[ $(realpath -ms -- "$target") == "$expected" ]]; then
            links+=("$path")
        fi
    fi
}
for name in llama-server llama-cli llama-bench; do
    add_link "$bin/$name" "$opt/current/$name"
done
add_link "$bin/pi" "$opt/pi/bin/pi"
add_link "$opt/current" "$opt/$release"
add_link "$opt/websearch" "$opt/$websearch"

weights=()
if $remove_models; then
    while IFS=$'\t' read -r name _repo _revision size _hash _rest; do
        [[ $name != filename ]] || continue
        [[ $name =~ ^[a-zA-Z0-9._-]+\.gguf$ ]] || fail "Ungültiger Modelldateiname: $name"
        path=$models/$name
        if [[ -L $path ]]; then
            weights+=("$path")
        elif [[ -f $path ]]; then
            if [[ $(stat -c %s -- "$path") == "$size" ]]; then
                weights+=("$path")
            else
                printf 'Abweichende Dateigröße, Modell bleibt erhalten: %s\n' "$path" >&2
            fi
        fi
        if [[ -L $path.partial || -f $path.partial ]]; then weights+=("$path.partial"); fi
    done < "$src/packages/models.tsv"
fi
if $remove_candidates; then
    while IFS=$'\t' read -r name _repo _revision size _hash _rest; do
        [[ $name != filename ]] || continue
        [[ $name =~ ^[a-zA-Z0-9._-]+\.gguf$ ]] || fail "Ungültiger Modelldateiname: $name"
        path=$models/$name
        if [[ -L $path ]]; then
            weights+=("$path")
        elif [[ -f $path ]]; then
            if [[ $(stat -c %s -- "$path") == "$size" ]]; then
                weights+=("$path")
            else
                printf 'Abweichende Dateigröße, Kandidat bleibt erhalten: %s\n' "$path" >&2
            fi
        fi
        if [[ -L $path.partial || -f $path.partial ]]; then weights+=("$path.partial"); fi
    done < "$src/packages/models-coding-candidates.tsv"
fi

if (( ${#units[@]} )); then
    if $dry_run; then
        printf 'Stoppen und deaktivieren: %s\n' "${units[*]}"
    else
        for unit in "${units[@]}"; do
            fragment=$(systemctl --user show -P FragmentPath "$unit") ||
                fail 'Die systemd-Benutzersitzung ist nicht erreichbar.'
            [[ -z $fragment || $fragment == "$units_dir/$unit" ]] ||
                fail "Unit wird aus einem anderen Verzeichnis geladen: $fragment"
        done
        systemctl --user stop "${units[@]}"
        systemctl --user disable --no-reload "${units[@]}"
    fi
fi

backup=
for path in "${save[@]}"; do
    exists "$path" || continue
    if $dry_run; then
        printf 'Sichern und aus der Installation entfernen: %s\n' "$path"
        continue
    fi
    if [[ -z $backup ]]; then
        mkdir -p -- "$state"
        backup=$(mktemp -d "$state/uninstall.XXXXXXXX")
        printf 'Sicherung: %s\n' "$backup"
    fi
    relative=${path#"$home/"}
    mkdir -p -- "$backup/${relative%/*}"
    mv -T -- "$path" "$backup/$relative"
done
if ! $dry_run && (( ${#units[@]} )); then
    systemctl --user daemon-reload
fi

for path in "${links[@]}" "${weights[@]}"; do
    if $dry_run; then printf 'Entfernen: %s\n' "$path"; else rm -f -- "$path"; fi
done
for name in "$release" node mcp github-mcp-v2.2.0 mcp-http-v0.15.0 "$websearch" pi; do
    path=$opt/$name
    exists "$path" || continue
    if $dry_run; then printf 'Entfernen: %s\n' "$path"; else rm -rf -- "$path"; fi
done
if ! $dry_run; then printf 'Deinstallation abgeschlossen.\n'; fi
