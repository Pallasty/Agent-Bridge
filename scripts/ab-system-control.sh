#!/usr/bin/env bash
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for helper in \
    "$script_dir/lib/ab-platform.sh" \
    "$script_dir/../scripts/lib/ab-platform.sh" \
    "/Data/CascadeProjects/agent-bridge/scripts/lib/ab-platform.sh"
do
    if [ -f "$helper" ]; then
        # shellcheck source=lib/ab-platform.sh
        . "$helper"
        break
    fi
done

if ! command -v ab_platform_os >/dev/null 2>&1; then
    ab_platform_os() { uname -s 2>/dev/null || printf 'unknown'; }
    ab_is_macos() { [ "$(ab_platform_os)" = "Darwin" ]; }
    ab_is_linux() { [ "$(ab_platform_os)" = "Linux" ]; }
    ab_default_data_dir() {
        if ab_is_macos; then
            printf '%s/Library/Application Support/agent-bridge' "${HOME:-.}"
        elif [ -n "${XDG_DATA_HOME:-}" ]; then
            printf '%s/agent-bridge' "$XDG_DATA_HOME"
        else
            printf '%s/.local/share/agent-bridge' "${HOME:-.}"
        fi
    }
    ab_default_system_control_audit_dir() {
        if [ -d /Data ] && [ -w /Data ]; then
            printf '/Data/agent-bridge/system-control'
        else
            printf '%s/system-control' "$(ab_default_data_dir)"
        fi
    }
fi
platform="$(ab_platform_os)"

default_audit_dir="$(ab_default_system_control_audit_dir)"
audit_dir="${AB_SYSTEM_CONTROL_AUDIT_DIR:-$default_audit_dir}"
audit_log="$audit_dir/system-actions.jsonl"
snapshot_log="$audit_dir/system-snapshots.jsonl"
actor="${AB_ACTOR:-local}"

ensure_audit_log() {
    mkdir -p "$audit_dir"
    chmod 700 "$audit_dir" 2>/dev/null || true
    touch "$audit_log"
    chmod 600 "$audit_log" 2>/dev/null || true
}

ensure_snapshot_log() {
    mkdir -p "$audit_dir"
    chmod 700 "$audit_dir" 2>/dev/null || true
    touch "$snapshot_log"
    chmod 600 "$snapshot_log" 2>/dev/null || true
}

json_string() {
    if command -v jq >/dev/null 2>&1; then
        jq -Rn --arg s "$1" '$s'
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
    else
        printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    fi
}

json_or_null() {
    local payload
    payload="$(cat)"
    if printf '%s' "$payload" | jq -e . >/dev/null 2>&1; then
        printf '%s' "$payload"
    else
        printf 'null'
    fi
}

audit() {
    local action="$1"
    local risk="$2"
    local result="$3"
    local detail="${4:-}"
    ensure_audit_log
    printf '{"ts":%s,"schema":"agent_bridge.system_control.audit.v0","actor":%s,"action":%s,"risk":%s,"result":%s,"detail":%s}\n' \
        "$(json_string "$(date -Is)")" \
        "$(json_string "$actor")" \
        "$(json_string "$action")" \
        "$(json_string "$risk")" \
        "$(json_string "$result")" \
        "$(json_string "$detail")" >>"$audit_log" 2>/dev/null || true
}

notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -a sway "$1" "$2" >/dev/null 2>&1 || true
    elif ab_is_macos && command -v osascript >/dev/null 2>&1; then
        osascript - "$1" "$2" >/dev/null 2>&1 <<'APPLESCRIPT' || true
on run argv
    display notification (item 2 of argv) with title (item 1 of argv)
end run
APPLESCRIPT
    fi
}

run_audited() {
    local action="$1"
    local risk="$2"
    shift 2
    if "$@"; then
        audit "$action" "$risk" "ok" "$*"
        return 0
    fi
    local rc=$?
    audit "$action" "$risk" "error" "rc=$rc $*"
    return "$rc"
}

unsupported_action() {
    local action="$1"
    local reason="${2:-unsupported on $platform}"
    audit "$action" "low" "unsupported" "$reason"
    echo "$action unsupported on $platform: $reason" >&2
    return 4
}

event_action() {
    case "${1:-}" in
        log)
            local source="${2:-unknown}"
            local name="${3:-event}"
            shift 3 2>/dev/null || true
            local detail="$*"
            source="${source//[^A-Za-z0-9_.-]/_}"
            name="${name//[^A-Za-z0-9_.-]/_}"
            audit "event.$source.$name" "low" "observed" "$detail"
            ;;
        *) echo "usage: ab-system-control event log <source> <name> [detail]" >&2; return 2 ;;
    esac
}

