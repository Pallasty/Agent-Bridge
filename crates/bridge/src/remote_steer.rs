//! Remote session steering — pure multiplexer / target / gate logic.
//!
//! Long-lived interactive agents (`codex resume`, `claude`) block on stdin and
//! never poll the AB inbox, so XM v0.2 messaging cannot reach them. The fix is
//! to run them inside a *named terminal-multiplexer session* that can be both
//! human-attached (context-preserving, drift-proof) and written to
//! programmatically. This module holds the dependency-light, unit-tested core
//! used by the `agent_steer_*` MCP tools in [`crate::mcp_tools`]:
//!
//! - a [`Multiplexer`] abstraction (only [`TmuxBackend`] today; screen/dtach/
//!   pty-broker can follow) that produces shell-command strings,
//! - [`Target`] = local vs a tailnet node reached over ssh,
//! - the `ab__<project>__<role>` naming convention (tmux rewrites `:` so the
//!   `ab:project:role` logical handle cannot be a literal tmux name),
//! - [`clean_capture`] (ANSI stripping) and [`detect_gate`] (classifying TUI
//!   prompts into *auto-answerable* vs *needs-human*).
//!
//! Boundary: execution/collection may be driven; research judgment stays
//! human-gated. Accordingly [`detect_gate`] only marks the trust-folder prompt
//! auto-answerable; quota/approval/unknown prompts are `needs_human`.

use std::time::Duration;

use serde::Serialize;
use tokio::process::Command as TokioCommand;

/// Prefix marking an AB-owned steerable multiplexer session.
pub const STEER_PREFIX: &str = "ab__";
/// Delimiter between the project and role components in a tmux session name.
pub const STEER_DELIM: &str = "__";

// ── naming ────────────────────────────────────────────────────────────────

/// Reduce a project/role component to tmux-safe characters: `[A-Za-z0-9-]`,
/// with every other character (including `_`, so the `__` delimiter stays
/// unambiguous) collapsed to a single `-` and leading/trailing dashes trimmed.
pub fn sanitize_component(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut last_dash = false;
    for ch in s.chars() {
        if ch.is_ascii_alphanumeric() || ch == '-' {
            out.push(ch);
            last_dash = false;
        } else if !last_dash {
            out.push('-');
            last_dash = true;
        }
    }
    let trimmed = out.trim_matches('-');
    if trimmed.is_empty() {
        "x".to_string()
    } else {
        trimmed.to_string()
    }
}

/// tmux-safe session name, e.g. `ab__biocortex-rs__codex`.
pub fn tmux_session_name(project: &str, role: &str) -> String {
    format!(
        "{STEER_PREFIX}{}{STEER_DELIM}{}",
        sanitize_component(project),
        sanitize_component(role)
    )
}

/// Human-facing logical handle, e.g. `ab:biocortex-rs:codex` (display only).
pub fn logical_handle(project: &str, role: &str) -> String {
    format!("ab:{project}:{role}")
}

/// Recover `(project, role)` from a tmux session name produced by
/// [`tmux_session_name`]. Returns `None` for non-steer names.
pub fn parse_tmux_session(name: &str) -> Option<(String, String)> {
    let rest = name.strip_prefix(STEER_PREFIX)?;
    let parts: Vec<&str> = rest.split(STEER_DELIM).collect();
    if parts.len() == 2 && !parts[0].is_empty() && !parts[1].is_empty() {
        Some((parts[0].to_string(), parts[1].to_string()))
    } else {
        None
    }
}

/// Synthetic presence session id for an AB-owned steer handle.
pub fn steer_presence_id(node: &str, session: &str) -> String {
    format!("steer:{node}:{session}")
}

// ── shell quoting ───────────────────────────────────────────────────────────

/// POSIX single-quote escape so arbitrary text is safe inside an `sh -c`
/// string (locally) or a remote ssh command line.
pub fn shq(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('\'');
    for ch in s.chars() {
        if ch == '\'' {
            out.push_str("'\\''");
        } else {
            out.push(ch);
        }
    }
    out.push('\'');
    out
}

// ── target ──────────────────────────────────────────────────────────────────

/// Where a multiplexer command runs: locally, or on a tailnet node over ssh.
#[derive(Debug, Clone, Default)]
pub struct Target {
    /// `None` = run locally. `Some(host)` = ssh to this node/IP.
    pub node: Option<String>,
    /// ssh user (only used when `node` is set).
    pub user: Option<String>,
}

impl Target {
    pub fn local() -> Self {
        Self::default()
    }

    pub fn is_local(&self) -> bool {
        self.node.is_none()
    }

    /// `user@host` or `host`, for ssh and for display.
    pub fn label(&self) -> String {
        match &self.node {
            None => "local".to_string(),
            Some(n) => match &self.user {
                Some(u) => format!("{u}@{n}"),
                None => n.clone(),
            },
        }
    }
}

/// Result of running one (possibly remote) shell command.
#[derive(Debug, Clone, Serialize)]
pub struct RunResult {
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
    /// True when the command was killed for exceeding the timeout.
    pub timed_out: bool,
}

impl RunResult {
    pub fn ok(&self) -> bool {
        self.code == 0 && !self.timed_out
    }
}

