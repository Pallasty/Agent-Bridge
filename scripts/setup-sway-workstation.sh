#!/usr/bin/env bash
set -euo pipefail

if [ "${SUDO_USER:-}" ]; then
    target_user="$SUDO_USER"
else
    target_user="$(id -un)"
fi

target_home="$(getent passwd "$target_user" | cut -d: -f6)"
if [ -z "$target_home" ] || [ ! -d "$target_home" ]; then
    echo "Cannot determine home directory for $target_user" >&2
    exit 1
fi

as_user() {
    if [ "$(id -un)" = "$target_user" ]; then
        "$@"
    else
        sudo -u "$target_user" "$@"
    fi
}

need_sudo() {
    if [ "$(id -u)" -ne 0 ]; then
        sudo "$@"
    else
        "$@"
    fi
}

if command -v apt-get >/dev/null 2>&1; then
    need_sudo apt-get update
    need_sudo apt-get install -y \
        sway swaybg swayidle swaylock swaybar foot jq network-manager \
        fcitx5 fcitx5-chinese-addons upower pipewire wireplumber \
        xdg-desktop-portal xdg-desktop-portal-wlr xdg-desktop-portal-gtk
fi

as_user mkdir -p "$target_home/.config/sway" "$target_home/.local/bin"

if [ -f "$target_home/.config/sway/config" ] && \
   ! grep -q "agent-bridge-sway-workstation" "$target_home/.config/sway/config"; then
    backup="$target_home/.config/sway/config.backup.$(date +%Y%m%d%H%M%S)"
    as_user cp "$target_home/.config/sway/config" "$backup"
    echo "Backed up existing sway config to $backup"
fi

cat > "$target_home/.config/sway/config" <<'SWAY_CONFIG'
# agent-bridge-sway-workstation
# Keep distro defaults, then add local session startup glue.
include /etc/sway/config

# Touchpad: one-finger tap is left click, two-finger tap is right click.
input type:touchpad {
    tap enabled
    tap_button_map lrm
}

# Fcitx5 IME for Chinese/Pinyin under Sway/Wayland.
exec_always systemctl --user set-environment GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus
exec_always dbus-update-activation-environment --systemd GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus
exec_always env GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus fcitx5 -d --replace

# Compact status dashboard for WARP, Wi-Fi, IME, battery, CPU, RAM, clock.
bar bar-0 {
    font pango:monospace 8
    status_command ~/.local/bin/sway-status
}
SWAY_CONFIG

cat > "$target_home/.local/bin/sway-status" <<'SWAY_STATUS'
#!/usr/bin/env bash
set -u

prev_total=0
prev_idle=0
cpu_percent=0
warp_text="WARP ..."
wifi_text="WiFi ..."
ime_text="IME ..."
battery_text="BAT ..."
warp_tick=99
wifi_tick=99
ime_tick=99
battery_tick=99

json_string() {
    jq -Rn --arg s "$1" '$s'
}

block() {
    local name="$1"
    local text="$2"
    local color="${3:-#ffffffff}"
    printf '{"name":%s,"full_text":%s,"color":%s}' \
        "$(json_string "$name")" \
        "$(json_string "$text")" \
        "$(json_string "$color")"
}

bars_for_percent() {
    local pct="$1"
    if [ "$pct" -ge 88 ]; then
        printf "████"
    elif [ "$pct" -ge 63 ]; then
        printf "███░"
    elif [ "$pct" -ge 38 ]; then
        printf "██░░"
    elif [ "$pct" -ge 13 ]; then
        printf "█░░░"
    else
        printf "░░░░"
    fi
}

open_wifi_selector() {
    if command -v foot >/dev/null 2>&1 && command -v nmtui-connect >/dev/null 2>&1; then
        setsid foot -T "WiFi" -e nmtui-connect >/dev/null 2>&1 &
    fi
}

toggle_wifi() {
    if ! command -v nmcli >/dev/null 2>&1; then
        return
    fi

    if [ "$(nmcli -t -f WIFI general 2>/dev/null)" = "enabled" ]; then
        nmcli radio wifi off >/dev/null 2>&1 || true
    else
        nmcli radio wifi on >/dev/null 2>&1 || true
    fi
}

