//! Streaming parser for OSC notification + shell-integration escape sequences.
//!
//! Supported payloads:
//!
//! | Code | Wire format                                    | Origin              |
//! |------|------------------------------------------------|---------------------|
//! |  9   | `ESC ] 9 ; BODY ST`                            | iTerm2 / WezTerm    |
//! |  99  | `ESC ] 99 ; { "title": "...", "body": "..." }` | agent-bridge custom |
//! |  133 | `ESC ] 133 ; A|B|C|D [;exit] ST`               | FinalTerm / iTerm2  |
//! |  777 | `ESC ] 777 ; notify ; TITLE ; BODY ST`         | urxvt / libnotify   |
//!
//! `ST` = `BEL` (`0x07`) or `ESC \` (`0x1B 0x5C`).
//!
//! OSC 133 carries shell-integration prompt markers (a.k.a. "FinalTerm"
//! prompt protocol). They let consumers segment a terminal stream into
//! discrete prompt / command / output regions without parsing prompt
//! visuals. `read_blocks` on the PTY backend uses these to recover the
//! same cmd → output mapping that the Warp IPC bridge provides.
//!
//! The parser is **streaming**: feed it chunks of arbitrary bytes via
//! [`OscParser::feed`] and it returns any complete events found, while
//! buffering partial sequences across calls.

use ab_core::{NotifyEvent, NotifySeverity, NotifySource};
use serde::{Deserialize, Serialize};

const ESC: u8 = 0x1B;
const BEL: u8 = 0x07;
const BACKSLASH: u8 = 0x5C;
const RBRACKET: u8 = 0x5D; // ']'

/// Cap on a single OSC body to protect against runaway payloads.
const MAX_BODY: usize = 64 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind")]
pub enum OscEvent {
    /// Successfully parsed notification.
    Notify(NotifyEvent),
    /// FinalTerm / iTerm2 OSC 133 shell-integration prompt marker. Carries
    /// no human-readable payload — it segments the byte stream into
    /// prompt / command-input / output / command-end regions.
    Prompt(PromptMarker),
    /// OSC 99 payload that wasn't valid JSON; surfaces the raw body so the
    /// caller can decide whether to drop or log.
    Malformed {
        code: u32,
        raw: String,
        reason: String,
    },
}

/// One item from [`OscParser::feed_segments`]: either a contiguous run
/// of non-OSC bytes that passed through the parser, or a finalised OSC
/// event. Used by `pty.rs` to slice the byte stream at OSC 133 marker
/// boundaries so command-input and output text land in the right
/// per-block buckets.
#[derive(Debug, Clone, PartialEq)]
pub enum FeedItem {
    Text(Vec<u8>),
    Event(OscEvent),
}

/// One OSC 133 prompt-protocol marker. See
/// <https://iterm2.com/documentation-shell-integration.html> and the
/// FinalTerm spec for full semantics.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "phase")]
pub enum PromptMarker {
    /// `OSC 133 ; A ST` — terminal is about to draw a fresh prompt.
    /// Resets per-command accumulator state.
    PromptStart,
    /// `OSC 133 ; B ST` — prompt finished drawing, the user (or shell
    /// pipeline) is about to type / inject the command.
    CommandInputStart,
    /// `OSC 133 ; C ST` — command has been submitted and is now executing;
    /// bytes after this until the next `D` are command output.
    OutputStart,
    /// `OSC 133 ; D [ ; <exit_code> ] ST` — command finished. Some shells
    /// omit the exit code, in which case `exit_code` is `None`.
    CommandEnd { exit_code: Option<i32> },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum State {
    Ground,
    Esc,        // saw ESC
    OscIntro,   // saw ESC ]
    OscBody,    // accumulating body
    OscBodyEsc, // inside body, saw ESC, waiting for '\\'
}

pub struct OscParser {
    state: State,
    buf: Vec<u8>,
}

impl Default for OscParser {
    fn default() -> Self {
        Self::new()
    }
}

impl OscParser {
    pub fn new() -> Self {
        Self {
            state: State::Ground,
            buf: Vec::new(),
        }
    }

