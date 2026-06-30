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
        xdg-desktop-portal xdg-desktop-portal-wlr xdg-desktop-portal-gtk \
        brightnessctl pulseaudio-utils playerctl grim slurp wl-clipboard \
        mako libnotify-bin rfkill wdisplays wlr-randr
    need_sudo apt-get install -y \
        mate-calc thunar rhythmbox xfce4-settings wmenu network-manager-gnome || true
fi

as_user mkdir -p "$target_home/.config/sway" "$target_home/.config/mako" "$target_home/.config/systemd/user" "$target_home/.config/Thunar" "$target_home/.local/bin"

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

# Run X11 apps (e.g. WeChat) under Sway via XWayland.
xwayland enable

# Borderless windows: remove the title bar and the blue focus border.
default_border none
default_floating_border none

# Touchpad: one-finger tap is left click, two-finger tap is right click.
input type:touchpad {
    tap enabled
    tap_button_map lrm
}

# Fcitx5 IME for Chinese/Pinyin under Sway/Wayland.
exec_always systemctl --user set-environment GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus
exec_always dbus-update-activation-environment --systemd GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus
exec_always env GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx INPUT_METHOD=fcitx SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus fcitx5 -d --replace
exec_always systemctl --user start mako.service
exec_always sh -c 'pkill -x swayidle 2>/dev/null || true; exec ~/.local/bin/sway-idle-display'
bindswitch --reload --locked lid:on exec ~/.local/bin/sway-lid-display off
bindswitch --reload --locked lid:off exec ~/.local/bin/sway-lid-display on
bindsym --release --locked XF86PowerOff exec ~/.local/bin/sway-power-button

# Compact status dashboard for WARP, Wi-Fi, IME, battery, CPU, RAM, clock.
bar bar-0 {
    font pango:monospace 8
    status_command ~/.local/bin/sway-status
}

# BEGIN local-hotkeys managed by setup-sway-workstation
bindsym --locked XF86AudioMute exec ~/.local/bin/sway-volume mute
bindsym --locked XF86AudioLowerVolume exec ~/.local/bin/sway-volume down
bindsym --locked XF86AudioRaiseVolume exec ~/.local/bin/sway-volume up
bindsym --locked XF86AudioMicMute exec ~/.local/bin/sway-volume micmute
bindsym --locked XF86MonBrightnessDown exec ~/.local/bin/sway-brightness down
bindsym --locked XF86MonBrightnessUp exec ~/.local/bin/sway-brightness up
bindsym --locked XF86AudioPlay exec playerctl play-pause
bindsym --locked XF86AudioNext exec playerctl next
bindsym --locked XF86AudioPrev exec playerctl previous
bindsym --locked XF86Display exec ~/.local/bin/sway-display-cycle
bindsym --locked XF86DisplayToggle exec ~/.local/bin/sway-display-cycle
bindsym --locked XF86RFKill exec ~/.local/bin/sway-airplane-mode
bindsym --locked XF86WLAN exec ~/.local/bin/sway-airplane-mode
bindsym --locked XF86VoiceCommand exec playerctl play-pause
bindsym --locked XF86Assistant exec playerctl play-pause
bindsym --locked XF86Dictate exec playerctl play-pause
bindsym --locked F9 exec playerctl play-pause
bindsym --locked XF86Phone workspace prev_on_output
bindsym --locked XF86PickupPhone workspace prev_on_output
bindsym --locked XF86VideoPhone workspace prev_on_output
bindsym --locked XF86HangupPhone workspace next_on_output
bindsym --locked $mod+p exec wdisplays
bindsym XF86Calculator exec mate-calc
bindsym XF86Favorites exec ~/.local/bin/sway-hotkey-action favorites
bindsym XF86Explorer exec thunar
bindsym XF86HomePage exec exo-open --launch WebBrowser
bindsym XF86WWW exec exo-open --launch WebBrowser
bindsym XF86Music exec rhythmbox
bindsym XF86Tools exec xfce4-settings-manager
bindsym XF86Search exec wmenu-run
bindsym XF86ScreenSaver exec swaylock -f -c 000000
bindsym --release --locked Print exec ~/.local/bin/sway-screenshot region
bindsym --release --locked Shift+Print exec ~/.local/bin/sway-screenshot full
bindsym --release --locked Sys_Req exec ~/.local/bin/sway-screenshot region
bindsym --release --locked XF86SelectiveScreenshot exec ~/.local/bin/sway-screenshot region
bindsym --release --locked $mod+Shift+s exec ~/.local/bin/sway-screenshot region
bindsym --release --locked F12 exec ~/.local/bin/sway-screenshot region
bindsym --release --locked F13 exec ~/.local/bin/sway-screenshot region
bindsym --release --locked F14 exec ~/.local/bin/sway-screenshot region
# END local-hotkeys managed by setup-sway-workstation
SWAY_CONFIG

cat > "$target_home/.local/bin/sway-status" <<'SWAY_STATUS'
#!/usr/bin/env bash
set -u

# Status-bar glyphs. U+FE0E (text variation selector) forces a monochrome,
# text-presentation glyph so the per-block color attribute still applies
# (otherwise pango may fall back to a colored emoji glyph and ignore color).
ic_agent=$'⬢'            # ⬢ agent-bridge node
ic_warp=$'☁︎'       # ☁ WARP (cloud tunnel)
ic_wifi=$'\U0001f4f6\ufe0e' # Wi-Fi signal
ic_lan=$'↔'             # wired LAN
ic_ime_py=$'中'          # 中 pinyin / Chinese input
ic_ime_en='A'                # A latin/ascii input
ic_ime_im=$'文'          # 文 other input method
ic_bat=$'\U0001f50b︎'   # 🔋 battery (on battery)
ic_chg=$'⚡︎'       # ⚡ charging
ic_cpu=$'⚙︎'       # ⚙ CPU
ic_ram=$'▦'             # ▦ RAM
level_marks=(▁ ▃ ▅ ▇)

prev_total=0
prev_idle=0
cpu_percent=0
warp_text="$ic_warp"
wifi_text="$ic_wifi"
lan_text="$ic_lan"
ime_text="$ic_ime_en"
battery_text="$ic_bat"
agent_text="$ic_agent"
warp_tick=99
wifi_tick=99
lan_tick=99
ime_tick=99
battery_tick=99
click_log="${XDG_RUNTIME_DIR:-/tmp}/sway-status-click.log"

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

level_of() {
    local p="$1"
    if   [ "$p" -le 25 ]; then printf 1
    elif [ "$p" -le 50 ]; then printf 2
    elif [ "$p" -le 75 ]; then printf 3
    else printf 4
    fi
}

level_mark() {
    local level
    level="$(level_of "$1")"
    printf '%s' "${level_marks[$((level - 1))]}"
}

level_color() {
    local p="$1" inverted="${2:-normal}"
    if [ "$inverted" = inverted ]; then
        if   [ "$p" -le 25 ]; then printf '#a6e3a1ff'
        elif [ "$p" -le 50 ]; then printf '#89b4faff'
        elif [ "$p" -le 75 ]; then printf '#f9e2afff'
        else printf '#f38ba8ff'
        fi
    else
        if   [ "$p" -le 25 ]; then printf '#f38ba8ff'
        elif [ "$p" -le 50 ]; then printf '#f9e2afff'
        elif [ "$p" -le 75 ]; then printf '#89b4faff'
        else printf '#a6e3a1ff'
        fi
    fi
}

