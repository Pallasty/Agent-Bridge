#!/bin/sh
# Deterministic local-runtime stand-in for delegated-cgroup lifecycle probes.
# Runtime CLI arguments are intentionally ignored; behavior is selected only
# by the test-owned environment variable below.
set -eu

case "${AB_CGROUP_STANDIN_MODE:-normal}" in
    normal)
        # Keep the workload alive across multiple body samples and include a
        # descendant plus a small CPU contribution.
        (
            n=0
            while [ "$n" -lt 200000 ]; do
                n=$((n + 1))
            done
        ) &
        cpu_child=$!
        sleep 2 &
        sleep_child=$!
        wait "$cpu_child"
        wait "$sleep_child"
        printf '%s\n' "workload-tree-standin complete"
        ;;
    term-immune)
        trap '' TERM HUP
        (
            trap '' TERM HUP
            while :; do
                sleep 1
            done
        ) &
        printf 'TERM-IMMUNE-DESCENDANT:%s\n' "$!"
        while :; do
            sleep 1
        done
        ;;
    interactive)
        printf '%s\n' "WORKLOAD-TREE-PTY-READY"
        exec /bin/cat
        ;;
    *)
        printf 'unknown AB_CGROUP_STANDIN_MODE\n' >&2
        exit 64
        ;;
esac
