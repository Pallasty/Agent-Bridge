#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
    cat <<'EOF'
Usage:
  invocation-guardian-v2-c2-isolation-preflight.sh --preflight-only
  sudo invocation-guardian-v2-c2-isolation-preflight.sh \
    --binary /absolute/path/invocation-guardian-isolation-probe \
    --guardian-user NAME --bridge-user NAME --agent-user NAME \
    --socket-group NAME

The full probe uses existing identities and transient systemd units only. It
never creates or edits users, groups, persistent units, or production paths.
All mutations stay under a fresh /run/ab-invocation-guardian-c2.* directory
which is removed on exit.
EOF
}

preflight_only=false
probe_binary=
guardian_user=
bridge_user=
agent_user=
socket_group=

while [ "$#" -gt 0 ]; do
    case "$1" in
        --preflight-only) preflight_only=true; shift ;;
        --binary) probe_binary=${2-}; shift 2 ;;
        --guardian-user) guardian_user=${2-}; shift 2 ;;
        --bridge-user) bridge_user=${2-}; shift 2 ;;
        --agent-user) agent_user=${2-}; shift 2 ;;
        --socket-group) socket_group=${2-}; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
    esac
done

if [ "$preflight_only" = true ]; then
    nonroot_users=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {count++} END {print count+0}')
    ptrace_scope=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null || echo unavailable)
    systemd_state=$(systemctl is-system-running 2>/dev/null || true)
    [ -n "$systemd_state" ] || systemd_state=unavailable
    if [ "$(id -u)" -eq 0 ] && [ "$nonroot_users" -ge 3 ]; then
        status=READY_FOR_EXPLICIT_IDENTITIES
        reason=provide_three_distinct_existing_nonroot_users_and_a_dedicated_group
    else
        status=HOLD
        reason=root_and_three_distinct_existing_nonroot_users_are_required
    fi
    printf '{"schema":"agent_bridge.invocation_guardian_c2_host_preflight.v1","status":"%s","reason":"%s","effective_uid":%s,"nonroot_user_count":%s,"ptrace_scope":"%s","systemd_state":"%s","production_authority":false}\n' \
        "$status" "$reason" "$(id -u)" "$nonroot_users" "$ptrace_scope" "$systemd_state"
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "full C2 isolation probe requires root; run --preflight-only for a non-mutating check" >&2
    exit 77
fi
for value in "$probe_binary" "$guardian_user" "$bridge_user" "$agent_user" "$socket_group"; do
    [ -n "$value" ] || { usage >&2; exit 64; }
done
for command_name in getent install systemctl systemd-run sha256sum; do
    command -v "$command_name" >/dev/null || { echo "missing command: $command_name" >&2; exit 69; }
done
systemctl is-system-running >/dev/null 2>&1 || { echo "systemd must be running" >&2; exit 69; }

probe_binary=$(realpath "$probe_binary")
[ -f "$probe_binary" ] && [ -x "$probe_binary" ] || { echo "probe binary must be an executable regular file" >&2; exit 66; }

guardian_uid=$(getent passwd "$guardian_user" | awk -F: 'NR==1 {print $3}')
guardian_gid=$(getent passwd "$guardian_user" | awk -F: 'NR==1 {print $4}')
bridge_uid=$(getent passwd "$bridge_user" | awk -F: 'NR==1 {print $3}')
bridge_gid=$(getent passwd "$bridge_user" | awk -F: 'NR==1 {print $4}')
agent_uid=$(getent passwd "$agent_user" | awk -F: 'NR==1 {print $3}')
agent_gid=$(getent passwd "$agent_user" | awk -F: 'NR==1 {print $4}')
socket_gid=$(getent group "$socket_group" | awk -F: 'NR==1 {print $3}')

for value in "$guardian_uid" "$guardian_gid" "$bridge_uid" "$bridge_gid" "$agent_uid" "$agent_gid" "$socket_gid"; do
    [ -n "$value" ] && [ "$value" -ne 0 ] || { echo "all users and the socket group must exist and be non-root" >&2; exit 65; }
done
[ "$guardian_uid" -ne "$bridge_uid" ] && [ "$guardian_uid" -ne "$agent_uid" ] && [ "$bridge_uid" -ne "$agent_uid" ] || {
    echo "guardian, bridge, and agent users must have distinct UIDs" >&2
    exit 65
}
[ "$socket_gid" -ne "$guardian_gid" ] && [ "$socket_gid" -ne "$bridge_gid" ] && [ "$socket_gid" -ne "$agent_gid" ] || {
    echo "socket group must be dedicated and differ from all three primary groups" >&2
    exit 65
}
id -G "$bridge_user" | tr ' ' '\n' | grep -qx "$socket_gid" || {
    echo "bridge user must be a member of the dedicated socket group" >&2
    exit 65
}
if id -G "$agent_user" | tr ' ' '\n' | grep -qx "$socket_gid"; then
    echo "agent user must not be a member of the dedicated socket group" >&2
    exit 65
fi

probe_root=$(mktemp -d /run/ab-invocation-guardian-c2.XXXXXX)
case "$probe_root" in
    /run/ab-invocation-guardian-c2.*) ;;
    *) echo "unsafe temporary path" >&2; exit 70 ;;
