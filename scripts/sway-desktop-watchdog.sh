#!/usr/bin/env bash
set -u

home_dir="${HOME:-/home/pallasting}"
control="${AB_SYSTEM_CONTROL_BIN:-$home_dir/.local/bin/ab-system-control}"
state_dir="${AB_SYSTEM_CONTROL_AUDIT_DIR:-/Data/agent-bridge/system-control}"
if [ ! -d /Data ] || [ ! -w /Data ]; then
    state_dir="${AB_SYSTEM_CONTROL_AUDIT_DIR:-$home_dir/.local/share/agent-bridge/system-control}"
fi
cooldown_file="$state_dir/sway-desktop-watchdog.last_heal"
notify_cooldown_file="$state_dir/sway-desktop-watchdog.last_notify"
cooldown_seconds="${SWAY_DESKTOP_WATCHDOG_COOLDOWN:-600}"
notify_cooldown_seconds="${SWAY_DESKTOP_WATCHDOG_NOTIFY_COOLDOWN:-1800}"
diagnose_lines="${SWAY_DESKTOP_WATCHDOG_DIAGNOSE_LINES:-20}"

case "$cooldown_seconds" in ''|*[!0-9]*) cooldown_seconds=600 ;; esac
case "$notify_cooldown_seconds" in ''|*[!0-9]*) notify_cooldown_seconds=1800 ;; esac
case "$diagnose_lines" in ''|*[!0-9]*) diagnose_lines=20 ;; esac
if [ "$diagnose_lines" -lt 1 ]; then diagnose_lines=1; fi
if [ "$diagnose_lines" -gt 200 ]; then diagnose_lines=200; fi

json_string() {
    jq -Rn --arg s "$1" '$s'
}

log_event() {
    local name="$1"
    local detail="${2:-}"
    "$control" event log watchdog "$name" "$detail" >/dev/null 2>&1 || true
}

record_snapshot() {
    [ "${SWAY_DESKTOP_WATCHDOG_RECORD_SNAPSHOT:-1}" = "0" ] && return 0
    "$control" status record >/dev/null 2>&1 || true
}

maybe_notify_diagnosis() {
    [ "${SWAY_DESKTOP_WATCHDOG_NOTIFY:-1}" = "0" ] && return 0
    command -v notify-send >/dev/null 2>&1 || return 0

    local diagnosis_json diagnosis_status hint latest last_notify now age body
    diagnosis_json="$("$control" status diagnose "$diagnose_lines" 2>/dev/null || true)"
    if ! printf '%s' "$diagnosis_json" | jq -e '.schema == "agent_bridge.system_control.snapshot_diagnosis.v0"' >/dev/null 2>&1; then
        return 0
    fi

    diagnosis_status="$(printf '%s' "$diagnosis_json" | jq -r '.status // "unknown"')"
    case "$diagnosis_status" in
        ok|no_history) return 0 ;;
    esac
    if [ "$diagnosis_status" = "recent_degradation" ] && [ "${SWAY_DESKTOP_WATCHDOG_NOTIFY_RECENT:-0}" != "1" ]; then
        return 0
    fi

    mkdir -p "$state_dir" 2>/dev/null || true
    last_notify=0
    if [ -r "$notify_cooldown_file" ]; then
        last_notify="$(sed -n '1p' "$notify_cooldown_file" 2>/dev/null || printf '0')"
    fi
    case "$last_notify" in ''|*[!0-9]*) last_notify=0 ;; esac

    now="$(date +%s)"
    age=$((now - last_notify))
    if [ "$age" -lt "$notify_cooldown_seconds" ]; then
        return 0
    fi

    hint="$(printf '%s' "$diagnosis_json" | jq -r '.hint // "Inspect status diagnosis."')"
    latest="$(printf '%s' "$diagnosis_json" | jq -r '
        .summary.latest // {} |
        "agent_bridge=" + (.agent_bridge_status // "unknown") +
        ", desktop=" + (.desktop_status // "unknown") +
        ", watchdog=" + (.watchdog_status // "unknown")
    ')"
    body="${latest}
${hint}"

    if notify-send -a sway "Agent-Bridge status: $diagnosis_status" "$body" >/dev/null 2>&1; then
        printf '%s\n' "$now" >"$notify_cooldown_file" 2>/dev/null || true
        log_event "notify" "diagnosis=$diagnosis_status"
    fi
}

emit() {
    local status="$1"
    local action="$2"
    local detail="$3"
    local doctor_json="${4:-null}"
    local heal_json="${5:-null}"
    jq -n \
        --arg schema "agent_bridge.sway_desktop.watchdog.v0" \
        --arg checked_at "$(date -Is)" \
        --arg status "$status" \
        --arg action "$action" \
        --arg detail "$detail" \
        --argjson doctor "$doctor_json" \
        --argjson heal "$heal_json" \
        '{
            schema: $schema,
            checked_at: $checked_at,
            status: $status,
            action: $action,
            detail: $detail,
            doctor: (if $doctor == null then null else {status: $doctor.status, summary: $doctor.summary} end),
            heal: (if $heal == null then null else {status: $heal.status, before: $heal.before, after: $heal.after} end)
        }'
}

if [ ! -x "$control" ]; then
    emit "error" "skipped" "$control missing or not executable"
    exit 2
fi

doctor_json="$("$control" desktop doctor 2>/dev/null || true)"
if ! printf '%s' "$doctor_json" | jq -e '.schema == "agent_bridge.sway_desktop.doctor.v0"' >/dev/null 2>&1; then
    log_event "error" "doctor did not return expected JSON"
    emit "error" "skipped" "desktop doctor did not return expected JSON"
    exit 1
fi

doctor_status="$(printf '%s' "$doctor_json" | jq -r '.status // "unknown"')"
if [ "$doctor_status" = "ok" ]; then
    log_event "ok" "desktop doctor ok"
    record_snapshot
    maybe_notify_diagnosis
    emit "ok" "noop" "desktop doctor ok" "$doctor_json"
    exit 0
fi

mkdir -p "$state_dir" 2>/dev/null || true
now="$(date +%s)"
last_heal=0
if [ -r "$cooldown_file" ]; then
    last_heal="$(sed -n '1p' "$cooldown_file" 2>/dev/null || printf '0')"
fi
case "$last_heal" in ''|*[!0-9]*) last_heal=0 ;; esac

age=$((now - last_heal))
if [ "$age" -lt "$cooldown_seconds" ]; then
    log_event "cooldown" "doctor=$doctor_status age=${age}s cooldown=${cooldown_seconds}s"
    record_snapshot
    maybe_notify_diagnosis
    emit "cooldown" "skipped" "desktop doctor is $doctor_status, but heal cooldown is active" "$doctor_json"
    exit 0
fi

printf '%s\n' "$now" >"$cooldown_file" 2>/dev/null || true
heal_json="$("$control" desktop heal --confirm 2>/dev/null || true)"
if printf '%s' "$heal_json" | jq -e '.schema == "agent_bridge.sway_desktop.heal.v0"' >/dev/null 2>&1; then
    heal_status="$(printf '%s' "$heal_json" | jq -r '.status // "unknown"')"
    log_event "heal" "doctor=$doctor_status heal=$heal_status"
    record_snapshot
    maybe_notify_diagnosis
    emit "$heal_status" "heal" "desktop doctor was $doctor_status; heal returned $heal_status" "$doctor_json" "$heal_json"
else
    log_event "error" "heal did not return expected JSON"
    record_snapshot
    maybe_notify_diagnosis
    emit "error" "heal" "desktop heal did not return expected JSON" "$doctor_json"
    exit 1
fi
