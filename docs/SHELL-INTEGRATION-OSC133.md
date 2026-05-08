# Shell Integration — OSC 133 prompt protocol

Status: required for `terminal_read_blocks` on the PTY backend (since 1744cb8).

`agent-bridge`'s PTY backend reconstructs structured `(command, output, exit_code)`
blocks from **OSC 133** escape sequences emitted by your shell at well-known
points in the prompt cycle. Without these markers, `terminal_read_blocks`
returns an empty list — `terminal_read_output` (raw scroll) keeps working
either way.

This is the same protocol VSCode's terminal, iTerm2's mark navigation,
Kitty's prompt awareness, and Alacritty's planned shell integration use,
so anything you set up here also lights those up.

---

## 1 · The four markers

| Wire form              | Meaning                                                |
|------------------------|--------------------------------------------------------|
| `OSC 133 ; A ST`       | Prompt about to draw                                   |
| `OSC 133 ; B ST`       | Prompt drawn, command input begins                     |
| `OSC 133 ; C ST`       | Command submitted, output begins                       |
| `OSC 133 ; D ; <n> ST` | Command finished with optional exit code `n`           |

`ST` is `BEL` (`0x07`) or `ESC \` — both work.

`agent-bridge`'s parser tolerates extra `key=value` attributes after the
letter (Warp emits `aid=<block-uuid>`; iTerm2 emits `cl=`, `aid=`, etc.)
so you can borrow other terminals' `precmd` / `preexec` hooks as-is.

---

## 2 · One-line setup per shell

### bash

Add to `~/.bashrc`:

```bash
__ab_osc133_preexec() { printf '\e]133;C\a'; }
__ab_osc133_precmd() {
    local exit=$?
    printf '\e]133;D;%s\a\e]133;A\a' "$exit"
    PS1='\[\e]133;B\a\]'"${PS1_ORIG:-$PS1}"
    PS1_ORIG="${PS1_ORIG:-$PS1}"
}
trap '__ab_osc133_preexec' DEBUG
PROMPT_COMMAND="__ab_osc133_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
```

The `DEBUG` trap fires before each command; `PROMPT_COMMAND` runs after
each command and before the next prompt. We splice `OSC 133 ; B` into
`PS1` so the marker lands exactly where the prompt ends.

### zsh

Add to `~/.zshrc`:

```zsh
__ab_osc133_preexec() { print -nP '\e]133;C\a'; }
__ab_osc133_precmd() {
    local exit=$?
    print -nP "\e]133;D;${exit}\a\e]133;A\a"
}
__ab_osc133_prompt_b() { print -nP '\e]133;B\a'; }
PS1='%{$(__ab_osc133_prompt_b)%}'"$PS1"
autoload -Uz add-zsh-hook
add-zsh-hook preexec __ab_osc133_preexec
add-zsh-hook precmd __ab_osc133_precmd
```

### fish

Add to `~/.config/fish/conf.d/agent-bridge-osc133.fish`:

```fish
function __ab_osc133_preexec --on-event fish_preexec
    printf '\e]133;C\a'
end
function __ab_osc133_postexec --on-event fish_postexec
    printf '\e]133;D;%s\a\e]133;A\a' $status
end
function fish_prompt_osc133 --description 'wrap fish_prompt with OSC 133 B marker'
    functions -c fish_prompt __ab_orig_fish_prompt 2>/dev/null
    function fish_prompt
        __ab_orig_fish_prompt
        printf '\e]133;B\a'
    end
end
fish_prompt_osc133
```

---

## 3 · Verifying

After sourcing the snippet (or starting a fresh shell), run any command,
then ask `agent-bridge`:

```bash
$ printf '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"terminal_read_blocks","arguments":{"limit":5}}}' \
    | agent-bridge mcp
```

You should see one block per command with the right exit code. If you get
`[]`, walk through:

1. **Markers actually emitting?** `cat -v` to render escapes:
   ```bash
   $ true; printf '\e]133;A\a' | cat -v
   ^[]133;A^G
   ```
   If the snippet ran, your prompt redraws should produce `^[]133;A^G`
   in `cat -v` of stdin (use `script` to capture).
2. **Inside a `tmux` / `screen` session?** Pass-through is enabled by
   default in modern tmux; on older versions add
   `set -g allow-passthrough on` to `~/.tmux.conf`.
3. **Using a non-interactive shell?** `-c` invocations skip
   `PROMPT_COMMAND` / `precmd`. Block extraction only works in
   interactive sessions.

---

## 4 · Terminals that already do this

If `agent-bridge`'s PTY backend wraps your shell with the snippet above,
you also get correct blocks in any of these terminals:

- **VSCode** built-in terminal — has its own shell integration; our snippet
  composes (both end up emitting the same markers).
- **iTerm2** (macOS) — auto-installs equivalent hooks; works out of the box.
- **Kitty** — `shell_integration enabled` (default).
- **WezTerm** — same.
- **Alacritty / xterm / gnome-terminal** — no built-in shell integration,
  so the snippet here is what makes them work.

Warp is the holdout: it uses a private IPC protocol instead of OSC 133.
That's why `agent-bridge` historically shipped a Warp fork — and why we're
phasing the fork out in favour of this open path.

---

## 5 · CLI helper: `agent-bridge shell-init`

If you'd rather not copy-paste, the binary emits the right snippet for
each shell on stdout:

```bash
$ agent-bridge shell-init bash >> ~/.bashrc
$ agent-bridge shell-init zsh  >> ~/.zshrc
$ agent-bridge shell-init fish >  ~/.config/fish/conf.d/agent-bridge-osc133.fish
```

The snippets in this document and the ones the CLI emits come from the
same Rust source-of-truth (`crates/bridge/src/main.rs::shell_init_snippet`),
so they stay in sync.