/// Run `shell_cmd` on `target`. Locally it goes through `sh -c` with a
/// homebrew-augmented PATH so a brew-installed tmux is found; remotely it is
/// handed to `ssh <dest> <shell_cmd>` (the remote login shell parses it).
pub async fn run_shell(target: &Target, shell_cmd: &str, timeout: Duration) -> RunResult {
    let mut builder = match &target.node {
        None => {
            let mut b = TokioCommand::new("sh");
            b.arg("-c").arg(shell_cmd);
            let base = std::env::var("PATH").unwrap_or_default();
            b.env("PATH", format!("/opt/homebrew/bin:/usr/local/bin:{base}"));
            b
        }
        Some(node) => {
            let dest = match &target.user {
                Some(u) => format!("{u}@{node}"),
                None => node.clone(),
            };
            let mut b = TokioCommand::new("ssh");
            b.arg("-o")
                .arg("BatchMode=yes")
                .arg("-o")
                .arg("ConnectTimeout=10")
                .arg(dest)
                .arg(shell_cmd);
            b
        }
    };
    builder.stdout(std::process::Stdio::piped());
    builder.stderr(std::process::Stdio::piped());

    let child = match builder.spawn() {
        Ok(c) => c,
        Err(e) => {
            return RunResult {
                code: -1,
                stdout: String::new(),
                stderr: format!("spawn failed: {e}"),
                timed_out: false,
            }
        }
    };

    match tokio::time::timeout(timeout, child.wait_with_output()).await {
        Err(_) => RunResult {
            code: -1,
            stdout: String::new(),
            stderr: format!("timed out after {} ms", timeout.as_millis()),
            timed_out: true,
        },
        Ok(Err(e)) => RunResult {
            code: -1,
            stdout: String::new(),
            stderr: format!("wait failed: {e}"),
            timed_out: false,
        },
        Ok(Ok(out)) => RunResult {
            code: out.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&out.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&out.stderr).into_owned(),
            timed_out: false,
        },
    }
}

// ── multiplexer backend ───────────────────────────────────────────────────

/// A terminal multiplexer. Methods return the *shell command string* to run
/// (locally or via ssh), keeping the backend pure and unit-testable.
pub trait Multiplexer: Send + Sync {
    fn name(&self) -> &'static str;
    /// Detached launch of `command` in session `session`.
    fn launch_cmd(
        &self,
        session: &str,
        command: &str,
        cwd: Option<&str>,
        env: &[(String, String)],
    ) -> String;
    /// Send literal `text`; submit it with Enter when `submit`.
    fn send_cmd(&self, session: &str, text: &str, submit: bool) -> String;
    /// Send a named key event (e.g. `Enter`, `C-c`) — NOT literal text. Used
    /// to auto-answer gates. `key` must be a tmux key token.
    fn send_key_cmd(&self, session: &str, key: &str) -> String;
    /// Print the last `lines` of the pane (incl. scrollback) to stdout.
    fn capture_cmd(&self, session: &str, lines: u32) -> String;
    /// One-line pane metadata for a structured snapshot, formatted as
    /// `w=<cols> h=<rows> cx=<cursor_x> cy=<cursor_y>` (0-based cursor).
    fn snapshot_meta_cmd(&self, session: &str) -> String;
    /// Like [`Self::capture_cmd`] but KEEPS SGR escapes (so highlighted /
    /// reverse-video menu items survive) and joins wrapped lines.
    fn capture_styled_cmd(&self, session: &str, lines: u32) -> String;
    /// Exit 0 iff the session exists.
    fn has_cmd(&self, session: &str) -> String;
    /// One session name per line.
    fn list_cmd(&self) -> String;
    fn kill_cmd(&self, session: &str) -> String;
}

/// tmux backend. `bin` defaults to `tmux` (override for an absolute path).
#[derive(Debug, Clone)]
pub struct TmuxBackend {
    pub bin: String,
}

impl Default for TmuxBackend {
    fn default() -> Self {
        Self {
            bin: std::env::var("AB_TMUX_BIN").unwrap_or_else(|_| "tmux".to_string()),
        }
    }
}

impl Multiplexer for TmuxBackend {
    fn name(&self) -> &'static str {
        "tmux"
    }

    fn launch_cmd(
        &self,
        session: &str,
        command: &str,
        cwd: Option<&str>,
        env: &[(String, String)],
    ) -> String {
        let mut cmd = format!("{} new-session -d -s {}", self.bin, shq(session));
        if let Some(c) = cwd {
            cmd.push_str(&format!(" -c {}", shq(c)));
        }
        for (k, v) in env {
            cmd.push_str(&format!(" -e {}", shq(&format!("{k}={v}"))));
        }
        cmd.push_str(&format!(" {}", shq(command)));
        cmd
    }

    fn send_cmd(&self, session: &str, text: &str, submit: bool) -> String {
        // Pane-target commands (send-keys/capture-pane) must use the BARE
        // session name: tmux's `=` exact-match prefix only applies to
        // session targets, and treats `=name` as a literal *pane* name here
        // ("can't find pane"). A bare name resolves to the exact session when
        // it exists (the drive flow has-session-checks first). `-l` sends text
        // literally so `C-c`-like substrings are not interpreted as keys;
        // Enter is a separate, non-literal key event.
        let mut cmd = format!(
            "{bin} send-keys -t {sess} -l -- {txt}",
            bin = self.bin,
            sess = session,
            txt = shq(text),
        );
        if submit {
            cmd.push_str(&format!(" ; {} send-keys -t {} Enter", self.bin, session));
        }
        cmd
    }

    fn send_key_cmd(&self, session: &str, key: &str) -> String {
        format!("{} send-keys -t {} {}", self.bin, session, key)
    }

    fn capture_cmd(&self, session: &str, lines: u32) -> String {
        format!(
            "{bin} capture-pane -p -t {sess} -S -{lines}",
            bin = self.bin,
            sess = session,
            lines = lines,
        )
    }

    fn snapshot_meta_cmd(&self, session: &str) -> String {
        // Pane-target (bare session name, like capture). `cursor_x/y` are
        // 0-based and pane-relative, aligning with `capture-pane -p` lines.
        format!(
            "{bin} display-message -p -t {sess} \
             'w=#{{pane_width}} h=#{{pane_height}} cx=#{{cursor_x}} cy=#{{cursor_y}}'",
            bin = self.bin,
            sess = session,
        )
    }

    fn capture_styled_cmd(&self, session: &str, lines: u32) -> String {
        // `-e` keeps SGR escapes; `-J` joins wrapped lines so a styled line
        // aligns by index with the plain capture.
        format!(
            "{bin} capture-pane -p -e -J -t {sess} -S -{lines}",
            bin = self.bin,
            sess = session,
            lines = lines,
        )
    }

    fn has_cmd(&self, session: &str) -> String {
        // Session-target command: `=` forces exact-name matching (no prefix
        // or fnmatch), so `ab__a__b` never resolves to `ab__a__bc`.
        //
        // The `=session` token MUST be single-quoted. On a remote target whose
        // login shell is zsh (macOS default), an unquoted leading `=` triggers
        // zsh equals-expansion (`=foo` → path of command `foo`): it fails with
        // "foo not found", masks the exit code as 0, and tmux never runs — so
        // `has_session().ok()` reads true for a session that doesn't exist
        // (launch falsely reports "already live"). Quoting passes the literal
        // `=session` through to tmux on both zsh and bash/sh. Wet-test found:
        // bash never expands `=`, so this only bit the real cross-node path.
        format!(
            "{} has-session -t {}",
            self.bin,
            shq(&format!("={session}"))
        )
    }

    fn list_cmd(&self) -> String {
        // 2>/dev/null so "no server running" is an empty list, not an error.
        format!(
            "{} list-sessions -F '#{{session_name}}' 2>/dev/null",
            self.bin
        )
    }

    fn kill_cmd(&self, session: &str) -> String {
        // Quote `=session` for the same zsh equals-expansion reason as has_cmd;
        // unquoted, a remote zsh would mangle it and the kill silently no-ops
        // (exit 0, session left alive as an orphan).
        format!(
            "{} kill-session -t {}",
            self.bin,
            shq(&format!("={session}"))
        )
    }
}