handle_clicks() {
    while IFS= read -r event; do
        case "$event" in
            *'"name":"wifi"'*)
                case "$event" in
                    *'"button":1*) open_wifi_selector ;;
                    *'"button":3*) toggle_wifi ;;
                esac
                ;;
        esac
    done
}

read_cpu() {
    local stat_label user nice system idle iowait irq softirq steal guest guest_nice
    read -r stat_label user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat
    local idle_all=$((idle + iowait))
    local non_idle=$((user + nice + system + irq + softirq + steal))
    local total=$((idle_all + non_idle))

    if [ "$prev_total" -eq 0 ]; then
        prev_total=$total
        prev_idle=$idle_all
        cpu_percent=0
        return
    fi

    local total_delta=$((total - prev_total))
    local idle_delta=$((idle_all - prev_idle))
    prev_total=$total
    prev_idle=$idle_all

    if [ "$total_delta" -le 0 ]; then
        cpu_percent=0
    else
        cpu_percent=$((100 * (total_delta - idle_delta) / total_delta))
    fi
}

read_ram() {
    local total available used pct bars color
    total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
    available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    used=$((total - available))
    pct=$((100 * used / total))
    bars=$(bars_for_percent "$pct")

    if [ "$pct" -ge 90 ]; then
        color="#f38ba8ff"
    elif [ "$pct" -ge 75 ]; then
        color="#f9e2afff"
    else
        color="#cba6f7ff"
    fi

    printf "RAM %s %d%%|%s" "$bars" "$pct" "$color"
}

read_warp() {
    local status
    if ! command -v warp-cli >/dev/null 2>&1; then
        printf "WARP|#6c7086ff"
        return
    fi

    status=$(warp-cli status 2>/dev/null || true)
    case "$status" in
        *"Status update: Connected"*) printf "WARP|#a6e3a1ff" ;;
        *"Status update: Disconnected"*) printf "WARP|#6c7086ff" ;;
        *"Unable to connect"*|*"Error"*|*"failed"*) printf "WARP|#f38ba8ff" ;;
        *) printf "WARP|#f9e2afff" ;;
    esac
}

read_wifi() {
    local radio active_line device type state ssid signal bars
    if ! command -v nmcli >/dev/null 2>&1; then
        printf "WIFI|#6c7086ff"
        return
    fi

    radio=$(nmcli -t -f WIFI general 2>/dev/null || true)
    if [ "$radio" != "enabled" ]; then
        printf "WIFI|#6c7086ff"
        return
    fi

    active_line=$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null | awk -F: '$2 == "wifi" && $3 == "connected" {print; exit}')
    if [ -z "$active_line" ]; then
        printf "WIFI|#f38ba8ff"
        return
    fi

    IFS=: read -r device type state ssid <<EOF
$active_line
EOF
    signal=$(nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi 2>/dev/null | awk -F: -v ssid="$ssid" '$1 == "yes" || $2 == ssid {print $3; exit}')
    if [ -n "$signal" ]; then
        bars=$(bars_for_percent "$signal")
        printf "WIFI %s %s|#89b4faff" "$bars" "$signal"
    else
        printf "WIFI|#89b4faff"
    fi
}

read_ime() {
    local name state
    if ! command -v fcitx5-remote >/dev/null 2>&1; then
        printf "A|#6c7086ff"
        return
    fi

    name=$(fcitx5-remote -n 2>/dev/null || true)
    state=$(fcitx5-remote 2>/dev/null || true)

    if [ -z "$name" ]; then
        printf "?|#f9e2afff"
        return
    fi

    case "$state" in
        1) printf "A|#6c7086ff" ;;
        2)
            case "$name" in
                *pinyin*|*Pinyin*) printf "PY|#fab387ff" ;;
                *keyboard*|*Keyboard*) printf "A|#6c7086ff" ;;
                *) printf "IM|#fab387ff" ;;
            esac
            ;;
        *) printf "IM|#f9e2afff" ;;
    esac
}