log_event() {
    local name="$1"
    local detail="${2:-}"
    if command -v "$HOME/.local/bin/ab-system-control" >/dev/null 2>&1; then
        "$HOME/.local/bin/ab-system-control" event log statusbar "$name" "$detail" >/dev/null 2>&1 || true
    fi
}

open_wifi_selector() {
    if command -v "$HOME/.local/bin/ab-system-control" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/ab-system-control" wifi networks >>"$click_log" 2>&1 &
    fi
}

open_wifi_actions() {
    if command -v "$HOME/.local/bin/ab-system-control" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/ab-system-control" wifi actions >>"$click_log" 2>&1 &
    fi
}

open_wifi_terminal() {
    if command -v "$HOME/.local/bin/ab-system-control" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/ab-system-control" wifi nmtui >>"$click_log" 2>&1 &
    fi
}

open_battery_actions() {
    if command -v "$HOME/.local/bin/sway-battery-menu" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/sway-battery-menu" actions >>"$click_log" 2>&1 &
    fi
}

open_agent_menu() {
    if command -v "$HOME/.local/bin/sway-agent-menu" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/sway-agent-menu" actions >>"$click_log" 2>&1 &
    fi
}

open_agent_status() {
    if command -v "$HOME/.local/bin/sway-agent-menu" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/sway-agent-menu" status >>"$click_log" 2>&1 &
    fi
}

open_agent_audit() {
    if command -v "$HOME/.local/bin/sway-agent-menu" >/dev/null 2>&1; then
        setsid "$HOME/.local/bin/sway-agent-menu" audit >>"$click_log" 2>&1 &
    fi
}

# --- On-demand block details (computed only when a block is clicked) ---
notify_detail() {
    notify-send -a sway "$1" "$2" >/dev/null 2>&1 || true
}

cpu_sample() {
    local _l u n s i io ir so st rest idle total
    read -r _l u n s i io ir so st rest < /proc/stat
    idle=$((i + io))
    total=$((u + n + s + i + io + ir + so + st))
    printf '%s %s' "$idle" "$total"
}

detail_cpu() {
    local s1 s2 i1 t1 i2 t2 dt di pct cores load
    cores=$(nproc 2>/dev/null || echo '?')
    load=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)
    s1=$(cpu_sample); i1=${s1% *}; t1=${s1#* }
    sleep 0.3
    s2=$(cpu_sample); i2=${s2% *}; t2=${s2#* }
    dt=$((t2 - t1)); di=$((i2 - i1))
    if [ "$dt" -gt 0 ]; then pct=$((100 * (dt - di) / dt)); else pct=0; fi
    notify_detail "CPU ${pct}%" "load (1/5/15m): ${load}
cores: ${cores}"
}

detail_ram() {
    local total avail used pct swt swf gb_used gb_total body
    total=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
    avail=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
    used=$((total - avail)); pct=$((100 * used / total))
    gb_used=$(awk -v k="$used" 'BEGIN{printf "%.1f", k/1048576}')
    gb_total=$(awk -v k="$total" 'BEGIN{printf "%.1f", k/1048576}')
    body="used: ${gb_used} / ${gb_total} GiB (${pct}%)"
    swt=$(awk '/^SwapTotal:/{print $2}' /proc/meminfo)
    swf=$(awk '/^SwapFree:/{print $2}' /proc/meminfo)
    if [ "${swt:-0}" -gt 0 ]; then
        local swu swgb swtgb
        swu=$((swt - swf))
        swgb=$(awk -v k="$swu" 'BEGIN{printf "%.1f", k/1048576}')
        swtgb=$(awk -v k="$swt" 'BEGIN{printf "%.1f", k/1048576}')
        body="${body}
swap: ${swgb} / ${swtgb} GiB"
    fi
    notify_detail "RAM ${pct}%" "$body"
}

detail_battery() {
    local bat info pct state tte ttf body threshold threshold_value conservation conservation_value conservation_label
    if ! command -v upower >/dev/null 2>&1; then
        notify_detail "Battery" "upower not available"; return
    fi
    bat=$(upower -e 2>/dev/null | awk '/battery/{print; exit}')
    if [ -z "$bat" ]; then notify_detail "Battery" "no battery detected"; return; fi
    info=$(upower -i "$bat" 2>/dev/null)
    pct=$(printf '%s\n' "$info" | awk -F': *' '/percentage:/{print $2; exit}')
    state=$(printf '%s\n' "$info" | awk -F': *' '/state:/{print $2; exit}')
    tte=$(printf '%s\n' "$info" | awk -F': *' '/time to empty:/{print $2; exit}')
    ttf=$(printf '%s\n' "$info" | awk -F': *' '/time to full:/{print $2; exit}')
    body="state: ${state:-unknown}"
    [ -n "$tte" ] && body="${body}
time to empty: ${tte}"
    [ -n "$ttf" ] && body="${body}
time to full: ${ttf}"
    for threshold in /sys/class/power_supply/BAT*/charge_control_end_threshold /sys/class/power_supply/BAT*/charge_stop_threshold; do
        [ -e "$threshold" ] || continue
        threshold_value="$(cat "$threshold" 2>/dev/null || true)"
        [ -n "$threshold_value" ] && body="${body}
charge limit: ${threshold_value}%"
        break
    done
    conservation="$(find /sys/devices -path '*/VPC2004:00/conservation_mode' -type f 2>/dev/null | head -1)"
    if [ -n "$conservation" ]; then
        conservation_value="$(cat "$conservation" 2>/dev/null || true)"
        case "$conservation_value" in
            1) conservation_label="on" ;;
            0) conservation_label="off" ;;
            *) conservation_label="${conservation_value:-unknown}" ;;
        esac
        body="${body}
maintenance mode: ${conservation_label}"
    fi
    notify_detail "Battery ${pct:-?}" "$body"
}

detail_warp() {
    local st
    if ! command -v warp-cli >/dev/null 2>&1; then
        notify_detail "WARP" "warp-cli not installed"; return
    fi
    st=$(warp-cli status 2>/dev/null | sed 's/^[[:space:]]*//' | grep -v '^$' | head -4)
    notify_detail "WARP" "${st:-unknown}"
}

detail_ime() {
    local name state label
    if ! command -v fcitx5-remote >/dev/null 2>&1; then
        notify_detail "Input method" "fcitx5 not available"; return
    fi
    name=$(fcitx5-remote -n 2>/dev/null)
    state=$(fcitx5-remote 2>/dev/null)
    case "$state" in
        1) label="inactive (latin)" ;;
        2) label="active" ;;
        *) label="state ${state:-?}" ;;
    esac
    notify_detail "Input method" "current: ${name:-unknown}
status: ${label}"
}

