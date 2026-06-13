#!/usr/bin/env bash
set -u

schema="agent_bridge.sway_desktop.doctor.v0"
home_dir="${HOME:-/home/pallasting}"
sway_config="${AB_SWAY_CONFIG:-$home_dir/.config/sway/config}"
setup_script="${AB_SWAY_SETUP_SCRIPT:-/Programs/Users/Pallasting/Documents/Sway/setup-sway-workstation.sh}"
source_setup_script="${AB_SWAY_SETUP_SOURCE:-/Data/CascadeProjects/agent-bridge/scripts/setup-sway-workstation.sh}"
tmp_checks="$(mktemp)"
tmp_heal_actions="$(mktemp)"

cleanup() {
    rm -f "$tmp_checks" "$tmp_heal_actions"
}
trap cleanup EXIT

json_string() {
    jq -Rn --arg s "$1" '$s'
}

add_check() {
    local id="$1"
    local status="$2"
    local detail="$3"
    local fix="${4:-}"
    jq -nc \
        --arg id "$id" \
        --arg status "$status" \
        --arg detail "$detail" \
        --arg fix "$fix" \
        '{id:$id,status:$status,detail:$detail,fix:$fix}' >>"$tmp_checks"
}

add_heal_action() {
    local id="$1"
    local status="$2"
    local detail="$3"
    jq -nc \
        --arg id "$id" \
        --arg status "$status" \
        --arg detail "$detail" \
        '{id:$id,status:$status,detail:$detail}' >>"$tmp_heal_actions"
}

check_command() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        add_check "command.$cmd" "ok" "$(command -v "$cmd")"
    else
        add_check "command.$cmd" "warn" "missing command: $cmd" "install desktop package set via setup-sway-workstation.sh"
    fi
}

check_helper() {
    local name="$1"
    local path="$home_dir/.local/bin/$name"
    if [ ! -f "$path" ]; then
        add_check "helper.$name" "fail" "$path missing" "run setup-sway-workstation.sh"
        return
    fi
    if [ ! -x "$path" ]; then
        add_check "helper.$name" "fail" "$path is not executable" "chmod 755 $path"
        return
    fi
    case "$(head -n 1 "$path" 2>/dev/null)" in
        *python*) python3 -m py_compile "$path" >/dev/null 2>&1 ;;
        *bash*) bash -n "$path" >/dev/null 2>&1 ;;
        *) sh -n "$path" >/dev/null 2>&1 ;;
    esac
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        add_check "helper.$name" "ok" "$path executable and syntax-ok"
    else
        add_check "helper.$name" "fail" "$path syntax check failed" "reinstall helper via setup-sway-workstation.sh"
    fi
}

check_config_contains() {
    local id="$1"
    local pattern="$2"
    if grep -Fq "$pattern" "$sway_config" 2>/dev/null; then
        add_check "sway_config.$id" "ok" "$pattern"
    else
        add_check "sway_config.$id" "fail" "missing: $pattern" "rerun setup-sway-workstation.sh and swaymsg reload"
    fi
}

check_config_any() {
    local id="$1"
    local fix="$2"
    shift 2
    local pattern
    for pattern in "$@"; do
        if grep -Fq "$pattern" "$sway_config" 2>/dev/null; then
            add_check "sway_config.$id" "ok" "$pattern"
            return
        fi
    done
    add_check "sway_config.$id" "fail" "missing any accepted pattern for $id" "$fix"
}

check_logind_rule() {
    local id="$1"
    local file="$2"
    local pattern="$3"
    if grep -Fq "$pattern" "$file" 2>/dev/null; then
        add_check "logind.$id" "ok" "$file contains $pattern"
    else
        add_check "logind.$id" "fail" "$file missing $pattern" "rerun setup-sway-workstation.sh as root/sudo"
    fi
}

check_user_unit() {
    local unit="$1"
    if systemctl --user is-enabled --quiet "$unit" 2>/dev/null; then
        add_check "systemd_user.$unit.enabled" "ok" "$unit enabled"
    else
        add_check "systemd_user.$unit.enabled" "warn" "$unit is not enabled" "run setup-sway-workstation.sh or systemctl --user enable --now $unit"
    fi

    if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
        add_check "systemd_user.$unit.active" "ok" "$unit active"
    else
        add_check "systemd_user.$unit.active" "warn" "$unit is not active" "run systemctl --user start $unit"
    fi
}

