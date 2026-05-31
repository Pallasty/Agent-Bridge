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
use sha2::{Digest, Sha256};
use std::io::Write as _;
use std::path::{Path, PathBuf};

/// Result envelope schema tag returned by the `present` tool.
pub const PRESENT_SCHEMA: &str = "present/v0";

/// Result envelope schema tag returned by the `present_dashboard` tool (E3).
pub const PRESENT_DASHBOARD_SCHEMA: &str = "present_dashboard/v0";

/// File stem (→ `_ab_dashboard.html`) of the E3 embodied-mirror surface. It is a
/// STABLE path (not content-addressed) so the human keeps one browser tab open
/// and every `present_dashboard` call refreshes the same file. It is excluded
/// from [`list_artifacts`] so the mirror never mirrors itself (which would feed
/// the dashboard back into the very `present_replay` chain it reflects). The
/// leading `_` also keeps it clear of the 16-hex content-addressed ids, which
/// never start with `_`.
pub const DASHBOARD_BASENAME: &str = "_ab_dashboard";

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

/// E2 (interactive artifact) self-verify outcome — the *second* honesty axis,
/// orthogonal to [`VerifyStatus`]. E1 asks "did it render"; E2 additionally asks
/// "is the interactivity REAL, not a dead control". Decided by the pure
/// [`classify_interactivity`] so a dead control is a deterministic unit test,
/// not a flaky live assertion.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InteractStatus {
    /// A control was driven headlessly and it actually changed the view (and the
    /// change was reversible — not a one-way wipe).
    Verified,
    /// A control exists/was expected but driving it did NOT change the view
    /// (missing handler, runtime threw, not wired) — a real fault.
    Dead,
    /// `interactive` was requested but this kind/payload is not enhanceable
    /// (e.g. non-table, or a non-keyed payload) — the tool added no interactivity
    /// and honestly says so (never `Dead` for something it didn't claim).
    NotApplicable,
    /// Too few rows to prove a filter changes the view (rowcount < 2).
    Skipped,
    /// No browser to drive the control (mirrors `VerifyStatus::NoBrowser`).
    NoBrowser,
    /// The interactivity probe itself errored.
    Error,
}

impl InteractStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Verified => "verified",
            Self::Dead => "dead",
            Self::NotApplicable => "not_applicable",
            Self::Skipped => "skipped",
            Self::NoBrowser => "no_browser",
            Self::Error => "error",
        }
    }
}

/// E3 (embodied-mirror) self-verify outcome — the output-expression ladder's
/// third honesty axis. E1 asks "did it render"; E2 "is the interactivity real";
/// E3 asks "does the persistent surface actually REFLECT the current lane state"
/// (the `present_replay` `chain_head`). Decided by the pure [`classify_embody`]
/// so a stale or broken surface is a deterministic unit test, not a live
/// assertion. The lane never claims an embodiment it didn't achieve (the E3
/// counterpart to E1 `blank` / E2 `Dead`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EmbodyStatus {
    /// The surface rendered AND the `chain_head` it shows matches the lane's
    /// current `chain_head` — the result faithfully inhabits the surface.
    Embodied,
    /// The surface rendered a `chain_head`, but it is NOT the current one — the
    /// surface is behind the lane (a newer artifact landed). Honest "live but
    /// out of date", distinct from a render fault.
    Stale,
    /// The surface produced nothing visible, or showed no `chain_head` at all —
    /// a real render fault (the E3 `blank`/`Dead`).
    Dead,
    /// No browser available / capability denied / launch failed — degraded, not
    /// failed (the artifact file was still written; mirrors `VerifyStatus::NoBrowser`).
    NoBrowser,
    /// The readback probe itself errored (eval threw) — surface still written.
    Error,
    /// Verify not requested.
    Skipped,
}

impl EmbodyStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Embodied => "embodied",
            Self::Stale => "stale",
            Self::Dead => "dead",
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
fn build_html_impl(
    kind: PresentKind,
    artifact: &str,
    title: Option<&str>,
    payload: Option<&Value>,
    provenance: Option<&Value>,
    interactive: bool,
) -> String {
    let title_str = title.unwrap_or("Agent-Bridge present/v0");

    // E2: the single enhancement decision. `enh` is Some(structured rows) iff
    // interactivity was requested AND this kind+artifact+payload can be driven
    // (see [`enhancement_payload`]). When enhanced, the human view is re-rendered
    // from THAT structure via [`render_table`] so the server-render, the embedded
    // #ab-payload, and the client re-render all share one column order (no serde
    // map-order dependency); markdown_table thereby also gains the #ab-payload it
    // lacked at E1. When not enhanced the output is byte-for-byte the E1 document.
    let enh = if interactive {
        enhancement_payload(kind, artifact, payload)
    } else {
        None
    };
    let interactive_on = enh.is_some();
    let rendered = match &enh {
        Some(p) => render_table(p),
        None => render_body(kind, artifact, payload),
    };
    // Controls live INSIDE #ab-render (the runtime fills #ab-controls on load)
    // so a dead/blank interactive artifact is still caught by the unchanged E1
    // blank check. The fixed runtime <script> is appended after </main> (outside
    // the verified region, mirroring the mermaid-script precedent) so it never
    // inflates the verify metrics.
    let (body, runtime_script) = if interactive_on {
        (
            format!("<div id=\"ab-controls\"></div><div id=\"ab-view\">{rendered}</div>"),
            format!("<script id=\"ab-runtime\">{AB_RUNTIME_JS}</script>"),
        )
    } else {
        (rendered, String::new())
    };

    // #ab-payload embeds the enhancement payload when enhanced (covers
    // markdown_table, which carries no caller payload), else the caller payload.
    // For kind=table the enhancement payload IS the caller payload → bytes
    // unchanged.
    let payload_for_embed: Option<&Value> = if interactive_on { enh.as_ref() } else { payload };
    let payload_script = match payload_for_embed {
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
{runtime_script}
</body></html>"#,
        schema = PRESENT_SCHEMA,
        title = html_escape(title_str),
        region = RENDER_REGION_ID,
        body = body,
        payload_script = payload_script,
        prov_script = prov_script,
        prov_footer = prov_footer,
        runtime_script = runtime_script,
    )
}

/// Build the E1 static-artifact document (no interactivity). Public API unchanged
/// — the 5 existing call sites and their byte-stable tests keep working verbatim.
pub fn build_html(
    kind: PresentKind,
    artifact: &str,
    title: Option<&str>,
    payload: Option<&Value>,
    provenance: Option<&Value>,
) -> String {
    build_html_impl(kind, artifact, title, payload, provenance, false)
}

/// Build the E2 interactive-artifact document. When `kind`/`payload` is
/// enhanceable (see [`is_enhanceable`]) the artifact gains client-side
/// filter+sort controls over the embedded `#ab-payload`; otherwise this is
/// byte-identical to [`build_html`] (the caller learns it was a no-op via
/// `is_enhanceable`, surfaced as `interactive_status: not_applicable`).
pub fn build_html_interactive(
    kind: PresentKind,
    artifact: &str,
    title: Option<&str>,
    payload: Option<&Value>,
    provenance: Option<&Value>,
) -> String {
    build_html_impl(kind, artifact, title, payload, provenance, true)
}

/// Parse a markdown pipe-table into an array-of-objects keyed by the header row,
/// so the E2 runtime can filter/sort it exactly like a `kind=table` payload.
/// Returns `None` unless there is a header row PLUS at least one data row (nothing
/// to drive otherwise). Mirrors [`render_markdown_table`]'s row parsing (the
/// 2nd line may be a `|---|` separator). This is what earns `markdown_table` a
/// `#ab-payload` (dual-encoding) it never had at E1 — the enhanced human view is
/// re-rendered from THIS structure via [`render_table`], so the column order is
/// identical across server-render / embedded payload / client re-render and does
/// not depend on serde map ordering.
pub fn md_table_to_payload(src: &str) -> Option<Value> {
    let lines: Vec<&str> = src
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();
    if lines.is_empty() {
        return None;
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
            continue;
        }
        rows.push(parse_row(line));
    }
    if rows.len() < 2 {
        return None; // need header + >=1 data row
    }
    let headers = rows[0].clone();
    let mut out = Vec::with_capacity(rows.len() - 1);
    for r in &rows[1..] {
        let mut obj = serde_json::Map::new();
        for (c, h) in headers.iter().enumerate() {
            let v = r.get(c).cloned().unwrap_or_default();
            obj.insert(h.clone(), Value::String(v));
        }
        out.push(Value::Object(obj));
    }
    Some(Value::Array(out))
}

/// The structured array-of-objects that should DRIVE interactivity (and be
/// embedded as `#ab-payload`), or `None` if this kind+content can't be enhanced.
/// Single source of truth shared by [`is_enhanceable`] and [`build_html_impl`] so
/// the tool's `enhanced` flag and the actual rendered runtime never disagree.
///   - `table`: the caller payload, iff a non-empty array of OBJECTS (the keyed
///     path [`render_table`] takes). The enhancement payload IS the caller
///     payload, so the embedded bytes are unchanged from E1.
///   - `markdown_table`: the artifact parsed via [`md_table_to_payload`].
///   - everything else (html/svg/mermaid, or a non-keyed table): `None`.
pub fn enhancement_payload(kind: PresentKind, artifact: &str, payload: Option<&Value>) -> Option<Value> {
    match kind {
        PresentKind::Table => match payload.and_then(|p| p.as_array()) {
            Some(arr) if !arr.is_empty() && arr.iter().all(Value::is_object) => {
                Some(Value::Array(arr.clone()))
            }
            _ => None,
        },
        PresentKind::MarkdownTable => md_table_to_payload(artifact),
        _ => None,
    }
}