handle_clicks() {
    while IFS= read -r event; do
        printf '%s %s\n' "$(date '+%F %T')" "$event" >>"$click_log" 2>/dev/null || true
        case "$event" in
            *"\"name\": \"agent\""*|*"\"name\":\"agent\""*)
                case "$event" in
                    *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=agent button=1 action=menu"; open_agent_menu ;;
                    *"\"button\": 2"*|*"\"button\":2"*) log_event click "block=agent button=2 action=status"; open_agent_status ;;
                    *"\"button\": 3"*|*"\"button\":3"*) log_event click "block=agent button=3 action=audit"; open_agent_audit ;;
                esac
                ;;
            *"\"name\": \"wifi\""*|*"\"name\":\"wifi\""*)
                case "$event" in
                    *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=wifi button=1 action=networks"; open_wifi_selector ;;
                    *"\"button\": 2"*|*"\"button\":2"*) log_event click "block=wifi button=2 action=nmtui"; open_wifi_terminal ;;
                    *"\"button\": 3"*|*"\"button\":3"*) log_event click "block=wifi button=3 action=actions"; open_wifi_actions ;;
                esac
                ;;
            *"\"name\": \"cpu\""*|*"\"name\":\"cpu\""*)
                case "$event" in *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=cpu button=1 action=detail"; detail_cpu & ;; esac
                ;;
            *"\"name\": \"ram\""*|*"\"name\":\"ram\""*)
                case "$event" in *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=ram button=1 action=detail"; detail_ram & ;; esac
                ;;
            *"\"name\": \"battery\""*|*"\"name\":\"battery\""*)
                case "$event" in
                    *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=battery button=1 action=detail"; detail_battery & ;;
                    *"\"button\": 3"*|*"\"button\":3"*) log_event click "block=battery button=3 action=actions"; open_battery_actions ;;
                esac
                ;;
            *"\"name\": \"warp\""*|*"\"name\":\"warp\""*)
                case "$event" in *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=warp button=1 action=detail"; detail_warp & ;; esac
                ;;
            *"\"name\": \"ime\""*|*"\"name\":\"ime\""*)
                case "$event" in *"\"button\": 1"*|*"\"button\":1"*) log_event click "block=ime button=1 action=detail"; detail_ime & ;; esac
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
    local total available used pct
    total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
    available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    used=$((total - available))
    pct=$((100 * used / total))

    printf '%s%s|%s' "$ic_ram" "$(level_mark "$pct")" "$(level_color "$pct" inverted)"
}

read_warp() {
    local status
    if ! command -v warp-cli >/dev/null 2>&1; then
        printf '%s|#6c7086ff' "$ic_warp"
        return
    fi

    status=$(warp-cli status 2>/dev/null || true)
    case "$status" in
        *"Status update: Connected"*)
            printf '%s|#a6e3a1ff' "$ic_warp"
            ;;
        *"Status update: Disconnected"*)
            printf '%s|#f38ba8ff' "$ic_warp"
            ;;
        *"Unable to connect"*|*"Error"*|*"failed"*)
            printf '%s|#f38ba8ff' "$ic_warp"
            ;;
        *)
            printf '%s|#f9e2afff' "$ic_warp"
            ;;
    esac
}

read_wifi() {
    local radio active_line device type state ssid signal
    if ! command -v nmcli >/dev/null 2>&1; then
        printf '%s×|#6c7086ff' "$ic_wifi"
        return
    fi

    radio=$(nmcli -t -f WIFI general 2>/dev/null || true)
    if [ "$radio" != "enabled" ]; then
        printf '%s×|#6c7086ff' "$ic_wifi"
        return
    fi

    active_line=$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null | awk -F: '$2 == "wifi" && $3 == "connected" {print; exit}')
    if [ -z "$active_line" ]; then
        printf '%s×|#6c7086ff' "$ic_wifi"
        return
    fi

    IFS=: read -r device type state ssid <<EOF
$active_line
EOF
    signal=$(nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi 2>/dev/null | awk -F: -v ssid="$ssid" '$1 == "yes" || $2 == ssid {print $3; exit}')
    case "$signal" in ''|*[!0-9]*) signal=50 ;; esac
    printf '%s%s|%s' "$ic_wifi" "$(level_mark "$signal")" "$(level_color "$signal")"
}

read_lan() {
    local line device type state connection speed
    if command -v nmcli >/dev/null 2>&1; then
        line=$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null | awk -F: '$2 == "ethernet" && $3 == "connected" {print; exit}')
        if [ -n "$line" ]; then
            IFS=: read -r device type state connection <<EOF
$line
EOF
            speed=$(cat "/sys/class/net/$device/speed" 2>/dev/null || true)
            case "$speed" in
                ''|*[!0-9]*) printf '%s?|#f9e2afff' "$ic_lan" ;;
                [0-9]|[0-9][0-9]|100) printf '%s100|#f9e2afff' "$ic_lan" ;;
                *) printf '%s1G|#a6e3a1ff' "$ic_lan" ;;
            esac
            return
        fi
    fi
    printf '%s×|#6c7086ff' "$ic_lan"
}

read_ime() {
    local name state
    if ! command -v fcitx5-remote >/dev/null 2>&1; then
        printf '%s|#6c7086ff' "$ic_ime_en"
        return
    fi

    name=$(fcitx5-remote -n 2>/dev/null || true)
    state=$(fcitx5-remote 2>/dev/null || true)

    if [ -z "$name" ]; then
        printf "?|#f9e2afff"
        return
    fi

    case "$state" in
        1) printf '%s|#6c7086ff' "$ic_ime_en" ;;
        2)
            case "$name" in
                *pinyin*|*Pinyin*) printf '%s|#fab387ff' "$ic_ime_py" ;;
                *keyboard*|*Keyboard*) printf '%s|#6c7086ff' "$ic_ime_en" ;;
                *) printf '%s|#fab387ff' "$ic_ime_im" ;;
            esac
            ;;
        *) printf '%s|#f9e2afff' "$ic_ime_im" ;;
    esac
}

read_battery() {
    local battery info state percent pct color label conservation conservation_value
    if ! command -v upower >/dev/null 2>&1; then
        printf '%s|#6c7086ff' "$ic_bat"
        return
    fi

    battery=$(upower -e 2>/dev/null | awk '/battery/ {print; exit}')
    if [ -z "$battery" ]; then
        printf '%s|#6c7086ff' "$ic_bat"
        return
    fi

    info=$(upower -i "$battery" 2>/dev/null || true)
    state=$(printf "%s\n" "$info" | awk -F': *' '/state:/ {print $2; exit}')
    percent=$(printf "%s\n" "$info" | awk -F': *' '/percentage:/ {print $2; exit}')
    pct=${percent%\%}
    if [ -z "$pct" ]; then
        printf '%s|#6c7086ff' "$ic_bat"
        return
    fi

    case "$state:$pct" in
        charging:*|fully-charged:*|not\ charging:*|pending-charge:*)
            label="$ic_chg"
            conservation="$(find /sys/devices -path '*/VPC2004:00/conservation_mode' -type f 2>/dev/null | head -1)"
            conservation_value=""
            [ -n "$conservation" ] && conservation_value="$(cat "$conservation" 2>/dev/null || true)"
            if [ "$conservation_value" = 1 ]; then
                color="#f9e2afff"
            else
                color="#94e2d5ff"
            fi
            ;;
        *:[0-9]|*:1[0-5]) color="#f38ba8ff" ;;
        *:1[6-9]|*:2[0-9]|*:3[0-5]) color="#f9e2afff" ;;
        *) color="#a6e3a1ff" ;;
    esac
    printf '%s|%s' "${label:-$ic_bat}" "$color"
}