doctor() {
    : >"$tmp_checks"

    for cmd in jq swaymsg systemctl notify-send; do
        check_command "$cmd"
    done

    for helper in \
        ab-system-control \
        sway-status \
        sway-volume \
        sway-brightness \
        sway-display-cycle \
        sway-airplane-mode \
        sway-screenshot \
        sway-hotkey-action \
        sway-agent-menu \
        sway-wifi-menu \
        sway-idle-display \
        sway-lid-display \
        sway-power-button \
        sway-desktop-doctor \
        sway-desktop-watchdog
    do
        check_helper "$helper"
    done

    if [ -f "$sway_config" ]; then
        add_check "sway_config.present" "ok" "$sway_config"
        check_config_any "managed_hotkeys" "rerun setup-sway-workstation.sh and swaymsg reload" \
            "agent-bridge-sway-workstation" \
            "BEGIN local-hotkeys managed by setup-sway-workstation"
        check_config_any "statusbar" "rerun setup-sway-workstation.sh and swaymsg reload" \
            "status_command ~/.local/bin/sway-status" \
            "status_command $home_dir/.local/bin/sway-status"
        check_config_contains "idle_display" "sway-idle-display"
        check_config_any "lid_on" "rerun setup-sway-workstation.sh and swaymsg reload" \
            "bindswitch --reload --locked lid:on exec ~/.local/bin/sway-lid-display off" \
            "bindswitch --reload --locked lid:on exec $home_dir/.local/bin/sway-lid-display off"
        check_config_any "lid_off" "rerun setup-sway-workstation.sh and swaymsg reload" \
            "bindswitch --reload --locked lid:off exec ~/.local/bin/sway-lid-display on" \
            "bindswitch --reload --locked lid:off exec $home_dir/.local/bin/sway-lid-display on"
        check_config_any "power_key" "rerun setup-sway-workstation.sh and swaymsg reload" \
            "bindsym --release --locked XF86PowerOff exec ~/.local/bin/sway-power-button" \
            "bindsym --release --locked XF86PowerOff exec $home_dir/.local/bin/sway-power-button"
        check_config_contains "volume_mute" "XF86AudioMute"
        check_config_contains "brightness_down" "XF86MonBrightnessDown"
        check_config_contains "display_cycle" "XF86Display"
        check_config_contains "screenshot" "XF86SelectiveScreenshot"
    else
        add_check "sway_config.present" "fail" "$sway_config missing" "run setup-sway-workstation.sh"
    fi

    check_logind_rule "power_ignore" "/etc/systemd/logind.conf.d/90-local-power-button.conf" "HandlePowerKey=ignore"
    check_logind_rule "lid_ignore" "/etc/systemd/logind.conf.d/90-local-lid-display-only.conf" "HandleLidSwitch=ignore"
    check_user_unit "sway-desktop-watchdog.timer"

    if [ -r "$setup_script" ]; then
        add_check "setup_script.present" "ok" "$setup_script"
    else
        add_check "setup_script.present" "fail" "$setup_script missing or unreadable" "restore the setup script"
    fi

    if [ -r "$setup_script" ] && [ -r "$source_setup_script" ]; then
        if cmp -s "$source_setup_script" "$setup_script"; then
            add_check "setup_script.sync" "ok" "$setup_script matches $source_setup_script"
        else
            add_check "setup_script.sync" "warn" "$setup_script differs from $source_setup_script" "copy the repo script to the documents Sway setup path"
        fi
    fi

    if [ -x "$home_dir/.local/bin/ab-system-control" ]; then
        local status_json=""
        status_json="$("$home_dir/.local/bin/ab-system-control" status summary 2>/dev/null || true)"
        if printf '%s' "$status_json" | jq -e '.schema == "agent_bridge.system_control.status.v0"' >/dev/null 2>&1; then
            add_check "runtime.status_summary" "ok" "$(printf '%s' "$status_json" | jq -c '{display,battery,services}')"
        else
            add_check "runtime.status_summary" "warn" "ab-system-control status summary did not return expected JSON" "run ab-system-control status summary manually"
        fi

        local timeline_json=""
        timeline_json="$("$home_dir/.local/bin/ab-system-control" events tail 5 2>/dev/null || true)"
        if printf '%s' "$timeline_json" | jq -e '.schema == "agent_bridge.system_control.timeline.v0" and (.events | type == "array")' >/dev/null 2>&1; then
            add_check "runtime.event_timeline" "ok" "events tail returned timeline JSON"
        else
            add_check "runtime.event_timeline" "warn" "events tail did not return expected timeline JSON" "run ab-system-control events tail 20 manually"
        fi

        local diagnosis_json=""
        diagnosis_json="$("$home_dir/.local/bin/ab-system-control" events diagnose test 20 2>/dev/null || true)"
        if printf '%s' "$diagnosis_json" | jq -e '.schema == "agent_bridge.system_control.diagnosis.v0" and (.status | type == "string")' >/dev/null 2>&1; then
            add_check "runtime.event_diagnosis" "ok" "events diagnose returned diagnosis JSON"
        else
            add_check "runtime.event_diagnosis" "warn" "events diagnose did not return expected diagnosis JSON" "run ab-system-control events diagnose test 20 manually"
        fi
    fi

    if [ -x "$home_dir/.local/bin/sway-status" ]; then
        local bar_sample=""
        bar_sample="$(timeout 4 sh -c '(sleep 1) | "$HOME/.local/bin/sway-status" | sed -n "1,4p"' 2>/dev/null || true)"
        if printf '%s' "$bar_sample" | grep -Fq '"name":"agent"' &&
           printf '%s' "$bar_sample" | grep -Fq '"name":"wifi"' &&
           printf '%s' "$bar_sample" | grep -Fq '"name":"battery"'; then
            add_check "runtime.statusbar_smoke" "ok" "agent, wifi, and battery blocks rendered"
        else
            add_check "runtime.statusbar_smoke" "warn" "statusbar smoke sample missing expected blocks" "run sway-status manually and inspect output"
        fi
    fi

    jq -s \
        --arg schema "$schema" \
        --arg checked_at "$(date -Is)" \
        'def count_status($s): map(select(.status == $s)) | length;
         . as $checks |
         {
           schema: $schema,
           checked_at: $checked_at,
           status: (if ($checks | count_status("fail")) > 0 then "fail" elif ($checks | count_status("warn")) > 0 then "warn" else "ok" end),
           summary: {
             ok: ($checks | count_status("ok")),
             warn: ($checks | count_status("warn")),
             fail: ($checks | count_status("fail"))
           },
           checks: $checks
         }' "$tmp_checks"
}