// ── high-level async ops ────────────────────────────────────────────────────

pub async fn has_session(target: &Target, mux: &dyn Multiplexer, session: &str) -> bool {
    run_shell(target, &mux.has_cmd(session), Duration::from_secs(15))
        .await
        .ok()
}

/// Launch `command` detached in `session`; returns Ok(true) once the session
/// is confirmed present, Ok(false) if launch ran but the session is absent
/// (command exited immediately), or Err on transport failure.
pub async fn launch(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    command: &str,
    cwd: Option<&str>,
    env: &[(String, String)],
) -> Result<bool, String> {
    let cmd = mux.launch_cmd(session, command, cwd, env);
    let r = run_shell(target, &cmd, Duration::from_secs(20)).await;
    if !r.ok() {
        return Err(format!(
            "launch failed (code {}): {}",
            r.code,
            r.stderr.trim()
        ));
    }
    Ok(has_session(target, mux, session).await)
}

// ── prompt injection profile (OB-3) ─────────────────────────────────────────
//
// How a given agent CLI accepts an injected prompt. Maps orca's
// `promptInjectionMode` onto AB terms (see docs/design/ORCA_BORROW_PLAN §4 OB-3).
// The mux layer (`Multiplexer`) stays ORTHOGONAL: it describes tmux/rmux, this
// describes the *CLI's* input contract. The two compose at `send_profiled`.

/// The way a CLI consumes its prompt at steer time.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InjectionMode {
    /// Launch bare, then type the prompt into the running TUI and submit. AB's
    /// only currently-exercised mode (orca: `flag-interactive`).
    FlagInteractive,
    /// Prompt supplied at launch (argv / `--prompt`); a running session does not
    /// take a fresh prompt via the TUI (orca: `argv` / `flag-prompt`). Runtime
    /// steer `send` is therefore unsupported for such a backend.
    LaunchOnly,
    /// Prompt piped to the process stdin after start (orca: `stdin-after-start`).
    /// Not expressible via `tmux send-keys`; reserved for a future stdin mux.
    StdinAfterStart,
}

/// Per-CLI prompt-injection descriptor consumed by `send_profiled`. `submit_key`
/// is the tmux key token used to submit after the literal text (re-validated by
/// `send_key`). `needs_quiet_render` asks the caller to confirm the pane is
/// input-ready before injecting; `paste_safe` records whether the CLI's composer
/// tolerates a trailing Enter after bulk literal input — `false` means the
/// long-prompt / bracketed-paste submit gotcha may apply and a caller may prefer
/// a split submit. These two flags are advisory (the steer driver / future
/// quiet-render logic reads them); `mode` and `submit_key` drive `send_profiled`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InjectionProfile {
    pub mode: InjectionMode,
    pub submit_key: String,
    pub needs_quiet_render: bool,
    pub paste_safe: bool,
}

impl Default for InjectionProfile {
    /// The conservative default == AB's historical steer behavior: type the text
    /// literally, submit with a single `Enter`, no quiet-render gating, paste
    /// safety NOT assumed. Every unverified backend resolves to this so the
    /// mechanism can never regress a working path.
    fn default() -> Self {
        Self {
            mode: InjectionMode::FlagInteractive,
            submit_key: "Enter".to_string(),
            needs_quiet_render: false,
            paste_safe: false,
        }
    }
}