run_status_loop() {
    printf '{"version":1,"click_events":true}\n'
    printf '[\n'

    first=1
    while true; do
        read_cpu
        cpu_color="$(level_color "$cpu_percent" inverted)"
        cpu_text="${ic_cpu}$(level_mark "$cpu_percent")"
        IFS='|' read -r ram_text ram_color <<<"$(read_ram)"

        if [ "$warp_tick" -ge 5 ]; then
            IFS='|' read -r warp_text warp_color <<<"$(read_warp)"
            warp_tick=0
        else
            warp_tick=$((warp_tick + 1))
        fi

        if [ "$wifi_tick" -ge 5 ]; then
            IFS='|' read -r wifi_text wifi_color <<<"$(read_wifi)"
            wifi_tick=0
        else
            wifi_tick=$((wifi_tick + 1))
        fi

        if [ "$lan_tick" -ge 5 ]; then
            IFS='|' read -r lan_text lan_color <<<"$(read_lan)"
            lan_tick=0
        else
            lan_tick=$((lan_tick + 1))
        fi

        if [ "$ime_tick" -ge 1 ]; then
            IFS='|' read -r ime_text ime_color <<<"$(read_ime)"
            ime_tick=0
        else
            ime_tick=$((ime_tick + 1))
        fi

        if [ "$battery_tick" -ge 15 ]; then
            IFS='|' read -r battery_text battery_color <<<"$(read_battery)"
            battery_tick=0
        else
            battery_tick=$((battery_tick + 1))
        fi

        if [ "$first" -eq 1 ]; then
            first=0
        else
            printf ','
        fi

        printf '[%s,%s,%s,%s,%s,%s,%s,%s,%s]\n' \
            "$(block agent "$agent_text" "#94e2d5ff")" \
            "$(block warp "$warp_text" "${warp_color:-#ffffffff}")" \
            "$(block wifi "$wifi_text" "${wifi_color:-#ffffffff}")" \
            "$(block lan "$lan_text" "${lan_color:-#ffffffff}")" \
            "$(block ime "$ime_text" "${ime_color:-#ffffffff}")" \
            "$(block battery "$battery_text" "${battery_color:-#ffffffff}")" \
            "$(block cpu "$cpu_text" "$cpu_color")" \
            "$(block ram "$ram_text" "${ram_color:-#cba6f7ff}")" \
            "$(block clock "$(date '+%Y-%m-%d %H:%M:%S')" "#ffffffff")"
        sleep 1
    done
}

run_status_loop &
status_pid=$!
handle_clicks
kill "$status_pid" 2>/dev/null || true
wait "$status_pid" 2>/dev/null || true

SWAY_STATUS

cat > "$target_home/.config/mako/config" <<'MAKO_CONFIG'
font=monospace 10
width=360
height=120
anchor=top-right
outer-margin=12
padding=10
border-size=1
border-radius=6
default-timeout=7000
ignore-timeout=0
max-visible=4
history=1
MAKO_CONFIG

cat > "$target_home/.local/bin/ab-system-control" <<'AB_SYSTEM_CONTROL'
#!/usr/bin/env bash
set -u

default_audit_dir="$HOME/.local/share/agent-bridge/system-control"
if [ -d /Data ] && [ -w /Data ]; then
    default_audit_dir="/Data/agent-bridge/system-control"
fi
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
    jq -Rn --arg s "$1" '$s'
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
    notify-send -a sway "$1" "$2" >/dev/null 2>&1 || true
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
        off) run_audited "display.off" "low" swaymsg "output * power off" >/dev/null ;;
        on) run_audited "display.on" "low" swaymsg "output * power on" >/dev/null ;;
        toggle-off) display_action off ;;
        *) echo "usage: ab-system-control display off|on" >&2; return 2 ;;
    esac
}

audio_action() {
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

wifi_action() {
    case "${1:-}" in
        networks|actions|reconnect|toggle|nmtui)
            run_audited "wifi.${1:-}" "medium" "$HOME/.local/bin/sway-wifi-menu" "${1:-}"
            ;;
        *) echo "usage: ab-system-control wifi networks|actions|reconnect|toggle|nmtui" >&2; return 2 ;;
    esac
}

desktop_action() {
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
            desktop_json="$("$HOME/.local/bin/sway-desktop-doctor" doctor 2>/dev/null | json_or_null)"
            events_json="$(events_action tail 40 2>/dev/null | json_or_null)"
            watchdog_diag="$(events_action diagnose watchdog 120 2>/dev/null | json_or_null)"
            power_diag="$(events_action diagnose power 120 2>/dev/null | json_or_null)"
            wifi_diag="$(events_action diagnose wifi 120 2>/dev/null | json_or_null)"
            screenshot_diag="$(events_action diagnose screenshot 120 2>/dev/null | json_or_null)"
            timer_text="$(systemctl --user --no-pager list-timers sway-desktop-watchdog.timer 2>&1 || true)"
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
AB_SYSTEM_CONTROL

cat > "$target_home/.local/bin/sway-volume" <<'SWAY_VOLUME'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log hotkey audio "${1:-}" >/dev/null 2>&1 || true
exec "$HOME/.local/bin/ab-system-control" audio "${1:-}"

SWAY_VOLUME

cat > "$target_home/.local/bin/sway-brightness" <<'SWAY_BRIGHTNESS'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log hotkey brightness "${1:-}" >/dev/null 2>&1 || true
exec "$HOME/.local/bin/ab-system-control" brightness "${1:-}"

SWAY_BRIGHTNESS

cat > "$target_home/.local/bin/sway-display-cycle" <<'SWAY_DISPLAY_CYCLE'
#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path


STATE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "sway-display-cycle.state"


def sway_json(kind):
    return json.loads(subprocess.check_output(["swaymsg", "-t", kind], text=True))


def notify(message):
    subprocess.run(["notify-send", "-a", "sway", "Display", message], check=False)


def event(name, detail=""):
    control = Path.home() / ".local" / "bin" / "ab-system-control"
    if control.exists():
        subprocess.run(
            [str(control), "event", "log", "hotkey", name, detail],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def run_sway(*args):
    subprocess.run(["swaymsg", *args], check=False)


def logical_width(output):
    mode = output.get("current_mode") or {}
    width = mode.get("width") or output.get("rect", {}).get("width") or 1920
    scale = output.get("scale") or 1
    return max(1, round(width / scale))


outputs = [o for o in sway_json("get_outputs") if not o.get("non_desktop")]
connected = [o for o in outputs if o.get("active") or o.get("modes")]
internal = next((o for o in connected if o["name"].startswith(("eDP", "LVDS", "DSI"))), None)
externals = [o for o in connected if o is not internal]
event("display_cycle", f"connected={len(connected)} externals={len(externals)}")

if not externals:
    notify("Only internal display connected")
    event("display_cycle.no_external", "only_internal")
    raise SystemExit(0)

try:
    state = int(STATE.read_text().strip())
except Exception:
    state = -1
state = (state + 1) % 3
STATE.write_text(str(state))

if state == 0 and internal:
    run_sway("output", internal["name"], "enable", "pos", "0", "0")
    for output in externals:
        run_sway("output", output["name"], "disable")
    notify("Internal display only")
    event("display_cycle.mode", "internal")
elif state == 1:
    x = 0
    for output in connected:
        run_sway("output", output["name"], "enable", "pos", str(x), "0")
        x += logical_width(output)
    notify("Extended displays")
    event("display_cycle.mode", "extended")
else:
    for output in connected:
        run_sway("output", output["name"], "enable", "pos", "0", "0")
    notify("Mirrored displays")
    event("display_cycle.mode", "mirror")
SWAY_DISPLAY_CYCLE

cat > "$target_home/.local/bin/sway-airplane-mode" <<'SWAY_AIRPLANE_MODE'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log hotkey airplane-mode press >/dev/null 2>&1 || true

if ! command -v rfkill >/dev/null 2>&1; then
    notify-send "Airplane mode" "rfkill is not installed" 2>/dev/null || true
    exit 1
fi

if rfkill -n -o SOFT | grep -q '^unblocked$'; then
    if rfkill block all; then
        notify-send "Airplane mode" "Wireless devices blocked" 2>/dev/null || true
    else
        notify-send "Airplane mode" "Could not block wireless devices" 2>/dev/null || true
        exit 1
    fi
else
    if rfkill unblock all; then
        notify-send "Airplane mode" "Wireless devices unblocked" 2>/dev/null || true
    else
        notify-send "Airplane mode" "Could not unblock wireless devices" 2>/dev/null || true
        exit 1
    fi
fi
SWAY_AIRPLANE_MODE

cat > "$target_home/.local/bin/sway-screenshot" <<'SWAY_SCREENSHOT'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log hotkey screenshot "${1:-region}" >/dev/null 2>&1 || true
exec "$HOME/.local/bin/ab-system-control" screenshot "${1:-region}"

SWAY_SCREENSHOT

cat > "$target_home/.local/bin/sway-hotkey-action" <<'SWAY_HOTKEY_ACTION'
#!/usr/bin/env sh
set -eu

notify() {
    notify-send "$1" "$2" 2>/dev/null || true
}

case "${1:-}" in
    favorites)
        "$HOME/.local/bin/ab-system-control" event log hotkey favorites press >/dev/null 2>&1 || true
        if [ -d "$HOME/Favorites" ] && command -v thunar >/dev/null 2>&1; then
            thunar "$HOME/Favorites"
        elif command -v exo-open >/dev/null 2>&1; then
            exo-open --launch WebBrowser
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$HOME"
        else
            notify "Favorites" "No favorite handler is configured"
        fi
        ;;
    *)
        notify "Hotkey" "No action configured"
        exit 2
        ;;
