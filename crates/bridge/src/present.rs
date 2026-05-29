//! Output / expression lane — **E1 `present()` PresentationSink** (first cut).
//!
//! This is the *dual* of the input provider-resolver (desktop_snapshot's
//! `shell/CDP > swaymsg > AT-SPI > vision` ladder): instead of climbing the
//! most-direct way to *act on* the computer, it climbs the most-direct way to
//! *express a result*. The E1 rung is "static artifact": render a structured
//! result into a standalone HTML document that carries BOTH a human-facing
//! render AND a machine-facing structured payload (dual-encoding), plus
//! provenance, and is self-verified by loading it in the headless browser.
//!
//! Terminology note: this `E1` is the output-expression-lane E-ladder rung
//! (north-star memo `agent_bridge_northstar_bidirectional_bridge_20260529`).
//! It is NOT the capability-roadmap "E1" self-modification gap — different
//! taxonomies that collide on the label.
//!
//! This module is intentionally dependency-light (serde_json + std) so the
//! rendering / dual-encoding / classification logic is unit-testable without a
//! browser. The browser-driven self-verify orchestration lives in
//! `PresentTool::execute` (mcp_tools.rs), which feeds the page metrics it reads
//! back into [`classify_render`] here.

use serde_json::Value;
use std::io::Write as _;
use std::path::{Path, PathBuf};

/// Result envelope schema tag returned by the `present` tool.
pub const PRESENT_SCHEMA: &str = "present/v0";

/// The E1 static-artifact kinds the first cut can render.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PresentKind {
    /// Structured rows → HTML `<table>` (data from `payload`, else `artifact` as JSON).
    Table,
    /// A markdown pipe-table string → HTML `<table>`.
    MarkdownTable,
    /// A caller-supplied HTML fragment, inlined as body content (NOT sanitized — see risks).
    Html,
    /// Inline SVG markup.
    Svg,
    /// Mermaid diagram source (client-rendered via the mermaid ESM module).
    Mermaid,
}

impl PresentKind {
    pub fn parse(s: &str) -> Option<Self> {
        match s.trim().to_ascii_lowercase().as_str() {
            "table" => Some(Self::Table),
            "markdown_table" | "md_table" => Some(Self::MarkdownTable),
            "html" => Some(Self::Html),
            "svg" => Some(Self::Svg),
            "mermaid" => Some(Self::Mermaid),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Table => "table",
            Self::MarkdownTable => "markdown_table",
            Self::Html => "html",
            Self::Svg => "svg",
            Self::Mermaid => "mermaid",
        }
    }
}

/// Self-verify outcome. Stringified into the tool result so consumers can tell
/// "the browser actually rendered this" from "I never checked".
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VerifyStatus {
    /// Loaded in the browser and the body had visible content.
    RenderedOk,
    /// Loaded but the body produced nothing (no nodes, no text) — a real fault.
    Blank,
    /// No browser available / capability denied / launch failed — degraded, not failed.
    NoBrowser,
    /// The verify step itself errored (e.g. eval threw) — artifact still written.
    Error,
    /// Verify not requested.
    Skipped,
}

impl VerifyStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::RenderedOk => "rendered_ok",
            Self::Blank => "blank",
            Self::NoBrowser => "no_browser",
            Self::Error => "error",
            Self::Skipped => "skipped",
        }
    }
}

/// Content metrics read from the rendered page's `<body>`. Produced by the
/// browser-driven verify path; consumed by [`classify_render`]. Kept as a plain
/// struct so the decision is testable without a browser.
#[derive(Debug, Clone, Copy, Default)]
pub struct RenderMetrics {
    pub inner_html_len: usize,
    pub text_len: usize,
    pub node_count: usize,
}