events_action() {
    case "${1:-tail}" in
        tail)
            local lines="${2:-80}"
            ensure_audit_log
            case "$lines" in ''|*[!0-9]*) lines=80 ;; esac
            lines=$((lines < 1 ? 1 : lines))
            lines=$((lines > 500 ? 500 : lines))
            tail -n "$lines" "$audit_log" |
                jq -s --arg schema "agent_bridge.system_control.timeline.v0" \
                    '{schema:$schema, events:.}' 2>/dev/null || true
            ;;
        diagnose)
            local topic="${2:-}"
            local lines="${3:-120}"
            if [ -z "$topic" ]; then
                echo "usage: ab-system-control events diagnose <topic> [n]" >&2
                return 2
            fi
            ensure_audit_log
            case "$lines" in ''|*[!0-9]*) lines=120 ;; esac
            lines=$((lines < 1 ? 1 : lines))
            lines=$((lines > 500 ? 500 : lines))
            tail -n "$lines" "$audit_log" |
                jq -s \
                    --arg schema "agent_bridge.system_control.diagnosis.v0" \
                    --arg topic "$topic" \
                    --arg inspected "$lines" \
                    '
                    def lc: ascii_downcase;
                    def match_topic($q):
                        (((.action // "") | lc | contains($q)) or
                         ((.detail // "") | lc | contains($q)));
                    ($topic | lc) as $q |
                    . as $events |
                    ($events | map(select(match_topic($q)))) as $matches |
                    ($matches | map(select((.action // "") | startswith("event.")))) as $signals |
                    ($signals | map(select((.action // "") | startswith("event.watchdog.")))) as $watchdog_signals |
                    ($matches | map(select(((.action // "") | startswith("event.")) | not))) as $actions |
                    ($matches | map(select((.result // "") as $r | ($r == "error" or $r == "blocked")))) as $bad |
                    ($actions | map(select((.result // "") == "ok"))) as $ok_actions |
                    ($matches[-1] // null) as $latest |
                    (if ($matches | length) == 0 then "no_signal"
                     elif (($latest.result // "") == "ok") then "ok"
                     elif (($latest.action // "") | startswith("event.watchdog.")) then "ok"
                     elif ($bad | length) > 0 then "action_errors"
                     elif ($ok_actions | length) > 0 then "ok"
                     elif (($watchdog_signals | length) > 0 and ($actions | length) == 0) then "ok"
                     elif (($signals | length) > 0 and ($actions | length) == 0) then "entry_seen_no_action"
                     else "observed" end) as $status |
                    {
                        schema: $schema,
                        topic: $topic,
                        inspected_events: ($inspected | tonumber),
                        status: $status,
                        summary: {
                            matches: ($matches | length),
                            entry_events: ($signals | length),
                            action_events: ($actions | length),
                            bad_events: ($bad | length),
                            ok_actions: ($ok_actions | length)
                        },
                        latest: $latest,
                        recent_matches: ($matches | .[-10:]),
                        hint: (if $status == "no_signal" then
                                  "No recent matching event; check Sway binding/key symbol and whether the helper script is executable."
                               elif $status == "entry_seen_no_action" then
                                  "Input reached the wrapper/menu, but no matching audited action followed; inspect helper routing."
                               elif $status == "action_errors" then
                                  "A matching action was blocked or failed; inspect latest.detail and run desktop doctor."
                               else
                                  "Recent matching events look healthy."
                               end)
                    }' 2>/dev/null || true
            ;;
        *) echo "usage: ab-system-control events tail [n] | events diagnose <topic> [n]" >&2; return 2 ;;
    esac
}

require_confirm() {
    local flag="${1:-}"
    [ "$flag" = "--confirm" ]
}

display_action() {
    case "${1:-}" in
        off)
            if ab_is_macos; then
                command -v pmset >/dev/null 2>&1 || { unsupported_action "display.off" "pmset not found"; return; }
                run_audited "display.off" "low" pmset displaysleepnow >/dev/null
            else
                run_audited "display.off" "low" swaymsg "output * power off" >/dev/null
            fi
            ;;
        on)
            if ab_is_macos; then
                unsupported_action "display.on" "macOS display wake requires user input or a separate input-grant path"
                return
            fi
            run_audited "display.on" "low" swaymsg "output * power on" >/dev/null
            ;;
        toggle-off) display_action off ;;
        *) echo "usage: ab-system-control display off|on" >&2; return 2 ;;
    esac
}

macos_audio_action() {
    command -v osascript >/dev/null 2>&1 || { unsupported_action "audio.${1:-}" "osascript not found"; return; }
    local current next
    case "${1:-}" in
        up)
            current="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || printf 0)"
            case "$current" in ''|*[!0-9]*) current=0 ;; esac
            next=$((current + 5))
            [ "$next" -gt 100 ] && next=100
            osascript -e "set volume output volume $next" -e 'set volume without output muted' >/dev/null
            ;;
        down)
            current="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || printf 0)"
            case "$current" in ''|*[!0-9]*) current=0 ;; esac
            next=$((current - 5))
            [ "$next" -lt 0 ] && next=0
            osascript -e "set volume output volume $next" -e 'set volume without output muted' >/dev/null
            ;;
        mute)
            current="$(osascript -e 'output muted of (get volume settings)' 2>/dev/null || printf false)"
            if [ "$current" = "true" ]; then
                osascript -e 'set volume without output muted' >/dev/null
            else
                osascript -e 'set volume with output muted' >/dev/null
            fi
            ;;
        micmute)
            unsupported_action "audio.micmute" "macOS microphone mute has no built-in shell equivalent"
            return
            ;;
        *) echo "usage: ab-system-control audio up|down|mute|micmute" >&2; return 2 ;;
    esac
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        audit "audio.${1:-}" "low" "ok"
        notify "Audio" "$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || true)%"
    else
        audit "audio.${1:-}" "low" "error" "rc=$rc"
    fi
    return "$rc"
}

audio_action() {
    if ab_is_macos; then
        macos_audio_action "$@"
        return
    fi
    case "${1:-}" in
        up)
            pactl set-sink-volume @DEFAULT_SINK@ +5% &&
            pactl set-sink-mute @DEFAULT_SINK@ 0
            ;;
        down)
            pactl set-sink-volume @DEFAULT_SINK@ -5% &&
            pactl set-sink-mute @DEFAULT_SINK@ 0
            ;;
        mute)
            pactl set-sink-mute @DEFAULT_SINK@ toggle
            ;;
        micmute)
            pactl set-source-mute @DEFAULT_SOURCE@ toggle
            ;;
        *) echo "usage: ab-system-control audio up|down|mute|micmute" >&2; return 2 ;;
    esac
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        audit "audio.${1:-}" "low" "ok"
        notify "Audio" "$(pactl get-sink-volume @DEFAULT_SINK@ | sed -n 's/^Volume: //p' | head -1)"
    else
        audit "audio.${1:-}" "low" "error" "rc=$rc"
    fi
    return "$rc"
}

brightness_action() {
    if ab_is_macos; then
        if ! command -v brightness >/dev/null 2>&1; then
            unsupported_action "brightness.${1:-}" "install the macOS brightness CLI or use system display settings"
            return
        fi
        case "${1:-}" in
            up) brightness +0.05 ;;
            down) brightness -0.05 ;;
            *) echo "usage: ab-system-control brightness up|down" >&2; return 2 ;;
        esac
        local rc=$?
        if [ "$rc" -eq 0 ]; then
            audit "brightness.${1:-}" "low" "ok"
            notify "Brightness" "$(brightness -l 2>/dev/null | awk '/brightness/ {print $NF; exit}')"
        else
            audit "brightness.${1:-}" "low" "error" "rc=$rc"
        fi
        return "$rc"
    fi
    case "${1:-}" in
        up) brightnessctl set +5% ;;
        down) brightnessctl set 5%- ;;
        *) echo "usage: ab-system-control brightness up|down" >&2; return 2 ;;
    esac
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        audit "brightness.${1:-}" "low" "ok"
        notify "Brightness" "$(brightnessctl -m | awk -F, '{print $4}')"
    else
        audit "brightness.${1:-}" "low" "error" "rc=$rc"
    fi
    return "$rc"
}

screenshot_action() {
    local mode="${1:-region}"
    local dir="${XDG_PICTURES_DIR:-$HOME/Pictures}/Screenshots"
    mkdir -p "$dir"
    local file="$dir/screenshot-$(date +%Y%m%d-%H%M%S).png"
    if ab_is_macos; then
        command -v screencapture >/dev/null 2>&1 || { unsupported_action "screenshot.$mode" "screencapture not found"; return; }
        case "$mode" in
            full)
                screencapture "$file" || { audit "screenshot.full" "low" "error"; return 1; }
                ;;
            region)
                notify "Screenshot" "Select an area"
                screencapture -i "$file" || { audit "screenshot.region" "low" "cancelled"; return 0; }
                [ -s "$file" ] || { audit "screenshot.region" "low" "cancelled"; return 0; }
                ;;
            *) echo "usage: ab-system-control screenshot full|region" >&2; return 2 ;;
        esac
        audit "screenshot.$mode" "low" "ok" "$file"
        notify "Screenshot" "Saved: $file"
        return
    fi
    case "$mode" in
        full)
            grim "$file" || { audit "screenshot.full" "low" "error"; return 1; }
            ;;
        region)
            notify "Screenshot" "Drag to select an area"
            local geometry
            geometry="$(slurp)" || { audit "screenshot.region" "low" "cancelled"; return 0; }
            [ -n "$geometry" ] || { audit "screenshot.region" "low" "cancelled"; return 0; }
            grim -g "$geometry" "$file" || { audit "screenshot.region" "low" "error"; return 1; }
            ;;
        *) echo "usage: ab-system-control screenshot full|region" >&2; return 2 ;;
    esac
    if command -v wl-copy >/dev/null 2>&1; then
        wl-copy <"$file" || true
    fi
    audit "screenshot.$mode" "low" "ok" "$file"
    notify "Screenshot" "Saved and copied: $file"
}

macos_wifi_device() {
    command -v networksetup >/dev/null 2>&1 || return 1
    networksetup -listallhardwareports 2>/dev/null |
        awk '/Hardware Port: (Wi-Fi|AirPort)/ {getline; if ($1 == "Device:") {print $2; exit}}'
}

macos_wifi_action() {
    local dev
    dev="$(macos_wifi_device)"
    [ -n "$dev" ] || { unsupported_action "wifi.${1:-}" "no macOS Wi-Fi device found"; return; }
    case "${1:-}" in
        networks)
            networksetup -listpreferredwirelessnetworks "$dev"
            audit "wifi.networks" "medium" "ok" "$dev"
            ;;
        reconnect)
            run_audited "wifi.reconnect" "medium" networksetup -setairportpower "$dev" off &&
                sleep 1 &&
                run_audited "wifi.reconnect" "medium" networksetup -setairportpower "$dev" on
            ;;
        toggle)
            local power
            power="$(networksetup -getairportpower "$dev" 2>/dev/null | awk '{print $NF}')"
            if [ "$power" = "On" ]; then
                run_audited "wifi.toggle" "medium" networksetup -setairportpower "$dev" off
            else
                run_audited "wifi.toggle" "medium" networksetup -setairportpower "$dev" on
            fi
            ;;
        actions|nmtui)
            unsupported_action "wifi.${1:-}" "NetworkManager/nmtui menu is Linux-only"
            ;;
        *) echo "usage: ab-system-control wifi networks|actions|reconnect|toggle|nmtui" >&2; return 2 ;;
    esac
}