esac
SWAY_HOTKEY_ACTION

cat > "$target_home/.local/bin/sway-desktop-doctor" <<'SWAY_DESKTOP_DOCTOR'
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
SWAY_DESKTOP_DOCTOR

cat > "$target_home/.local/bin/sway-desktop-watchdog" <<'SWAY_DESKTOP_WATCHDOG'
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
SWAY_DESKTOP_WATCHDOG

cat > "$target_home/.local/bin/sway-agent-menu" <<'SWAY_AGENT_MENU'
#!/usr/bin/env bash
set -u

menu() {
    if command -v wmenu >/dev/null 2>&1; then
        wmenu -i -l 10 -p "${1:-Agent-Bridge}"
    else
        return 1
    fi
}

terminal_hold() {
    local title="$1"
    shift
    if command -v foot >/dev/null 2>&1; then
        setsid foot -T "$title" -e sh -lc "$*; printf '\nPress Enter to close...'; read -r _" >/dev/null 2>&1 &
    else
        notify-send -a sway "$title" "foot is not installed" >/dev/null 2>&1 || true
        return 1
    fi
}

log_event() {
    local name="$1"
    local detail="${2:-}"
    "$HOME/.local/bin/ab-system-control" event log agent-menu "$name" "$detail" >/dev/null 2>&1 || true
}

show_status() {
    log_event action status
    terminal_hold "Agent-Bridge Status" "$HOME/.local/bin/ab-system-control status summary | jq ."
}

show_report() {
    log_event action status-report
    terminal_hold "Status Report" "$HOME/.local/bin/ab-system-control status report 20"
}

show_snapshot() {
    log_event action status-snapshot
    terminal_hold "System Snapshot" "$HOME/.local/bin/ab-system-control status snapshot | jq ."
}

record_snapshot() {
    log_event action status-record
    terminal_hold "Record Snapshot" "$HOME/.local/bin/ab-system-control status record | jq ."
}

show_snapshot_history() {
    log_event action status-history
    terminal_hold "Snapshot History" "$HOME/.local/bin/ab-system-control status history 20 | jq ."
}

show_snapshot_diagnosis() {
    log_event action status-diagnose
    terminal_hold "Snapshot Diagnosis" "$HOME/.local/bin/ab-system-control status diagnose 20 | jq ."
}

show_audit() {
    log_event action audit
    terminal_hold "System Control Audit" "$HOME/.local/bin/ab-system-control audit-tail 40"
}

show_doctor() {
    log_event action agent-bridge-doctor
    terminal_hold "Agent-Bridge Doctor" "agent-bridge doctor"
}

show_desktop_doctor() {
    log_event action desktop-doctor
    terminal_hold "Desktop Doctor" "$HOME/.local/bin/ab-system-control desktop doctor | jq ."
}

repair_desktop() {
    log_event action desktop-repair
    terminal_hold "Desktop Repair" "AB_SWAY_DESKTOP_REPAIR_INTERACTIVE=1 $HOME/.local/bin/ab-system-control desktop repair --confirm"
}

heal_desktop() {
    log_event action desktop-heal
    terminal_hold "Desktop Heal" "$HOME/.local/bin/ab-system-control desktop heal --confirm | jq ."
}

run_desktop_watchdog() {
    log_event action desktop-watchdog
    terminal_hold "Desktop Watchdog" "$HOME/.local/bin/ab-system-control desktop watchdog --confirm | jq ."
}

restart_daemon() {
    log_event action restart-daemon
    if systemctl --user restart agent-bridge-daemon.service >/dev/null 2>&1; then
        notify-send -a sway "Agent-Bridge" "Daemon restarted" >/dev/null 2>&1 || true
    else
        notify-send -a sway "Agent-Bridge" "Could not restart daemon" >/dev/null 2>&1 || true
    fi
}

reload_sway() {
    log_event action reload-sway
    swaymsg reload >/dev/null 2>&1 &&
        notify-send -a sway "Sway" "Configuration reloaded" >/dev/null 2>&1 || true
}

actions_menu() {
    if ! command -v wmenu >/dev/null 2>&1; then
        show_status
        return
    fi

    local selected
    selected="$(printf '%s\n' \
        "Status summary" \
        "Status report" \
        "System snapshot" \
        "Record snapshot" \
        "Snapshot history" \
        "Snapshot diagnosis" \
        "Desktop doctor" \
        "Run desktop watchdog" \
        "Heal desktop services" \
        "Repair desktop config" \
        "System control audit" \
        "Agent-Bridge doctor" \
        "Restart Agent-Bridge daemon" \
        "Reload Sway config" |
        menu "Agent-Bridge")" || return 0

    case "$selected" in
        "Status summary") show_status ;;
        "Status report") show_report ;;
        "System snapshot") show_snapshot ;;
        "Record snapshot") record_snapshot ;;
        "Snapshot history") show_snapshot_history ;;
        "Snapshot diagnosis") show_snapshot_diagnosis ;;
        "Desktop doctor") show_desktop_doctor ;;
        "Run desktop watchdog") run_desktop_watchdog ;;
        "Heal desktop services") heal_desktop ;;
        "Repair desktop config") repair_desktop ;;
        "System control audit") show_audit ;;
        "Agent-Bridge doctor") show_doctor ;;
        "Restart Agent-Bridge daemon") restart_daemon ;;
        "Reload Sway config") reload_sway ;;
    esac
}

case "${1:-actions}" in
    actions) actions_menu ;;
    status) show_status ;;
    report) show_report ;;
    snapshot) show_snapshot ;;
    record-snapshot) record_snapshot ;;
    snapshot-history) show_snapshot_history ;;
    snapshot-diagnosis) show_snapshot_diagnosis ;;
    desktop-doctor) show_desktop_doctor ;;
    desktop-watchdog) run_desktop_watchdog ;;
    desktop-heal) heal_desktop ;;
    desktop-repair) repair_desktop ;;
    audit) show_audit ;;
    doctor) show_doctor ;;
    restart-daemon) restart_daemon ;;
    reload-sway) reload_sway ;;
    *)
        echo "usage: sway-agent-menu [actions|status|report|snapshot|record-snapshot|snapshot-history|snapshot-diagnosis|desktop-doctor|desktop-watchdog|desktop-heal|desktop-repair|audit|doctor|restart-daemon|reload-sway]" >&2
        exit 2
        ;;
esac
SWAY_AGENT_MENU

