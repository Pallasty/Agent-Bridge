#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail
umask 077
PATH=/usr/bin:/bin
export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
/usr/bin/python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_refrozen_unsigned_subject_s21b_a4.py" check-schema
printf 'S21B_A4_STATIC_GATE\tPASS\n'