wifi_action() {
    if ab_is_macos; then
        macos_wifi_action "$@"
        return
    fi
    case "${1:-}" in
        networks|actions|reconnect|toggle|nmtui)
            run_audited "wifi.${1:-}" "medium" "$HOME/.local/bin/sway-wifi-menu" "${1:-}"
            ;;
        *) echo "usage: ab-system-control wifi networks|actions|reconnect|toggle|nmtui" >&2; return 2 ;;
    esac
}

desktop_action() {
    if ab_is_macos; then
        case "${1:-doctor}" in
            doctor|check)
                jq -n \
                    --arg schema "agent_bridge.system_control.desktop_doctor.v0" \
                    --arg platform "$platform" \
                    --arg osascript "$(command -v osascript || true)" \
                    --arg screencapture "$(command -v screencapture || true)" \
                    --arg pmset "$(command -v pmset || true)" \
                    --arg networksetup "$(command -v networksetup || true)" \
                    '{
                        schema: $schema,
                        platform: $platform,
                        status: "ok",
                        summary: "macOS fallback path; Sway repair/watchdog actions are not applicable",
                        checks: [
                            {name:"osascript", status:(if $osascript == "" then "warn" else "ok" end), path:$osascript},
                            {name:"screencapture", status:(if $screencapture == "" then "warn" else "ok" end), path:$screencapture},
                            {name:"pmset", status:(if $pmset == "" then "warn" else "ok" end), path:$pmset},
                            {name:"networksetup", status:(if $networksetup == "" then "warn" else "ok" end), path:$networksetup}
                        ]
                    }'
                ;;
            heal|watchdog|repair)
                if ! require_confirm "${2:-}"; then
                    audit "desktop.${1:-}" "medium" "blocked" "missing --confirm"
                    echo "Refusing desktop ${1:-} without --confirm" >&2
                    return 3
                fi
                unsupported_action "desktop.${1:-}" "Sway desktop repair/watchdog helpers are Linux-only"
                ;;
            *) echo "usage: ab-system-control desktop doctor|heal --confirm|watchdog --confirm|repair --confirm" >&2; return 2 ;;
        esac
        return
    fi
    case "${1:-doctor}" in
        doctor|check)
            "$HOME/.local/bin/sway-desktop-doctor" doctor
            ;;
        heal)
            if ! require_confirm "${2:-}"; then
                audit "desktop.heal" "medium" "blocked" "missing --confirm"
                echo "Refusing desktop heal without --confirm" >&2
                return 3
            fi
            run_audited "desktop.heal" "medium" "$HOME/.local/bin/sway-desktop-doctor" heal
            ;;
        watchdog)
            if ! require_confirm "${2:-}"; then
                audit "desktop.watchdog" "medium" "blocked" "missing --confirm"
                echo "Refusing desktop watchdog without --confirm" >&2
                return 3
            fi
            run_audited "desktop.watchdog" "medium" "$HOME/.local/bin/sway-desktop-watchdog"
            ;;
        repair)
            if ! require_confirm "${2:-}"; then
                audit "desktop.repair" "medium" "blocked" "missing --confirm"
                echo "Refusing desktop repair without --confirm" >&2
                return 3
            fi
            run_audited "desktop.repair" "medium" "$HOME/.local/bin/sway-desktop-doctor" repair
            ;;
        *) echo "usage: ab-system-control desktop doctor|heal --confirm|watchdog --confirm|repair --confirm" >&2; return 2 ;;
    esac
}