cat > "$target_home/.local/bin/sway-wifi-menu" <<'SWAY_WIFI_MENU'
#!/usr/bin/env bash
set -u

notify() {
    notify-send -a sway "WiFi" "$1" >/dev/null 2>&1 || true
}

log_event() {
    local name="$1"
    local detail="${2:-}"
    "$HOME/.local/bin/ab-system-control" event log wifi-menu "$name" "$detail" >/dev/null 2>&1 || true
}

menu() {
    if command -v wmenu >/dev/null 2>&1; then
        wmenu -i -l 12 -p "${1:-WiFi}"
    else
        return 1
    fi
}

open_nmtui() {
    log_event action open-nmtui
    if command -v foot >/dev/null 2>&1 && command -v nmtui-connect >/dev/null 2>&1; then
        setsid foot -T "WiFi" -e nmtui-connect >/dev/null 2>&1 &
        return 0
    fi
    notify "No WiFi menu program found"
    return 1
}

toggle_wifi() {
    log_event action toggle
    if [ "$(nmcli -t -f WIFI general 2>/dev/null)" = "enabled" ]; then
        nmcli radio wifi off >/dev/null 2>&1 && notify "WiFi disabled"
    else
        nmcli radio wifi on >/dev/null 2>&1 && notify "WiFi enabled"
    fi
}

current_wifi_connection() {
    nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null |
        awk -F: '$2 == "wifi" && $3 == "connected" {print $4; exit}'
}

wifi_device() {
    nmcli -t -f DEVICE,TYPE dev status 2>/dev/null |
        awk -F: '$2 == "wifi" {print $1; exit}'
}

reconnect_wifi() {
    log_event action reconnect
    local connection
    connection="$(current_wifi_connection)"
    if [ -n "$connection" ]; then
        nmcli connection down id "$connection" >/dev/null 2>&1 || true
        nmcli connection up id "$connection" >/dev/null 2>&1 && notify "Reconnected: $connection" && return 0
    fi

    local device
    device="$(wifi_device)"
    if [ -n "$device" ]; then
        nmcli device disconnect "$device" >/dev/null 2>&1 || true
        nmcli device connect "$device" >/dev/null 2>&1 && notify "WiFi reconnected" && return 0
    fi

    notify "No WiFi device found"
    return 1
}

disconnect_wifi() {
    log_event action disconnect
    local device
    device="$(wifi_device)"
    if [ -n "$device" ]; then
        nmcli device disconnect "$device" >/dev/null 2>&1 && notify "WiFi disconnected"
    else
        notify "No WiFi device found"
        return 1
    fi
}

open_connection_editor() {
    log_event action connection-editor
    if command -v nm-connection-editor >/dev/null 2>&1; then
        setsid nm-connection-editor >/dev/null 2>&1 &
    else
        open_nmtui
    fi
}

network_lines() {
    nmcli device wifi rescan >/dev/null 2>&1 || true
    nmcli -t -f IN-USE,SSID,SECURITY,SIGNAL dev wifi list 2>/dev/null |
        awk -F: 'length($2) > 0 {
            mark = ($1 == "*" ? "*" : " ")
            sec = ($3 == "" ? "open" : $3)
            printf "%s %s | %s%% | %s\n", mark, $2, $4, sec
        }'
}

connect_networks() {
    log_event action networks
    if ! command -v nmcli >/dev/null 2>&1; then
        notify "nmcli is not installed"
        return 1
    fi

    if ! command -v wmenu >/dev/null 2>&1; then
        open_nmtui
        return
    fi

    local selected ssid
    selected="$(network_lines | menu "WiFi network")" || return 0
    [ -n "$selected" ] || return 0

    ssid="${selected#? }"
    ssid="${ssid%% | *}"
    log_event selected "ssid=$ssid"

    if nmcli device wifi connect "$ssid" >/dev/null 2>&1; then
        log_event connect.ok "ssid=$ssid"
        notify "Connected: $ssid"
    else
        log_event connect.error "ssid=$ssid"
        notify "Could not connect: $ssid"
        open_nmtui
    fi
}

actions_menu() {
    log_event action actions
    if ! command -v wmenu >/dev/null 2>&1; then
        open_nmtui
        return
    fi

    local selected
    selected="$(printf '%s\n' \
        "Connect to WiFi network" \
        "Reconnect current WiFi" \
        "Rescan and show networks" \
        "Toggle WiFi on/off" \
        "Disconnect WiFi" \
        "Open nmtui-connect" \
        "Open Network Connections" |
        menu "WiFi action")" || return 0

    case "$selected" in
        "Connect to WiFi network") connect_networks ;;
        "Reconnect current WiFi") reconnect_wifi ;;
        "Rescan and show networks") connect_networks ;;
        "Toggle WiFi on/off") toggle_wifi ;;
        "Disconnect WiFi") disconnect_wifi ;;
        "Open nmtui-connect") open_nmtui ;;
        "Open Network Connections") open_connection_editor ;;
    esac
}

case "${1:-networks}" in
    networks) connect_networks ;;
    actions) actions_menu ;;
    reconnect) reconnect_wifi ;;
    toggle) toggle_wifi ;;
    nmtui) open_nmtui ;;
    *)
        echo "usage: sway-wifi-menu [networks|actions|reconnect|toggle|nmtui]" >&2
        exit 2
        ;;
esac
SWAY_WIFI_MENU

cat > "$target_home/.local/bin/sway-idle-display" <<'SWAY_IDLE_DISPLAY'
#!/usr/bin/env sh
set -eu

timeout_seconds="${SWAY_DISPLAY_IDLE_TIMEOUT:-600}"

exec swayidle -w \
    timeout "$timeout_seconds" 'swaymsg "output * power off"' \
    resume 'swaymsg "output * power on"'
SWAY_IDLE_DISPLAY

cat > "$target_home/.local/bin/sway-lid-display" <<'SWAY_LID_DISPLAY'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log switch lid "${1:-}" >/dev/null 2>&1 || true
exec "$HOME/.local/bin/ab-system-control" lid "${1:-}"

SWAY_LID_DISPLAY

cat > "$target_home/.local/bin/sway-power-button" <<'SWAY_POWER_BUTTON'
#!/usr/bin/env sh
set -eu

"$HOME/.local/bin/ab-system-control" event log hotkey power press >/dev/null 2>&1 || true
exec "$HOME/.local/bin/ab-system-control" power press

SWAY_POWER_BUTTON

cat > "$target_home/.local/bin/sway-battery-charge-limit" <<'SWAY_BATTERY_CHARGE_LIMIT'
#!/usr/bin/env bash
set -euo pipefail

notify() {
    notify-send -a Battery "$1" "${2:-}" >/dev/null 2>&1 || true
}

find_conservation_mode() {
    find /sys/devices -path '*/VPC2004:00/conservation_mode' -type f 2>/dev/null | head -1
}

find_end_threshold() {
    for bat in /sys/class/power_supply/BAT*; do
        [ -d "$bat" ] || continue
        for name in charge_control_end_threshold charge_stop_threshold; do
            [ -e "$bat/$name" ] && printf '%s\n' "$bat/$name" && return 0
        done
    done
    return 1
}