/// The verify decision, isolated as a pure function so A3 ("an empty artifact
/// MUST report `blank`") is a deterministic unit test rather than a flaky
/// browser assertion. If this ever returned `RenderedOk` for empty metrics the
/// self-verify would be fake — that is exactly the falsifier.
pub fn classify_render(m: &RenderMetrics) -> VerifyStatus {
    if m.node_count == 0 && m.text_len == 0 {
        VerifyStatus::Blank
    } else {
        VerifyStatus::RenderedOk
    }
}

/// Parse the metrics object the verify JS returns. Tolerant of the backend
/// handing us either a JSON object or a JSON string (CDP returnByValue vs
/// stringified), so the real path doesn't depend on which one fires.
pub fn parse_metrics(v: &Value) -> RenderMetrics {
    let obj = match v {
        Value::String(s) => serde_json::from_str::<Value>(s).unwrap_or(Value::Null),
        other => other.clone(),
    };
    let g = |k: &str| obj.get(k).and_then(Value::as_u64).unwrap_or(0) as usize;
    RenderMetrics {
        inner_html_len: g("h"),
        text_len: g("t"),
        node_count: g("n"),
    }
}

/// The JS expression evaluated in the rendered page to produce [`RenderMetrics`].
/// Returns a JSON string `{h,t,n}`. Kept here so the contract with
/// [`parse_metrics`] stays in one place.
pub const VERIFY_METRICS_JS: &str = "JSON.stringify({h:document.body?document.body.innerHTML.trim().length:0,t:document.body?(document.body.innerText||'').trim().length:0,n:document.body?document.body.querySelectorAll('*').length:0})";

// ---------------------------------------------------------------------------
// HTML rendering (pure)
// ---------------------------------------------------------------------------

/// Local copy of the repo's `html_escape` (the existing copies in
/// daemon_http.rs / main.rs are module-private — duplicating the 12-line body
/// is the established convention, not a smell).
fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

/// Serialize a JSON value for safe embedding inside a `<script>` tag: escaping
/// `</` → `<\/` means the payload can never contain a literal `</script>`, so
/// it both terminates cleanly AND round-trips (a JSON parser decodes `\/` back
/// to `/`). Mirrors `html_json_script` (daemon_http.rs:3393).
fn json_script(value: &Value) -> String {
    serde_json::to_string(value)
        .unwrap_or_else(|_| "null".to_string())
        .replace("</", "<\\/")
}

fn value_to_cell(v: &Value) -> String {
    match v {
        Value::String(s) => html_escape(s),
        Value::Null => String::new(),
        other => html_escape(&other.to_string()),
    }
}

