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

    fn has_cmd(&self, session: &str) -> String {
        // Session-target command: `=` forces exact-name matching (no prefix
        // or fnmatch), so `ab__a__b` never resolves to `ab__a__bc`.
        format!("{} has-session -t ={}", self.bin, session)
    }

    fn list_cmd(&self) -> String {
        // 2>/dev/null so "no server running" is an empty list, not an error.
        format!(
            "{} list-sessions -F '#{{session_name}}' 2>/dev/null",
            self.bin
        )
    }

    fn kill_cmd(&self, session: &str) -> String {
        format!("{} kill-session -t ={}", self.bin, session)
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

pub async fn send(
    target: &Target,
    mux: &dyn Multiplexer,
    session: &str,
    text: &str,
    submit: bool,
) -> Result<(), String> {
    let r = run_shell(
        target,
        &mux.send_cmd(session, text, submit),
        Duration::from_secs(15),
    )
    .await;
    if r.ok() {
        Ok(())
    } else {
        Err(format!(
            "send failed (code {}): {}",
            r.code,
            r.stderr.trim()
        ))
    }
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
        assert!(b.send_cmd("ab__p__r", "hi", true).contains("send-keys -t ab__p__r -l"));
        assert!(!b.send_cmd("ab__p__r", "hi", true).contains("-t =ab__p__r"));
        assert!(b.send_cmd("ab__p__r", "hi", true).contains("Enter"));
        assert!(!b.send_cmd("ab__p__r", "hi", false).contains("Enter"));
        assert!(b.capture_cmd("ab__p__r", 10).contains("capture-pane -p -t ab__p__r"));
        assert!(b.has_cmd("ab__p__r").contains("has-session -t =ab__p__r"));
        assert!(b.kill_cmd("ab__p__r").contains("kill-session -t =ab__p__r"));
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
    fn clean_capture_strips_ansi_and_trailing_blanks() {
        let raw = "\u{1b}[31mred\u{1b}[0m line\n\u{1b}]0;title\u{07}ok\n\n\n";
        assert_eq!(clean_capture(raw), "red line\nok");
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
        assert!(cap.contains("STEER_E2E_OK"), "capture missing marker: {cap:?}");

        let listed = list_steer_sessions(&target, &mux).await.expect("list");
        assert!(listed.contains(&session), "list missing session: {listed:?}");

        kill(&target, &mux, &session).await.expect("kill");
        assert!(!has_session(&target, &mux, &session).await);
    }
}