write_root_file() {
    local path="$1" value="$2" label="${3:-value}"
    if [ -w "$path" ]; then
        printf '%s\n' "$value" >"$path"
        return
    fi
    if sudo -n true >/dev/null 2>&1 || [ -t 0 ]; then
        sudo sh -c 'printf "%s\n" "$1" > "$2"' sh "$value" "$path"
        return
    fi
    if command -v xfce4-terminal >/dev/null 2>&1 && [ -n "${SWAYSOCK:-}" ]; then
        swaymsg exec "xfce4-terminal --title='Battery charge limit' --command=\"bash -lc 'if sudo sh -c '\\''printf \\\"%s\\\\n\\\" $value > $path'\\''; then echo; echo $label 已设置; sleep 1; else echo; echo 设置失败，按回车关闭; read; fi'\"" >/dev/null
        return
    fi
    echo "Need sudo to write $path" >&2
    return 1
}

status() {
    local threshold conservation value capacity state
    capacity="$(cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1 || true)"
    state="$(cat /sys/class/power_supply/BAT*/status 2>/dev/null | head -1 || true)"
    printf 'battery: %s%% %s\n' "${capacity:-?}" "${state:-unknown}"

    if threshold="$(find_end_threshold)"; then
        value="$(cat "$threshold" 2>/dev/null || true)"
        printf 'threshold: %s (%s)\n' "${value:-?}" "$threshold"
    else
        printf 'threshold: unsupported by current BAT sysfs\n'
    fi

    if conservation="$(find_conservation_mode)"; then
        value="$(cat "$conservation" 2>/dev/null || true)"
        printf 'lenovo conservation_mode: %s (%s)\n' "${value:-?}" "$conservation"
    else
        printf 'lenovo conservation_mode: unavailable\n'
    fi
}

set_conservation() {
    local value="$1" path
    path="$(find_conservation_mode || true)"
    if [ -z "$path" ]; then
        notify "Battery conservation" "This machine does not expose Lenovo conservation_mode"
        echo "Lenovo conservation_mode is unavailable" >&2
        return 2
    fi
    write_root_file "$path" "$value" "conservation_mode"
    if [ "$value" = 1 ]; then
        notify "Battery conservation on" "Charging will be limited by Lenovo firmware"
    else
        notify "Battery conservation off" "Normal charging restored"
    fi
}

set_percent() {
    local pct="$1" threshold
    case "$pct" in
        ''|*[!0-9]*) echo "usage: sway-battery-charge-limit set <50-100>" >&2; return 2 ;;
    esac
    if [ "$pct" -lt 50 ] || [ "$pct" -gt 100 ]; then
        echo "percentage must be 50..100" >&2
        return 2
    fi

    if threshold="$(find_end_threshold)"; then
        write_root_file "$threshold" "$pct" "charge threshold"
        notify "Battery charge limit" "Set charge threshold to ${pct}%"
        return
    fi

    if [ "$pct" -le 60 ]; then
        set_conservation 1
        echo "Precise ${pct}% threshold is not exposed; enabled Lenovo conservation mode instead."
        return
    fi

    notify "Battery charge limit unsupported" "This machine exposes only Lenovo conservation mode, not a precise ${pct}% threshold"
    echo "Precise ${pct}% threshold is not supported by the current kernel/hardware interface." >&2
    echo "Use: sway-battery-charge-limit conservation on" >&2
    return 4
}

case "${1:-status}" in
    status) status ;;
    set) set_percent "${2:-}" ;;
    conservation)
        case "${2:-}" in
            on|1|enable|enabled) set_conservation 1 ;;
            off|0|disable|disabled) set_conservation 0 ;;
            toggle)
                path="$(find_conservation_mode || true)"
                [ -n "$path" ] || { echo "Lenovo conservation_mode is unavailable" >&2; exit 2; }
                current="$(cat "$path" 2>/dev/null || echo 0)"
                [ "$current" = 1 ] && set_conservation 0 || set_conservation 1
                ;;
            *) echo "usage: sway-battery-charge-limit conservation on|off|toggle" >&2; exit 2 ;;
        esac
        ;;
    *) echo "usage: sway-battery-charge-limit [status|set <percent>|conservation on|off|toggle]" >&2; exit 2 ;;
esac
SWAY_BATTERY_CHARGE_LIMIT

cat > "$target_home/.local/bin/sway-battery-menu" <<'SWAY_BATTERY_MENU'
#!/usr/bin/env bash
set -u

tool="$HOME/.local/bin/sway-battery-charge-limit"

notify() {
    notify-send -a Battery "$1" "${2:-}" >/dev/null 2>&1 || true
}

menu() {
    if command -v wmenu >/dev/null 2>&1; then
        wmenu -i -l 8 -p "${1:-Battery}"
    else
        return 1
    fi
}

status_text() {
    if [ -x "$tool" ]; then
        "$tool" status 2>/dev/null
    else
        printf 'battery charge limit helper is not installed\n'
    fi
}

show_status() {
    notify "Battery" "$(status_text)"
}

actions_menu() {
    if ! command -v wmenu >/dev/null 2>&1; then
        show_status
        return 0
    fi

    local selected
    selected="$(printf '%s\n' \
        "Status" \
        "Enable conservation mode" \
        "Disable conservation mode" \
        "Toggle conservation mode" \
        "Try precise 50% limit" \
        "Try precise 80% limit" |
        menu "Battery")" || return 0

    case "$selected" in
        "Status") show_status ;;
        "Enable conservation mode") "$tool" conservation on ;;
        "Disable conservation mode") "$tool" conservation off ;;
        "Toggle conservation mode") "$tool" conservation toggle ;;
        "Try precise 50% limit") "$tool" set 50 ;;
        "Try precise 80% limit") "$tool" set 80 || notify "Battery" "This machine does not expose a precise 80% threshold" ;;
    esac
}

case "${1:-actions}" in
    actions) actions_menu ;;
    status) show_status ;;
    *) echo "usage: sway-battery-menu [actions|status]" >&2; exit 2 ;;
esac
SWAY_BATTERY_MENU

cat > "$target_home/.local/bin/thunar-copy-file-address" <<'THUNAR_COPY_FILE_ADDRESS'
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
    notify-send -a Thunar "复制文件地址" "没有选中文件" >/dev/null 2>&1 || true
    exit 0
fi

if command -v wl-copy >/dev/null 2>&1; then
    printf '%s\n' "$@" | wl-copy
elif command -v xclip >/dev/null 2>&1; then
    printf '%s\n' "$@" | xclip -selection clipboard
elif command -v xsel >/dev/null 2>&1; then
    printf '%s\n' "$@" | xsel --clipboard --input
else
    notify-send -a Thunar "复制文件地址失败" "未找到 wl-copy/xclip/xsel" >/dev/null 2>&1 || true
    exit 1
fi

if [ "$#" -eq 1 ]; then
    notify-send -a Thunar "已复制文件地址" "$1" >/dev/null 2>&1 || true
else
    notify-send -a Thunar "已复制文件地址" "已复制 $# 个路径" >/dev/null 2>&1 || true
fi
THUNAR_COPY_FILE_ADDRESS

cat > "$target_home/.config/Thunar/uca.xml" <<'THUNAR_UCA'
<?xml version="1.0" encoding="UTF-8"?>
<actions>
<action>
	<icon>utilities-terminal</icon>
	<name>Open Terminal Here</name>
	<submenu></submenu>
	<unique-id>1781071470589882-1</unique-id>
	<command>exo-open --working-directory %f --launch TerminalEmulator</command>
	<description>Open a terminal in the selected directory</description>
	<range></range>
	<patterns>*</patterns>
	<startup-notify/>
	<directories/>