/// Render structured data to an HTML `<table>`. Arrays of objects become a
/// keyed table (column = union of keys); arrays of arrays/scalars become rows;
/// anything else is shown as pretty JSON in a `<pre>`.
fn render_table(data: &Value) -> String {
    let rows = match data {
        Value::Array(rows) => rows,
        other => {
            return format!(
                "<pre>{}</pre>",
                html_escape(&serde_json::to_string_pretty(other).unwrap_or_default())
            )
        }
    };
    if rows.is_empty() {
        return "<table></table>".to_string();
    }
    // Keyed table when every row is an object.
    let mut cols: Vec<String> = Vec::new();
    let all_objects = rows.iter().all(|r| r.is_object());
    if all_objects {
        for r in rows {
            if let Value::Object(map) = r {
                for k in map.keys() {
                    if !cols.iter().any(|c| c == k) {
                        cols.push(k.clone());
                    }
                }
            }
        }
    }
    if all_objects && !cols.is_empty() {
        let head: String = cols
            .iter()
            .map(|c| format!("<th>{}</th>", html_escape(c)))
            .collect();
        let body: String = rows
            .iter()
            .map(|r| {
                let cells: String = cols
                    .iter()
                    .map(|c| {
                        format!(
                            "<td>{}</td>",
                            r.get(c).map(value_to_cell).unwrap_or_default()
                        )
                    })
                    .collect();
                format!("<tr>{cells}</tr>")
            })
            .collect();
        format!("<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    } else {
        let body: String = rows
            .iter()
            .map(|r| match r {
                Value::Array(cells) => {
                    let tds: String = cells
                        .iter()
                        .map(|c| format!("<td>{}</td>", value_to_cell(c)))
                        .collect();
                    format!("<tr>{tds}</tr>")
                }
                other => format!("<tr><td>{}</td></tr>", value_to_cell(other)),
            })
            .collect();
        format!("<table><tbody>{body}</tbody></table>")
    }
}

/// Convert a markdown pipe-table into an HTML `<table>`. The first non-separator
/// row is the header; `|---|` separator rows are dropped.
fn render_markdown_table(src: &str) -> String {
    let mut rows: Vec<Vec<String>> = Vec::new();
    for line in src.lines() {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        let nopipe: String = t
            .chars()
            .filter(|c| !matches!(c, '|' | '-' | ':' | ' '))
            .collect();
        if nopipe.is_empty() && t.contains('-') {
            continue; // separator row
        }
        let cells: Vec<String> = t
            .trim_matches('|')
            .split('|')
            .map(|c| c.trim().to_string())
            .collect();
        rows.push(cells);
    }
    if rows.is_empty() {
        return "<table></table>".to_string();
    }
    let head: String = rows[0]
        .iter()
        .map(|c| format!("<th>{}</th>", html_escape(c)))
        .collect();
    let body: String = rows[1..]
        .iter()
        .map(|r| {
            let tds: String = r
                .iter()
                .map(|c| format!("<td>{}</td>", html_escape(c)))
                .collect();
            format!("<tr>{tds}</tr>")
        })
        .collect();
    format!("<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
}

fn render_body(kind: PresentKind, artifact: &str, payload: Option<&Value>) -> String {
    match kind {
        PresentKind::Table => {
            // Prefer the structured payload; fall back to parsing the artifact as JSON.
            let owned;
            let data: &Value = match payload {
                Some(p) => p,
                None => {
                    owned = serde_json::from_str::<Value>(artifact).unwrap_or(Value::Null);
                    &owned
                }
            };
            render_table(data)
        }
        PresentKind::MarkdownTable => render_markdown_table(artifact),
        // Caller-intended markup — inlined raw. Sanitization of untrusted HTML
        // is explicitly out of scope for the first cut (documented risk).
        PresentKind::Html | PresentKind::Svg => artifact.to_string(),
        PresentKind::Mermaid => format!(
            "<pre class=\"mermaid\">{}</pre>\
             <script type=\"module\">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';mermaid.initialize({{startOnLoad:true}});</script>",
            html_escape(artifact)
        ),
    }
}

/// Build the complete standalone HTML document: human render + embedded
/// machine-facing `#ab-payload` (dual-encoding) + `#ab-provenance`.
///
/// CSS braces in the template are doubled per the `format!` raw-string idiom.
pub fn build_html(
    kind: PresentKind,
    artifact: &str,
    title: Option<&str>,
    payload: Option<&Value>,
    provenance: Option<&Value>,
) -> String {
    let title_str = title.unwrap_or("Agent-Bridge present/v0");
    let body = render_body(kind, artifact, payload);

    let payload_script = match payload {
        Some(p) => format!(
            "<script type=\"application/json\" id=\"ab-payload\">{}</script>",
            json_script(p)
        ),
        None => String::new(),
    };
    let prov_script = match provenance {
        Some(pv) => format!(
            "<script type=\"application/json\" id=\"ab-provenance\">{}</script>",
            json_script(pv)
        ),
        None => String::new(),
    };
    let prov_footer = match provenance {
        Some(pv) => format!(
            "<footer id=\"ab-provenance-view\">provenance: {}</footer>",
            html_escape(&serde_json::to_string(pv).unwrap_or_default())
        ),
        None => String::new(),
    };

    format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="generator" content="agent-bridge {schema}">
<title>{title}</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:24px;color:#1a1a2e;background:#fafafe}}
table{{border-collapse:collapse;margin:8px 0}}
th,td{{border:1px solid #c7c7e0;padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#eaeaf6}}
pre{{background:#f4f4fb;padding:10px;border-radius:6px;overflow:auto}}
footer{{margin-top:28px;font-size:11px;color:#9a9ab0;border-top:1px solid #e3e3ef;padding-top:8px;word-break:break-all}}
</style></head>
<body>
{body}
{payload_script}
{prov_script}
{prov_footer}
</body></html>"#,
        schema = PRESENT_SCHEMA,
        title = html_escape(title_str),
        body = body,
        payload_script = payload_script,
        prov_script = prov_script,
        prov_footer = prov_footer,
    )
}

/// Recover a `<script type="application/json" id="...">` payload from a rendered
/// artifact. This is the *consumer* side of dual-encoding: another agent reads
/// structured data straight out of the HTML instead of OCR-ing the pixels.
pub fn extract_script_json(html: &str, id: &str) -> Option<Value> {
    let marker = format!("id=\"{id}\">");
    let start = html.find(&marker)? + marker.len();
    let rest = &html[start..];
    let end = rest.find("</script>")?;
    serde_json::from_str(&rest[..end]).ok()
}

/// Convenience: recover the embedded `#ab-payload` structured payload.
pub fn extract_ab_payload(html: &str) -> Option<Value> {
    extract_script_json(html, "ab-payload")
}

// ---------------------------------------------------------------------------
// Filesystem (sink)
// ---------------------------------------------------------------------------

/// Stable 16-hex content id (FNV-1a). Local copy per the repo convention
/// (`fnv1a_hex16` exists privately in mcp_tools.rs / rescue.rs).
pub fn derive_id(content: &str) -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for b in content.as_bytes() {
        hash ^= u64::from(*b);
        hash = hash.wrapping_mul(0x1000_0000_01b3);
    }
    format!("{hash:016x}")
}

/// `~/.cache/agent-bridge/presentations` (override: `AGENT_BRIDGE_PRESENTATIONS_DIR`).
/// Follows the XDG_CACHE_HOME → HOME/.cache fallback used at sync.rs:418.
pub fn presentations_dir() -> PathBuf {
    if let Ok(d) = std::env::var("AGENT_BRIDGE_PRESENTATIONS_DIR") {
        if !d.is_empty() {
            return PathBuf::from(d);
        }
    }
    let base = std::env::var("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::var("HOME")
                .map(|h| PathBuf::from(h).join(".cache"))
                .unwrap_or_else(|_| PathBuf::from("/tmp"))
        });
    base.join("agent-bridge").join("presentations")
}

/// Atomic write: tmp-then-rename (mirrors sync.rs:436), creating parents.
pub fn write_artifact_atomic(path: &Path, contents: &str) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension(format!("tmp-{}", std::process::id()));
    {
        let mut f = std::fs::File::create(&tmp)?;
        f.write_all(contents.as_bytes())?;
        f.sync_all()?;
    }
    std::fs::rename(&tmp, path)?;
    Ok(())
}

pub fn now_unix() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn kind_parse_roundtrip() {
        for k in [
            PresentKind::Table,
            PresentKind::MarkdownTable,
            PresentKind::Html,
            PresentKind::Svg,
            PresentKind::Mermaid,
        ] {
            assert_eq!(PresentKind::parse(k.as_str()), Some(k));
        }
        assert_eq!(PresentKind::parse("nope"), None);
    }

    // A1 — a table payload renders a real HTML <table> with the cell values.
    #[test]
    fn a1_table_renders_html_table() {
        let payload = json!([{"name": "e5", "dims": 384}, {"name": "MiniLM", "dims": 384}]);
        let html = build_html(PresentKind::Table, "", Some("dims"), Some(&payload), None);
        assert!(html.contains("<!doctype html>"));
        assert!(html.contains("<table>"));
        assert!(html.contains("<th>name</th>"));
        assert!(html.contains("<th>dims</th>"));
        assert!(html.contains("<td>e5</td>"));
        assert!(html.contains("<td>MiniLM</td>"));
    }

    // A2 — dual-encoding byte round-trip, including a payload that contains "</"
    // (which the script-embed escapes to "<\/" and a JSON parser decodes back).
    #[test]
    fn a2_dual_encoding_roundtrips_even_with_close_tag() {
        let payload = json!([{"a": 1, "b": "danger</script><x></y>"}]);
        let html = build_html(PresentKind::Table, "", None, Some(&payload), None);
        // The raw HTML must NOT contain a literal "</script>" inside the payload.
        let recovered = extract_ab_payload(&html).expect("payload must be recoverable");
        assert_eq!(recovered, payload);
    }

    // A3 — the verify classifier is real: empty body → blank, content → ok.
    #[test]
    fn a3_classify_render_blank_vs_ok() {
        let empty = RenderMetrics::default();
        assert_eq!(classify_render(&empty), VerifyStatus::Blank);

        let content = RenderMetrics {
            inner_html_len: 120,
            text_len: 14,
            node_count: 7,
        };
        assert_eq!(classify_render(&content), VerifyStatus::RenderedOk);

        // text but no element nodes (e.g. a bare string body) is still NOT blank.
        let text_only = RenderMetrics {
            inner_html_len: 5,
            text_len: 5,
            node_count: 0,
        };
        assert_eq!(classify_render(&text_only), VerifyStatus::RenderedOk);
    }

    // A3 — metrics parse tolerates both stringified and object forms from eval.
    #[test]
    fn a3_parse_metrics_string_and_object() {
        let s = parse_metrics(&json!("{\"h\":10,\"t\":3,\"n\":2}"));
        assert_eq!((s.inner_html_len, s.text_len, s.node_count), (10, 3, 2));
        let o = parse_metrics(&json!({"h": 9, "t": 0, "n": 0}));
        assert_eq!((o.inner_html_len, o.text_len, o.node_count), (9, 0, 0));
        // an empty body parsed from real eval → classified blank.
        assert_eq!(
            classify_render(&parse_metrics(&json!("{\"h\":0,\"t\":0,\"n\":0}"))),
            VerifyStatus::Blank
        );
    }

    // A4 — provenance is embedded; absence of payload means dual_encoding=false.
    #[test]
    fn a4_provenance_embedded_and_no_payload_means_no_dual_encoding() {
        let prov = json!({"generated_by": "present/v0", "source_tool": "memory_search"});
        let html = build_html(PresentKind::Html, "<p>hi</p>", None, None, Some(&prov));
        assert_eq!(extract_script_json(&html, "ab-provenance"), Some(prov));
        // no payload passed → not recoverable → caller reports dual_encoding=false
        assert_eq!(extract_ab_payload(&html), None);
    }

    #[test]
    fn markdown_table_parses_header_and_rows() {
        let md = "| name | dims |\n|------|------|\n| e5 | 384 |\n| minilm | 384 |";
        let html = build_html(PresentKind::MarkdownTable, md, None, None, None);
        assert!(html.contains("<th>name</th>"));
        assert!(html.contains("<th>dims</th>"));
        assert!(html.contains("<td>e5</td>"));
        assert!(html.contains("<td>minilm</td>"));
    }

    #[test]
    fn derive_id_is_stable_and_16_hex() {
        let a = derive_id("hello");
        let b = derive_id("hello");
        assert_eq!(a, b);
        assert_eq!(a.len(), 16);
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(derive_id("hello"), derive_id("world"));
    }

    #[test]
    fn atomic_write_roundtrip() {
        let dir = std::env::temp_dir().join(format!("ab-present-test-{}", std::process::id()));
        let path = dir.join("x.html");
        write_artifact_atomic(&path, "<p>hi</p>").unwrap();
        let read = std::fs::read_to_string(&path).unwrap();
        assert_eq!(read, "<p>hi</p>");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