read_battery() {
    local battery info state percent pct bars color
    if ! command -v upower >/dev/null 2>&1; then
        printf "BAT ░░░░|#6c7086ff"
        return
    fi

    battery=$(upower -e 2>/dev/null | awk '/battery/ {print; exit}')
    if [ -z "$battery" ]; then
        printf "BAT ░░░░|#6c7086ff"
        return
    fi

    info=$(upower -i "$battery" 2>/dev/null || true)
    state=$(printf "%s\n" "$info" | awk -F': *' '/state:/ {print $2; exit}')
    percent=$(printf "%s\n" "$info" | awk -F': *' '/percentage:/ {print $2; exit}')
    pct=${percent%\%}
    if [ -z "$pct" ]; then
        printf "BAT ░░░░|#6c7086ff"
        return
    fi

    bars=$(bars_for_percent "$pct")

    case "$state:$pct" in
        charging:*|fully-charged:*) color="#94e2d5ff" ;;
        *:[0-9]|*:1[0-5]) color="#f38ba8ff" ;;
        *:1[6-9]|*:2[0-9]|*:3[0-5]) color="#f9e2afff" ;;
        *) color="#a6e3a1ff" ;;
    esac
    printf "BAT %s %s|%s" "$bars" "$percent" "$color"
}

handle_clicks &

printf '{"version":1,"click_events":true}\n'
printf '[\n'

first=1
while true; do
    read_cpu
    IFS='|' read -r ram_text ram_color <<EOF
$(read_ram)
EOF

    if [ "$warp_tick" -ge 5 ]; then
        IFS='|' read -r warp_text warp_color <<EOF
$(read_warp)
EOF
        warp_tick=0
    else
        warp_tick=$((warp_tick + 1))
    fi

    if [ "$wifi_tick" -ge 5 ]; then
        IFS='|' read -r wifi_text wifi_color <<EOF
$(read_wifi)
EOF
        wifi_tick=0
    else
        wifi_tick=$((wifi_tick + 1))
    fi

    if [ "$ime_tick" -ge 1 ]; then
        IFS='|' read -r ime_text ime_color <<EOF
$(read_ime)
EOF
        ime_tick=0
    else
        ime_tick=$((ime_tick + 1))
    fi

    if [ "$battery_tick" -ge 15 ]; then
        IFS='|' read -r battery_text battery_color <<EOF
$(read_battery)
EOF
        battery_tick=0
    else
        battery_tick=$((battery_tick + 1))
    fi

    if [ "$first" -eq 1 ]; then
        first=0
    else
        printf ','
    fi

    printf '[%s,%s,%s,%s,%s,%s,%s]\n' \
        "$(block warp "$warp_text" "${warp_color:-#ffffffff}")" \
        "$(block wifi "$wifi_text" "${wifi_color:-#ffffffff}")" \
        "$(block ime "$ime_text" "${ime_color:-#ffffffff}")" \
        "$(block battery "$battery_text" "${battery_color:-#ffffffff}")" \
        "$(block cpu "CPU ${cpu_percent}%" "#f9e2afff")" \
        "$(block ram "$ram_text" "${ram_color:-#cba6f7ff}")" \
        "$(block clock "$(date '+%Y-%m-%d %H:%M:%S')" "#ffffffff")"
    sleep 1
done
SWAY_STATUS

chown -R "$target_user:$target_user" "$target_home/.config/sway" "$target_home/.local/bin/sway-status"
chmod 755 "$target_home/.config/sway" "$target_home/.local/bin/sway-status"
chmod 644 "$target_home/.config/sway/config"

as_user bash -n "$target_home/.local/bin/sway-status"

if [ "${SWAYSOCK:-}" ] && command -v swaymsg >/dev/null 2>&1; then
    as_user swaymsg reload >/dev/null || true
    echo "Reloaded current Sway session."
else
    echo "Sway config installed. Log into Sway or run 'swaymsg reload' inside Sway."
fi

echo "Installed Sway workstation config for $target_user."