esac
guardian_pid=
guardian_unit=ab-invocation-guardian-c2-$(basename "$probe_root" | cut -d. -f2)
cleanup() {
    systemctl stop "$guardian_unit.service" >/dev/null 2>&1 || true
    systemctl reset-failed "$guardian_unit.service" >/dev/null 2>&1 || true
    case "$probe_root" in
        /run/ab-invocation-guardian-c2.*) rm -rf -- "$probe_root" ;;
    esac
}
trap cleanup EXIT INT TERM

chmod 0711 "$probe_root"
install -d -o root -g root -m 0711 "$probe_root/bin"
install -o root -g root -m 0755 "$probe_binary" "$probe_root/bin/probe"
install -d -o "$guardian_uid" -g "$guardian_gid" -m 0700 "$probe_root/state"
install -d -o "$guardian_uid" -g "$socket_gid" -m 2750 "$probe_root/ipc"
install -d -o "$bridge_uid" -g "$bridge_gid" -m 0700 "$probe_root/bridge"
install -d -o "$agent_uid" -g "$agent_gid" -m 0700 "$probe_root/agent"

socket_path=$probe_root/ipc/guardian.sock
ready_file=$probe_root/state/ready.json
systemd-run --quiet --collect --service-type=exec --unit="$guardian_unit" \
    --uid="$guardian_user" --gid="$guardian_gid" \
    --property=UMask=0077 \
    --property=NoNewPrivileges=yes \
    --property=PrivateTmp=yes \
    --property=PrivateDevices=yes \
    --property=ProtectSystem=strict \
    --property=ProtectHome=yes \
    --property=ProtectKernelTunables=yes \
    --property=ProtectKernelModules=yes \
    --property=ProtectControlGroups=yes \
    --property=RestrictSUIDSGID=yes \
    --property=LockPersonality=yes \
    --property=CapabilityBoundingSet= \
    --property=AmbientCapabilities= \
    --property=RestrictAddressFamilies=AF_UNIX \
    --property=ReadOnlyPaths=/run \
    --property="ReadWritePaths=$probe_root/state $probe_root/ipc" \
    "$probe_root/bin/probe" serve \
    --socket "$socket_path" \
    --state-dir "$probe_root/state" \
    --ready-file "$ready_file" \
    --expected-bridge-uid "$bridge_uid" \
    --socket-gid "$socket_gid"

for _ in $(seq 1 100); do
    [ -f "$ready_file" ] && break
    systemctl is-active --quiet "$guardian_unit.service" || { echo "probe server exited before readiness" >&2; exit 1; }
    sleep 0.05
done
[ -f "$ready_file" ] || { echo "probe server readiness timed out" >&2; exit 1; }
guardian_pid=$(sed -n 's/.*"pid":\([0-9][0-9]*\).*/\1/p' "$ready_file")
listener_fd_inode=$(sed -n 's/.*"listener_fd_inode":\([0-9][0-9]*\).*/\1/p' "$ready_file")
[ -n "$guardian_pid" ] && [ -n "$listener_fd_inode" ] || { echo "invalid ready evidence" >&2; exit 1; }

systemd-run --quiet --wait --pipe --collect --service-type=exec \
    --uid="$bridge_user" --gid="$bridge_gid" \
    --property="SupplementaryGroups=$socket_group" \
    --property=NoNewPrivileges=yes --property=PrivateTmp=yes \
    --property=PrivateDevices=yes --property=RestrictSUIDSGID=yes \
    --property=LockPersonality=yes --property=CapabilityBoundingSet= \
    --property=AmbientCapabilities= --property=RestrictAddressFamilies=AF_UNIX \
    "$probe_root/bin/probe" attack \
    --role bridge --socket "$socket_path" --state-dir "$probe_root/state" \
    --attacker-dir "$probe_root/bridge" --guardian-uid "$guardian_uid" \
    --guardian-pid "$guardian_pid" --socket-gid "$socket_gid" \
    --listener-fd-inode "$listener_fd_inode" --expect-connect allow \
    --expect-socket-group allow >"$probe_root/bridge.json"

systemd-run --quiet --wait --pipe --collect --service-type=exec \
    --uid="$agent_user" --gid="$agent_gid" \
    --property=NoNewPrivileges=yes --property=PrivateTmp=yes \
    --property=PrivateDevices=yes --property=RestrictSUIDSGID=yes \
    --property=LockPersonality=yes --property=CapabilityBoundingSet= \
    --property=AmbientCapabilities= --property=RestrictAddressFamilies=AF_UNIX \
    "$probe_root/bin/probe" attack \
    --role agent --socket "$socket_path" --state-dir "$probe_root/state" \
    --attacker-dir "$probe_root/agent" --guardian-uid "$guardian_uid" \
    --guardian-pid "$guardian_pid" --socket-gid "$socket_gid" \
    --listener-fd-inode "$listener_fd_inode" --expect-connect deny \
    --expect-socket-group deny >"$probe_root/agent.json"

printf '{"schema":"agent_bridge.invocation_guardian_c2_isolation_substrate.v1","status":"ISOLATION_SUBSTRATE_PASS","c2_gate":"HOLD_actual_v2_guardian_not_deployed","helper_sha256":"%s","ready":' \
    "$(sha256sum "$probe_root/bin/probe" | awk '{print $1}')"
tr -d '\n' <"$ready_file"
printf ',"bridge":'
tr -d '\n' <"$probe_root/bridge.json"
printf ',"agent":'
tr -d '\n' <"$probe_root/agent.json"
printf ',"production_authority":false}\n'