repair() {
    if [ ! -r "$setup_script" ]; then
        jq -n \
            --arg schema "agent_bridge.sway_desktop.repair.v0" \
            --arg status "error" \
            --arg detail "$setup_script missing or unreadable" \
            '{schema:$schema,status:$status,detail:$detail}'
        return 2
    fi

    if [ "$(id -u)" -ne 0 ] && [ "${AB_SWAY_DESKTOP_REPAIR_INTERACTIVE:-0}" != "1" ]; then
        if ! sudo -n true >/dev/null 2>&1; then
            jq -n \
                --arg schema "agent_bridge.sway_desktop.repair.v0" \
                --arg status "needs_sudo" \
                --arg detail "repair would run setup-sway-workstation.sh, which needs sudo for logind/udev rules" \
                '{schema:$schema,status:$status,detail:$detail,fix:"run from an interactive terminal or set AB_SWAY_DESKTOP_REPAIR_INTERACTIVE=1"}'
            return 3
        fi
    fi

    bash "$setup_script"
}

heal() {
    : >"$tmp_heal_actions"
    local before after
    before="$(doctor)"

    for helper in \
        ab-system-control \
        sway-status \
        sway-volume \
        sway-brightness \
        sway-display-cycle \
        sway-airplane-mode \
        sway-screenshot \
        sway-hotkey-action \
        sway-agent-menu \
        sway-wifi-menu \
        sway-idle-display \
        sway-lid-display \
        sway-power-button \
        sway-desktop-doctor \
        sway-desktop-watchdog
    do
        local path="$home_dir/.local/bin/$helper"
        if [ -f "$path" ]; then
            if [ -x "$path" ]; then
                add_heal_action "helper.$helper" "noop" "already executable"
            elif chmod 755 "$path" 2>/dev/null; then
                add_heal_action "helper.$helper" "ok" "chmod 755 $path"
            else
                add_heal_action "helper.$helper" "error" "could not chmod $path"
            fi
        else
            add_heal_action "helper.$helper" "skipped" "$path missing; use desktop repair"
        fi
    done

    if [ -r "$source_setup_script" ] && [ -e "$setup_script" ]; then
        if cmp -s "$source_setup_script" "$setup_script"; then
            add_heal_action "setup_script.sync" "noop" "setup script already synchronized"
        elif cp -f "$source_setup_script" "$setup_script" 2>/dev/null; then
            add_heal_action "setup_script.sync" "ok" "copied $source_setup_script to $setup_script"
        else
            add_heal_action "setup_script.sync" "warn" "could not copy $source_setup_script to $setup_script"
        fi
    elif [ -r "$source_setup_script" ]; then
        if cp -f "$source_setup_script" "$setup_script" 2>/dev/null; then
            add_heal_action "setup_script.sync" "ok" "created $setup_script from $source_setup_script"
        else
            add_heal_action "setup_script.sync" "warn" "could not create $setup_script"
        fi
    else
        add_heal_action "setup_script.sync" "skipped" "$source_setup_script missing"
    fi

    if pgrep -x mako >/dev/null 2>&1; then
        add_heal_action "service.mako" "noop" "mako already running"
    elif systemctl --user start mako.service >/dev/null 2>&1; then
        add_heal_action "service.mako" "ok" "started mako.service"
    elif command -v mako >/dev/null 2>&1; then
        setsid mako >/dev/null 2>&1 &
        add_heal_action "service.mako" "ok" "started mako directly"
    else
        add_heal_action "service.mako" "error" "mako not available"
    fi

    if pgrep -x swayidle >/dev/null 2>&1; then
        add_heal_action "service.swayidle" "noop" "swayidle already running"
    elif [ -x "$home_dir/.local/bin/sway-idle-display" ]; then
        setsid "$home_dir/.local/bin/sway-idle-display" >/dev/null 2>&1 &
        add_heal_action "service.swayidle" "ok" "started sway-idle-display"
    else
        add_heal_action "service.swayidle" "error" "sway-idle-display missing or not executable"
    fi

    if systemctl --user is-active --quiet agent-bridge-daemon.service 2>/dev/null; then
        add_heal_action "service.agent_bridge_daemon" "noop" "agent-bridge daemon already active"
    elif systemctl --user restart agent-bridge-daemon.service >/dev/null 2>&1; then
        add_heal_action "service.agent_bridge_daemon" "ok" "restarted agent-bridge-daemon.service"
    else
        add_heal_action "service.agent_bridge_daemon" "warn" "could not restart user daemon"
    fi

    if systemctl --user enable --now sway-desktop-watchdog.timer >/dev/null 2>&1; then
        add_heal_action "service.sway_desktop_watchdog" "ok" "enabled and started sway-desktop-watchdog.timer"
    else
        add_heal_action "service.sway_desktop_watchdog" "warn" "could not enable/start sway-desktop-watchdog.timer"
    fi

    if systemctl is-active --quiet NetworkManager.service 2>/dev/null; then
        add_heal_action "service.networkmanager" "noop" "NetworkManager already active"
    elif sudo -n true >/dev/null 2>&1 && sudo -n systemctl start NetworkManager.service >/dev/null 2>&1; then
        add_heal_action "service.networkmanager" "ok" "started NetworkManager.service"
    else
        add_heal_action "service.networkmanager" "skipped" "NetworkManager inactive and non-interactive sudo unavailable"
    fi

    if [ "${SWAYSOCK:-}" ] && command -v swaymsg >/dev/null 2>&1; then
        if swaymsg reload >/dev/null 2>&1; then
            add_heal_action "sway.reload" "ok" "reloaded Sway config"
        else
            add_heal_action "sway.reload" "warn" "swaymsg reload failed"
        fi
    else
        add_heal_action "sway.reload" "skipped" "no active SWAYSOCK"
    fi

    after="$(doctor)"
    jq -n \
        --arg schema "agent_bridge.sway_desktop.heal.v0" \
        --arg healed_at "$(date -Is)" \
        --argjson before "$before" \
        --argjson after "$after" \
        --slurpfile actions "$tmp_heal_actions" \
        '{
            schema: $schema,
            healed_at: $healed_at,
            before: {status: $before.status, summary: $before.summary},
            after: {status: $after.status, summary: $after.summary},
            status: (if $after.status == "ok" then "ok" elif $after.status == "warn" then "partial" else "needs_repair" end),
            actions: $actions
        }'
}

case "${1:-doctor}" in
    doctor|check) doctor ;;
    heal) heal ;;
    repair) repair ;;
    *)
        echo "usage: sway-desktop-doctor [doctor|heal|repair]" >&2
        exit 2
        ;;
esac