status_action() {
    case "${1:-summary}" in
        summary) ;;
        snapshot)
            local status_json desktop_json events_json watchdog_diag power_diag wifi_diag screenshot_diag
            local timer_text agent_doctor_text
            status_json="$(status_action summary 2>/dev/null | json_or_null)"
            if ab_is_macos; then
                desktop_json="$(desktop_action doctor 2>/dev/null | json_or_null)"
            else
                desktop_json="$("$HOME/.local/bin/sway-desktop-doctor" doctor 2>/dev/null | json_or_null)"
            fi
            events_json="$(events_action tail 40 2>/dev/null | json_or_null)"
            watchdog_diag="$(events_action diagnose watchdog 120 2>/dev/null | json_or_null)"
            power_diag="$(events_action diagnose power 120 2>/dev/null | json_or_null)"
            wifi_diag="$(events_action diagnose wifi 120 2>/dev/null | json_or_null)"
            screenshot_diag="$(events_action diagnose screenshot 120 2>/dev/null | json_or_null)"
            if ab_is_macos; then
                timer_text="$(launchctl print "gui/$(id -u)/com.agentbridge.desktop-watchdog" 2>&1 || true)"
            else
                timer_text="$(systemctl --user --no-pager list-timers sway-desktop-watchdog.timer 2>&1 || true)"
            fi
            if [ "${AB_SYSTEM_CONTROL_SNAPSHOT_SKIP_AGENT_DOCTOR:-0}" = "1" ]; then
                agent_doctor_text="skipped by AB_SYSTEM_CONTROL_SNAPSHOT_SKIP_AGENT_DOCTOR=1"
            else
                agent_doctor_text="$(agent-bridge doctor 2>&1 || "$HOME/.local/bin/agent-bridge.real" doctor 2>&1 || true)"
            fi
            jq -n \
                --arg schema "agent_bridge.system_control.snapshot.v0" \
                --arg captured_at "$(date -Is)" \
                --arg timer_text "$timer_text" \
                --arg agent_doctor_text "$agent_doctor_text" \
                --argjson status "$status_json" \
                --argjson desktop "$desktop_json" \
                --argjson events "$events_json" \
                --argjson watchdog_diag "$watchdog_diag" \
                --argjson power_diag "$power_diag" \
                --argjson wifi_diag "$wifi_diag" \
                --argjson screenshot_diag "$screenshot_diag" \
                '{
                    schema: $schema,
                    captured_at: $captured_at,
                    read_only: true,
                    summary: {
                        agent_bridge_status: (if ($agent_doctor_text | startswith("skipped by ")) then "skipped" elif ($agent_doctor_text | contains("/ 0 warn / 0 fail ---")) then "ok" elif ($agent_doctor_text | contains("/ 0 fail ---")) then "warn" else "fail" end),
                        agent_bridge_ok: ($agent_doctor_text | contains("/ 0 fail ---")),
                        desktop_status: ($desktop.status // "unknown"),
                        desktop_summary: ($desktop.summary // null),
                        watchdog_status: ($watchdog_diag.status // "unknown"),
                        status_services: ($status.services // null)
                    },
                    status: $status,
                    desktop_doctor: (if $desktop == null then null else {status: $desktop.status, summary: $desktop.summary, problems: [$desktop.checks[]? | select(.status != "ok")]} end),
                    watchdog: {
                        timer_text: $timer_text,
                        diagnosis: $watchdog_diag
                    },
                    diagnostics: {
                        power: $power_diag,
                        wifi: $wifi_diag,
                        screenshot: $screenshot_diag
                    },
                    recent_events: ($events.events // []),
                    agent_bridge_doctor_text: $agent_doctor_text
                }'
            return
            ;;
        record)
            ensure_snapshot_log
            local snapshot record keep tmp
            keep="${AB_SYSTEM_CONTROL_SNAPSHOT_KEEP:-200}"
            case "$keep" in ''|*[!0-9]*) keep=200 ;; esac
            keep=$((keep < 1 ? 1 : keep))
            keep=$((keep > 2000 ? 2000 : keep))
            snapshot="$(AB_SYSTEM_CONTROL_SNAPSHOT_SKIP_AGENT_DOCTOR=1 status_action snapshot 2>/dev/null | json_or_null)"
            record="$(printf '%s' "$snapshot" | jq -c \
                --arg schema "agent_bridge.system_control.snapshot_record.v0" \
                '{
                    schema: $schema,
                    captured_at: (.captured_at // now | tostring),
                    summary: (.summary // {}),
                    status: (.status // null),
                    desktop_doctor: (.desktop_doctor // null),
                    watchdog: (.watchdog.diagnosis // null),
                    diagnostics: (.diagnostics // null)
                }')"
            printf '%s\n' "$record" >>"$snapshot_log"
            tmp="$(mktemp)"
            tail -n "$keep" "$snapshot_log" >"$tmp" 2>/dev/null || true
            cat "$tmp" >"$snapshot_log"
            rm -f "$tmp"
            chmod 600 "$snapshot_log" 2>/dev/null || true
            printf '%s\n' "$record"
            return
            ;;
        history)
            ensure_snapshot_log
            local lines="${2:-20}"
            case "$lines" in ''|*[!0-9]*) lines=20 ;; esac
            lines=$((lines < 1 ? 1 : lines))
            lines=$((lines > 200 ? 200 : lines))
            tail -n "$lines" "$snapshot_log" |
                jq -s --arg schema "agent_bridge.system_control.snapshot_history.v0" \
                    --arg path "$snapshot_log" \
                    '{schema:$schema,path:$path,snapshots:.}' 2>/dev/null || true
            return
            ;;
        diagnose)
            ensure_snapshot_log
            local lines="${2:-20}"
            case "$lines" in ''|*[!0-9]*) lines=20 ;; esac
            lines=$((lines < 1 ? 1 : lines))
            lines=$((lines > 200 ? 200 : lines))
            tail -n "$lines" "$snapshot_log" |
                jq -s --arg schema "agent_bridge.system_control.snapshot_diagnosis.v0" \
                    --arg path "$snapshot_log" \
                    '
                    def summary: .summary // {};
                    def services: (summary.status_services // {});
                    def services_ok: ([services[]?] | all(. == true));
                    def hard_bad:
                        ((summary.desktop_status // "unknown") != "ok") or
                        ((summary.watchdog_status // "unknown") != "ok") or
                        ((summary.agent_bridge_status // "unknown") == "fail") or
                        (services_ok | not);
                    def soft_warn:
                        ((summary.agent_bridge_status // "unknown") == "warn");
                    def compact:
                        {
                            captured_at,
                            agent_bridge_status: summary.agent_bridge_status,
                            desktop_status: summary.desktop_status,
                            desktop_summary: summary.desktop_summary,
                            watchdog_status: summary.watchdog_status,
                            services: summary.status_services
                        };
                    . as $snapshots |
                    ($snapshots[-1] // null) as $latest |
                    ($snapshots[-2] // null) as $previous |
                    ($snapshots | map(select(hard_bad))) as $bad |
                    ($snapshots | map(select(soft_warn))) as $warn |
                    {
                        schema: $schema,
                        read_only: true,
                        path: $path,
                        inspected_snapshots: ($snapshots | length),
                        status: (if ($snapshots | length) == 0 then "no_history"
                                 elif ($latest | hard_bad) then "degraded"
                                 elif ($bad | length) > 0 then "recent_degradation"
                                 elif ($latest | soft_warn) then "watch"
                                 else "ok" end),
                        summary: {
                            hard_bad_snapshots: ($bad | length),
                            warn_snapshots: ($warn | length),
                            latest: (if $latest == null then null else ($latest | compact) end),
                            previous: (if $previous == null then null else ($previous | compact) end)
                        },
                        changes: (if ($latest == null or $previous == null) then []
                                  else [
                                      (if (($previous.summary.agent_bridge_status // null) != ($latest.summary.agent_bridge_status // null)) then {field:"agent_bridge_status",from:$previous.summary.agent_bridge_status,to:$latest.summary.agent_bridge_status} else empty end),
                                      (if (($previous.summary.desktop_status // null) != ($latest.summary.desktop_status // null)) then {field:"desktop_status",from:$previous.summary.desktop_status,to:$latest.summary.desktop_status} else empty end),
                                      (if (($previous.summary.watchdog_status // null) != ($latest.summary.watchdog_status // null)) then {field:"watchdog_status",from:$previous.summary.watchdog_status,to:$latest.summary.watchdog_status} else empty end),
                                      (if (($previous.summary.status_services // {}) != ($latest.summary.status_services // {})) then {field:"status_services",from:$previous.summary.status_services,to:$latest.summary.status_services} else empty end)
                                  ] end),
                        recent_bad: ($bad | .[-5:] | map(compact)),
                        hint: (if ($snapshots | length) == 0 then
                                  "No snapshot history yet; run ab-system-control status record or wait for the watchdog timer."
                               elif ($latest | hard_bad) then
                                  "Latest snapshot is degraded; inspect latest summary and run desktop doctor."
                               elif ($bad | length) > 0 then
                                  "Latest snapshot is healthy, but recent history contains degradation; inspect recent_bad."
                               elif ($latest | soft_warn) then
                                  "Latest snapshot is usable with a warning; inspect agent_bridge_status."
                               else
                                  "Recent snapshot history looks healthy."
                               end)
                    }' 2>/dev/null || true
            return
            ;;
        report)
            local lines="${2:-20}"
            case "$lines" in ''|*[!0-9]*) lines=20 ;; esac
            lines=$((lines < 1 ? 1 : lines))
            lines=$((lines > 200 ? 200 : lines))
            local diagnosis
            diagnosis="$(status_action diagnose "$lines" 2>/dev/null | json_or_null)"
            printf '%s' "$diagnosis" | jq -r --arg generated_at "$(date -Is)" '
                def s: .summary.latest // {};
                def services:
                    (s.services // {})
                    | to_entries
                    | map(.key + "=" + (if .value then "ok" else "bad" end))
                    | join(", ");
                def changes:
                    if (.changes // [] | length) == 0 then
                        "Changes: none"
                    else
                        "Changes:\n" + ((.changes // []) | map("- " + .field + ": " + (.from|tostring) + " -> " + (.to|tostring)) | join("\n"))
                    end;
                [
                    "System status report",
                    "Generated: " + $generated_at,
                    "Status: " + (.status // "unknown"),
                    "Snapshots inspected: " + ((.inspected_snapshots // 0) | tostring),
                    "Hard bad snapshots: " + ((.summary.hard_bad_snapshots // 0) | tostring),
                    "Warn snapshots: " + ((.summary.warn_snapshots // 0) | tostring),
                    "Latest: agent_bridge=" + (s.agent_bridge_status // "unknown") + ", desktop=" + (s.desktop_status // "unknown") + ", watchdog=" + (s.watchdog_status // "unknown"),
                    "Services: " + (services // ""),
                    changes,
                    "Hint: " + (.hint // "")
                ] | join("\n")
            '
            return
            ;;
        *) echo "usage: ab-system-control status [summary|snapshot|record|history [n]|diagnose [n]|report [n]]" >&2; return 2 ;;
    esac

    if ab_is_macos; then
        local audio_volume="" audio_muted="" mic_muted=""
        if command -v osascript >/dev/null 2>&1; then
            audio_volume="$(osascript -e 'output volume of (get volume settings)' 2>/dev/null || true)"
            [ -n "$audio_volume" ] && audio_volume="${audio_volume}%"
            audio_muted="$(osascript -e 'output muted of (get volume settings)' 2>/dev/null || true)"
            case "$audio_muted" in
                true) audio_muted="yes" ;;
                false) audio_muted="no" ;;
            esac
        fi

        local brightness=""
        if command -v brightness >/dev/null 2>&1; then
            brightness="$(brightness -l 2>/dev/null | awk '/brightness/ {print $NF; exit}')"
        fi

        local wifi_radio="" wifi_connected="false" wifi_ssid="" wifi_signal=""
        if command -v networksetup >/dev/null 2>&1; then
            local wifi_dev="" power_line ssid_line
            wifi_dev="$(macos_wifi_device)"
            if [ -n "$wifi_dev" ]; then
                power_line="$(networksetup -getairportpower "$wifi_dev" 2>/dev/null || true)"
                case "$power_line" in
                    *": On") wifi_radio="enabled" ;;
                    *": Off") wifi_radio="disabled" ;;
                    *) wifi_radio="" ;;
                esac
                ssid_line="$(networksetup -getairportnetwork "$wifi_dev" 2>/dev/null || true)"
                case "$ssid_line" in
                    "Current Wi-Fi Network:"*)
                        wifi_connected="true"
                        wifi_ssid="${ssid_line#Current Wi-Fi Network: }"
                        ;;
                esac
            fi
        fi

        local outputs_total=1 outputs_active=1 outputs_powered=1 focused_output="main"
        local battery_state="" battery_percent=""
        if command -v pmset >/dev/null 2>&1; then
            local batt=""
            batt="$(pmset -g batt 2>/dev/null || true)"
            battery_percent="$(printf '%s\n' "$batt" | grep -oE '[0-9]+%' | head -1 || true)"
            battery_state="$(printf '%s\n' "$batt" | awk -F'; *' 'NR == 2 {print $2; exit}')"
        fi

        jq -n \
            --arg schema "agent_bridge.system_control.status.v0" \
            --arg platform "$platform" \
            --arg audio_volume "$audio_volume" \
            --arg audio_muted "$audio_muted" \
            --arg mic_muted "$mic_muted" \
            --arg brightness "$brightness" \
            --arg wifi_radio "$wifi_radio" \
            --arg wifi_ssid "$wifi_ssid" \
            --arg wifi_signal "$wifi_signal" \
            --arg focused_output "$focused_output" \
            --arg battery_state "$battery_state" \
            --arg battery_percent "$battery_percent" \
            --argjson wifi_connected "$wifi_connected" \
            --argjson outputs_total "$outputs_total" \
            --argjson outputs_active "$outputs_active" \
            --argjson outputs_powered "$outputs_powered" \
            '{
                schema: $schema,
                platform: {os: $platform},
                audio: {volume: $audio_volume, muted: $audio_muted, mic_muted: $mic_muted},
                brightness: {percent: $brightness},
                wifi: {radio: $wifi_radio, connected: $wifi_connected, ssid: $wifi_ssid, signal: $wifi_signal},
                display: {outputs_total: $outputs_total, outputs_active: $outputs_active, outputs_powered: $outputs_powered, focused_output: $focused_output},
                battery: {state: $battery_state, percentage: $battery_percent},
                services: {swayidle: false, mako: false, networkmanager: false}
            }'
        return
    fi

    local audio_volume="" audio_muted="" mic_muted=""
    if command -v pactl >/dev/null 2>&1; then
        audio_volume="$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | awk -F/ 'NR == 1 {gsub(/ /, "", $2); print $2}')"
        audio_muted="$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | awk '{print $2}')"
        mic_muted="$(pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | awk '{print $2}')"
    fi

    local brightness=""
    if command -v brightnessctl >/dev/null 2>&1; then
        brightness="$(brightnessctl -m 2>/dev/null | awk -F, '{print $4}')"
    fi

    local wifi_radio="" wifi_connected="false" wifi_ssid="" wifi_signal=""
    if command -v nmcli >/dev/null 2>&1; then
        wifi_radio="$(nmcli -t -f WIFI general 2>/dev/null || true)"
        local active_line=""
        active_line="$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null | awk -F: '$2 == "wifi" && $3 == "connected" {print; exit}')"
        if [ -n "$active_line" ]; then
            wifi_connected="true"
            wifi_ssid="$(printf '%s\n' "$active_line" | awk -F: '{print $4}')"
            wifi_signal="$(nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi 2>/dev/null | awk -F: -v ssid="$wifi_ssid" '$1 == "yes" || $2 == ssid {print $3; exit}')"
        fi
    fi

    local outputs_total=0 outputs_active=0 outputs_powered=0 focused_output=""
    if command -v swaymsg >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
        local outputs_json=""
        outputs_json="$(swaymsg -t get_outputs -r 2>/dev/null || printf '[]')"
        outputs_total="$(printf '%s' "$outputs_json" | jq 'length' 2>/dev/null || printf 0)"
        outputs_active="$(printf '%s' "$outputs_json" | jq '[.[] | select(.active == true)] | length' 2>/dev/null || printf 0)"
        outputs_powered="$(printf '%s' "$outputs_json" | jq '[.[] | select(.power == true)] | length' 2>/dev/null || printf 0)"
        focused_output="$(printf '%s' "$outputs_json" | jq -r '.[] | select(.focused == true) | .name' 2>/dev/null | head -1)"
    fi

    local battery_state="" battery_percent=""
    if command -v upower >/dev/null 2>&1; then
        local battery=""
        battery="$(upower -e 2>/dev/null | awk '/battery/ {print; exit}')"
        if [ -n "$battery" ]; then
            local info=""
            info="$(upower -i "$battery" 2>/dev/null || true)"
            battery_state="$(printf '%s\n' "$info" | awk -F': *' '/state:/ {print $2; exit}')"
            battery_percent="$(printf '%s\n' "$info" | awk -F': *' '/percentage:/ {print $2; exit}')"
        fi
    fi

    local swayidle_running="false" mako_running="false" networkmanager_running="false"
    pgrep -x swayidle >/dev/null 2>&1 && swayidle_running="true"
    pgrep -x mako >/dev/null 2>&1 && mako_running="true"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl is-active --quiet NetworkManager.service 2>/dev/null && networkmanager_running="true"
    fi

    jq -n \
        --arg schema "agent_bridge.system_control.status.v0" \
        --arg audio_volume "$audio_volume" \
        --arg audio_muted "$audio_muted" \
        --arg mic_muted "$mic_muted" \
        --arg brightness "$brightness" \
        --arg wifi_radio "$wifi_radio" \
        --arg wifi_ssid "$wifi_ssid" \
        --arg wifi_signal "$wifi_signal" \
        --arg focused_output "$focused_output" \
        --arg battery_state "$battery_state" \
        --arg battery_percent "$battery_percent" \
        --argjson wifi_connected "$wifi_connected" \
        --argjson outputs_total "$outputs_total" \
        --argjson outputs_active "$outputs_active" \
        --argjson outputs_powered "$outputs_powered" \
        --argjson swayidle_running "$swayidle_running" \
        --argjson mako_running "$mako_running" \
        --argjson networkmanager_running "$networkmanager_running" \
        '{
            schema: $schema,
            audio: {volume: $audio_volume, muted: $audio_muted, mic_muted: $mic_muted},
            brightness: {percent: $brightness},
            wifi: {radio: $wifi_radio, connected: $wifi_connected, ssid: $wifi_ssid, signal: $wifi_signal},
            display: {outputs_total: $outputs_total, outputs_active: $outputs_active, outputs_powered: $outputs_powered, focused_output: $focused_output},
            battery: {state: $battery_state, percentage: $battery_percent},
            services: {swayidle: $swayidle_running, mako: $mako_running, networkmanager: $networkmanager_running}
        }'
}

lid_action() {
    case "${1:-}" in
        off) display_action off ;;
        on) display_action on ;;
        *) echo "usage: ab-system-control lid off|on" >&2; return 2 ;;
    esac
}

display_powered_count() {
    if command -v swaymsg >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
        swaymsg -t get_outputs -r 2>/dev/null | jq '[.[] | select(.power == true)] | length' 2>/dev/null || printf 1
    else
        printf 1
    fi
}

power_action() {
    local sub="${1:-press}"
    case "$sub" in
        press)
            local window_seconds="${SWAY_POWER_DOUBLE_PRESS_SECONDS:-2}"
            local state_file="${XDG_RUNTIME_DIR:-/tmp}/sway-power-button.last"
            local now last powered_count
            now="$(date +%s)"
            last=""
            if [ -r "$state_file" ]; then
                last="$(cat "$state_file" 2>/dev/null || true)"
            fi
            case "$last" in ''|*[!0-9]*) last="" ;; esac
            if ab_is_macos; then
                if [ -n "$last" ] && [ $((now - last)) -le "$window_seconds" ]; then
                    rm -f "$state_file"
                    audit "power.press.double" "high" "blocked" "macOS poweroff is not mapped"
                    notify "Power button" "Poweroff is not mapped on macOS"
                    unsupported_action "power.press.double" "use an explicit human-confirmed shutdown path on macOS"
                    return
                fi
                printf '%s\n' "$now" >"$state_file"
                audit "power.press.single" "medium" "ok" "macos_display_sleep; double_window=${window_seconds}s"
                notify "Power button" "Screen off"
                command -v pmset >/dev/null 2>&1 || { unsupported_action "display.off" "pmset not found"; return; }
                pmset displaysleepnow
                return
            fi
            if [ -n "$last" ] && [ $((now - last)) -le "$window_seconds" ]; then
                rm -f "$state_file"
                audit "power.press.double" "high" "confirmed" "window=${window_seconds}s"
                notify "Power button" "Powering off"
                exec systemctl poweroff
            fi

            powered_count="$(display_powered_count)"
            case "$powered_count" in ''|*[!0-9]*) powered_count=1 ;; esac
            if [ "$powered_count" -eq 0 ]; then
                rm -f "$state_file"
                audit "power.press.wake" "low" "ok" "screen_on"
                notify "Power button" "Screen on"
                swaymsg "output * power on" >/dev/null
                return
            fi

            printf '%s\n' "$now" >"$state_file"
            audit "power.press.single" "medium" "ok" "screen_off; double_window=${window_seconds}s"
            notify "Power button" "Screen off. Press again within ${window_seconds}s to power off"
            swaymsg "output * power off" >/dev/null
            ;;
        off)
            if ! require_confirm "${2:-}"; then
                audit "power.off" "high" "blocked" "missing --confirm"
                echo "Refusing poweroff without --confirm" >&2
                return 3
            fi
            if ab_is_macos; then
                unsupported_action "power.off" "macOS shutdown requires a separate human-confirmed adapter"
                return
            fi
            audit "power.off" "high" "confirmed" "--confirm"
            exec systemctl poweroff
            ;;
        *) echo "usage: ab-system-control power press|off --confirm" >&2; return 2 ;;
    esac
}

case "${1:-}" in
    event) shift; event_action "$@" ;;
    events) shift; events_action "$@" ;;
    display) shift; display_action "$@" ;;
    audio) shift; audio_action "$@" ;;
    brightness) shift; brightness_action "$@" ;;
    screenshot) shift; screenshot_action "$@" ;;
    wifi) shift; wifi_action "$@" ;;
    desktop) shift; desktop_action "$@" ;;
    status) shift; status_action "$@" ;;
    lid) shift; lid_action "$@" ;;
    power) shift; power_action "$@" ;;
    audit-tail)
        shift
        ensure_audit_log
        tail -n "${1:-40}" "$audit_log"
        ;;
    *)
        cat >&2 <<'EOF'
usage: ab-system-control <command> [...]

commands:
  display off|on
  event log <source> <name> [detail]
  events tail [n]
  events diagnose <topic> [n]
  audio up|down|mute|micmute
  brightness up|down
  screenshot full|region
  wifi networks|actions|reconnect|toggle|nmtui
  desktop doctor
  desktop heal --confirm
  desktop watchdog --confirm
  desktop repair --confirm
  status [summary|snapshot|record|history [n]|diagnose [n]|report [n]]
  lid off|on
  power press
  power off --confirm
  audit-tail [n]
EOF
        exit 2
        ;;
esac
