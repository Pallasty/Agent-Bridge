#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$1" != "--phase" ]; then
    echo "usage: $0 --phase precommit|postcommit" >&2
    exit 64
fi
case "$2" in
    precommit|postcommit) ;;
    *)
        echo "usage: $0 --phase precommit|postcommit" >&2
        exit 64
        ;;
esac

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
exec python3 scripts/eval/check_engram_g14_wasi_clock_preregistration.py --phase "$2"