/// Classify a backend label (a `Frontend` label like `claude-code`, or a steer
/// session role) into an [`InjectionProfile`]. **Verify-first discipline**: ONLY
/// rows confirmed by a real wet-test may diverge from [`InjectionProfile::default`];
/// every other backend returns the default verbatim, pending per-row
/// falsification (ORCA_BORROW_PLAN §4 OB-3 C-table). The explicit arms below are
/// the falsification slots — fill a row's profile only after its wet-test, never
/// from a hypothesis.
pub fn injection_profile(backend: &str) -> InjectionProfile {
    match backend.trim().to_ascii_lowercase().as_str() {
        // Confirmed path: the primary tested steer flow (type-then-Enter works).
        // paste/multi-line edge is still unverified, so paste_safe stays false
        // (identical to default) until a wet-test confirms the composer.
        "claude-code" | "claudecode" | "claude" => InjectionProfile::default(),
        // Pending wet-test (C-table ⚠️ rows). Listed as explicit no-ops so the
        // falsification work has obvious, greppable slots:
        "codex" | "codex-cli" | "gemini-cli" | "warp" | "auggie" | "local-cli" => {
            InjectionProfile::default()
        }
        // IDE-embedded backends are very likely NOT tmux-steerable at all; their
        // profile is N/A pending a probe, so default (and the steer launch path
        // would not target them via tmux in the first place).
        "codex-ide" | "cursor" => InjectionProfile::default(),
        _ => InjectionProfile::default(),
    }
}

/// Inject `text` into `session` and (when `submit`) submit it per `profile`.
/// With the default profile (`submit_key == "Enter"`) this is byte-identical to
/// the historical single-command path. A non-`Enter` submit key types the text
/// literally (no Enter), then sends the profile's key as a separate validated
/// key event — the seam for fixing the long-prompt / bracketed-paste gotcha
/// once a backend's row is wet-tested.
pub async fn send_profiled(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    text: &str,
    submit: bool,
    profile: &InjectionProfile,
) -> Result<(), String> {
    if profile.mode == InjectionMode::LaunchOnly {
        return Err(
            "backend takes its prompt only at launch; runtime steer send is unsupported".to_string(),
        );
    }
    if profile.mode == InjectionMode::StdinAfterStart {
        return Err(
            "backend expects stdin injection; not expressible via tmux send-keys".to_string(),
        );
    }
    // Default Enter submit (or no submit): the historical combined command.
    if !submit || profile.submit_key == "Enter" {
        let r = run_shell(
            target,
            &mux.send_cmd(session, text, submit),
            Duration::from_secs(15),
        )
        .await;
        return if r.ok() {
            Ok(())
        } else {
            Err(format!("send failed (code {}): {}", r.code, r.stderr.trim()))
        };
    }
    // Non-default submit key: type literally (no Enter), then submit separately.
    let r = run_shell(
        target,
        &mux.send_cmd(session, text, false),
        Duration::from_secs(15),
    )
    .await;
    if !r.ok() {
        return Err(format!("send failed (code {}): {}", r.code, r.stderr.trim()));
    }
    send_key(target, mux, session, &profile.submit_key).await
}

/// Inject `text` into `session`, submitting with `Enter` when `submit`. Routes
/// through [`send_profiled`] with the default profile, so behavior is unchanged
/// from the historical path; callers that know the backend can use
/// [`send_profiled`] with [`injection_profile`] to opt into a tuned profile.
pub async fn send(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    text: &str,
    submit: bool,
) -> Result<(), String> {
    send_profiled(
        target,
        mux,
        session,
        text,
        submit,
        &InjectionProfile::default(),
    )
    .await
}

/// Send a named key event (e.g. `Enter`) to auto-answer a gate. `key` is
/// validated to a conservative token set so it can never inject shell syntax.
pub async fn send_key(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    key: &str,
) -> Result<(), String> {
    if key.is_empty()
        || !key
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(format!("refusing to send unsafe key token: {key:?}"));
    }
    let r = run_shell(
        target,
        &mux.send_key_cmd(session, key),
        Duration::from_secs(15),
    )
    .await;
    if r.ok() {
        Ok(())
    } else {
        Err(format!(
            "send_key failed (code {}): {}",
            r.code,
            r.stderr.trim()
        ))
    }
}

pub async fn capture(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    lines: u32,
) -> Result<String, String> {
    let r = run_shell(
        target,
        &mux.capture_cmd(session, lines),
        Duration::from_secs(15),
    )
    .await;
    if r.ok() {
        Ok(clean_capture(&r.stdout))
    } else {
        Err(format!(
            "capture failed (code {}): {}",
            r.code,
            r.stderr.trim()
        ))
    }
}

/// Like [`capture`] but returns a structured [`PaneSnapshot`] (dimensions,
/// cursor, cleaned lines, highlighted-line indices). The meta/styled probes are
/// best-effort: a backend that cannot supply them yields an empty cursor /
/// no highlights rather than an error, so the plain capture still drives gate
/// detection.
pub async fn capture_snapshot(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    lines: u32,
) -> Result<PaneSnapshot, String> {
    let plain = run_shell(
        target,
        &mux.capture_cmd(session, lines),
        Duration::from_secs(15),
    )
    .await;
    if !plain.ok() {
        return Err(format!(
            "capture failed (code {}): {}",
            plain.code,
            plain.stderr.trim()
        ));
    }
    let meta = run_shell(
        target,
        &mux.snapshot_meta_cmd(session),
        Duration::from_secs(15),
    )
    .await;
    let styled = run_shell(
        target,
        &mux.capture_styled_cmd(session, lines),
        Duration::from_secs(15),
    )
    .await;
    let meta_s = if meta.ok() {
        meta.stdout
    } else {
        String::new()
    };
    let styled_s = if styled.ok() {
        styled.stdout
    } else {
        String::new()
    };
    Ok(PaneSnapshot::parse(&meta_s, &plain.stdout, &styled_s))
}

/// List live steerable (`ab__`) session names on `target`.
pub async fn list_steer_sessions(
    target: &Target,
    mux: &dyn Multiplexer,
) -> Result<Vec<String>, String> {
    let r = run_shell(target, &mux.list_cmd(), Duration::from_secs(15)).await;
    if r.timed_out {
        return Err(r.stderr);
    }
    Ok(r.stdout
        .lines()
        .map(|l| l.trim())
        .filter(|l| l.starts_with(STEER_PREFIX))
        .map(|l| l.to_string())
        .collect())
}

