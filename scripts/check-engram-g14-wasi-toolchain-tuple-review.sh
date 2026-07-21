#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/eval/check_engram_g14_wasi_toolchain_tuple_review.py"