</action>
<action>
	<icon>edit-copy</icon>
	<name>复制文件地址</name>
	<submenu></submenu>
	<unique-id>1781071470589882-2</unique-id>
	<command>sh -c &apos;&quot;$HOME/.local/bin/thunar-copy-file-address&quot; &quot;$@&quot;&apos; thunar-copy-file-address %F</command>
	<description>复制所选文件的绝对路径及完整文件名</description>
	<range></range>
	<patterns>*</patterns>
	<startup-notify/>
	<directories/>
	<text-files/>
	<image-files/>
	<audio-files/>
	<video-files/>
	<other-files/>
</action>
</actions>
THUNAR_UCA

cat > "$target_home/.config/systemd/user/sway-desktop-watchdog.service" <<'SWAY_DESKTOP_WATCHDOG_SERVICE'
[Unit]
Description=Sway desktop watchdog (Agent-Bridge)

[Service]
Type=oneshot
ExecStart=%h/.local/bin/sway-desktop-watchdog
SWAY_DESKTOP_WATCHDOG_SERVICE

cat > "$target_home/.config/systemd/user/sway-desktop-watchdog.timer" <<'SWAY_DESKTOP_WATCHDOG_TIMER'
[Unit]
Description=Run Sway desktop watchdog periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Unit=sway-desktop-watchdog.service

[Install]
WantedBy=timers.target
SWAY_DESKTOP_WATCHDOG_TIMER

logind_power_rule="$(mktemp)"
cat > "$logind_power_rule" <<'LOGIND_POWER'
[Login]
HandlePowerKey=ignore
HandlePowerKeyLongPress=ignore
LOGIND_POWER
need_sudo install -d -m 0755 /etc/systemd/logind.conf.d
need_sudo install -m 0644 "$logind_power_rule" /etc/systemd/logind.conf.d/90-local-power-button.conf
rm -f "$logind_power_rule"
need_sudo systemctl reload systemd-logind || true

logind_lid_rule="$(mktemp)"
cat > "$logind_lid_rule" <<'LOGIND_LID'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
LOGIND_LID
need_sudo install -d -m 0755 /etc/systemd/logind.conf.d
need_sudo install -m 0644 "$logind_lid_rule" /etc/systemd/logind.conf.d/90-local-lid-display-only.conf
rm -f "$logind_lid_rule"
need_sudo systemctl reload systemd-logind || true

backlight_rule="$(mktemp)"
cat > "$backlight_rule" <<'BACKLIGHT_UDEV'
ACTION=="add", SUBSYSTEM=="backlight", RUN+="/bin/chmod 0666 /sys/class/backlight/%k/brightness"
BACKLIGHT_UDEV
need_sudo install -m 0644 "$backlight_rule" /etc/udev/rules.d/90-local-backlight-permissions.rules
rm -f "$backlight_rule"
need_sudo udevadm control --reload-rules || true
for brightness_node in /sys/class/backlight/*/brightness; do
    [ -e "$brightness_node" ] || continue
    need_sudo chmod 0666 "$brightness_node" || true
done

need_sudo chown -R "$target_user:$target_user" "$target_home/.config/sway" "$target_home/.config/mako" "$target_home/.config/systemd" "$target_home/.config/Thunar"
need_sudo chown "$target_user:$target_user" \
    "$target_home/.local/bin/ab-system-control" \
    "$target_home/.local/bin/sway-status" \
    "$target_home/.local/bin/sway-volume" \
    "$target_home/.local/bin/sway-brightness" \
    "$target_home/.local/bin/sway-display-cycle" \
    "$target_home/.local/bin/sway-airplane-mode" \
    "$target_home/.local/bin/sway-screenshot" \
    "$target_home/.local/bin/sway-hotkey-action" \
    "$target_home/.local/bin/sway-desktop-doctor" \
    "$target_home/.local/bin/sway-desktop-watchdog" \
    "$target_home/.local/bin/sway-agent-menu" \
    "$target_home/.local/bin/sway-wifi-menu" \
    "$target_home/.local/bin/sway-idle-display" \
    "$target_home/.local/bin/sway-lid-display" \
    "$target_home/.local/bin/sway-power-button" \
    "$target_home/.local/bin/sway-battery-charge-limit" \
    "$target_home/.local/bin/sway-battery-menu" \
    "$target_home/.local/bin/thunar-copy-file-address"
need_sudo chmod 755 "$target_home/.config/sway" "$target_home/.config/mako" "$target_home/.config/Thunar"
need_sudo chmod 755 \
    "$target_home/.local/bin/ab-system-control" \
    "$target_home/.local/bin/sway-status" \
    "$target_home/.local/bin/sway-volume" \
    "$target_home/.local/bin/sway-brightness" \
    "$target_home/.local/bin/sway-display-cycle" \
    "$target_home/.local/bin/sway-airplane-mode" \
    "$target_home/.local/bin/sway-screenshot" \
    "$target_home/.local/bin/sway-hotkey-action" \
    "$target_home/.local/bin/sway-desktop-doctor" \
    "$target_home/.local/bin/sway-desktop-watchdog" \
    "$target_home/.local/bin/sway-agent-menu" \
    "$target_home/.local/bin/sway-wifi-menu" \
    "$target_home/.local/bin/sway-idle-display" \
    "$target_home/.local/bin/sway-lid-display" \
    "$target_home/.local/bin/sway-power-button" \
    "$target_home/.local/bin/sway-battery-charge-limit" \
    "$target_home/.local/bin/sway-battery-menu" \
    "$target_home/.local/bin/thunar-copy-file-address"
need_sudo chmod 644 "$target_home/.config/sway/config"
need_sudo chmod 644 "$target_home/.config/mako/config"
need_sudo chmod 644 "$target_home/.config/Thunar/uca.xml"
need_sudo chmod 644 \
    "$target_home/.config/systemd/user/sway-desktop-watchdog.service" \
    "$target_home/.config/systemd/user/sway-desktop-watchdog.timer"

as_user bash -n "$target_home/.local/bin/ab-system-control"
as_user bash -n "$target_home/.local/bin/sway-status"
as_user sh -n "$target_home/.local/bin/sway-volume"
as_user sh -n "$target_home/.local/bin/sway-brightness"
as_user sh -n "$target_home/.local/bin/sway-airplane-mode"
as_user sh -n "$target_home/.local/bin/sway-screenshot"
as_user sh -n "$target_home/.local/bin/sway-hotkey-action"
as_user bash -n "$target_home/.local/bin/sway-desktop-doctor"
as_user bash -n "$target_home/.local/bin/sway-desktop-watchdog"
as_user bash -n "$target_home/.local/bin/sway-agent-menu"
as_user sh -n "$target_home/.local/bin/sway-idle-display"
as_user sh -n "$target_home/.local/bin/sway-lid-display"
as_user sh -n "$target_home/.local/bin/sway-power-button"
as_user bash -n "$target_home/.local/bin/sway-battery-charge-limit"
as_user bash -n "$target_home/.local/bin/sway-battery-menu"
as_user bash -n "$target_home/.local/bin/thunar-copy-file-address"
as_user bash -n "$target_home/.local/bin/sway-wifi-menu"
as_user python3 -m py_compile "$target_home/.local/bin/sway-display-cycle"

if as_user systemctl --user daemon-reload >/dev/null 2>&1; then
    as_user systemctl --user enable --now sway-desktop-watchdog.timer >/dev/null 2>&1 || true
else
    echo "Could not reload user systemd; enable sway-desktop-watchdog.timer after login if needed." >&2
fi

if [ "${SWAYSOCK:-}" ] && command -v swaymsg >/dev/null 2>&1; then
    as_user swaymsg reload >/dev/null || true
    echo "Reloaded current Sway session."
else
    echo "Sway config installed. Log into Sway or run 'swaymsg reload' inside Sway."
fi

echo "Installed Sway workstation config for $target_user."