/// Whether `interactive` rendering does anything for this kind+artifact+payload.
/// `kind=table` with a non-empty array of OBJECTS, or `kind=markdown_table` whose
/// artifact parses to a header + >=1 row. Everything else is a no-op the caller
/// surfaces as `interactive_status: not_applicable` — the tool never claims
/// interactivity it didn't add. (charts / sliders are deferred rungs.)
pub fn is_enhanceable(kind: PresentKind, artifact: &str, payload: Option<&Value>) -> bool {
    enhancement_payload(kind, artifact, payload).is_some()
}

/// The fixed, server-authored interactive runtime — ONE reviewed-once const baked
/// into the binary (NOT author JS, NOT per-artifact codegen, loads NO remote
/// module). On load it reads the full structure from `#ab-payload` (dual-encoding
/// pays off: the machine payload IS the source for the human view), derives the
/// columns the same union-of-keys way [`render_table`] does, populates
/// `#ab-controls` with a filter input + makes the `<thead>` headers click/keyboard
/// sortable, and re-renders ONLY `#ab-view tbody` via `textContent` (never
/// innerHTML-from-data, so payload values stay inert — safer than html/svg kinds).
/// Re-render is synchronous (NO timers/rAF/debounce) so the headless falsifier is
/// race-free. With JS disabled #ab-controls stays empty and the server-rendered
/// table remains valid (graceful E1 fallback).
pub const AB_RUNTIME_JS: &str = r#"(function(){
var pe=document.getElementById('ab-payload');var view=document.getElementById('ab-view');
if(!pe||!view)return;var rows;try{rows=JSON.parse(pe.textContent);}catch(e){return;}
if(!Array.isArray(rows)||!rows.length)return;
var table=view.querySelector('table');if(!table)return;
var tbody=table.querySelector('tbody');if(!tbody)return;
var cols=[];rows.forEach(function(r){if(r&&typeof r==='object'&&!Array.isArray(r)){Object.keys(r).forEach(function(k){if(cols.indexOf(k)<0)cols.push(k);});}});
if(!cols.length)return;
var controls=document.getElementById('ab-controls');
var filter=document.createElement('input');filter.type='search';filter.setAttribute('data-ab-filter','');filter.placeholder='filter...';filter.setAttribute('aria-label','filter rows');
if(controls)controls.appendChild(filter);
var sortCol=null,sortDir=1;
function cell(v){return v==null?'':(typeof v==='string'?v:JSON.stringify(v));}
function render(){
var q=(filter.value||'').toLowerCase();
var out=rows.filter(function(r){if(!q)return true;for(var i=0;i<cols.length;i++){if(cell(r&&r[cols[i]]).toLowerCase().indexOf(q)>=0)return true;}return false;});
if(sortCol!=null){out=out.slice().sort(function(a,b){var x=cell(a&&a[sortCol]),y=cell(b&&b[sortCol]);var nx=parseFloat(x),ny=parseFloat(y),c;if(!isNaN(nx)&&!isNaN(ny)&&x!==''&&y!=='')c=nx-ny;else c=x.localeCompare(y);return c*sortDir;});}
while(tbody.firstChild)tbody.removeChild(tbody.firstChild);
out.forEach(function(r){var tr=document.createElement('tr');cols.forEach(function(c){var td=document.createElement('td');td.textContent=cell(r&&r[c]);tr.appendChild(td);});tbody.appendChild(tr);});
}
filter.addEventListener('input',render);
var ths=table.querySelectorAll('thead th');
for(var j=0;j<ths.length&&j<cols.length;j++){(function(idx){var th=ths[idx];th.style.cursor='pointer';th.setAttribute('role','button');th.setAttribute('tabindex','0');function doSort(){var c=cols[idx];if(sortCol===c){sortDir=-sortDir;}else{sortCol=c;sortDir=1;}render();}th.addEventListener('click',doSort);th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();doSort();}});})(j);}
render();
})();"#;

/// The E2 self-verify probe — ONE self-contained eval (one round-trip, no waits)
/// that drives REAL controls and returns a JSON signature; the Live/Dead decision
/// is the pure [`classify_interactivity`]. Sequence: snapshot tbody → set the
/// filter to a high-entropy ABSENT token + dispatch input (a live filter MUST
/// empty a non-empty view) → snapshot → clear + dispatch (a real filter MUST
/// restore exactly) → snapshot → click the first header (sort) → snapshot. A dead
/// control leaves the view unchanged; a one-way wipe cannot restore.
pub const INTERACT_DRIVE_JS: &str = r#"(function(){
var view=document.getElementById('ab-view');if(!view)return JSON.stringify({drove:false,reason:'no-view'});
var table=view.querySelector('table');var tbody=table&&table.querySelector('tbody');
if(!tbody)return JSON.stringify({drove:false,reason:'no-tbody'});
var filter=document.querySelector('#ab-controls [data-ab-filter]');
if(!filter)return JSON.stringify({drove:false,reason:'no-control'});
function sig(){return tbody.innerText;}
var sig0=sig();var rowcount0=tbody.querySelectorAll('tr').length;
filter.value='zzqx-ABSENT-7f3a9-nomatch';filter.dispatchEvent(new Event('input',{bubbles:true}));var sigFiltered=sig();
filter.value='';filter.dispatchEvent(new Event('input',{bubbles:true}));var sigRestored=sig();
var th=table.querySelector('thead th');if(th)th.dispatchEvent(new MouseEvent('click',{bubbles:true}));var sigSorted=sig();
return JSON.stringify({drove:true,rowcount0:rowcount0,filtered_changed:sigFiltered!==sig0,restored:sigRestored===sig0,sorted_changed:sigSorted!==sig0});
})();"#;

/// Signature returned by [`INTERACT_DRIVE_JS`], parsed for [`classify_interactivity`].
#[derive(Debug, Clone, Default)]
pub struct InteractSignature {
    pub drove: bool,
    pub reason: Option<String>,
    pub rowcount0: usize,
    pub filtered_changed: bool,
    pub restored: bool,
    pub sorted_changed: bool,
}

/// Parse the interact-probe JSON. Tolerant of object-or-stringified-JSON like
/// [`parse_metrics`], so the decision doesn't depend on which the backend returns.
pub fn parse_interact_signature(v: &Value) -> InteractSignature {
    let obj = match v {
        Value::String(s) => serde_json::from_str::<Value>(s).unwrap_or(Value::Null),
        other => other.clone(),
    };
    let b = |k: &str| obj.get(k).and_then(Value::as_bool).unwrap_or(false);
    InteractSignature {
        drove: b("drove"),
        reason: obj.get("reason").and_then(Value::as_str).map(String::from),
        rowcount0: obj.get("rowcount0").and_then(Value::as_u64).unwrap_or(0) as usize,
        filtered_changed: b("filtered_changed"),
        restored: b("restored"),
        sorted_changed: b("sorted_changed"),
    }
}

/// The E2 falsifier decision (pure, browser-free — sibling of [`classify_render`]).
/// `Verified` requires driving the filter with an ABSENT token CHANGED the view
/// AND clearing it RESTORED the exact original — so a one-way wipe or a crash that
/// blanks the table cannot masquerade as working. A dead/no-op control (missing
/// handler, runtime threw, not wired) leaves the view unchanged → `filtered_changed
/// == false` → `Dead`. The sort signal (`sorted_changed`) is observed and carried
/// in the result detail but NOT gated, to avoid a false `Dead` on a degenerate
/// all-identical-row table; the restore check alone already defeats the wipe
/// false-positive. Too few rows to prove a filter (<2) → `Skipped`, not `Dead`.
pub fn classify_interactivity(s: &InteractSignature) -> InteractStatus {
    if !s.drove {
        return InteractStatus::Dead;
    }
    if s.rowcount0 < 2 {
        return InteractStatus::Skipped;
    }
    if s.filtered_changed && s.restored {
        InteractStatus::Verified
    } else {
        InteractStatus::Dead
    }
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
        let stem = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or_default()
            .to_string();
        // The E3 embodied-mirror surface is infrastructure, not a content
        // artifact: excluding it keeps the mirror out of the present_replay
        // chain it reflects (otherwise each dashboard write would perturb the
        // very chain_head it displays).
        if stem == DASHBOARD_BASENAME {
            continue;
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
            id: stem,
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

// ---------------------------------------------------------------------------
// slice 2 — read-only replay/audit projection (NOT a new source of truth)
// ---------------------------------------------------------------------------

/// All-zero SHA-256, the chain's genesis `prev_hash` (mirrors `event_spine`).
const PRESENT_REPLAY_ZERO_HASH: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";

/// Read-only replay/audit projection over persisted `present()` artifacts — the
/// slice-2 counterpart to [`crate::event_spine`]: it does NOT create a new source
/// of truth. It orders the self-describing on-disk artifacts ([`list_artifacts`])
/// oldest→newest, derives an `event_spine`-style SHA-256 hash chain over their
/// identity (so loss/tamper is detectable via `chain_head`), and cross-checks the
/// artifact count against `present_calls_logged` (the number of `present` calls
/// already recorded in `mcp_tool_calls`) to surface `drift`. The dual-encoding
/// tally audits how many artifacts carry a machine-readable `#ab-payload`.
///
/// Returns a `serde_json::Value` so this module stays dependency-light (no
/// `Serialize` derives); the `present_replay` MCP tool returns it verbatim.
pub fn present_replay_snapshot(
    artifacts: &[ArtifactInfo],
    present_calls_logged: usize,
    window_secs: u64,
    generated_at: u64,
) -> Value {
    let mut ordered: Vec<&ArtifactInfo> = artifacts.iter().collect();
    // oldest → newest; stable tiebreak on id keeps the chain deterministic when
    // two artifacts share a ts (or both lack one — None sorts first, then by id).
    ordered.sort_by(|a, b| a.ts.cmp(&b.ts).then_with(|| a.id.cmp(&b.id)));

    let mut prev = PRESENT_REPLAY_ZERO_HASH.to_string();
    let mut dual_ok = 0usize;
    let mut events: Vec<Value> = Vec::with_capacity(ordered.len());
    for a in &ordered {
        if a.dual_encoding {
            dual_ok += 1;
        }
        let hash = present_replay_hash(a, &prev);
        events.push(serde_json::json!({
            "artifact_id": a.id,
            "ts": a.ts,
            "kind": a.kind,
            "generated_by": a.generated_by,
            "session_id": a.session_id,
            "dual_encoding": a.dual_encoding,
            "has_screenshot": a.has_screenshot,
            "bytes": a.bytes,
            "artifact_path": a.artifact_path,
            "prev_hash": prev,
            "hash": hash,
        }));
        prev = hash;
    }
    let artifact_count = events.len();
    serde_json::json!({
        "schema_version": 1u32,
        "hash_algorithm": "sha256",
        "generated_at": generated_at,
        "window_secs": window_secs,
        "artifact_count": artifact_count,
        "present_calls_logged": present_calls_logged,
        // logged calls minus on-disk artifacts: +N = calls deduped/cleaned up
        // (content-addressed writes collapse, files may be GC'd); -N = artifacts
        // whose call rows fell outside the window or predate telemetry.
        "drift": present_calls_logged as i64 - artifact_count as i64,
        "dual_encoding_ok": dual_ok,
        "dual_encoding_missing": artifact_count - dual_ok,
        "chain_head": prev,
        "events": events,
    })
}

/// One link of the [`present_replay_snapshot`] chain: SHA-256 over the canonical
/// JSON of the artifact identity + the previous hash (event_spine `sha256_json`
/// idiom). Excludes volatile fields (path, screenshot presence) so the chain is
/// stable across moves/GC of sidecar files.
fn present_replay_hash(a: &ArtifactInfo, prev_hash: &str) -> String {
    let v = serde_json::json!({
        "artifact_id": a.id,
        "ts": a.ts,
        "kind": a.kind,
        "bytes": a.bytes,
        "dual_encoding": a.dual_encoding,
        "prev_hash": prev_hash,
    });
    let bytes = serde_json::to_vec(&v).unwrap_or_else(|_| v.to_string().into_bytes());
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    present_hex_lower(&hasher.finalize())
}

/// Lowercase hex (local copy per the repo convention — `hex_lower` is private to
/// `event_spine`).
fn present_hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0x0f) as usize] as char);
    }
    out
}