pub async fn kill(target: &Target, mux: &dyn Multiplexer, session: &str) -> Result<(), String> {
    let r = run_shell(target, &mux.kill_cmd(session), Duration::from_secs(15)).await;
    if r.ok() {
        Ok(())
    } else {
        Err(format!(
            "kill failed (code {}): {}",
            r.code,
            r.stderr.trim()
        ))
    }
}

// ── capture cleaning ────────────────────────────────────────────────────────

/// Strip ANSI escape sequences (CSI + OSC) and trim trailing blank lines, so a
/// captured TUI pane reads cleanly in a tool result.
pub fn clean_capture(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut chars = raw.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\u{1b}' {
            match chars.peek() {
                // CSI: ESC [ ... <final byte 0x40..=0x7e>
                Some('[') => {
                    chars.next();
                    for d in chars.by_ref() {
                        if ('\u{40}'..='\u{7e}').contains(&d) {
                            break;
                        }
                    }
                }
                // OSC: ESC ] ... (BEL | ESC \)
                Some(']') => {
                    chars.next();
                    while let Some(d) = chars.next() {
                        if d == '\u{07}' {
                            break;
                        }
                        if d == '\u{1b}' {
                            if let Some('\\') = chars.peek() {
                                chars.next();
                            }
                            break;
                        }
                    }
                }
                // Other 2-byte escapes — drop the escape, keep nothing extra.
                _ => {
                    chars.next();
                }
            }
        } else {
            out.push(c);
        }
    }
    // Trim trailing blank lines.
    let trimmed: Vec<&str> = out.lines().collect();
    let mut end = trimmed.len();
    while end > 0 && trimmed[end - 1].trim().is_empty() {
        end -= 1;
    }
    trimmed[..end].join("\n")
}

// ── structured snapshot ──────────────────────────────────────────────────────

/// A structured snapshot of a pane: dimensions, cursor position, cleaned lines,
/// and which lines carried a reverse-video (highlight) SGR. This is richer
/// input for gate detection than flat ANSI-stripped text — the cursor row marks
/// the *active* prompt and a highlighted line marks the *selected* menu option.
///
/// The shape intentionally mirrors a terminal-multiplexer pane snapshot so a
/// future non-tmux backend (e.g. an in-process SDK) could fill the same struct
/// without changing [`detect_gate`]'s structured path.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct PaneSnapshot {
    pub cols: u16,
    pub rows: u16,
    /// 0-based pane-relative `(x, y)` cursor; `None` if it could not be read.
    pub cursor: Option<(u16, u16)>,
    /// Cleaned (ANSI-stripped) pane lines, top-to-bottom, trailing blanks
    /// trimmed (same cleaning as [`clean_capture`]).
    pub lines: Vec<String>,
    /// Indices into [`Self::lines`] that contained a reverse-video span — the
    /// likely "selected" item in a TUI menu.
    pub highlighted: Vec<usize>,
    /// [`Self::lines`] joined with `\n` — the back-compatible flat text, equal
    /// to what [`clean_capture`] would produce.
    pub text: String,
}

impl PaneSnapshot {
    /// The line the cursor currently sits on, if the cursor row is in range.
    pub fn cursor_line(&self) -> Option<&str> {
        let y = self.cursor?.1 as usize;
        self.lines.get(y).map(String::as_str)
    }

    /// Build from raw backend outputs: a `meta` line
    /// (`w=.. h=.. cx=.. cy=..`), the `plain` capture, and the `styled`
    /// (SGR-preserving) capture. `meta` and `styled` may be empty.
    pub fn parse(meta: &str, plain: &str, styled: &str) -> Self {
        let (mut cols, mut rows) = (0u16, 0u16);
        let (mut cx, mut cy): (Option<u16>, Option<u16>) = (None, None);
        for tok in meta.split_whitespace() {
            let Some((k, v)) = tok.split_once('=') else {
                continue;
            };
            match k {
                "w" => cols = v.parse().unwrap_or(0),
                "h" => rows = v.parse().unwrap_or(0),
                "cx" => cx = v.parse().ok(),
                "cy" => cy = v.parse().ok(),
                _ => {}
            }
        }
        let cursor = match (cx, cy) {
            (Some(x), Some(y)) => Some((x, y)),
            _ => None,
        };

        let cleaned = clean_capture(plain);
        let lines: Vec<String> = if cleaned.is_empty() {
            Vec::new()
        } else {
            cleaned.lines().map(str::to_string).collect()
        };

        // A styled line aligns by index with the plain line (both `-J`-joined).
        let mut highlighted = Vec::new();
        for (i, sline) in styled.lines().enumerate() {
            if i >= lines.len() {
                break;
            }
            if line_has_reverse_sgr(sline) {
                highlighted.push(i);
            }
        }

        let text = lines.join("\n");
        Self {
            cols,
            rows,
            cursor,
            lines,
            highlighted,
            text,
        }
    }
}

/// True iff `s` contains an SGR sequence with the reverse-video parameter `7`.
/// A highlighted menu item is typically `ESC[7m…ESC[0m` — the span is closed
/// before the line ends, so we test for *presence* of `7`, not whether reverse
/// is still active at end-of-line. Foreground colours like `37` are distinct
/// `;`-delimited tokens and never match.
fn line_has_reverse_sgr(s: &str) -> bool {
    let bytes = s.as_bytes();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == 0x1b && bytes[i + 1] == b'[' {
            let start = i + 2;
            let mut j = start;
            while j < bytes.len() && !bytes[j].is_ascii_alphabetic() {
                j += 1;
            }
            if j < bytes.len() && bytes[j] == b'm' && s[start..j].split(';').any(|p| p == "7") {
                return true;
            }
            i = j + 1;
        } else {
            i += 1;
        }
    }
    false
}

