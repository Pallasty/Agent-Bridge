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

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

cd "$repo_root"
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
# This semantic check is necessary but requires the contract's out-of-band pin.
exec python3 scripts/eval/check_engram_g14_strong_clock_isolation_review.py \
    --phase "$2"
