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
//! Self-verify honesty: the human-rendered artifact is wrapped in a single
//! `<main id="ab-render">` element and ALL chrome (the dual-encoding /
//! provenance `<script>` blocks, the provenance footer) lives OUTSIDE it
//! (`<script>`s in `<head>`, footer after `</main>`). The verify metrics query
//! only `#ab-render`, so an artifact that renders nothing for a human reports
//! `blank` even though the document still carries provenance — without the
//! container the always-present chrome would make `blank` unreachable and the
//! falsifier fake.
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

/// The id of the container wrapping the human-rendered artifact. The verify
/// metrics query only inside this element so document chrome (provenance
/// scripts/footer) cannot inflate the "did it render" signal.
pub const RENDER_REGION_ID: &str = "ab-render";

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
    /// Loaded in the browser and the artifact region had visible content.
    RenderedOk,
    /// Loaded but the artifact region produced nothing visible — a real fault.
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

/// Content metrics read from the rendered `#ab-render` region. Produced by the
/// browser-driven verify path; consumed by [`classify_render`]. Kept as a plain
/// struct so the decision is testable without a browser.
#[derive(Debug, Clone, Copy, Default)]
pub struct RenderMetrics {
    /// `innerHTML.trim().length` of the region (diagnostic).
    pub inner_html_len: usize,
    /// `innerText.trim().length` of the region (visible text).
    pub text_len: usize,
    /// element count in the region, excluding `script`/`style` (diagnostic).
    pub node_count: usize,
    /// count of region elements with a non-empty `getClientRects()` (laid-out /
    /// visible). Catches `display:none`-only content as not-rendered.
    pub visible_count: usize,
}

/// The verify decision, isolated as a pure function so A3 ("an empty artifact
/// MUST report `blank`") is a deterministic unit test rather than a flaky
/// browser assertion. If this ever returned `RenderedOk` for empty metrics the
/// self-verify would be fake — that is exactly the falsifier.
///
/// `RenderedOk` means "the artifact region contains visible text or at least
/// one laid-out element". It does NOT assert pixel-level correctness (e.g. an
/// element rendered off-screen or fully transparent still counts) — the honest
/// guarantee is "something rendered into the artifact region", not "it looks
/// right".
pub fn classify_render(m: &RenderMetrics) -> VerifyStatus {
    if m.text_len == 0 && m.visible_count == 0 {
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
        visible_count: g("v"),
    }
}

/// The JS expression evaluated in the rendered page to produce [`RenderMetrics`].
/// Returns a JSON string `{h,t,n,v}` measured over `#ab-render` ONLY (so the
/// provenance chrome cannot inflate the signal). Keys MUST stay in sync with
/// [`parse_metrics`] — guarded by a unit canary.
pub const VERIFY_METRICS_JS: &str = "JSON.stringify((function(){var e=document.getElementById('ab-render');if(!e)return{h:0,t:0,n:0,v:0};var els=e.querySelectorAll('*:not(script):not(style)');var vis=0;els.forEach(function(x){if(x.getClientRects().length>0)vis++;});return{h:e.innerHTML.trim().length,t:(e.innerText||'').trim().length,n:els.length,v:vis};})())";

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

