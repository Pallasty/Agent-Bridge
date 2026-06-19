//! Produce a real session-walkthrough HTML artifact and self-check it.
//!
//! Surface-free producer for the evidence-anchored walkthrough renderer
//! (`present::build_walkthrough_html` / `write_walkthrough_artifact`). It writes
//! into the present artifact store (`~/.cache/agent-bridge/presentations/`), so
//! the result is listed by `present_list` and viewable through the same gallery
//! as any other present artifact — NO new MCP tool.
//!
//!   # render any walkthrough doc (JSON) → artifact:
//!   cargo run -p ab-bridge --example walkthrough_demo -- /path/to/doc.json
//!   # or, with no arg, render THIS session's real arc as a grounded demo:
//!   cargo run -p ab-bridge --example walkthrough_demo
//!
//! Doc shape:
//!   { "summary": "...",
//!     "steps": [ { "heading": "...", "narrative": "...",
//!                  "evidence": [ { "kind": "...", "reference": "...",
//!                                  "label": "..." } ] } ] }

use ab_bridge::present::{
    extract_ab_payload, presentations_dir, render_region, write_walkthrough_artifact,
};
use serde_json::{json, Value};

fn main() {
    // Either render a caller-supplied doc, or the built-in grounded demo of
    // this very session's arc (every evidence anchor below is a REAL artifact).
    let (doc, title): (Value, String) = match std::env::args().nth(1) {
        Some(path) => {
            let raw = std::fs::read_to_string(&path).expect("read doc json");
            let doc: Value = serde_json::from_str(&raw).expect("parse doc json");
            (doc, format!("Walkthrough — {path}"))
        }
        None => (session_arc_demo(), "AB session walkthrough — gos_lite + present artifact".into()),
    };

    let provenance = json!({
        "source": "walkthrough_demo",
        "node": "aio2",
        "project": "agent-bridge",
    });

    let dir = presentations_dir();
    let (id, path) =
        write_walkthrough_artifact(&dir, &doc, Some(&title), Some(&provenance)).expect("write");
    eprintln!("[walkthrough] wrote artifact id={id}");
    eprintln!("[walkthrough] path={}", path.display());

    // Self-check (no green-laundering): read the written file back and confirm
    // it actually carries the rendered content + an extractable payload.
    let html = std::fs::read_to_string(&path).expect("read back");
    let region = render_region(&html).expect("render region present");
    let payload = extract_ab_payload(&html).expect("ab-payload extractable");
    let steps = doc.get("steps").and_then(Value::as_array).map_or(0, Vec::len);

    let mut ok = true;
    let mut check = |name: &str, cond: bool| {
        eprintln!("[check] {name}: {}", if cond { "PASS" } else { "FAIL" });
        ok &= cond;
    };
    check("schema tag injected", payload["schema"] == "present_walkthrough/v0");
    check("payload step count matches doc", payload.get("steps").and_then(Value::as_array).map_or(0, Vec::len) == steps);
    check("render region non-empty", region.trim().len() > 40);
    check("payload lives outside verified region", !region.contains("ab-payload"));
    // Evidence is actually anchored in the human render (grounded, not hidden).
    if let Some(first_ev_ref) = doc["steps"][0]["evidence"][0]["reference"].as_str() {
        check("first evidence ref appears in render", region.contains(first_ev_ref));
    }

    eprintln!("[walkthrough] self-check: {}", if ok { "ALL PASS" } else { "FAILED" });
    if !ok {
        std::process::exit(2);
    }
}

/// This session's real arc, every anchor a real commit / thread / memory key.
fn session_arc_demo() -> Value {
    json!({
        "summary": "aio2 session: promoted the gos_lite SSB diagnostic to the default tier, dogfooded it, then borrowed the artifact-as-shareable-doc idea into the present lane as an evidence-anchored walkthrough.",
        "steps": [
            {
                "heading": "Promote gos_lite_snapshot Niche → Standard",
                "narrative": "gos_lite is the SSB belief-graph synthesis over Essential-tier telemetry; its siblings (semantic_bus_*) were already Standard. Flipped the registry tier so it is reachable on the default standard profile, surface-free.",
                "evidence": [
                    {"kind": "commit", "reference": "eeddcf2", "label": "feat(ssb): promote gos_lite_snapshot to Standard tier"},
                    {"kind": "verdict", "reference": "verified", "label": "1040 lib tests green; live standard=126 tools (has it) / codex-lean=40 (absent)"},
                    {"kind": "forum", "reference": "thread 111", "label": "GoS-lite readiness board"}
                ]
            },
            {
                "heading": "Dogfood gos_lite → stale finding, live-falsified",
                "narrative": "First default-on call surfaced memory_search failing with 'no such column: assembly' (replay verdict supported). Live-falsified on the deployed binary: assembly:test → graceful empty, content:gos_lite → works. The bug was already fixed; the telemetry sample predated the fix.",
                "evidence": [
                    {"kind": "commit", "reference": "4d1a7a2", "label": "Fix spaced FTS column filters in memory search (the real fix)"},
                    {"kind": "memory", "reference": "lesson_gos_lite_telemetry_stale_findings_live_falsify_20260618", "label": "live-falsify before acting on telemetry findings"}
                ]
            },
            {
                "heading": "Evaluate external artifact tools → borrow, not adopt",
                "narrative": "Anthropic Artifacts-in-CC (closed), austeane/walkthrough (local skill), serenakeyitan/tdoc (Cloudflare). All validate SSB §3.6 presentation; verify-first found present.rs already renders interactive HTML, so the value is borrow-design not adopt-codebase.",
                "evidence": [
                    {"kind": "memory", "reference": "decision_artifacts_walkthrough_tdoc_borrow_not_adopt_20260618", "label": "evaluation + verdict"},
                    {"kind": "forum", "reference": "thread 114", "label": "presentation-artifact claim (claim-before-execute)"}
                ]
            },
            {
                "heading": "Land the evidence-anchored walkthrough renderer",
                "narrative": "Added build_walkthrough_html + write_walkthrough_artifact to the present lane: a session walkthrough renders to a self-contained HTML artifact reusing build_html (inherits dual-encoding + self-verify honesty). Each step anchors to real evidence — the AB differentiator. This very page is its own output.",
                "evidence": [
                    {"kind": "commit", "reference": "a012681", "label": "feat(present): evidence-anchored session walkthrough HTML renderer"},
                    {"kind": "file", "reference": "crates/bridge/src/present.rs", "label": "build_walkthrough_html / write_walkthrough_artifact"},
                    {"kind": "verdict", "reference": "verified", "label": "present module 96/96 tests; this artifact self-checked on write"}
                ]
            }
        ]
    })
}