    /// Feed bytes; returns any complete OSC events parsed.
    pub fn feed(&mut self, bytes: &[u8]) -> Vec<OscEvent> {
        self.feed_segments(bytes)
            .into_iter()
            .filter_map(|item| match item {
                FeedItem::Event(e) => Some(e),
                FeedItem::Text(_) => None,
            })
            .collect()
    }

    /// Like [`feed`], but interleaves complete OSC events with the
    /// runs of non-OSC bytes that passed between them. Lets callers
    /// segment a byte stream at OSC marker boundaries — needed for
    /// OSC-133-driven block bucketing in `pty.rs`. The parser still
    /// owns its multi-chunk continuation state, so cross-chunk OSC
    /// sequences are stitched back together correctly.
    pub fn feed_segments(&mut self, bytes: &[u8]) -> Vec<FeedItem> {
        let mut out = Vec::new();
        // Pending text in this chunk (bytes seen in Ground state).
        let mut text_buf: Vec<u8> = Vec::new();
        let flush_text = |text_buf: &mut Vec<u8>, out: &mut Vec<FeedItem>| {
            if !text_buf.is_empty() {
                out.push(FeedItem::Text(std::mem::take(text_buf)));
            }
        };
        for &b in bytes {
            match self.state {
                State::Ground => {
                    if b == ESC {
                        // End the text run before stepping into ESC.
                        flush_text(&mut text_buf, &mut out);
                        self.state = State::Esc;
                    } else {
                        text_buf.push(b);
                    }
                }
                State::Esc => {
                    if b == RBRACKET {
                        self.state = State::OscIntro;
                        self.buf.clear();
                    } else {
                        // Not actually an OSC; the lone ESC + the
                        // following byte are passthrough text. Emit
                        // both so the upstream stripper can handle them.
                        text_buf.push(ESC);
                        text_buf.push(b);
                        self.state = State::Ground;
                    }
                }
                State::OscIntro | State::OscBody => match b {
                    BEL => {
                        if let Some(evt) = self.finalise() {
                            out.push(FeedItem::Event(evt));
                        }
                        self.state = State::Ground;
                    }
                    ESC => self.state = State::OscBodyEsc,
                    _ => {
                        if self.buf.len() < MAX_BODY {
                            self.buf.push(b);
                        }
                        self.state = State::OscBody;
                    }
                },
                State::OscBodyEsc => {
                    if b == BACKSLASH {
                        // ST terminator
                        if let Some(evt) = self.finalise() {
                            out.push(FeedItem::Event(evt));
                        }
                        self.state = State::Ground;
                    } else {
                        // ESC followed by something else — recover.
                        if self.buf.len() < MAX_BODY {
                            self.buf.push(ESC);
                            self.buf.push(b);
                        }
                        self.state = State::OscBody;
                    }
                }
            }
        }
        flush_text(&mut text_buf, &mut out);
        out
    }

