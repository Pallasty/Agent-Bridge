#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

quiet=false
requirements=()
biocortex_rs_resolved=""

usage() {
    cat <<'USAGE'
usage: scripts/check-verification-dependencies.sh [flags]

Flags:
  --all                 Check every known verification dependency. Default.
  --require NAME        Check one dependency group. Known: shell-tools, biocortex-rs.
  --quiet               Suppress success output.
  -h, --help            Show this help.

This is a read-only doctor for verification prerequisites. It does not fetch,
repair, mutate external checkouts, run Cargo builds, or write Agent-Bridge state.
USAGE
}

add_requirement() {
    local requirement="$1"
    if [ "${#requirements[@]}" -gt 0 ]; then
        for existing in "${requirements[@]}"; do
            if [ "$existing" = "$requirement" ]; then
                return
            fi
        done
    fi
    requirements+=("$requirement")
}

require_command() {
    local command_name="$1"
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "verification dependency doctor: required command not found: $command_name" >&2
        exit 2
    fi
}

resolve_biocortex_rs() {
    local checkout=""
    if [ -n "${AB_BIOCORTEX_RS:-}" ]; then
        checkout="$AB_BIOCORTEX_RS"
    elif [ -n "${BIOCORTEX_RS:-}" ]; then
        checkout="$BIOCORTEX_RS"
    fi

    if [ -n "$checkout" ]; then
        printf '%s\n' "$checkout"
        return
    fi

    for candidate in \
        "$repo_root/../biocortex-rs" \
        /Data/CascadeProjects/biocortex-rs \
        /Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs
    do
        if [ -f "$candidate/Cargo.toml" ]; then
            printf '%s\n' "$candidate"
            return
        fi
    done

    return 1
}

check_shell_tools() {
    require_command git
    require_command cargo
    require_command jq
}

check_biocortex_rs() {
    require_command git

    if ! biocortex_rs_resolved="$(resolve_biocortex_rs)"; then
        echo "verification dependency doctor: could not find biocortex-rs checkout." >&2
        echo "Set AB_BIOCORTEX_RS=/path/to/a/clean/biocortex-rs checkout." >&2
        exit 2
    fi

    bash scripts/check-biocortex-checkout-hygiene.sh "$biocortex_rs_resolved"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --all)
            add_requirement shell-tools
            add_requirement biocortex-rs
            shift
            ;;
        --require)
            if [ "$#" -lt 2 ]; then
                echo "--require needs a dependency name" >&2
                usage >&2
                exit 2
            fi
            case "$2" in
                shell-tools|biocortex-rs) add_requirement "$2" ;;
                *)
                    echo "unknown dependency group: $2" >&2
                    usage >&2
                    exit 2
                    ;;
            esac
            shift 2
            ;;
        --quiet)
            quiet=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown flag: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ "${#requirements[@]}" -eq 0 ]; then
    add_requirement shell-tools
    add_requirement biocortex-rs
fi

for requirement in "${requirements[@]}"; do
    case "$requirement" in
        shell-tools) check_shell_tools ;;
        biocortex-rs) check_biocortex_rs ;;
    esac
done

if [ "$quiet" = false ]; then
    echo "verification dependency doctor: ok"
    printf '  checked:'
    for requirement in "${requirements[@]}"; do
        printf ' %s' "$requirement"
    done
    printf '\n'
    if [ -n "$biocortex_rs_resolved" ]; then
        echo "  biocortex-rs: $biocortex_rs_resolved"
    fi
fi