// ---------------------------------------------------------------------------
// E3 — embodied-mirror surface (output-expression ladder's third rung)
// ---------------------------------------------------------------------------
//
// E1 wrote a static artifact; E2 made it interactive; E3 lets the lane state
// INHABIT a persistent surface the human already watches — a dashboard browser
// tab. The dashboard is a read-only MIRROR of the slice-2 `present_replay`
// snapshot (NOT a new source of truth): its content is the snapshot's
// `chain_head` + counts + recent events. Embodiment is falsifiable: a headless
// probe reads the `chain_head` the rendered surface shows and compares it to the
// lane's current `chain_head`. Surface reflects current head → `embodied`;
// reflects an older head → `stale`; renders nothing / no head → `dead`.
//
// Honesty discipline (shared with E1/E2): the human-facing render lives in
// `<main id="ab-render">` and the readback target `#ab-chain-head` is INSIDE it,
// so a surface that renders no head for a human cannot report `embodied` — the
// machine-only `#ab-payload` chrome (in <head>) is NOT what the falsifier reads.

/// Readback signature from [`DASHBOARD_READBACK_JS`], parsed for [`classify_embody`].
#[derive(Debug, Clone, Default)]
pub struct DashboardReadback {
    /// `#ab-render` exists AND has ≥1 laid-out (visible) element — the E3 blank check.
    pub rendered: bool,
    /// The `chain_head` text the rendered `#ab-chain-head` element shows (the
    /// human-visible head, not the machine `#ab-payload`).
    pub chain_head: String,
    /// Rendered event-table rows (diagnostic).
    pub rows: usize,
}

/// The JS evaluated in the loaded dashboard to produce [`DashboardReadback`].
/// Reads the human-rendered `#ab-chain-head` (NOT the `#ab-payload` chrome) so
/// the falsifier proves what a human would actually see, and measures visible
/// layout inside `#ab-render` ONLY (mirrors [`VERIFY_METRICS_JS`]). Keys MUST
/// stay in sync with [`parse_dashboard_readback`] — guarded by a unit canary.
pub const DASHBOARD_READBACK_JS: &str = "JSON.stringify((function(){var e=document.getElementById('ab-render');var ch=document.getElementById('ab-chain-head');var rows=document.querySelectorAll('#ab-events tbody tr').length;var vis=0;if(e){var els=e.querySelectorAll('*:not(script):not(style)');els.forEach(function(x){if(x.getClientRects().length>0)vis++;});}return{rendered:(!!e&&vis>0),chain_head:(ch?(ch.textContent||'').trim():''),rows:rows};})())";

/// Parse the dashboard readback JSON. Tolerant of object-or-stringified-JSON
/// like [`parse_metrics`], so the decision doesn't depend on which the backend returns.
pub fn parse_dashboard_readback(v: &Value) -> DashboardReadback {
    let obj = match v {
        Value::String(s) => serde_json::from_str::<Value>(s).unwrap_or(Value::Null),
        other => other.clone(),
    };
    DashboardReadback {
        rendered: obj.get("rendered").and_then(Value::as_bool).unwrap_or(false),
        chain_head: obj
            .get("chain_head")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string(),
        rows: obj.get("rows").and_then(Value::as_u64).unwrap_or(0) as usize,
    }
}

/// The E3 falsifier decision (pure, browser-free — sibling of [`classify_render`]
/// / [`classify_interactivity`]). `Embodied` requires the surface rendered visible
/// content AND the `chain_head` it shows equals the lane's current `chain_head`.
/// A surface that renders an OLDER head is `Stale` (honest "live but behind"),
/// not a fault; a surface that renders nothing, or shows no head at all, is `Dead`
/// (a broken mirror cannot masquerade as embodied). The empty-lane case
/// (`expected == ` all-zero genesis) is `Embodied` when the surface faithfully
/// shows that genesis head — an empty lane is still faithfully mirrored.
pub fn classify_embody(r: &DashboardReadback, expected_chain_head: &str) -> EmbodyStatus {
    if !r.rendered {
        return EmbodyStatus::Dead;
    }
    if r.chain_head.is_empty() {
        return EmbodyStatus::Dead;
    }
    if r.chain_head == expected_chain_head {
        EmbodyStatus::Embodied
    } else {
        EmbodyStatus::Stale
    }
}