    fn finalise(&mut self) -> Option<OscEvent> {
        let body = std::mem::take(&mut self.buf);
        let s = String::from_utf8_lossy(&body).into_owned();
        Some(parse_body(&s))
    }
}

fn parse_body(s: &str) -> OscEvent {
    // Split on the first ';' to extract Ps (the numeric code).
    let (code_str, rest) = match s.split_once(';') {
        Some(p) => p,
        None => {
            return OscEvent::Malformed {
                code: 0,
                raw: s.to_string(),
                reason: "missing ';'".into(),
            };
        }
    };
    let code: u32 = match code_str.trim().parse() {
        Ok(n) => n,
        Err(_) => {
            return OscEvent::Malformed {
                code: 0,
                raw: s.to_string(),
                reason: "non-numeric code".into(),
            };
        }
    };

    match code {
        9 => OscEvent::Notify(NotifyEvent {
            source: NotifySource::Osc9,
            severity: NotifySeverity::Attention,
            title: "Terminal".into(),
            body: rest.to_string(),
            session_id: None,
            context: serde_json::Value::Null,
        }),
        99 => parse_osc99(rest),
        133 => parse_osc133(rest, s),
        777 => parse_osc777(rest),
        other => OscEvent::Malformed {
            code: other,
            raw: s.to_string(),
            reason: format!("unsupported OSC code {other}"),
        },
    }
}

/// Parse an OSC 133 body. Format: `<letter> [ ; <key=value | exit_code> ]*`.
/// We recognise A/B/C/D; ignore unknown key=value attributes (e.g. `aid=…`
/// from Warp's shell integration). For D, the second token is interpreted
/// as the command exit code if it parses as i32.
fn parse_osc133(rest: &str, full: &str) -> OscEvent {
    let mut parts = rest.split(';');
    let letter = parts.next().unwrap_or("").trim();
    let marker = match letter {
        "A" => PromptMarker::PromptStart,
        "B" => PromptMarker::CommandInputStart,
        "C" => PromptMarker::OutputStart,
        "D" => {
            // Find first non-key=value part — that's the exit code.
            let exit_code = parts
                .find(|p| !p.contains('='))
                .and_then(|s| s.trim().parse::<i32>().ok());
            PromptMarker::CommandEnd { exit_code }
        }
        other => {
            return OscEvent::Malformed {
                code: 133,
                raw: full.to_string(),
                reason: format!("unrecognised OSC 133 letter '{other}' (want A|B|C|D)"),
            };
        }
    };
    OscEvent::Prompt(marker)
}

fn parse_osc99(payload: &str) -> OscEvent {
    #[derive(Deserialize)]
    struct Wire {
        title: Option<String>,
        body: Option<String>,
        severity: Option<String>,
    }

    match serde_json::from_str::<Wire>(payload) {
        Ok(w) => OscEvent::Notify(NotifyEvent {
            source: NotifySource::Osc99,
            severity: w
                .severity
                .as_deref()
                .and_then(parse_sev)
                .unwrap_or(NotifySeverity::Info),
            title: w.title.unwrap_or_else(|| "agent-bridge".into()),
            body: w.body.unwrap_or_default(),
            session_id: None,
            context: serde_json::Value::Null,
        }),
        Err(e) => OscEvent::Malformed {
            code: 99,
            raw: payload.to_string(),
            reason: format!("invalid json: {e}"),
        },
    }
}

fn parse_osc777(payload: &str) -> OscEvent {
    // Format: notify;TITLE;BODY
    let mut parts = payload.splitn(3, ';');
    let head = parts.next().unwrap_or_default();
    if head != "notify" {
        return OscEvent::Malformed {
            code: 777,
            raw: payload.to_string(),
            reason: format!("expected 'notify;...', got '{head};...'"),
        };
    }
    let title = parts.next().unwrap_or("").to_string();
    let body = parts.next().unwrap_or("").to_string();
    OscEvent::Notify(NotifyEvent {
        source: NotifySource::Osc777,
        severity: NotifySeverity::Info,
        title,
        body,
        session_id: None,
        context: serde_json::Value::Null,
    })
}

fn parse_sev(s: &str) -> Option<NotifySeverity> {
    Some(match s {
        "info" => NotifySeverity::Info,
        "success" => NotifySeverity::Success,
        "warning" => NotifySeverity::Warning,
        "error" => NotifySeverity::Error,
        "attention" => NotifySeverity::Attention,
        _ => return None,
    })
}

// =========================================================================
//                                   Tests
// =========================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn one(parser: &mut OscParser, bytes: &[u8]) -> OscEvent {
        let evts = parser.feed(bytes);
        assert_eq!(evts.len(), 1, "expected 1 event, got {evts:?}");
        evts.into_iter().next().unwrap()
    }

    #[test]
    fn osc9_bel_terminator() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]9;hello world\x07");
        match evt {
            OscEvent::Notify(n) => {
                assert_eq!(n.source, NotifySource::Osc9);
                assert_eq!(n.body, "hello world");
                assert_eq!(n.severity, NotifySeverity::Attention);
            }
            _ => panic!("expected Notify"),
        }
    }

    #[test]
    fn osc9_st_terminator() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]9;st-form\x1b\\");
        match evt {
            OscEvent::Notify(n) => assert_eq!(n.body, "st-form"),
            _ => panic!("expected Notify"),
        }
    }

    #[test]
    fn osc777_notify_with_title_body() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]777;notify;Claude;PR review done\x07");
        match evt {
            OscEvent::Notify(n) => {
                assert_eq!(n.source, NotifySource::Osc777);
                assert_eq!(n.title, "Claude");
                assert_eq!(n.body, "PR review done");
            }
            _ => panic!("expected Notify"),
        }
    }

    #[test]
    fn osc99_json_payload_with_severity() {
        let mut p = OscParser::new();
        let payload = br#"\x1b]99;{"title":"Build","body":"failed","severity":"error"}\x07"#;
        // Replace literal escapes for the bytes parser:
        let mut bytes = Vec::new();
        for chunk in payload.split(|&b| b == b'\\') {
            bytes.extend_from_slice(chunk);
        }
        let _ = bytes; // unused — we build a real byte stream below.

        let mut buf = Vec::new();
        buf.push(0x1B);
        buf.push(b']');
        buf.extend_from_slice(br#"99;{"title":"Build","body":"failed","severity":"error"}"#);
        buf.push(0x07);

        let evt = one(&mut p, &buf);
        match evt {
            OscEvent::Notify(n) => {
                assert_eq!(n.source, NotifySource::Osc99);
                assert_eq!(n.title, "Build");
                assert_eq!(n.body, "failed");
                assert_eq!(n.severity, NotifySeverity::Error);
            }
            _ => panic!("expected Notify, got {evt:?}"),
        }
    }

    #[test]
    fn streaming_across_chunks() {
        let mut p = OscParser::new();
        assert!(p.feed(b"\x1b]9;par").is_empty());
        assert!(p.feed(b"tial ").is_empty());
        let evts = p.feed(b"chunked\x07");
        assert_eq!(evts.len(), 1);
        match &evts[0] {
            OscEvent::Notify(n) => assert_eq!(n.body, "partial chunked"),
            _ => panic!(),
        }
    }

    #[test]
    fn back_to_back_sequences() {
        let mut p = OscParser::new();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"\x1b]9;first\x07");
        buf.extend_from_slice(b"\x1b]777;notify;T;B\x07");
        let evts = p.feed(&buf);
        assert_eq!(evts.len(), 2);
    }

    #[test]
    fn unsupported_code_yields_malformed() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]42;whatever\x07");
        match evt {
            OscEvent::Malformed { code, .. } => assert_eq!(code, 42),
            _ => panic!(),
        }
    }

    #[test]
    fn osc777_wrong_keyword_is_malformed() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]777;something_else;X;Y\x07");
        assert!(matches!(evt, OscEvent::Malformed { code: 777, .. }));
    }

    #[test]
    fn ignores_garbage_between_sequences() {
        let mut p = OscParser::new();
        let evts = p.feed(b"some prompt $ \x1b]9;alert\x07more text");
        assert_eq!(evts.len(), 1);
    }

    #[test]
    fn osc99_invalid_json() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]99;{not json};\x07");
        assert!(matches!(evt, OscEvent::Malformed { code: 99, .. }));
    }

    // ── OSC 133 (FinalTerm prompt protocol) ────────────────────────────────

    #[test]
    fn osc133_a_is_prompt_start() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;A\x07");
        assert_eq!(evt, OscEvent::Prompt(PromptMarker::PromptStart));
    }

    #[test]
    fn osc133_b_is_command_input_start() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;B\x07");
        assert_eq!(evt, OscEvent::Prompt(PromptMarker::CommandInputStart));
    }

    #[test]
    fn osc133_c_is_output_start() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;C\x07");
        assert_eq!(evt, OscEvent::Prompt(PromptMarker::OutputStart));
    }

    #[test]
    fn osc133_d_without_exit_code() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;D\x07");
        assert_eq!(
            evt,
            OscEvent::Prompt(PromptMarker::CommandEnd { exit_code: None })
        );
    }

    #[test]
    fn osc133_d_with_exit_code_zero() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;D;0\x07");
        assert_eq!(
            evt,
            OscEvent::Prompt(PromptMarker::CommandEnd { exit_code: Some(0) })
        );
    }

    #[test]
    fn osc133_d_with_nonzero_exit_code() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;D;137\x07");
        assert_eq!(
            evt,
            OscEvent::Prompt(PromptMarker::CommandEnd {
                exit_code: Some(137)
            })
        );
    }

    #[test]
    fn osc133_a_with_extra_key_value_pairs_is_tolerated() {
        // Warp / iTerm2 emit `OSC 133 ; A ; aid=foo` etc. We don't care
        // about the metadata; only that the marker survives parsing.
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;A;aid=warp_block_42\x07");
        assert_eq!(evt, OscEvent::Prompt(PromptMarker::PromptStart));
    }

    #[test]
    fn osc133_d_ignores_key_value_pairs_when_finding_exit_code() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;D;aid=foo;42\x07");
        assert_eq!(
            evt,
            OscEvent::Prompt(PromptMarker::CommandEnd {
                exit_code: Some(42)
            })
        );
    }

    #[test]
    fn osc133_unknown_letter_is_malformed() {
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;Z\x07");
        match evt {
            OscEvent::Malformed { code, .. } => assert_eq!(code, 133),
            _ => panic!("expected Malformed"),
        }
    }

    #[test]
    fn osc133_streaming_full_command_lifecycle() {
        // Simulate a real shell session: prompt → input → output → end.
        // Verify all 4 markers come back in order.
        let mut p = OscParser::new();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"\x1b]133;A\x07");
        buf.extend_from_slice(b"$ ls /tmp"); // user input (raw bytes, no markers)
        buf.extend_from_slice(b"\x1b]133;B\x07");
        buf.extend_from_slice(b"\n"); // enter
        buf.extend_from_slice(b"\x1b]133;C\x07");
        buf.extend_from_slice(b"foo\nbar\n"); // command output
        buf.extend_from_slice(b"\x1b]133;D;0\x07");
        let evts = p.feed(&buf);
        assert_eq!(evts.len(), 4);
        assert_eq!(evts[0], OscEvent::Prompt(PromptMarker::PromptStart));
        assert_eq!(evts[1], OscEvent::Prompt(PromptMarker::CommandInputStart));
        assert_eq!(evts[2], OscEvent::Prompt(PromptMarker::OutputStart));
        assert_eq!(
            evts[3],
            OscEvent::Prompt(PromptMarker::CommandEnd { exit_code: Some(0) })
        );
    }

    #[test]
    fn osc133_st_terminator_form() {
        // Some shells emit OSC 133 with ESC \ instead of BEL.
        let mut p = OscParser::new();
        let evt = one(&mut p, b"\x1b]133;A\x1b\\");
        assert_eq!(evt, OscEvent::Prompt(PromptMarker::PromptStart));
    }

    // ── feed_segments — chunk-precise text/event interleaving ──────────────

    fn text_of(item: &FeedItem) -> &[u8] {
        match item {
            FeedItem::Text(b) => b,
            FeedItem::Event(_) => panic!("expected Text, got Event"),
        }
    }
    fn event_of(item: &FeedItem) -> &OscEvent {
        match item {
            FeedItem::Text(_) => panic!("expected Event, got Text"),
            FeedItem::Event(e) => e,
        }
    }

    #[test]
    fn segments_pure_text_is_one_text_item() {
        let mut p = OscParser::new();
        let items = p.feed_segments(b"hello world");
        assert_eq!(items.len(), 1);
        assert_eq!(text_of(&items[0]), b"hello world");
    }

    #[test]
    fn segments_pure_osc_is_one_event_item() {
        let mut p = OscParser::new();
        let items = p.feed_segments(b"\x1b]133;A\x07");
        assert_eq!(items.len(), 1);
        assert_eq!(
            *event_of(&items[0]),
            OscEvent::Prompt(PromptMarker::PromptStart)
        );
    }

    #[test]
    fn segments_text_then_marker_then_text_split_correctly() {
        // "foo" + OSC 133 A + "bar" → 3 items in order: Text, Event, Text.
        let mut p = OscParser::new();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"foo");
        buf.extend_from_slice(b"\x1b]133;A\x07");
        buf.extend_from_slice(b"bar");
        let items = p.feed_segments(&buf);
        assert_eq!(items.len(), 3);
        assert_eq!(text_of(&items[0]), b"foo");
        assert_eq!(
            *event_of(&items[1]),
            OscEvent::Prompt(PromptMarker::PromptStart)
        );
        assert_eq!(text_of(&items[2]), b"bar");
    }

    #[test]
    fn segments_full_command_lifecycle_yields_text_and_events() {
        // Realistic shell stream: prompt → command echo → output → end.
        let mut p = OscParser::new();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"\x1b]133;A\x07"); // prompt start
        buf.extend_from_slice(b"$ "); // shell prompt text
        buf.extend_from_slice(b"\x1b]133;B\x07"); // input start
        buf.extend_from_slice(b"ls /tmp\n"); // command + enter
        buf.extend_from_slice(b"\x1b]133;C\x07"); // output start
        buf.extend_from_slice(b"foo\nbar\n"); // output bytes
        buf.extend_from_slice(b"\x1b]133;D;0\x07"); // command end
        let items = p.feed_segments(&buf);

        // 4 events + 3 text spans = 7 items, in interleaved order.
        assert_eq!(items.len(), 7);
        assert!(matches!(&items[0], FeedItem::Event(_))); // A
        assert_eq!(text_of(&items[1]), b"$ "); // prompt rendering
        assert!(matches!(&items[2], FeedItem::Event(_))); // B
        assert_eq!(text_of(&items[3]), b"ls /tmp\n"); // command-input bytes
        assert!(matches!(&items[4], FeedItem::Event(_))); // C
        assert_eq!(text_of(&items[5]), b"foo\nbar\n"); // output bytes
        assert!(matches!(&items[6], FeedItem::Event(_))); // D
    }

    #[test]
    fn segments_partial_osc_across_chunks_does_not_leak_into_text() {
        // OSC sequence split across two feed calls. The parser must NOT
        // emit the sequence's bytes as text on either side of the boundary.
        let mut p = OscParser::new();
        let items1 = p.feed_segments(b"head\x1b]133;");
        // Only "head" is text; the partial OSC stays buffered internally.
        assert_eq!(items1.len(), 1);
        assert_eq!(text_of(&items1[0]), b"head");

        let items2 = p.feed_segments(b"A\x07tail");
        // Now the OSC closes and we see the tail text after it.
        assert_eq!(items2.len(), 2);
        assert_eq!(
            *event_of(&items2[0]),
            OscEvent::Prompt(PromptMarker::PromptStart)
        );
        assert_eq!(text_of(&items2[1]), b"tail");
    }

    #[test]
    fn segments_lone_esc_recovers_as_text() {
        // ESC not followed by ']' is not an OSC opener — those bytes
        // should resurface as text so downstream ANSI strip can handle
        // them (they may belong to a CSI / SS3 / etc.).
        let mut p = OscParser::new();
        let items = p.feed_segments(b"a\x1b[31mb"); // CSI red, not OSC
        // The "a" comes out, then ESC and '[' resurface as text, then "31mb".
        let mut all_text = Vec::new();
        for item in &items {
            if let FeedItem::Text(b) = item {
                all_text.extend_from_slice(b);
            }
        }
        assert_eq!(all_text, b"a\x1b[31mb");
        // No events for a CSI sequence.
        assert!(items.iter().all(|i| matches!(i, FeedItem::Text(_))));
    }

    #[test]
    fn feed_back_compat_returns_only_events() {
        // Confirm the public `feed` API is unchanged: text spans dropped,
        // only events surfaced. Existing callers (router.rs, mcp_tools.rs)
        // depend on this.
        let mut p = OscParser::new();
        let evts = p.feed(b"foo\x1b]133;C\x07bar\x1b]133;D;1\x07");
        assert_eq!(evts.len(), 2);
        assert_eq!(evts[0], OscEvent::Prompt(PromptMarker::OutputStart));
        assert_eq!(
            evts[1],
            OscEvent::Prompt(PromptMarker::CommandEnd { exit_code: Some(1) })
        );
    }
}
