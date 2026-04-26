//! Streaming parser for OSC notification escape sequences.
//!
//! Supported payloads:
//!
//! | Code | Wire format                                    | Origin              |
//! |------|------------------------------------------------|---------------------|
//! |  9   | `ESC ] 9 ; BODY ST`                            | iTerm2 / WezTerm    |
//! |  99  | `ESC ] 99 ; { "title": "...", "body": "..." }` | agent-bridge custom |
//! |  777 | `ESC ] 777 ; notify ; TITLE ; BODY ST`         | urxvt / libnotify   |
//!
//! `ST` = `BEL` (`0x07`) or `ESC \` (`0x1B 0x5C`).
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
    /// OSC 99 payload that wasn't valid JSON; surfaces the raw body so the
    /// caller can decide whether to drop or log.
    Malformed { code: u32, raw: String, reason: String },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum State {
    Ground,
    Esc,           // saw ESC
    OscIntro,      // saw ESC ]
    OscBody,       // accumulating body
    OscBodyEsc,    // inside body, saw ESC, waiting for '\\'
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
        let mut out = Vec::new();
        for &b in bytes {
            match self.state {
                State::Ground => {
                    if b == ESC {
                        self.state = State::Esc;
                    }
                }
                State::Esc => {
                    if b == RBRACKET {
                        self.state = State::OscIntro;
                        self.buf.clear();
                    } else {
                        self.state = State::Ground;
                    }
                }
                State::OscIntro | State::OscBody => match b {
                    BEL => {
                        if let Some(evt) = self.finalise() {
                            out.push(evt);
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
                            out.push(evt);
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
        777 => parse_osc777(rest),
        other => OscEvent::Malformed {
            code: other,
            raw: s.to_string(),
            reason: format!("unsupported OSC code {other}"),
        },
    }
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
        let payload =
            br#"\x1b]99;{"title":"Build","body":"failed","severity":"error"}\x07"#;
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
}