/// Render a [`present_replay_snapshot`] into the E3 embodied-mirror dashboard
/// document. Pure (browser-free, unit-testable). The document mirrors the snapshot
/// — `chain_head`, the count/drift/dual-encoding summary, and a recent-events
/// table — and carries dual-encoding: the WHOLE snapshot is embedded as
/// `#ab-payload` (machine bypass) while `chain_head` is ALSO rendered into the
/// human-visible `<code id="ab-chain-head">` inside `#ab-render` (the readback
/// target). Chrome (the `#ab-payload`/`#ab-provenance` scripts, the footer) lives
/// OUTSIDE `#ab-render` so the E3 blank/readback check stays honest.
pub fn build_dashboard_html(snapshot: &Value, title: Option<&str>) -> String {
    let title_str = title.unwrap_or("Agent-Bridge present_dashboard — output lane mirror");
    let chain_head = snapshot
        .get("chain_head")
        .and_then(Value::as_str)
        .unwrap_or("");
    let u = |k: &str| snapshot.get(k).and_then(Value::as_u64).unwrap_or(0);
    let i = |k: &str| snapshot.get(k).and_then(Value::as_i64).unwrap_or(0);
    let artifact_count = u("artifact_count");
    let present_calls_logged = u("present_calls_logged");
    let drift = i("drift");
    let dual_ok = u("dual_encoding_ok");
    let dual_missing = u("dual_encoding_missing");
    let window_secs = u("window_secs");
    let generated_at = u("generated_at");

    let events = snapshot
        .get("events")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut rows_html = String::new();
    for ev in &events {
        let id = ev.get("artifact_id").and_then(Value::as_str).unwrap_or("");
        let ts = ev
            .get("ts")
            .and_then(Value::as_u64)
            .map(|t| t.to_string())
            .unwrap_or_default();
        let kind = ev.get("kind").and_then(Value::as_str).unwrap_or("—");
        let dual = ev
            .get("dual_encoding")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let bytes = ev.get("bytes").and_then(Value::as_u64).unwrap_or(0);
        let hash = ev.get("hash").and_then(Value::as_str).unwrap_or("");
        let hash_short: String = hash.chars().take(12).collect();
        rows_html.push_str(&format!(
            "<tr><td>{id}</td><td>{ts}</td><td>{kind}</td><td>{dual}</td><td>{bytes}</td><td><code>{hash}</code></td></tr>",
            id = html_escape(id),
            ts = html_escape(&ts),
            kind = html_escape(kind),
            dual = if dual { "✓" } else { "" },
            bytes = bytes,
            hash = html_escape(&hash_short),
        ));
    }
    if rows_html.is_empty() {
        rows_html =
            "<tr><td colspan=\"6\"><em>no artifacts in window</em></td></tr>".to_string();
    }

    // The human-render region. #ab-chain-head is the readback target — it MUST be
    // inside #ab-render so a surface that shows no head reports blank/dead.
    let body = format!(
        r#"<h1>{title}</h1>
<p class="ab-head">chain_head: <code id="ab-chain-head">{head}</code></p>
<ul class="ab-summary">
<li>artifacts: <strong>{artifact_count}</strong></li>
<li>present calls logged: {present_calls_logged}</li>
<li>drift: {drift}</li>
<li>dual-encoding: {dual_ok} ok / {dual_missing} missing</li>
<li>window: {window_secs}s · generated_at: {generated_at}</li>
</ul>
<table id="ab-events"><thead><tr><th>artifact_id</th><th>ts</th><th>kind</th><th>dual</th><th>bytes</th><th>hash</th></tr></thead><tbody>{rows}</tbody></table>"#,
        title = html_escape(title_str),
        head = html_escape(chain_head),
        artifact_count = artifact_count,
        present_calls_logged = present_calls_logged,
        drift = drift,
        dual_ok = dual_ok,
        dual_missing = dual_missing,
        window_secs = window_secs,
        generated_at = generated_at,
        rows = rows_html,
    );

    // Dual-encoding chrome (machine side): the whole snapshot + provenance, both
    // in <head> so a future kind=html body could never shadow them.
    let payload_script = format!(
        "<script type=\"application/json\" id=\"ab-payload\">{}</script>",
        json_script(snapshot)
    );
    let provenance = serde_json::json!({
        "generated_by": PRESENT_DASHBOARD_SCHEMA,
        "surface": "browser_tab",
        "ts": generated_at,
        "chain_head": chain_head,
    });
    let prov_script = format!(
        "<script type=\"application/json\" id=\"ab-provenance\">{}</script>",
        json_script(&provenance)
    );
    let prov_footer = format!(
        "<footer id=\"ab-provenance-view\">provenance: {}</footer>",
        html_escape(&serde_json::to_string(&provenance).unwrap_or_default())
    );

    format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="generator" content="agent-bridge {schema}">
<title>{title}</title>
{payload_script}
{prov_script}
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;margin:24px;color:#1a1a2e;background:#fafafe}}
h1{{font-size:18px;margin:0 0 12px}}
table{{border-collapse:collapse;margin:8px 0}}
th,td{{border:1px solid #c7c7e0;padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#eaeaf6}}
code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f4f4fb;padding:1px 5px;border-radius:4px;word-break:break-all}}
.ab-head{{font-size:13px}}
.ab-summary{{font-size:13px;color:#444;list-style:none;padding:0;margin:8px 0 16px;display:flex;flex-wrap:wrap;gap:6px 18px}}
footer{{margin-top:28px;font-size:11px;color:#9a9ab0;border-top:1px solid #e3e3ef;padding-top:8px;word-break:break-all}}
</style></head>
<body>
<main id="{region}">{body}</main>
{prov_footer}
</body></html>"#,
        schema = PRESENT_DASHBOARD_SCHEMA,
        title = html_escape(title_str),
        region = RENDER_REGION_ID,
        body = body,
        payload_script = payload_script,
        prov_script = prov_script,
        prov_footer = prov_footer,
    )
}

// ---------------------------------------------------------------------------
// Slice A — falsifier-gated verified (intent → action → outcome) stream
// ---------------------------------------------------------------------------
//
// The output lane already produces falsifier-LABELED records (VerifyStatus /
// InteractStatus / EmbodyStatus) but they die as one-shot tool results. This
// slice persists each render's outcome as a `<id>.outcome.json` sidecar (next to
// the artifact + its `<id>.png`) and exposes a READ-ONLY, gate-filtered
// projection (`present_outcomes`). The gate is a PURE decision — the E-ladder's
// fourth honesty surface: "is this a VERIFIED outcome, eligible for a downstream
// training signal?" — so what counts as a clean label is unit-tested, never a
// self-fulfilling claim. This slice only PRODUCES the gated stream; consuming it
// (memory ingestion, a learner) is a separate lane's slice. It does NOT touch
// event_spine or the memory schema.

/// Sidecar filename suffix: `<artifact_id>.outcome.json`.
pub const OUTCOME_SIDECAR_SUFFIX: &str = "outcome.json";

/// Pure falsifier gate over a record's honesty axes — is this action→outcome
/// record eligible for the verified training-signal stream? Eligible iff the
/// render verified (`verify_status == rendered_ok`) AND, where the axis applies,
/// embodiment did not fail (`embody_status` absent or `embodied`) AND
/// interactivity did not fail (`interactive_status` absent or one of
/// `verified` / `not_applicable`) AND, for a record that carries a human-decision
/// axis (an approval card), the human actually DECIDED (`decision` absent or one
/// of `approved` / `rejected` — a `timed_out` / `dead` / `pending` decision is NOT
/// a verified outcome). Mirrors [`classify_render`] / [`classify_embody`] /
/// [`crate::present_approval::classify_approval`]: a deterministic, browser-free
/// decision, so "what counts as a verified label" is a unit test, not a runtime
/// hand-wave. Returns `(eligible, reason)`.
pub fn outcome_gate(
    verify_status: &str,
    embody_status: Option<&str>,
    interactive_status: Option<&str>,
    decision: Option<&str>,
) -> (bool, String) {
    if verify_status != "rendered_ok" {
        return (
            false,
            format!("verify_status={verify_status} (need rendered_ok)"),
        );
    }
    if let Some(e) = embody_status {
        if e != "embodied" {
            return (false, format!("embody_status={e} (need embodied)"));
        }
    }
    if let Some(i) = interactive_status {
        if i != "verified" && i != "not_applicable" {
            return (
                false,
                format!("interactive_status={i} (need verified|not_applicable)"),
            );
        }
    }
    // Human-decision axis: an approval surface is a verified outcome only when a
    // human actually decided. A render that timed out / a dead card / a still-pending
    // card carries no verified human label (fail-closed — timeout is never approval).
    if let Some(d) = decision {
        if d != "approved" && d != "rejected" {
            return (
                false,
                format!("decision={d} (need approved|rejected)"),
            );
        }
    }
    (true, "verified".to_string())
}

/// Persist an action→outcome record as a `<id>.outcome.json` sidecar next to the
/// artifact (mirrors the `<id>.png` screenshot sidecar). Atomic; best-effort.
pub fn write_outcome_sidecar(dir: &Path, id: &str, record: &Value) -> std::io::Result<()> {
    let path = dir.join(format!("{id}.{OUTCOME_SIDECAR_SUFFIX}"));
    let body = serde_json::to_string(record).unwrap_or_else(|_| "{}".to_string());
    write_artifact_atomic(&path, &body)
}

/// Read persisted action→outcome sidecars, newest-first (by `ts`), within the
/// look-back window (`ts >= cutoff_ts`; records lacking a ts are kept). Missing
/// dir → []. Read-only.
pub fn read_outcome_records(dir: &Path, limit: usize, cutoff_ts: u64) -> Vec<Value> {
    let read = match std::fs::read_dir(dir) {
        Ok(r) => r,
        Err(_) => return Vec::new(),
    };
    let suffix = format!(".{OUTCOME_SIDECAR_SUFFIX}");
    let mut recs: Vec<Value> = read
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .map_or(false, |n| n.ends_with(&suffix))
        })
        .filter_map(|p| std::fs::read_to_string(&p).ok())
        .filter_map(|s| serde_json::from_str::<Value>(&s).ok())
        .filter(|v| {
            v.get("ts")
                .and_then(Value::as_u64)
                .map_or(true, |t| t >= cutoff_ts)
        })
        .collect();
    recs.sort_by(|a, b| {
        let ta = a.get("ts").and_then(Value::as_u64).unwrap_or(0);
        let tb = b.get("ts").and_then(Value::as_u64).unwrap_or(0);
        tb.cmp(&ta)
    });
    recs.truncate(limit);
    recs
}

/// Apply [`outcome_gate`] over a set of outcome records, returning the
/// training-signal projection: each surfaced record annotated with `eligible` +
/// `gate_reason`, plus eligible/rejected tallies. `verified_only` drops rejected
/// records from the `outcomes` list (the strict training-signal view); the
/// tallies ALWAYS reflect the full input set (so a consumer never mistakes a
/// filtered list for "everything was verified"). Pure / browser-free.
pub fn present_outcomes_projection(records: &[Value], verified_only: bool) -> Value {
    let mut eligible = 0usize;
    let mut out: Vec<Value> = Vec::with_capacity(records.len());
    for r in records {
        let vs = r.get("verify_status").and_then(Value::as_str).unwrap_or("");
        let es = r.get("embody_status").and_then(Value::as_str);
        let is = r.get("interactive_status").and_then(Value::as_str);
        let ds = r.get("decision").and_then(Value::as_str);
        let (ok, reason) = outcome_gate(vs, es, is, ds);
        if ok {
            eligible += 1;
        }
        if ok || !verified_only {
            let mut rec = r.clone();
            if let Some(obj) = rec.as_object_mut() {
                obj.insert("eligible".into(), Value::Bool(ok));
                obj.insert("gate_reason".into(), Value::String(reason));
            }
            out.push(rec);
        }
    }
    serde_json::json!({
        "schema_version": 1u32,
        "total_records": records.len(),
        "eligible_count": eligible,
        "rejected_count": records.len() - eligible,
        "verified_only": verified_only,
        "outcomes": out,
    })
}

/// **Output-expression lane Slice B (v0) — read-only outcome→memory drift
/// projection.** Given the gate-eligible verified outcome records (the
/// `outcomes` list of [`present_outcomes_projection`] with `verified_only=true`)
/// and a caller-supplied map of `artifact_id → matched memory keys` (the
/// representation probe, run read-only by the tool wrapper via the store's
/// non-mutating `memory_search`), folds an event_spine-style SHA-256 chain over
/// each verified outcome and reports which are vs are NOT already represented in
/// memory. `drift == missing_count` is the literal size of the open
/// output→memory loop.
///
/// PURE / store-free / browser-free: it writes nothing it later reads
/// (`represented` is decided by the passed-in probe map, not by anything this
/// fn authored) so it provably cannot self-fulfill. The chain reuses the
/// [`present_replay_hash`] idiom (local SHA-256 + [`present_hex_lower`], seeded
/// with [`PRESENT_REPLAY_ZERO_HASH`]) — it does NOT touch `event_spine` (a
/// read-only #56 projection) and adds no source of truth.
///
/// For each missing (verified, not-yet-represented) record it also emits the
/// `proposed_*` candidate a future opt-in ingest WOULD persist (deterministic
/// `outcome_<artifact_id>` key, distinct `present_outcome` kind, additive tags
/// INCLUDING `decision:<d>` for approval outcomes — byte-identical to what
/// [`crate::present_ingest::build_outcome_memory`] writes) — as REPORT DATA
/// ONLY; this fn never writes memory. The proposed candidate is omitted for a
/// keyless (empty artifact_id) record, matching the ingest path's refusal.
///
/// **STRICT `represented`** (review fix): `represented_keys_by_artifact` carries
/// only EXACT outcome-row keys (`outcome_<artifact_id>`), so `drift ==
/// distinct_missing` equals exactly the writes the ingest tool would make. Loose
/// substring mentions in unrelated memory bodies are passed via `mentions` and
/// surfaced per-event WITHOUT counting as represented (they would understate the
/// gap). Counts are over DISTINCT artifact_ids (a duplicate artifact_id closes
/// with ONE write, so it must not double-count).
pub fn outcomes_memory_drift_snapshot(
    verified_records: &[Value],
    represented_keys_by_artifact: &std::collections::HashMap<String, Vec<String>>,
    mentions_by_artifact: &std::collections::HashMap<String, Vec<String>>,
    generated_at: u64,
    window_secs: u64,
) -> Value {
    // Stable order: by ts ascending, artifact_id as tiebreak — same idiom as
    // present_replay so the chain is deterministic and reorder/loss is evident.
    let mut recs: Vec<&Value> = verified_records.iter().collect();
    recs.sort_by(|a, b| {
        let ta = a.get("ts").and_then(Value::as_u64).unwrap_or(0);
        let tb = b.get("ts").and_then(Value::as_u64).unwrap_or(0);
        ta.cmp(&tb).then_with(|| {
            let ia = a.get("artifact_id").and_then(Value::as_str).unwrap_or("");
            let ib = b.get("artifact_id").and_then(Value::as_str).unwrap_or("");
            ia.cmp(ib)
        })
    });

    let mut prev = PRESENT_REPLAY_ZERO_HASH.to_string();
    let mut events: Vec<Value> = Vec::with_capacity(recs.len());
    // DISTINCT-artifact counting: one deterministic row closes the loop per
    // artifact_id, so dedupe before counting (mirrors the ingest seen_keys
    // discipline). All records still emit an event (full audit), but the
    // headline counts reflect distinct artifacts.
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut distinct_verified = 0usize;
    let mut distinct_represented = 0usize;
    let mut embody_unknown = 0usize;
    for r in recs {
        let artifact_id = r.get("artifact_id").and_then(Value::as_str).unwrap_or("");
        let ts = r.get("ts").and_then(Value::as_u64).unwrap_or(0);
        let intent = r.get("intent").and_then(Value::as_str).unwrap_or("");
        let verify_status = r.get("verify_status").and_then(Value::as_str).unwrap_or("");
        let verify_method = r.get("verify_method").and_then(Value::as_str).unwrap_or("");
        let action_tool = r.get("action_tool").and_then(Value::as_str).unwrap_or("");
        let gate_reason = r.get("gate_reason").and_then(Value::as_str).unwrap_or("");
        let decision = r.get("decision").and_then(Value::as_str);
        // Known limitation surfaced honestly: present()-origin sidecars omit
        // embody_status, so outcome_gate's embodiment rung was skipped (Option
        // None passes). Flag it rather than implying the embody axis was checked.
        if r.get("embody_status").is_none() {
            embody_unknown += 1;
        }
        let matched = represented_keys_by_artifact
            .get(artifact_id)
            .cloned()
            .unwrap_or_default();
        let mentions = mentions_by_artifact
            .get(artifact_id)
            .cloned()
            .unwrap_or_default();
        let represented = !matched.is_empty();
        let first_seen = !artifact_id.is_empty() && seen.insert(artifact_id.to_string());
        if first_seen {
            distinct_verified += 1;
            if represented {
                distinct_represented += 1;
            }
        }

        let hash = outcomes_drift_hash(artifact_id, ts, verify_status, gate_reason, represented, &prev);
        let mut ev = serde_json::json!({
            "artifact_id": artifact_id,
            "ts": ts,
            "intent": intent,
            "action_tool": action_tool,
            "verify_method": verify_method,
            "gate_reason": gate_reason,
            "represented": represented,
            "memory_keys": matched,
            "mentions": mentions,
            "prev_hash": prev,
            "hash": hash,
        });
        // would-write candidate for the missing ones — REPORT DATA ONLY. Omit
        // for keyless records (ingest refuses them) so the preview matches what
        // build_outcome_memory would actually mint, INCLUDING the decision tag.
        if !represented && !artifact_id.is_empty() {
            let mut proposed_tags = vec![
                Value::String("present_outcome".into()),
                Value::String("verified_outcome".into()),
                Value::String("auto_ingested".into()),
            ];
            if !verify_status.is_empty() {
                proposed_tags.push(Value::String(format!("verify:{verify_status}")));
            }
            if !verify_method.is_empty() {
                proposed_tags.push(Value::String(format!("method:{verify_method}")));
            }
            if let Some(d) = decision {
                proposed_tags.push(Value::String(format!("decision:{d}")));
            }
            if let Some(obj) = ev.as_object_mut() {
                obj.insert(
                    "proposed_key".into(),
                    Value::String(format!("outcome_{artifact_id}")),
                );
                obj.insert("proposed_kind".into(), Value::String("present_outcome".into()));
                obj.insert("proposed_scope".into(), Value::String(format!("outcome:{artifact_id}")));
                obj.insert("proposed_tags".into(), Value::Array(proposed_tags));
            }
        }
        events.push(ev);
        prev = hash;
    }

    let distinct_missing = distinct_verified - distinct_represented;
    serde_json::json!({
        "schema": "outcomes_memory_drift/v0",
        "hash_algorithm": "sha256",
        "generated_at": generated_at,
        "window_secs": window_secs,
        "event_count": events.len(),
        "verified_count": distinct_verified,
        "represented_count": distinct_represented,
        "missing_count": distinct_missing,
        "drift": distinct_missing,
        "embody_status_absent": embody_unknown,
        "chain_head": prev,
        "events": events,
    })
}

/// SHA-256 over a verified outcome's stable identity + `prev_hash` — the
/// drift-chain analogue of [`present_replay_hash`]. Local copy of the idiom
/// (does not import from `event_spine`).
fn outcomes_drift_hash(
    artifact_id: &str,
    ts: u64,
    verify_status: &str,
    gate_reason: &str,
    represented: bool,
    prev_hash: &str,
) -> String {
    let v = serde_json::json!({
        "artifact_id": artifact_id,
        "ts": ts,
        "verify_status": verify_status,
        "gate_reason": gate_reason,
        "represented": represented,
        "prev_hash": prev_hash,
    });
    let bytes = serde_json::to_vec(&v).unwrap_or_else(|_| v.to_string().into_bytes());
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    present_hex_lower(&hasher.finalize())
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

    // ----- E2 (interactive artifact) -----

    // is_enhanceable gates the keyed-table case (via payload) and the
    // markdown_table case (via artifact) the runtime can drive.
    #[test]
    fn e2_is_enhanceable_only_keyed_table() {
        let objs = json!([{"a": 1}, {"a": 2}]);
        assert!(is_enhanceable(PresentKind::Table, "", Some(&objs)));
        // non-table kind, array-of-arrays, empty array, no payload → not enhanceable
        assert!(!is_enhanceable(PresentKind::Html, "", Some(&objs)));
        assert!(!is_enhanceable(PresentKind::Table, "", Some(&json!([[1, 2], [3, 4]]))));
        assert!(!is_enhanceable(PresentKind::Table, "", Some(&json!([]))));
        assert!(!is_enhanceable(PresentKind::Table, "", None));
        // markdown_table is enhanceable via its ARTIFACT (header + >=1 row), never
        // via a payload arg; header-only does not qualify.
        assert!(!is_enhanceable(PresentKind::MarkdownTable, "", Some(&objs)));
        assert!(is_enhanceable(
            PresentKind::MarkdownTable,
            "| a | b |\n|---|---|\n| 1 | 2 |",
            None
        ));
        assert!(!is_enhanceable(
            PresentKind::MarkdownTable,
            "| a | b |",
            None
        ));
    }

    // E2 enhanceable table gains controls/view/runtime; #ab-payload still recovers
    // in ONE parse (dual-encoding byte-identical to E1), and the payload script
    // still lives in <head> (a2b shadow protection holds).
    #[test]
    fn e2_interactive_table_adds_controls_keeps_payload() {
        let payload = json!([{"name": "e5", "dims": 384}, {"name": "minilm", "dims": 384}]);
        let html = build_html_interactive(PresentKind::Table, "", Some("dims"), Some(&payload), None);
        assert!(html.contains("id=\"ab-controls\""));
        assert!(html.contains("id=\"ab-view\""));
        assert!(html.contains("<script id=\"ab-runtime\">"));
        // controls + view are INSIDE the verified render region (honesty: a blank
        // interactive artifact is still caught by the E1 blank check).
        let region = render_region(&html).expect("render region");
        assert!(region.contains("id=\"ab-controls\""));
        assert!(region.contains("id=\"ab-view\""));
        // the runtime <script> is OUTSIDE the region (after </main>) so it can't
        // inflate verify metrics.
        assert!(!region.contains("ab-runtime"));
        // dual-encoding unchanged: payload recovers in one parse, from <head>.
        assert_eq!(extract_ab_payload(&html), Some(payload));
    }

    // E2 markdown_table: interactive synthesizes a #ab-payload from the pipe
    // table (dual-encoding it never had at E1), re-renders the human view from
    // THAT payload via the keyed-table path, and adds the same controls/runtime.
    #[test]
    fn e2_interactive_markdown_table_synthesizes_payload() {
        let md = "| name | dims |\n|---|---|\n| e5 | 384 |\n| minilm | 256 |";
        let html = build_html_interactive(PresentKind::MarkdownTable, md, Some("emb"), None, None);
        assert!(html.contains("id=\"ab-controls\""));
        assert!(html.contains("id=\"ab-view\""));
        assert!(html.contains("<script id=\"ab-runtime\">"));
        // synthesized payload recovers in one parse, rows keyed by the header row
        // (order-independent Value equality), giving md_table dual-encoding.
        let p = extract_ab_payload(&html).expect("synthesized #ab-payload");
        assert_eq!(
            p,
            json!([
                {"name": "e5", "dims": "384"},
                {"name": "minilm", "dims": "256"}
            ])
        );
        // the human view is the keyed render of that payload (so column order is
        // consistent with the embedded payload + client re-render).
        let region = render_region(&html).expect("render region");
        assert!(region.contains("<th>name</th>"));
        assert!(region.contains("<td>minilm</td>"));
    }

    // A markdown_table with only a header (no data row) is NOT enhanceable, so
    // interactive is a byte-identical E1 no-op (no synthesized payload, no chrome).
    #[test]
    fn e2_markdown_table_header_only_is_noop() {
        let md = "| a | b |";
        let a = build_html_interactive(PresentKind::MarkdownTable, md, None, None, None);
        let b = build_html(PresentKind::MarkdownTable, md, None, None, None);
        assert_eq!(a, b, "non-enhanceable md_table interactive must equal E1");
        assert!(!a.contains("ab-runtime"));
    }

    // interactive on a NON-enhanceable kind is a byte-identical no-op vs E1, and
    // E1 (build_html) for a table never gains the interactive chrome.
    #[test]
    fn e2_noop_is_byte_identical_to_e1() {
        let a = build_html_interactive(PresentKind::Html, "<p>hi</p>", None, None, None);
        let b = build_html(PresentKind::Html, "<p>hi</p>", None, None, None);
        assert_eq!(a, b, "interactive no-op must equal E1 byte-for-byte");

        let payload = json!([{"a": 1}]);
        let e1_table = build_html(PresentKind::Table, "", None, Some(&payload), None);
        assert!(!e1_table.contains("ab-controls"));
        assert!(!e1_table.contains("ab-runtime"));
    }

    // The E2 falsifier decision is real (sibling of a3_classify_render): a dead
    // control → Dead; a live+reversible filter → Verified; <2 rows → Skipped.
    #[test]
    fn e2_classify_interactivity_truth_table() {
        let live = InteractSignature { drove: true, reason: None, rowcount0: 5, filtered_changed: true, restored: true, sorted_changed: true };
        assert_eq!(classify_interactivity(&live), InteractStatus::Verified);

        // sort didn't change (e.g. degenerate) but filter+restore held → still Verified.
        let mut no_sort = live.clone();
        no_sort.sorted_changed = false;
        assert_eq!(classify_interactivity(&no_sort), InteractStatus::Verified);

        // dead control: driving the filter changed nothing.
        let dead = InteractSignature { drove: true, rowcount0: 5, filtered_changed: false, restored: true, ..Default::default() };
        assert_eq!(classify_interactivity(&dead), InteractStatus::Dead);

        // one-way wipe: filter changed but never restored → Dead (the falsifier's point).
        let wipe = InteractSignature { drove: true, rowcount0: 5, filtered_changed: true, restored: false, ..Default::default() };
        assert_eq!(classify_interactivity(&wipe), InteractStatus::Dead);

        // no control found at all → Dead.
        let none = InteractSignature { drove: false, reason: Some("no-control".into()), ..Default::default() };
        assert_eq!(classify_interactivity(&none), InteractStatus::Dead);

        // too few rows to prove a filter → Skipped, not Dead.
        let one = InteractSignature { drove: true, rowcount0: 1, filtered_changed: false, restored: true, ..Default::default() };
        assert_eq!(classify_interactivity(&one), InteractStatus::Skipped);
    }

    // parse_interact_signature tolerates object OR stringified JSON (mirrors parse_metrics).
    #[test]
    fn e2_parse_interact_signature_string_and_object() {
        let s = parse_interact_signature(&json!(
            "{\"drove\":true,\"rowcount0\":3,\"filtered_changed\":true,\"restored\":true,\"sorted_changed\":false}"
        ));
        assert!(s.drove && s.filtered_changed && s.restored && !s.sorted_changed);
        assert_eq!(s.rowcount0, 3);
        let o = parse_interact_signature(&json!({"drove": false, "reason": "no-view"}));
        assert!(!o.drove);
        assert_eq!(o.reason.as_deref(), Some("no-view"));
    }

    // Canary: the fixed runtime targets the right ids and is SYNCHRONOUS (no
    // timers/rAF — the falsifier assumes a synchronous re-render) and can't
    // terminate its own <script> early.
    #[test]
    fn e2_runtime_js_canary() {
        for needle in ["ab-payload", "ab-view", "ab-controls", "data-ab-filter", "addEventListener"] {
            assert!(AB_RUNTIME_JS.contains(needle), "runtime missing {needle}");
        }
        assert!(!AB_RUNTIME_JS.contains("setTimeout"), "runtime must re-render synchronously");
        assert!(!AB_RUNTIME_JS.contains("requestAnimationFrame"), "runtime must re-render synchronously");
        assert!(!AB_RUNTIME_JS.contains("</script>"), "runtime must not terminate its own script tag");
    }

    // Canary: the probe drives both controls and returns exactly the keys
    // parse_interact_signature reads (cheap guard against silent drift).
    #[test]
    fn e2_drive_js_canary() {
        for needle in ["ab-view", "ab-controls", "data-ab-filter", "'input'", "MouseEvent", "click"] {
            assert!(INTERACT_DRIVE_JS.contains(needle), "drive-js missing {needle}");
        }
        for key in ["drove", "rowcount0", "filtered_changed", "restored", "sorted_changed"] {
            assert!(INTERACT_DRIVE_JS.contains(key), "drive-js missing key {key}");
        }
        assert!(!INTERACT_DRIVE_JS.contains("</script>"));
    }

    // ----- slice 2 (read-only replay/audit projection) -----

    fn art(id: &str, ts: u64, kind: &str, dual: bool) -> ArtifactInfo {
        ArtifactInfo {
            id: id.into(),
            artifact_path: format!("/p/{id}.html"),
            kind: Some(kind.into()),
            ts: Some(ts),
            generated_by: Some("present/v0".into()),
            session_id: None,
            dual_encoding: dual,
            has_screenshot: false,
            bytes: 1000 + ts,
        }
    }

    // present_replay orders oldest→newest, chains hashes from a zero genesis,
    // tallies dual-encoding, and reports logged-vs-on-disk drift — deterministically.
    #[test]
    fn slice2_present_replay_projection_chain_and_drift() {
        // intentionally out of ts order on input
        let arts = vec![
            art("bbb", 200, "table", true),
            art("aaa", 100, "html", false),
        ];
        let snap = present_replay_snapshot(&arts, 3, 86_400, 1_000);
        assert_eq!(snap["artifact_count"], json!(2));
        assert_eq!(snap["present_calls_logged"], json!(3));
        assert_eq!(snap["drift"], json!(1)); // 3 logged − 2 on disk
        assert_eq!(snap["dual_encoding_ok"], json!(1));
        assert_eq!(snap["dual_encoding_missing"], json!(1));
        assert_eq!(snap["hash_algorithm"], json!("sha256"));

        let events = snap["events"].as_array().unwrap();
        // ordered oldest→newest by ts: aaa(100) then bbb(200)
        assert_eq!(events[0]["artifact_id"], json!("aaa"));
        assert_eq!(events[1]["artifact_id"], json!("bbb"));
        // genesis prev is zero; each link chains the previous hash; head == last hash
        assert_eq!(events[0]["prev_hash"], json!(PRESENT_REPLAY_ZERO_HASH));
        assert_eq!(events[1]["prev_hash"], events[0]["hash"]);
        assert_eq!(snap["chain_head"], events[1]["hash"]);
        assert_ne!(snap["chain_head"], json!(PRESENT_REPLAY_ZERO_HASH));

        // deterministic for identical inputs
        assert_eq!(snap, present_replay_snapshot(&arts, 3, 86_400, 1_000));
    }

    // empty disk → empty chain (head stays genesis), no panic, drift = logged calls.
    #[test]
    fn slice2_present_replay_empty_is_genesis() {
        let snap = present_replay_snapshot(&[], 0, 86_400, 1_000);
        assert_eq!(snap["artifact_count"], json!(0));
        assert_eq!(snap["chain_head"], json!(PRESENT_REPLAY_ZERO_HASH));
        assert_eq!(snap["drift"], json!(0));
        assert_eq!(snap["events"].as_array().unwrap().len(), 0);
    }

    // ----- E3 (embodied-mirror dashboard) -----

    // The dashboard renders the snapshot's chain_head INTO the human #ab-render
    // region (the readback target #ab-chain-head lives inside it, not only in the
    // machine #ab-payload chrome), and embeds the whole snapshot as #ab-payload.
    #[test]
    fn e3_dashboard_mirrors_chain_head_in_render_region_and_payload() {
        let arts = vec![
            art("aaa", 100, "table", true),
            art("bbb", 200, "html", false),
        ];
        let snap = present_replay_snapshot(&arts, 2, 86_400, 1_000);
        let head = snap["chain_head"].as_str().unwrap().to_string();
        assert_ne!(head, PRESENT_REPLAY_ZERO_HASH);

        let html = build_dashboard_html(&snap, Some("mirror"));

        // chain_head is rendered into the HUMAN region via #ab-chain-head, so a
        // surface that shows no head reports blank/dead (the E3 falsifier hinges
        // on this being inside #ab-render, not the machine chrome).
        let region = render_region(&html).expect("render region present");
        assert!(
            region.contains("id=\"ab-chain-head\""),
            "readback target must live inside #ab-render"
        );
        assert!(
            region.contains(&head),
            "rendered region must show the chain_head a human sees"
        );
        // both artifact ids appear in the events table (visible mirror content).
        assert!(region.contains("aaa") && region.contains("bbb"));

        // dual-encoding: the whole snapshot is recoverable from #ab-payload in ONE parse.
        assert_eq!(extract_ab_payload(&html), Some(snap.clone()));
        // provenance marks the embodied surface.
        let prov = extract_script_json(&html, "ab-provenance").unwrap();
        assert_eq!(prov["generated_by"], json!(PRESENT_DASHBOARD_SCHEMA));
        assert_eq!(prov["surface"], json!("browser_tab"));
        assert_eq!(prov["chain_head"], json!(head));
    }

    // empty lane → dashboard still renders (summary + genesis head + an explicit
    // "no artifacts" row), so a human sees an empty-but-faithful mirror (vis>0,
    // not blank/dead).
    #[test]
    fn e3_dashboard_empty_lane_still_renders_genesis_head() {
        let snap = present_replay_snapshot(&[], 0, 86_400, 1_000);
        let html = build_dashboard_html(&snap, None);
        let region = render_region(&html).unwrap();
        assert!(region.contains("id=\"ab-chain-head\""));
        assert!(region.contains(PRESENT_REPLAY_ZERO_HASH));
        assert!(region.contains("no artifacts in window"));
    }

    // The E3 falsifier (pure): embodied iff rendered AND head matches the current
    // one; an older head is stale (live but behind); no render / no head is dead
    // (a broken mirror cannot pass); the genesis head is embodied when faithfully shown.
    #[test]
    fn e3_classify_embody_matrix() {
        let head = "abc123";
        let embodied = DashboardReadback {
            rendered: true,
            chain_head: head.into(),
            rows: 3,
        };
        assert_eq!(classify_embody(&embodied, head), EmbodyStatus::Embodied);

        let stale = DashboardReadback {
            rendered: true,
            chain_head: "0ldhead".into(),
            rows: 3,
        };
        assert_eq!(classify_embody(&stale, head), EmbodyStatus::Stale);

        // rendered but no head shown → broken mirror → Dead.
        let no_head = DashboardReadback {
            rendered: true,
            chain_head: String::new(),
            rows: 0,
        };
        assert_eq!(classify_embody(&no_head, head), EmbodyStatus::Dead);

        // nothing rendered → Dead (the E3 blank).
        let blank = DashboardReadback {
            rendered: false,
            chain_head: head.into(),
            rows: 0,
        };
        assert_eq!(classify_embody(&blank, head), EmbodyStatus::Dead);

        // empty lane faithfully shown → Embodied.
        let genesis = DashboardReadback {
            rendered: true,
            chain_head: PRESENT_REPLAY_ZERO_HASH.into(),
            rows: 0,
        };
        assert_eq!(
            classify_embody(&genesis, PRESENT_REPLAY_ZERO_HASH),
            EmbodyStatus::Embodied
        );
    }

    // parse_dashboard_readback tolerates object OR stringified JSON (mirrors parse_metrics)
    // and trims the head text.
    #[test]
    fn e3_parse_dashboard_readback_string_and_object() {
        let s =
            parse_dashboard_readback(&json!("{\"rendered\":true,\"chain_head\":\"deadbeef\",\"rows\":4}"));
        assert!(s.rendered);
        assert_eq!(s.chain_head, "deadbeef");
        assert_eq!(s.rows, 4);
        let o = parse_dashboard_readback(&json!({"rendered": false, "chain_head": " x ", "rows": 0}));
        assert!(!o.rendered);
        assert_eq!(o.chain_head, "x");
    }

    // Canary: the readback probe targets the right ids and returns exactly the
    // keys parse_dashboard_readback reads (cheap guard against silent drift).
    #[test]
    fn e3_dashboard_readback_js_canary() {
        for needle in ["ab-render", "ab-chain-head", "ab-events", "getClientRects"] {
            assert!(DASHBOARD_READBACK_JS.contains(needle), "readback-js missing {needle}");
        }
        for key in ["rendered", "chain_head", "rows"] {
            assert!(DASHBOARD_READBACK_JS.contains(key), "readback-js missing key {key}");
        }
        assert!(!DASHBOARD_READBACK_JS.contains("</script>"));
    }

    // The mirror does not mirror itself: the stable dashboard file is excluded from
    // list_artifacts, so writing it never feeds the present_replay chain it reflects.
    #[test]
    fn e3_list_artifacts_excludes_dashboard() {
        let dir = std::env::temp_dir().join(format!(
            "ab-present-e3-test-{}-{}",
            std::process::id(),
            now_unix()
        ));
        let prov = json!({"generated_by": "present/v0", "kind": "table", "ts": 111});
        write_artifact_atomic(
            &dir.join("aaaaaaaaaaaaaaaa.html"),
            &build_html(PresentKind::Table, "", None, Some(&json!([{"x": 1}])), Some(&prov)),
        )
        .unwrap();
        // a dashboard file sitting alongside the real artifacts must be skipped.
        let snap = present_replay_snapshot(&[], 0, 86_400, 1_000);
        write_artifact_atomic(
            &dir.join(format!("{DASHBOARD_BASENAME}.html")),
            &build_dashboard_html(&snap, None),
        )
        .unwrap();

        let all = list_artifacts(&dir, 50, None);
        assert_eq!(all.len(), 1, "dashboard must be excluded from the index");
        assert_eq!(all[0].id, "aaaaaaaaaaaaaaaa");
        assert!(all.iter().all(|a| a.id != DASHBOARD_BASENAME));

        let _ = std::fs::remove_dir_all(&dir);
    }

    // ----- Slice A (falsifier-gated verified outcome stream) -----

    // The gate is the fourth honesty surface: only a fully-verified render is
    // eligible for the training-signal stream; any failed axis rejects with a
    // reason naming it. Absent axes (verify-only renders) don't reject.
    #[test]
    fn slice_a_outcome_gate_truth_table() {
        // fully verified, no embody/interact/decision axes → eligible.
        assert!(outcome_gate("rendered_ok", None, None, None).0);
        // verified + embodied + interactive verified → eligible.
        assert!(outcome_gate("rendered_ok", Some("embodied"), Some("verified"), None).0);
        // verified + interactive not_applicable → eligible (no interactivity claimed).
        assert!(outcome_gate("rendered_ok", None, Some("not_applicable"), None).0);

        // render did not verify → rejected, reason names verify_status.
        let (ok, why) = outcome_gate("blank", None, None, None);
        assert!(!ok && why.contains("verify_status=blank"));
        let (ok, _) = outcome_gate("no_browser", None, None, None);
        assert!(!ok, "unverified render is not a training label");

        // rendered but embodiment stale/dead → rejected on the embody axis.
        let (ok, why) = outcome_gate("rendered_ok", Some("stale"), None, None);
        assert!(!ok && why.contains("embody_status=stale"));

        // rendered but a dead interactive control → rejected on the interact axis.
        let (ok, why) = outcome_gate("rendered_ok", None, Some("dead"), None);
        assert!(!ok && why.contains("interactive_status=dead"));

        // human-decision axis (approval cards): a real human decision (approve OR
        // reject) is a verified outcome; an undecided/timed-out/dead card is not.
        assert!(outcome_gate("rendered_ok", None, None, Some("approved")).0);
        assert!(
            outcome_gate("rendered_ok", None, None, Some("rejected")).0,
            "a human Reject is still a verified decision outcome"
        );
        let (ok, why) = outcome_gate("rendered_ok", None, None, Some("timed_out"));
        assert!(!ok && why.contains("decision=timed_out"), "timeout is never approval");
        let (ok, why) = outcome_gate("rendered_ok", None, None, Some("dead"));
        assert!(!ok && why.contains("decision=dead"));
    }

    // The projection tallies the FULL set regardless of verified_only, and
    // verified_only drops rejected rows from the surfaced list (so a consumer
    // never mistakes a filtered list for "all verified").
    #[test]
    fn slice_a_projection_tallies_full_set_and_filters() {
        let records = vec![
            json!({"artifact_id": "a", "verify_status": "rendered_ok", "ts": 3}),
            json!({"artifact_id": "b", "verify_status": "blank", "ts": 2}),
            json!({"artifact_id": "c", "verify_status": "rendered_ok", "interactive_status": "dead", "ts": 1}),
        ];
        let strict = present_outcomes_projection(&records, true);
        assert_eq!(strict["total_records"], json!(3));
        assert_eq!(strict["eligible_count"], json!(1));
        assert_eq!(strict["rejected_count"], json!(2));
        assert_eq!(strict["outcomes"].as_array().unwrap().len(), 1, "verified_only surfaces only eligible");
        assert_eq!(strict["outcomes"][0]["artifact_id"], json!("a"));
        assert_eq!(strict["outcomes"][0]["eligible"], json!(true));

        let full = present_outcomes_projection(&records, false);
        assert_eq!(full["eligible_count"], json!(1));
        assert_eq!(full["outcomes"].as_array().unwrap().len(), 3, "verified_only=false surfaces all, annotated");
        // each surfaced row carries the gate verdict + reason.
        let b = full["outcomes"].as_array().unwrap().iter().find(|r| r["artifact_id"] == json!("b")).unwrap();
        assert_eq!(b["eligible"], json!(false));
        assert!(b["gate_reason"].as_str().unwrap().contains("verify_status=blank"));
    }

    // Sidecar write → read roundtrip, newest-first, window-filtered.
    #[test]
    fn slice_a_outcome_sidecar_roundtrip_and_window() {
        let dir = std::env::temp_dir().join(format!(
            "ab-sliceA-test-{}-{}",
            std::process::id(),
            now_unix()
        ));
        write_outcome_sidecar(&dir, "old", &json!({"artifact_id": "old", "verify_status": "rendered_ok", "ts": 100})).unwrap();
        write_outcome_sidecar(&dir, "new", &json!({"artifact_id": "new", "verify_status": "rendered_ok", "ts": 300})).unwrap();
        // a non-sidecar file must be ignored.
        write_artifact_atomic(&dir.join("decoy.html"), "<p>x</p>").unwrap();

        let all = read_outcome_records(&dir, 50, 0);
        assert_eq!(all.len(), 2, "reads both sidecars, ignores non-sidecar files");
        assert_eq!(all[0]["artifact_id"], json!("new"), "newest-first");

        let windowed = read_outcome_records(&dir, 50, 200);
        assert_eq!(windowed.len(), 1, "ts<cutoff dropped");
        assert_eq!(windowed[0]["artifact_id"], json!("new"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    // ── Slice B (v0) — outcomes_memory_drift_snapshot falsifiers (T1-T6) ──
    // The pure fn takes represented_keys_by_artifact as a plain HashMap so the
    // tests are store-free and browser-free — and the fn provably cannot
    // self-fulfill (represented is decided by the passed-in probe, not by
    // anything the fn authored).

    fn vrec(artifact_id: &str, ts: u64) -> Value {
        // shape of a present_outcomes_projection(verified_only=true) entry
        json!({
            "artifact_id": artifact_id,
            "ts": ts,
            "intent": "x",
            "action_tool": "present",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "gate_reason": "verified",
            "eligible": true,
        })
    }

    fn empty_mentions() -> std::collections::HashMap<String, Vec<String>> {
        std::collections::HashMap::new()
    }

    #[test]
    fn slice_b_drift_computes_represented_and_missing() {
        // T1: K of N have a probe match → represented_count==K, drift==N-K.
        use std::collections::HashMap;
        let recs = vec![vrec("aaa1", 1), vrec("bbb2", 2), vrec("ccc3", 3)];
        let mut probe: HashMap<String, Vec<String>> = HashMap::new();
        probe.insert("aaa1".into(), vec!["outcome_aaa1".into()]); // represented
        probe.insert("bbb2".into(), vec![]); // missing
        // ccc3 absent from map → missing
        let snap = outcomes_memory_drift_snapshot(&recs, &probe, &empty_mentions(), 999, 86400);
        assert_eq!(snap["verified_count"], json!(3));
        assert_eq!(snap["represented_count"], json!(1));
        assert_eq!(snap["missing_count"], json!(2));
        assert_eq!(snap["drift"], json!(2));
    }

    #[test]
    fn slice_b_drift_missing_emits_proposed_candidate() {
        use std::collections::HashMap;
        let recs = vec![vrec("dead1", 5)];
        let probe: HashMap<String, Vec<String>> = HashMap::new(); // missing
        let snap = outcomes_memory_drift_snapshot(&recs, &probe, &empty_mentions(), 1, 1);
        let ev = &snap["events"][0];
        assert_eq!(ev["represented"], json!(false));
        assert_eq!(ev["proposed_key"], json!("outcome_dead1"));
        assert_eq!(ev["proposed_kind"], json!("present_outcome"));
        assert_eq!(ev["proposed_scope"], json!("outcome:dead1"));
        // represented record must NOT carry a proposed_* candidate.
        let mut p: HashMap<String, Vec<String>> = HashMap::new();
        p.insert("dead1".into(), vec!["outcome_dead1".into()]);
        let snap2 = outcomes_memory_drift_snapshot(&recs, &p, &empty_mentions(), 1, 1);
        assert!(snap2["events"][0].get("proposed_key").is_none());
    }

    #[test]
    fn slice_b_drift_proposed_tags_include_decision_for_approval() {
        // LOW fix: proposed_tags must match build_outcome_memory (decision tag).
        use std::collections::HashMap;
        let mut approval = vrec("appr00001234", 1);
        approval["action_tool"] = json!("present_await_decision");
        approval["decision"] = json!("approved");
        let snap = outcomes_memory_drift_snapshot(&[approval], &HashMap::new(), &empty_mentions(), 0, 1);
        let tags = snap["events"][0]["proposed_tags"].as_array().unwrap();
        assert!(tags.iter().any(|t| t == "decision:approved"));
    }

    #[test]
    fn slice_b_drift_keyless_record_emits_no_proposed_candidate() {
        // LOW fix: a keyless (empty artifact_id) record must NOT advertise a
        // proposed candidate (build_outcome_memory refuses it).
        use std::collections::HashMap;
        let keyless = json!({"ts": 1u64, "verify_status": "rendered_ok", "gate_reason": "verified"});
        let snap = outcomes_memory_drift_snapshot(&[keyless], &HashMap::new(), &empty_mentions(), 0, 1);
        assert!(snap["events"][0].get("proposed_key").is_none());
    }

    #[test]
    fn slice_b_drift_dedupes_duplicate_artifact_id() {
        // LOW fix: a repeated artifact_id closes with ONE write, so counts are
        // over DISTINCT artifacts — two missing records with the same id → drift==1.
        use std::collections::HashMap;
        let recs = vec![vrec("dup00001234", 1), vrec("dup00001234", 2)];
        let snap = outcomes_memory_drift_snapshot(&recs, &HashMap::new(), &empty_mentions(), 0, 1);
        assert_eq!(snap["verified_count"], json!(1), "distinct artifacts");
        assert_eq!(snap["drift"], json!(1), "one write closes the loop, not two");
        assert_eq!(snap["event_count"], json!(2), "but both records still audited");
    }

    #[test]
    fn slice_b_drift_tamper_and_reorder_evident() {
        // T3: flipping an identity field OR reordering changes chain_head.
        use std::collections::HashMap;
        let probe: HashMap<String, Vec<String>> = HashMap::new();
        let a = vec![vrec("id1", 1), vrec("id2", 2)];
        let h1 = outcomes_memory_drift_snapshot(&a, &probe, &empty_mentions(), 0, 1)["chain_head"].clone();
        // reorder by giving id2 an earlier ts so sort order flips
        let b = vec![vrec("id1", 5), vrec("id2", 2)];
        let h2 = outcomes_memory_drift_snapshot(&b, &probe, &empty_mentions(), 0, 1)["chain_head"].clone();
        assert_ne!(h1, h2, "different ts ordering must change chain_head");
        // flip a represented bit → chain changes (represented is in the hash)
        let mut p: HashMap<String, Vec<String>> = HashMap::new();
        p.insert("id1".into(), vec!["outcome_id1".into()]);
        let h3 = outcomes_memory_drift_snapshot(&a, &p, &empty_mentions(), 0, 1)["chain_head"].clone();
        assert_ne!(h1, h3, "flipping represented must change chain_head");
    }

    #[test]
    fn slice_b_drift_empty_is_genesis_not_error() {
        // T4: empty stream → counts 0, chain_head == genesis.
        let snap = outcomes_memory_drift_snapshot(&[], &empty_mentions(), &empty_mentions(), 7, 9);
        assert_eq!(snap["verified_count"], json!(0));
        assert_eq!(snap["drift"], json!(0));
        assert_eq!(snap["chain_head"], json!(PRESENT_REPLAY_ZERO_HASH));
    }

    #[test]
    fn slice_b_drift_no_cross_contamination() {
        // T5: one record's zero matches yields represented=false even when
        // another record in the same snapshot matches.
        use std::collections::HashMap;
        let recs = vec![vrec("hit0aaaa", 1), vrec("miss0bbb", 2)];
        let mut probe: HashMap<String, Vec<String>> = HashMap::new();
        probe.insert("hit0aaaa".into(), vec!["outcome_hit0aaaa".into()]);
        probe.insert("miss0bbb".into(), vec![]);
        let snap = outcomes_memory_drift_snapshot(&recs, &probe, &empty_mentions(), 0, 1);
        let by_id: std::collections::HashMap<String, bool> = snap["events"]
            .as_array()
            .unwrap()
            .iter()
            .map(|e| {
                (
                    e["artifact_id"].as_str().unwrap().to_string(),
                    e["represented"].as_bool().unwrap(),
                )
            })
            .collect();
        assert_eq!(by_id["hit0aaaa"], true);
        assert_eq!(by_id["miss0bbb"], false);
    }

    #[test]
    fn slice_b_drift_mentions_do_not_count_as_represented() {
        // review fix: a loose substring mention (not the outcome_ row) must NOT
        // mark represented — it is surfaced separately so drift is not understated.
        use std::collections::HashMap;
        let recs = vec![vrec("mention01234", 1)];
        let probe: HashMap<String, Vec<String>> = HashMap::new(); // no exact outcome_ row
        let mut mentions: HashMap<String, Vec<String>> = HashMap::new();
        mentions.insert("mention01234".into(), vec!["some_lesson_key".into()]);
        let snap = outcomes_memory_drift_snapshot(&recs, &probe, &mentions, 0, 1);
        assert_eq!(snap["represented_count"], json!(0));
        assert_eq!(snap["drift"], json!(1), "a mere mention is not representation");
        assert_eq!(snap["events"][0]["mentions"], json!(["some_lesson_key"]));
    }

    #[test]
    fn slice_b_drift_flags_absent_embody_status() {
        // T6 (honesty): present()-origin records omit embody_status; surface it
        // as a known limitation rather than implying the embody axis was checked.
        let recs = vec![vrec("noembody1234", 1)]; // vrec has no embody_status
        let snap = outcomes_memory_drift_snapshot(&recs, &empty_mentions(), &empty_mentions(), 0, 1);
        assert_eq!(snap["embody_status_absent"], json!(1));
    }
}
