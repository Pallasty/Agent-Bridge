# WezTerm integration

Drop `agent-bridge.lua` into your `~/.config/wezterm/` and load it from
`~/.wezterm.lua`:

```lua
require 'agent-bridge'  -- adjust path as needed
return {
  -- ... your existing config ...
}
```

## Triggering a notification from a pane

Manually:

```bash
printf '\033]1337;SetUserVar=ab_notify=%s\007' \
  "$(printf '%s' '{"title":"Hi","body":"from a pane","severity":"success"}' | base64 -w0)"
```

From a Claude Code stop-hook:

```jsonc
// ~/.claude/settings.json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "printf '\\033]1337;SetUserVar=ab_notify=%s\\007' \"$(printf '%s' '{\"title\":\"Claude\",\"body\":\"awaiting input\",\"severity\":\"attention\"}' | base64 -w0)\""
      }]
    }]
  }
}
```

`agent-bridge.lua` will catch the `SetUserVar` event, decode the JSON, and
forward it to `agent-cli notify` — which in turn fans it out to D-Bus,
SQLite history, and any future notifier you register.
