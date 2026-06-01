#!/usr/bin/env bash
# TRY-IT sandbox for the human-mediated cross-process control plane (Slice B).
#
# Lets you EXPERIENCE the kind=steer capability WITHOUT deploying — fully isolated:
#   - the AB store is redirected to a throwaway $XDG_CACHE_HOME (zero live-dock contamination)
#   - the dock runs on a probe port off THIS worktree's GATED dock_server (executes on approve)
#   - injections target a throwaway tmux session you can watch read-only
#
# Click 允许/拒绝 in the dock window; an approved steer injects into the target session,
# a rejected one is killed and runs nothing. Ctrl-C here (or closing the window) tears
# everything down — server, window, session, the throwaway store — leaving live untouched.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # scripts/dock
REPO="$(cd "$DIR/../.." && pwd)"                          # worktree root
PORT="${AB_DEMO_PORT:-8799}"
SESS="${AB_DEMO_SESSION:-ab__demo__target}"
DEMO_CACHE="${TMPDIR:-/tmp}/ab-steer-demo"
CHROME="${AB_CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo google-chrome)}"
PROFILE="$DEMO_CACHE/chrome-profile"

export XDG_CACHE_HOME="$DEMO_CACHE"   # isolate the AB store (pendings/decisions) from live
export AB_REPO_ROOT="$REPO"           # so dock_server finds the blessed phase-2 executors
mkdir -p "$DEMO_CACHE/agent-bridge/desktop_pending"

cleanup() {
  echo; echo "🧹  tearing down demo…"
  kill "${HTTP_PID:-}" "${AGG_PID:-}" "${CHROME_PID:-}" 2>/dev/null || true
  tmux kill-session -t "$SESS" 2>/dev/null || true
  rm -rf "$DEMO_CACHE" 2>/dev/null || true
  echo "    done — live dock / store / waybar untouched."
}
trap cleanup EXIT INT TERM

# a throwaway target session = "another process's session"
tmux kill-session -t "$SESS" 2>/dev/null || true
tmux new-session -d -s "$SESS" -x 130 -y 32
tmux send-keys -t "$SESS" \
  "clear; echo '↓↓↓ 这是「另一个进程的会话」。你在坞里批准的注入会落在这里 ↓↓↓'" Enter

# stage a few demo steers (long TTL so you have time to play)
cd "$DIR"
python3 stage_steer.py --session "$SESS" --submit --by demo-worker-A --ttl 1800 \
  --text "echo '✅ 你刚在坞里批准了我 —— 我落到了另一个会话并运行了'" >/dev/null
python3 stage_steer.py --session "$SESS" --submit --by demo-worker-B --ttl 1800 \
  --text "date '+被批准注入于 %H:%M:%S'" >/dev/null
python3 stage_steer.py --session "$SESS" --submit --by sketchy-worker --ttl 1800 \
  --text "echo '[假装危险] 我看着像该拒绝的命令 —— 因为你看得清我,请拒绝我'" >/dev/null
python3 aggregate.py >/dev/null

# keep the snapshot fresh so each card vanishes once you decide it
( while true; do python3 aggregate.py >/dev/null 2>&1 || true; sleep 2; done ) & AGG_PID=$!
# GATED dock_server off THIS worktree (records-only -> executes on approve)
( python3 "$DIR/dock_server.py" "$PORT" >/dev/null 2>&1 ) & HTTP_PID=$!
sleep 0.6

"$CHROME" --app="http://127.0.0.1:$PORT/dock.html" \
  --user-data-dir="$PROFILE" --window-size=400,560 --window-position=60,60 \
  --no-first-run --no-default-browser-check --disable-features=Translate \
  >/dev/null 2>&1 & CHROME_PID=$!

cat <<EOF

🧪  跨进程控制平面 demo 已起(隔离沙盒,未碰 live dock/store/waybar)
    坞窗口 : http://127.0.0.1:$PORT/dock.html   ← GATED executor 版(approve 会真执行)
    目标会话: $SESS

    ① 另开一个终端,只读旁观注入落地:
         tmux attach -t $SESS -r          (看完按 Ctrl-b 然后 d 脱离)
    ② 在坞里:每张 steer 卡都标明「注入什么 · 进哪个会话 · 谁排的」
         【允许】→ 该命令真的注入 $SESS 并执行(你在 ① 里能看见它跑出来)
         【拒绝】→ 该 pending 被杀,什么都不跑(那张"假装危险"的卡专门用来体验拒绝)
    ③ 每决定一张卡,它就从坞里消失(approve=已消费单用 / reject=已杀)

    在本终端按 Ctrl-C(或关掉坞窗口)→ 全部拆掉,live 侧零影响。
EOF

wait "$CHROME_PID"