// ── gate detection ──────────────────────────────────────────────────────────

/// How a detected TUI prompt may be handled.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GateClass {
    /// Safe for the driver to answer automatically (e.g. trust-this-folder).
    AutoAnswerable,
    /// A judgment/cost/safety decision — surface to a human, never auto-answer.
    NeedsHuman,
}

/// A blocking prompt detected in a captured pane.
#[derive(Debug, Clone, Serialize)]
pub struct Gate {
    pub kind: &'static str,
    pub class: GateClass,
    /// Key to send if `class == AutoAnswerable`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggested_key: Option<&'static str>,
    /// The matched line, for the human.
    pub excerpt: String,
}

fn matched_line(capture: &str, needles: &[&str]) -> Option<String> {
    for line in capture.lines().rev().take(30) {
        let low = line.to_ascii_lowercase();
        if needles.iter().all(|n| low.contains(n)) {
            return Some(line.trim().to_string());
        }
    }
    None
}

fn matched_any(capture: &str, alternatives: &[&[&str]]) -> Option<String> {
    alternatives
        .iter()
        .find_map(|set| matched_line(capture, set))
}

/// Classify the most recent blocking prompt in a captured pane, if any.
///
/// Only the trust-folder prompt is auto-answerable; quota/model-switch,
/// command-approval, and any unrecognized numbered/`?` prompt are `needs_human`
/// — consistent with the steering boundary (no blind auto-answering of
/// judgment/cost/safety decisions).
pub fn detect_gate(capture: &str) -> Option<Gate> {
    // Trust-this-folder (auto-answerable).
    if let Some(line) = matched_any(
        capture,
        &[
            &["trust", "folder"],
            &["trust", "directory"],
            &["trust", "workspace"],
            &["allow", "codex", "work"],
            &["do you trust"],
        ],
    ) {
        return Some(Gate {
            kind: "trust_dir",
            class: GateClass::AutoAnswerable,
            suggested_key: Some("Enter"),
            excerpt: line,
        });
    }

    // Quota / model-switch (needs human — cost/quality judgment).
    if let Some(line) = matched_any(
        capture,
        &[
            &["usage limit"],
            &["approaching", "limit"],
            &["rate limit"],
            &["weekly limit"],
            &["switch to", "model"],
            &["smaller model"],
        ],
    ) {
        return Some(Gate {
            kind: "quota_model_switch",
            class: GateClass::NeedsHuman,
            suggested_key: None,
            excerpt: line,
        });
    }

    // Command approval (needs human — safety).
    if let Some(line) = matched_any(
        capture,
        &[
            &["allow this command"],
            &["approve", "command"],
            &["run this command"],
            &["allow command"],
            &["(y/n)"],
            &["[y/n]"],
        ],
    ) {
        return Some(Gate {
            kind: "approval",
            class: GateClass::NeedsHuman,
            suggested_key: None,
            excerpt: line,
        });
    }

    // Unrecognized multiple-choice prompt (1) … 2) …) — surface to human.
    let has_opt = |n: &str| {
        capture.lines().rev().take(30).any(|l| {
            let t = l.trim_start();
            t.starts_with(&format!("{n})")) || t.starts_with(&format!("{n}."))
        })
    };
    if has_opt("1") && has_opt("2") {
        let excerpt = capture
            .lines()
            .rev()
            .take(30)
            .find(|l| {
                let t = l.trim_start();
                t.starts_with("1)") || t.starts_with("1.")
            })
            .map(|l| l.trim().to_string())
            .unwrap_or_default();
        return Some(Gate {
            kind: "unknown_choice",
            class: GateClass::NeedsHuman,
            suggested_key: None,
            excerpt,
        });
    }

    None
}

/// Does `l` look like a selectable menu option, e.g. `1) Yes`, `2. No`,
/// `> 1. Yes`? Used by the structured path to recognise a choice prompt even
/// when no wording needle matched.
fn is_option_line(l: &str) -> bool {
    let t = l
        .trim_start()
        .trim_start_matches(['>', '*', '•', '-'])
        .trim_start();
    let mut cs = t.chars();
    match cs.next() {
        Some(d) if d.is_ascii_digit() => matches!(cs.next(), Some(')') | Some('.') | Some(' ')),
        _ => false,
    }
}

