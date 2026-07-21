#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/eval/check_engram_g14_wasi_g2a_canonical_preflight.py"
