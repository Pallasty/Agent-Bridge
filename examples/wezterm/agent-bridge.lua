-- agent-bridge ↔ WezTerm hook
--
-- Forward OSC notifications and SetUserVar events from any pane to the
-- agent-bridge daemon, so they end up in the desktop notification system
-- and the persistent history.
--
-- Drop this into your `~/.wezterm.lua` (or `require` it from there) and
-- ensure `agent-cli` is on $PATH.
--
-- Two channels are wired:
--
--   1. OSC 1337 SetUserVar  →  Used by Claude Code / hooks to publish
--      structured notifications:
--          printf '\033]1337;SetUserVar=%s=%s\007' \
--              ab_notify "$(printf '%s' '{"title":"Claude","body":"awaiting input","severity":"attention"}' | base64)"
--      The payload is base64-encoded JSON: {title, body, severity}.
--
--   2. WezTerm `bell` event  →  Sends a low-priority "bell" notification
--      so terminal bells (e.g. completed long commands) reach the desktop.
--
-- Both paths shell out to `agent-cli notify` — fire-and-forget.

local wezterm = require 'wezterm'

local function spawn_notify(title, body, severity)
  wezterm.background_child_process({
    'agent-cli', 'notify',
    '-t', title or 'agent-bridge',
    '-s', severity or 'info',
    body or '',
  })
end

-- Decode base64 SetUserVar payloads. WezTerm gives us already-decoded
-- strings for SetUserVar values, but the canonical convention is base64
-- (so binary-safe over the wire). We accept either.
local function maybe_b64(s)
  if not s then return nil end
  -- WezTerm `wezterm.base64` only added in recent versions; guard with pcall.
  local ok, decoded = pcall(function() return wezterm.base64.decode(s) end)
  if ok and decoded and #decoded > 0 then return decoded end
  return s
end

wezterm.on('user-var-changed', function(window, pane, name, value)
  if name ~= 'ab_notify' then return end
  local raw = maybe_b64(value)
  local ok, payload = pcall(function() return wezterm.json_parse(raw) end)
  if not ok or type(payload) ~= 'table' then
    spawn_notify('agent-bridge', tostring(raw), 'info')
    return
  end
  spawn_notify(payload.title, payload.body, payload.severity)
end)

wezterm.on('bell', function(window, pane)
  local title = pane:get_title() or 'terminal bell'
  spawn_notify('Bell — ' .. title, 'A pane just rang the bell.', 'info')
end)

return {
  -- Returning {} lets you `require` this file without overriding the user's
  -- existing wezterm config.
}