/// Structured-snapshot gate detection. Delegates wording + class to
/// [`detect_gate`] (single source of truth — so the trust-folder prompt stays
/// the only auto-answerable gate), then uses cursor / highlight signal to:
///
/// 1. replace the excerpt with the actually-*highlighted* option, which the
///    flat-text path cannot see, and
/// 2. catch a reverse-video menu with no literal `1)`/`1.` markers as an
///    `unknown_choice` — always `NeedsHuman`, never blind-answered.
pub fn detect_gate_snapshot(snap: &PaneSnapshot) -> Option<Gate> {
    if let Some(mut gate) = detect_gate(&snap.text) {
        if let Some(line) = snap
            .highlighted
            .first()
            .and_then(|&i| snap.lines.get(i))
            .map(|l| l.trim())
            .filter(|l| !l.is_empty())
        {
            gate.excerpt = line.to_string();
        }
        return Some(gate);
    }

    // No wording match, but a highlighted menu of ≥2 option-like lines is still
    // a blocking choice the human must resolve.
    if !snap.highlighted.is_empty() {
        let option_like = snap.lines.iter().filter(|l| is_option_line(l)).count();
        if option_like >= 2 {
            let excerpt = snap
                .highlighted
                .first()
                .and_then(|&i| snap.lines.get(i))
                .map(|l| l.trim().to_string())
                .unwrap_or_default();
            return Some(Gate {
                kind: "unknown_choice",
                class: GateClass::NeedsHuman,
                suggested_key: None,
                excerpt,
            });
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_keeps_dash_collapses_rest() {
        assert_eq!(sanitize_component("biocortex-rs"), "biocortex-rs");
        assert_eq!(sanitize_component("foo_bar"), "foo-bar");
        assert_eq!(sanitize_component("a:b.c d"), "a-b-c-d");
        assert_eq!(sanitize_component("__weird__"), "weird");
        assert_eq!(sanitize_component(""), "x");
    }

    #[test]
    fn session_name_and_roundtrip() {
        let s = tmux_session_name("biocortex-rs", "codex");
        assert_eq!(s, "ab__biocortex-rs__codex");
        assert_eq!(
            parse_tmux_session(&s),
            Some(("biocortex-rs".to_string(), "codex".to_string()))
        );
        assert_eq!(parse_tmux_session("random"), None);
        assert_eq!(parse_tmux_session("ab__only-one"), None);
    }

    #[test]
    fn shq_escapes_single_quotes() {
        assert_eq!(shq("plain"), "'plain'");
        assert_eq!(shq("it's"), "'it'\\''s'");
    }

    #[test]
    fn tmux_cmds_use_exact_target() {
        let b = TmuxBackend {
            bin: "tmux".to_string(),
        };
        // Pane targets are bare; session targets are exact-matched (`=`).
        assert!(b
            .send_cmd("ab__p__r", "hi", true)
            .contains("send-keys -t ab__p__r -l"));
        assert!(!b.send_cmd("ab__p__r", "hi", true).contains("-t =ab__p__r"));
        assert!(b.send_cmd("ab__p__r", "hi", true).contains("Enter"));
        assert!(!b.send_cmd("ab__p__r", "hi", false).contains("Enter"));
        assert!(b
            .capture_cmd("ab__p__r", 10)
            .contains("capture-pane -p -t ab__p__r"));
        // `=session` must be SINGLE-QUOTED: an unquoted leading `=` is mangled
        // by a remote zsh login shell (equals-expansion), which made has_session
        // read true for absent sessions and kill silently no-op. Regression guard.
        assert!(b.has_cmd("ab__p__r").contains("has-session -t '=ab__p__r'"));
        assert!(b
            .kill_cmd("ab__p__r")
            .contains("kill-session -t '=ab__p__r'"));
        assert!(!b.has_cmd("ab__p__r").contains("has-session -t =ab__p__r"));
        assert!(!b.kill_cmd("ab__p__r").contains("kill-session -t =ab__p__r"));
        let launch = b.launch_cmd(
            "ab__p__r",
            "codex resume",
            Some("/tmp"),
            &[("K".into(), "V".into())],
        );
        assert!(launch.contains("new-session -d -s 'ab__p__r'"));
        assert!(launch.contains("-c '/tmp'"));
        assert!(launch.contains("-e 'K=V'"));
        assert!(launch.contains("'codex resume'"));
    }

    #[test]
    fn injection_profile_defaults_are_conservative() {
        let d = InjectionProfile::default();
        assert_eq!(d.mode, InjectionMode::FlagInteractive);
        assert_eq!(d.submit_key, "Enter");
        assert!(!d.needs_quiet_render);
        assert!(!d.paste_safe);
    }

    #[test]
    fn injection_profile_known_backends_resolve_to_default_pending_wettest() {
        // Until a backend's C-table row is wet-tested, every label resolves to
        // the conservative default so the mechanism never regresses a path.
        for b in [
            "claude-code",
            "ClaudeCode",
            "claude",
            "codex",
            "codex-cli",
            "gemini-cli",
            "warp",
            "auggie",
            "local-cli",
            "codex-ide",
            "cursor",
            "totally-unknown-backend",
            "",
        ] {
            assert_eq!(
                injection_profile(b),
                InjectionProfile::default(),
                "backend {b:?} should resolve to default until wet-tested"
            );
        }
    }

    #[test]
    fn injection_profile_is_case_and_whitespace_insensitive() {
        assert_eq!(
            injection_profile("  CLAUDE-CODE  "),
            injection_profile("claude-code")
        );
    }

    #[test]
    fn clean_capture_strips_ansi_and_trailing_blanks() {
        let raw = "\u{1b}[31mred\u{1b}[0m line\n\u{1b}]0;title\u{07}ok\n\n\n";
        assert_eq!(clean_capture(raw), "red line\nok");
    }

    #[test]
    fn snapshot_parse_dims_cursor_and_lines() {
        let meta = "w=100 h=24 cx=8 cy=2";
        let plain = "Do you trust this folder?\n> 1. Yes\n  2. No\n\n\n";
        let snap = PaneSnapshot::parse(meta, plain, "");
        assert_eq!((snap.cols, snap.rows), (100, 24));
        assert_eq!(snap.cursor, Some((8, 2)));
        // Trailing blank lines trimmed by clean_capture.
        assert_eq!(snap.lines.len(), 3);
        assert_eq!(snap.cursor_line(), Some("  2. No"));
        assert_eq!(snap.text, "Do you trust this folder?\n> 1. Yes\n  2. No");
    }

    #[test]
    fn snapshot_missing_meta_yields_no_cursor() {
        let snap = PaneSnapshot::parse("", "line one\nline two", "");
        assert_eq!(snap.cursor, None);
        assert_eq!(snap.cursor_line(), None);
        assert_eq!(snap.lines.len(), 2);
    }

    #[test]
    fn snapshot_detects_reverse_video_highlight() {
        let plain = "  1. Yes\n  2. No";
        // The first option is wrapped in reverse-video and reset before EOL.
        let styled = "  \u{1b}[7m1. Yes\u{1b}[0m\n  2. No";
        let snap = PaneSnapshot::parse("", plain, styled);
        assert_eq!(snap.highlighted, vec![0]);
    }

    #[test]
    fn reverse_sgr_presence_not_fooled_by_fg_color_or_reset() {
        // foreground white (37) and reverse-off (27) must NOT count as reverse.
        assert!(!line_has_reverse_sgr("\u{1b}[37mwhite\u{1b}[0m"));
        assert!(!line_has_reverse_sgr("\u{1b}[27mno-reverse"));
        assert!(!line_has_reverse_sgr("plain text, no escapes"));
        // a closed reverse span and a bold+reverse combo both count.
        assert!(line_has_reverse_sgr("\u{1b}[7mrev\u{1b}[0m"));
        assert!(line_has_reverse_sgr("\u{1b}[1;7mbold-rev\u{1b}[0m"));
    }

    #[test]
    fn snapshot_gate_delegates_and_keeps_trust_auto_answerable() {
        let plain = "Do you trust the files in this folder?\n> 1. Yes\n  2. No";
        let snap = PaneSnapshot::parse("w=80 h=24 cx=0 cy=3", plain, "");
        let g = detect_gate_snapshot(&snap).expect("gate");
        assert_eq!(g.kind, "trust_dir");
        assert_eq!(g.class, GateClass::AutoAnswerable);
        assert_eq!(g.suggested_key, Some("Enter"));
    }

    #[test]
    fn snapshot_gate_excerpt_uses_highlighted_option() {
        let plain =
            "Approaching your weekly usage limit\n  1. Continue\n  2. Switch to a smaller model";
        let styled = "Approaching your weekly usage limit\n  1. Continue\n  \u{1b}[7m2. Switch to a smaller model\u{1b}[0m";
        let snap = PaneSnapshot::parse("", plain, styled);
        let g = detect_gate_snapshot(&snap).expect("gate");
        assert_eq!(g.kind, "quota_model_switch");
        assert_eq!(g.class, GateClass::NeedsHuman);
        // Excerpt is the actually-highlighted option (flat text cannot know this).
        assert_eq!(g.excerpt, "2. Switch to a smaller model");
    }

    #[test]
    fn snapshot_gate_catches_highlighted_menu_without_literal_markers() {
        // Options are arrow-prefixed, so no line *starts* with "1)"/"1." and the
        // flat-text classifier misses it entirely.
        let plain = "  Pick an action\n  > 1. Deploy to prod\n    2. Roll back";
        let styled = "  Pick an action\n  \u{1b}[7m> 1. Deploy to prod\u{1b}[0m\n    2. Roll back";
        let snap = PaneSnapshot::parse("", plain, styled);
        assert!(
            detect_gate(&snap.text).is_none(),
            "flat-text path should miss this menu"
        );
        let g = detect_gate_snapshot(&snap).expect("structured gate");
        assert_eq!(g.kind, "unknown_choice");
        assert_eq!(g.class, GateClass::NeedsHuman);
        assert_eq!(g.excerpt, "> 1. Deploy to prod");
    }

    #[test]
    fn is_option_line_recognises_common_menu_shapes() {
        assert!(is_option_line("1) Yes"));
        assert!(is_option_line("  2. No"));
        assert!(is_option_line("> 1. Yes"));
        assert!(is_option_line("- 3 Maybe"));
        assert!(!is_option_line("Do you trust this folder?"));
        assert!(!is_option_line("  Select: "));
    }

    #[test]
    fn gate_trust_is_auto_answerable() {
        let cap = "Do you want to allow Codex to work in this folder?\n  > Yes";
        let g = detect_gate(cap).expect("gate");
        assert_eq!(g.kind, "trust_dir");
        assert_eq!(g.class, GateClass::AutoAnswerable);
        assert_eq!(g.suggested_key, Some("Enter"));
    }

    #[test]
    fn gate_quota_needs_human() {
        let cap = "You are approaching your usage limit. Switch to a smaller model?\n1) yes\n2) no";
        let g = detect_gate(cap).expect("gate");
        assert_eq!(g.kind, "quota_model_switch");
        assert_eq!(g.class, GateClass::NeedsHuman);
        assert_eq!(g.suggested_key, None);
    }

    #[test]
    fn gate_unknown_choice_needs_human() {
        let cap = "Pick an option:\n1) alpha\n2) beta\n3) gamma";
        let g = detect_gate(cap).expect("gate");
        assert_eq!(g.kind, "unknown_choice");
        assert_eq!(g.class, GateClass::NeedsHuman);
    }

    #[test]
    fn no_gate_on_plain_output() {
        assert!(detect_gate("just some normal output\n• PONG\n").is_none());
    }

    /// End-to-end against a live LOCAL tmux. Ignored by default (needs tmux);
    /// run with `cargo test -p ab-bridge --lib remote_steer -- --ignored`.
    #[tokio::test]
    #[ignore]
    async fn e2e_local_launch_send_capture_kill() {
        let target = Target::local();
        let mux = TmuxBackend::default();
        let session = tmux_session_name("steertest", "rt");
        let _ = kill(&target, &mux, &session).await; // clean slate

        // `cat` keeps the session alive and echoes what we send.
        let present = launch(&target, &mux, &session, "cat", None, &[])
            .await
            .expect("launch");
        assert!(present, "session should exist after launch");
        assert!(has_session(&target, &mux, &session).await);

        send(&target, &mux, &session, "STEER_E2E_OK", true)
            .await
            .expect("send");
        tokio::time::sleep(Duration::from_millis(400)).await;
        let cap = capture(&target, &mux, &session, 20).await.expect("capture");
        assert!(
            cap.contains("STEER_E2E_OK"),
            "capture missing marker: {cap:?}"
        );

        let listed = list_steer_sessions(&target, &mux).await.expect("list");
        assert!(
            listed.contains(&session),
            "list missing session: {listed:?}"
        );

        kill(&target, &mux, &session).await.expect("kill");
        assert!(!has_session(&target, &mux, &session).await);
    }
}