/// Normalize an incoming `present` payload before it is embedded.
///
/// The `payload` arg accepts any JSON shape, and some MCP clients serialize a
/// structured argument to a JSON *string* before sending it (the `payload`
/// schema historically declared no `type`, so a client defaults to string).
/// Left as-is, that string is embedded in `#ab-payload` quoted-and-escaped, so
/// a consumer's `JSON.parse` yields a string instead of the structure — the
/// dual-encoding footgun (forum #1786). When the value is a string that itself
/// parses to a JSON object or array, decode it; otherwise return it unchanged
/// (a genuine non-JSON string is not a structured payload). Mirrors
/// [`parse_metrics`]' tolerance for stringified JSON.
pub fn normalize_payload(v: &Value) -> Value {
    if let Value::String(s) = v {
        if let Ok(decoded) = serde_json::from_str::<Value>(s) {
            if decoded.is_object() || decoded.is_array() {
                return decoded;
            }
        }
    }
    v.clone()
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
                    .map(|c| format!("<td>{}</td>", r.get(c).map(value_to_cell).unwrap_or_default()))
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

/// True iff `cells_line` is a markdown table separator row (e.g. `|---|:--:|`).
fn is_md_separator(line: &str) -> bool {
    let nopipe: String = line
        .chars()
        .filter(|c| !matches!(c, '|' | '-' | ':' | ' '))
        .collect();
    nopipe.is_empty() && line.contains('-')
}

/// Convert a markdown pipe-table into an HTML `<table>`. The first row is the
/// header; ONLY the second row may be a `|---|` separator (so a legitimate
/// all-dashes data row elsewhere is not silently dropped).
fn render_markdown_table(src: &str) -> String {
    let lines: Vec<&str> = src
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();
    if lines.is_empty() {
        return "<table></table>".to_string();
    }
    let parse_row = |t: &str| -> Vec<String> {
        t.trim_matches('|')
            .split('|')
            .map(|c| c.trim().to_string())
            .collect()
    };
    let mut rows: Vec<Vec<String>> = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        if i == 1 && is_md_separator(line) {
            continue; // the canonical separator position
        }
        rows.push(parse_row(line));
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
        // is explicitly out of scope for the first cut (documented risk); the
        // caller is trusted for html/svg kinds.
        PresentKind::Html | PresentKind::Svg => artifact.to_string(),
        PresentKind::Mermaid => format!(
            "<pre class=\"mermaid\">{}</pre>\
             <script type=\"module\">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';mermaid.initialize({{startOnLoad:true}});</script>",
            html_escape(artifact)
        ),
    }
}

/// Build the complete standalone HTML document. Layout invariant (load-bearing
/// for self-verify honesty + dual-encoding extraction):
///   - `<head>` holds the `#ab-payload` / `#ab-provenance` JSON `<script>`s, so
///     [`extract_script_json`] (first-match) always returns the generator's
///     payload, never one injected inside a `kind=html` artifact body.
///   - the human render lives inside `<main id="ab-render">{body}</main>`.
///   - the provenance footer follows `</main>` (inside `<body>` but outside the
///     render region), so it never inflates the verify metrics.
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
{payload_script}
{prov_script}
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:24px;color:#1a1a2e;background:#fafafe}}
table{{border-collapse:collapse;margin:8px 0}}
th,td{{border:1px solid #c7c7e0;padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#eaeaf6}}
pre{{background:#f4f4fb;padding:10px;border-radius:6px;overflow:auto}}
footer{{margin-top:28px;font-size:11px;color:#9a9ab0;border-top:1px solid #e3e3ef;padding-top:8px;word-break:break-all}}
</style></head>
<body>
<main id="{region}">{body}</main>
{prov_footer}
</body></html>"#,
        schema = PRESENT_SCHEMA,
        title = html_escape(title_str),
        region = RENDER_REGION_ID,
        body = body,
        payload_script = payload_script,
        prov_script = prov_script,
        prov_footer = prov_footer,
    )
}

/// Recover a `<script type="application/json" id="...">` payload from a rendered
/// artifact. This is the *consumer* side of dual-encoding: another agent reads
/// structured data straight out of the HTML instead of OCR-ing the pixels.
/// Returns the FIRST match; the generator emits these in `<head>` so a payload
/// injected inside a `kind=html` body cannot shadow it.
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

/// The inner HTML of the `#ab-render` region — the human-render content only,
/// excluding provenance chrome. Used by tests to prove an empty artifact yields
/// an empty render region (so the browser metrics would classify it `blank`).
pub fn render_region(html: &str) -> Option<&str> {
    let marker = format!("<main id=\"{RENDER_REGION_ID}\">");
    let start = html.find(&marker)? + marker.len();
    let rest = &html[start..];
    let end = rest.find("</main>")?;
    Some(&rest[..end])
}

// ---------------------------------------------------------------------------
// Filesystem (sink)
// ---------------------------------------------------------------------------

/// Stable 16-hex id (FNV-1a) over the given canonical string. The CALLER chooses
/// what to hash: `PresentTool` hashes the content (kind+title+artifact+payload),
/// NOT the rendered HTML, so the id is content-addressed (identical content →
/// same id/path → dedupes) and does not drift with the per-call provenance ts.
/// Local copy per the repo convention (`fnv1a_hex16` exists privately elsewhere).
pub fn derive_id(canonical: &str) -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for b in canonical.as_bytes() {
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

/// Summary of a persisted presentation artifact, reconstructed from the
/// self-describing HTML — dual-encoding pays off here: the artifacts ARE the
/// index, so we read the embedded provenance/payload back out instead of
/// keeping a separate sidecar that could drift.
#[derive(Debug, Clone)]
pub struct ArtifactInfo {
    pub id: String,
    pub artifact_path: String,
    pub kind: Option<String>,
    pub ts: Option<u64>,
    pub generated_by: Option<String>,
    pub session_id: Option<String>,
    pub dual_encoding: bool,
    pub has_screenshot: bool,
    pub bytes: u64,
}

/// List persisted artifacts in `dir`, most-recent-first (by mtime), reading each
/// artifact's embedded `#ab-provenance` + `#ab-payload` to reconstruct the
/// index. `kind_filter` keeps only matching kinds. Missing/unreadable dir → [].
pub fn list_artifacts(dir: &Path, limit: usize, kind_filter: Option<&str>) -> Vec<ArtifactInfo> {
    let read = match std::fs::read_dir(dir) {
        Ok(r) => r,
        Err(_) => return Vec::new(),
    };
    let mut entries: Vec<(std::time::SystemTime, PathBuf)> = read
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("html"))
        .map(|p| {
            let mtime = std::fs::metadata(&p)
                .and_then(|m| m.modified())
                .unwrap_or(std::time::UNIX_EPOCH);
            (mtime, p)
        })
        .collect();
    entries.sort_by(|a, b| b.0.cmp(&a.0));

    let mut out = Vec::new();
    for (_, path) in entries {
        if out.len() >= limit {
            break;
        }
        let html = match std::fs::read_to_string(&path) {
            Ok(h) => h,
            Err(_) => continue,
        };
        let prov = extract_script_json(&html, "ab-provenance");
        let field = |k: &str| {
            prov.as_ref()
                .and_then(|p| p.get(k))
                .and_then(Value::as_str)
                .map(String::from)
        };
        let kind = field("kind");
        if let Some(want) = kind_filter {
            if kind.as_deref() != Some(want) {
                continue;
            }
        }
        out.push(ArtifactInfo {
            id: path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or_default()
                .to_string(),
            artifact_path: path.display().to_string(),
            kind,
            ts: prov
                .as_ref()
                .and_then(|p| p.get("ts"))
                .and_then(Value::as_u64),
            generated_by: field("generated_by"),
            session_id: field("session_id"),
            dual_encoding: extract_ab_payload(&html).is_some(),
            has_screenshot: path.with_extension("png").exists(),
            bytes: html.len() as u64,
        });
    }
    out
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

    // A1 — a table payload renders a real HTML <table> with the cell values,
    // inside the #ab-render region.
    #[test]
    fn a1_table_renders_html_table() {
        let payload = json!([{"name": "e5", "dims": 384}, {"name": "MiniLM", "dims": 384}]);
        let html = build_html(PresentKind::Table, "", Some("dims"), Some(&payload), None);
        assert!(html.contains("<!doctype html>"));
        assert!(html.contains("<main id=\"ab-render\">"));
        let region = render_region(&html).expect("render region");
        assert!(region.contains("<table>"));
        assert!(region.contains("<th>name</th>"));
        assert!(region.contains("<th>dims</th>"));
        assert!(region.contains("<td>e5</td>"));
        assert!(region.contains("<td>MiniLM</td>"));
    }

    // A2 — dual-encoding byte round-trip, including a payload that contains "</"
    // (escaped to "<\/" so the browser parser sees clean JSON and the embed
    // never terminates early). Asserts the escape directly, not just the trip.
    #[test]
    fn a2_dual_encoding_roundtrips_and_escapes_close_tag() {
        let payload = json!([{"a": 1, "b": "danger</script><x></y>"}]);
        let html = build_html(PresentKind::Table, "", None, Some(&payload), None);
        // The escape is actually applied …
        assert!(html.contains("danger<\\/script>"));
        // … and no literal "</script>" leaks from the payload value.
        assert!(!html.contains("danger</script>"));
        // … and the value round-trips byte-for-byte.
        let recovered = extract_ab_payload(&html).expect("payload must be recoverable");
        assert_eq!(recovered, payload);
    }

    // A2b — a kind=html artifact that itself contains a fake #ab-payload must
    // NOT shadow the generator's payload (generator emits in <head>, first-match).
    #[test]
    fn a2b_body_injected_payload_does_not_shadow_real_one() {
        let real = json!({"real": true});
        let evil_body = "<script type=\"application/json\" id=\"ab-payload\">{\"real\":false}</script><p>hi</p>";
        let html = build_html(PresentKind::Html, evil_body, None, Some(&real), None);
        assert_eq!(extract_ab_payload(&html), Some(real));
    }

    // #1786 falsifier — a client that JSON-stringifies a structured payload must
    // NOT yield a double-encoded #ab-payload. After normalize_payload the embed
    // recovers in a SINGLE JSON.parse; before the fix it round-tripped to a
    // String (the consumer footgun the dogfood caught).
    #[test]
    fn normalize_payload_undoes_client_double_encoding() {
        let structured = json!({"thesis": "north star", "lanes": ["in", "out"]});
        let as_string = Value::String(serde_json::to_string(&structured).unwrap());
        assert_eq!(normalize_payload(&as_string), structured);

        let arr = json!([{"x": 1}, {"x": 2}]);
        assert_eq!(
            normalize_payload(&Value::String(serde_json::to_string(&arr).unwrap())),
            arr
        );

        // Already-structured values pass through untouched; a genuine non-JSON
        // string stays a string (it is not a structured payload to decode).
        assert_eq!(normalize_payload(&structured), structured);
        assert_eq!(normalize_payload(&json!("just a label")), json!("just a label"));

        // End-to-end: normalize → build_html → extract recovers the object in
        // ONE parse (extract_ab_payload does a single from_str), proving the
        // double-encoding is gone.
        let html = build_html(
            PresentKind::Html,
            "<p>x</p>",
            None,
            Some(&normalize_payload(&as_string)),
            None,
        );
        assert_eq!(extract_ab_payload(&html), Some(structured));
    }

    // A3 — the verify classifier is real: empty region → blank, visible → ok,
    // and (the case the always-on chrome used to hide) nodes present but NOTHING
    // visible → blank.
    #[test]
    fn a3_classify_render_blank_vs_ok() {
        let empty = RenderMetrics::default();
        assert_eq!(classify_render(&empty), VerifyStatus::Blank);

        let visible = RenderMetrics {
            inner_html_len: 120,
            text_len: 14,
            node_count: 7,
            visible_count: 7,
        };
        assert_eq!(classify_render(&visible), VerifyStatus::RenderedOk);

        // elements exist but none are laid out / visible (e.g. display:none) and
        // there is no visible text → blank.
        let hidden_only = RenderMetrics {
            inner_html_len: 60,
            text_len: 0,
            node_count: 3,
            visible_count: 0,
        };
        assert_eq!(classify_render(&hidden_only), VerifyStatus::Blank);

        // visible text but zero element nodes (a bare text body) → rendered.
        let text_only = RenderMetrics {
            inner_html_len: 5,
            text_len: 5,
            node_count: 0,
            visible_count: 0,
        };
        assert_eq!(classify_render(&text_only), VerifyStatus::RenderedOk);
    }

    // A3 — metrics parse tolerates both stringified and object forms, incl `v`.
    #[test]
    fn a3_parse_metrics_string_and_object() {
        let s = parse_metrics(&json!("{\"h\":10,\"t\":3,\"n\":2,\"v\":2}"));
        assert_eq!(
            (s.inner_html_len, s.text_len, s.node_count, s.visible_count),
            (10, 3, 2, 2)
        );
        let o = parse_metrics(&json!({"h": 9, "t": 0, "n": 1, "v": 0}));
        assert_eq!((o.text_len, o.visible_count), (0, 0));
        assert_eq!(
            classify_render(&parse_metrics(&json!("{\"h\":0,\"t\":0,\"n\":0,\"v\":0}"))),
            VerifyStatus::Blank
        );
    }

    // A3 end-to-end logic (without a browser): an empty artifact yields an EMPTY
    // #ab-render region, so the metrics over that region would be all-zero and
    // classify blank. A table yields a non-empty region. This pins the seam the
    // adversarial review found broken (chrome inflating whole-body metrics).
    #[test]
    fn a3_empty_artifact_region_is_empty_table_is_not() {
        let prov = json!({"generated_by": "present/v0"});
        let empty_html = build_html(PresentKind::Html, "", None, None, Some(&prov));
        assert_eq!(render_region(&empty_html).map(str::trim), Some(""));

        let table_html = build_html(
            PresentKind::Table,
            "",
            None,
            Some(&json!([{"x": 1}])),
            Some(&prov),
        );
        assert!(!render_region(&table_html).unwrap().trim().is_empty());
    }

    // Canary: the JS that produces the metrics MUST emit the keys parse_metrics
    // reads, and MUST target the render region (not document.body). Cheap guard
    // against silent drift that would re-break the falsifier.
    #[test]
    fn verify_metrics_js_targets_region_and_keys_match() {
        assert!(VERIFY_METRICS_JS.contains("ab-render"));
        for key in ["h:", "t:", "n:", "v:"] {
            assert!(VERIFY_METRICS_JS.contains(key), "missing key {key}");
        }
    }

    // A4 — provenance is embedded (and recoverable from <head>); absence of
    // payload means dual_encoding=false (caller reports it).
    #[test]
    fn a4_provenance_embedded_and_no_payload_means_no_dual_encoding() {
        let prov = json!({"generated_by": "present/v0", "source_tool": "memory_search"});
        let html = build_html(PresentKind::Html, "<p>hi</p>", None, None, Some(&prov));
        assert_eq!(extract_script_json(&html, "ab-provenance"), Some(prov));
        assert_eq!(extract_ab_payload(&html), None);
    }

    #[test]
    fn markdown_table_parses_header_and_rows() {
        let md = "| name | dims |\n|------|------|\n| e5 | 384 |\n| minilm | 384 |";
        let html = build_html(PresentKind::MarkdownTable, md, None, None, None);
        let region = render_region(&html).unwrap();
        assert!(region.contains("<th>name</th>"));
        assert!(region.contains("<th>dims</th>"));
        assert!(region.contains("<td>e5</td>"));
        assert!(region.contains("<td>minilm</td>"));
    }

    // An all-dashes DATA row (not at the separator position) must survive.
    #[test]
    fn markdown_all_dash_data_row_is_kept() {
        let md = "| a | b |\n|---|---|\n| - | - |\n| x | y |";
        let html = build_html(PresentKind::MarkdownTable, md, None, None, None);
        let region = render_region(&html).unwrap();
        // header <tr> + 2 body <tr>: the all-dash data row survived; only the
        // idx-1 separator was dropped.
        assert_eq!(region.matches("<tr>").count(), 3);
        assert!(region.contains("<td>-</td>"));
        assert!(region.contains("<td>x</td>"));
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

    // list_artifacts reconstructs the index from the self-describing HTML
    // (provenance kind + payload presence), honoring the kind filter — proving
    // the dual-encoding consumer side end-to-end.
    #[test]
    fn list_artifacts_reads_kind_and_dual_encoding_from_files() {
        let dir = std::env::temp_dir().join(format!(
            "ab-present-list-test-{}-{}",
            std::process::id(),
            now_unix()
        ));
        let prov_t = json!({"generated_by": "present/v0", "kind": "table", "ts": 111});
        write_artifact_atomic(
            &dir.join("aaaaaaaaaaaaaaaa.html"),
            &build_html(PresentKind::Table, "", None, Some(&json!([{"x": 1}])), Some(&prov_t)),
        )
        .unwrap();
        let prov_h = json!({"generated_by": "present/v0", "kind": "html", "ts": 222});
        write_artifact_atomic(
            &dir.join("bbbbbbbbbbbbbbbb.html"),
            &build_html(PresentKind::Html, "<p>hi</p>", None, None, Some(&prov_h)),
        )
        .unwrap();

        let all = list_artifacts(&dir, 50, None);
        assert_eq!(all.len(), 2);

        let only_table = list_artifacts(&dir, 50, Some("table"));
        assert_eq!(only_table.len(), 1);
        assert_eq!(only_table[0].kind.as_deref(), Some("table"));
        assert!(only_table[0].dual_encoding, "table carried a payload");
        assert_eq!(only_table[0].ts, Some(111));

        let only_html = list_artifacts(&dir, 50, Some("html"));
        assert_eq!(only_html.len(), 1);
        assert!(!only_html[0].dual_encoding, "html had no payload");

        // missing dir → empty, no panic.
        assert!(list_artifacts(std::path::Path::new("/nonexistent/ab/xyz"), 10, None).is_empty());

        let _ = std::fs::remove_dir_all(&dir);
    }
}
