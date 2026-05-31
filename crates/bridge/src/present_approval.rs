//! Host-confirm path B — present() approval card (Linux Computer Use, thread 79).
//!
//! The decision-channel piece the present lane was missing (see #1919 RFC to the
//! present owner): a self-contained approval surface that renders a pending HOST
//! desktop action's summary + its single-use confirm token with Approve / Reject
//! buttons. A human click stamps a `#ab-decision` element in the DOM; the server
//! reads that back via `eval` (the same readback-from-DOM pattern as the E3
//! `DASHBOARD_READBACK_JS`), turning a client-side click into a server-side verdict
//! WITHOUT any new HTTP origin or write-back endpoint.
//!
//! Deliberately isolated in its own module (zero edits to taste-skill-curate's
//! `present.rs`) so the present owner can review or relocate it. It only reuses the
//! lane's public file helpers (`presentations_dir`, `write_artifact_atomic`).
//!
//! Honest threat model (same as host-confirm paths A/C): on a box where the agent
//! has a shell + browser eval, `#ab-decision` is not agent-proof — its job is to put
//! a human-readable summary in front of a human and require a deliberate click, not
//! to sandbox an adversarial agent. The authority is borrowed entirely from path A:
//! Approve only matters because the caller then presents the (already human-minted)
//! token to `desktop_confirm`, which enforces single-use + TTL.

use serde_json::Value;

/// `present_await_decision` artifact schema tag.
pub const PRESENT_APPROVAL_SCHEMA: &str = "present_approval/v0";

/// CSS selector the server `wait_for`s on: the decision element once a human has
/// clicked (the buttons set `data-decided="1"`). Blocking on this turns the human
/// click into the unblock signal.
pub const APPROVAL_DECIDED_SELECTOR: &str = "#ab-decision[data-decided=\"1\"]";

/// JS evaluated in the loaded card to read the human's verdict back out of the DOM.
/// Mirrors [`crate::present::DASHBOARD_READBACK_JS`]: reads the human-clicked
/// `#ab-decision` (not machine chrome). `wired` reports whether the decision
/// affordance actually exists (the `#ab-decision` element AND both buttons), so a
/// card that rendered but offers no working approve/reject path is detectable as
/// `dead` rather than indistinguishable from "not yet decided". Keys MUST stay in
/// sync with [`parse_approval_readback`] — guarded by a unit canary.
pub const APPROVAL_READBACK_JS: &str = "JSON.stringify((function(){var d=document.getElementById('ab-decision');var t=document.getElementById('ab-token');var wired=(!!d&&!!document.getElementById('ab-approve')&&!!document.getElementById('ab-reject'));return{decided:(d?d.getAttribute('data-decided')==='1':false),decision:(d?(d.textContent||'').trim():''),token:(t?(t.textContent||'').trim():''),wired:wired};})())";

/// JS that simulates a human click (sets the decision) — used only by acceptance
/// harnesses / live-verify to exercise the readback machinery without a real human
/// (the production unblock is a real button click). `decision` is "approve"|"reject".
pub fn approval_stamp_js(decision: &str) -> String {
    let d = if decision == "approve" {
        "approve"
    } else {
        "reject"
    };
    format!("(function(){{var e=document.getElementById('ab-decision');if(!e)return false;e.textContent='{d}';e.setAttribute('data-decided','1');return true;}})()")
}

/// Readback signature from [`APPROVAL_READBACK_JS`], parsed for [`classify_approval`].
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ApprovalReadback {
    /// A human clicked a button (`#ab-decision[data-decided="1"]`).
    pub decided: bool,
    /// The verdict text the clicked button stamped ("approve" | "reject").
    pub decision: String,
    /// The token the card rendered (so the verdict provably refers to THIS action).
    pub token: String,
    /// The decision affordance exists: the `#ab-decision` element AND both buttons.
    /// `false` means the card cannot ever be decided (broken/tampered) → `Dead`.
    pub wired: bool,
}

/// Parse the approval readback JSON. Tolerant of object-or-stringified-JSON like
/// [`crate::present::parse_dashboard_readback`].
pub fn parse_approval_readback(v: &Value) -> ApprovalReadback {
    let obj = match v {
        Value::String(s) => serde_json::from_str::<Value>(s).unwrap_or(Value::Null),
        other => other.clone(),
    };
    ApprovalReadback {
        decided: obj.get("decided").and_then(Value::as_bool).unwrap_or(false),
        decision: obj
            .get("decision")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string(),
        token: obj
            .get("token")
            .and_then(Value::as_str)
            .unwrap_or("")
            .trim()
            .to_string(),
        // Absent `wired` (older readback / tolerant default) assumes a wired card so
        // we don't spuriously report `dead`; the readback JS always emits it now.
        wired: obj.get("wired").and_then(Value::as_bool).unwrap_or(true),
    }
}

/// The verdict a human gave (pure, browser-free — sibling of
/// [`crate::present::classify_embody`]). `Dead` when the card offers no working
/// decision affordance (cannot ever be decided — broken/tampered); `Pending` while
/// a wired card awaits a click; an unrecognized stamp stays `Pending` (the lane
/// never reads a verdict it can't name). The tool layer maps a `Pending` that
/// survived the `wait_for` window to `timed_out` (a timeout is never an approval).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApprovalDecision {
    Pending,
    Approved,
    Rejected,
    Dead,
}

impl ApprovalDecision {
    pub fn as_str(&self) -> &'static str {
        match self {
            ApprovalDecision::Pending => "pending",
            ApprovalDecision::Approved => "approved",
            ApprovalDecision::Rejected => "rejected",
            ApprovalDecision::Dead => "dead",
        }
    }
    /// True only for an explicit human Approve — the single point that authorizes
    /// the caller to proceed to `desktop_confirm(token)`.
    pub fn is_approved(&self) -> bool {
        matches!(self, ApprovalDecision::Approved)
    }
}

pub fn classify_approval(r: &ApprovalReadback) -> ApprovalDecision {
    // A card with no decision affordance can never be decided → Dead (distinct from
    // a wired card that simply hasn't been clicked yet, which is Pending).
    if !r.wired {
        return ApprovalDecision::Dead;
    }
    if !r.decided {
        return ApprovalDecision::Pending;
    }
    match r.decision.as_str() {
        "approve" => ApprovalDecision::Approved,
        "reject" => ApprovalDecision::Rejected,
        _ => ApprovalDecision::Pending,
    }
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

/// Build the standalone approval-card HTML. Layout mirrors the present lane's
/// convention: machine chrome (`#ab-payload`) in `<head>`, the human surface inside
/// `<main id="ab-render">`, the readback target `#ab-decision` stamped only by a
/// real button click. `summary` and `token` are HTML-escaped.
pub fn build_approval_html(summary: &str, token: &str, title: Option<&str>) -> String {
    let title_str = title.unwrap_or("Agent-Bridge — approve host desktop action?");
    let payload = serde_json::json!({ "token": token, "summary": summary, "schema": PRESENT_APPROVAL_SCHEMA });
    let payload_json = serde_json::to_string(&payload)
        .unwrap_or_else(|_| "{}".to_string())
        .replace("</", "<\\/");
    format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<script type="application/json" id="ab-payload">{payload}</script>
<style>
  body{{font:15px/1.5 system-ui,sans-serif;margin:0;background:#1e1e2e;color:#cdd6f4;display:flex;min-height:100vh;align-items:center;justify-content:center}}
  main{{max-width:560px;padding:28px 32px;background:#181825;border:1px solid #313244;border-radius:12px;box-shadow:0 8px 32px #0008}}
  h1{{font-size:18px;margin:0 0 14px;color:#f38ba8}}
  .summary{{font-size:15px;background:#11111b;border-left:3px solid #f9e2af;padding:10px 14px;border-radius:6px;word-break:break-word}}
  .token{{font-size:12px;color:#6c7086;margin:14px 0 22px}}
  .btns{{display:flex;gap:14px}}
  button{{flex:1;font:600 15px system-ui;padding:12px;border:0;border-radius:8px;cursor:pointer}}
  #ab-approve{{background:#a6e3a1;color:#11111b}} #ab-reject{{background:#f38ba8;color:#11111b}}
  button:disabled{{opacity:.4;cursor:default}}
  #ab-decision{{display:block;margin-top:18px;font-size:13px;color:#a6adc8;min-height:1em}}
</style></head>
<body><main id="ab-render">
  <h1>Approve host desktop action?</h1>
  <p class="summary" id="ab-summary">{summary}</p>
  <p class="token">confirm token: <code id="ab-token">{token}</code></p>
  <div class="btns">
    <button id="ab-approve" type="button" onclick="abDecide('approve')">Approve</button>
    <button id="ab-reject" type="button" onclick="abDecide('reject')">Reject</button>
  </div>
  <code id="ab-decision" data-decided="0"></code>
</main>
<script>
function abDecide(d){{var e=document.getElementById('ab-decision');e.textContent=d;e.setAttribute('data-decided','1');
  document.getElementById('ab-approve').disabled=true;document.getElementById('ab-reject').disabled=true;}}
</script></body></html>
"#,
        title = html_escape(title_str),
        payload = payload_json,
        summary = html_escape(summary),
        token = html_escape(token),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn classify_approval_truth_table() {
        // a wired card awaiting a click → Pending.
        let pending = ApprovalReadback {
            decided: false,
            decision: String::new(),
            token: "t".into(),
            wired: true,
        };
        assert_eq!(classify_approval(&pending), ApprovalDecision::Pending);
        let approved = ApprovalReadback {
            decided: true,
            decision: "approve".into(),
            token: "t".into(),
            wired: true,
        };
        assert_eq!(classify_approval(&approved), ApprovalDecision::Approved);
        assert!(classify_approval(&approved).is_approved());
        let rejected = ApprovalReadback {
            decided: true,
            decision: "reject".into(),
            token: "t".into(),
            wired: true,
        };
        assert_eq!(classify_approval(&rejected), ApprovalDecision::Rejected);
        assert!(!classify_approval(&rejected).is_approved());
        // decided but unknown verdict stays Pending (never read a verdict we can't name)
        let weird = ApprovalReadback {
            decided: true,
            decision: "xyz".into(),
            token: "t".into(),
            wired: true,
        };
        assert_eq!(classify_approval(&weird), ApprovalDecision::Pending);
        // no decision affordance (broken/tampered card) → Dead, NOT Pending — and a
        // dead card is never approved.
        let dead = ApprovalReadback {
            decided: false,
            decision: String::new(),
            token: "t".into(),
            wired: false,
        };
        assert_eq!(classify_approval(&dead), ApprovalDecision::Dead);
        assert!(!classify_approval(&dead).is_approved());
    }

    #[test]
    fn readback_parse_tolerates_object_and_string() {
        let as_obj = json!({"decided": true, "decision": "approve", "token": "abc", "wired": true});
        let r1 = parse_approval_readback(&as_obj);
        assert!(r1.decided && r1.decision == "approve" && r1.token == "abc" && r1.wired);
        // stringified JSON (some backends return eval results as strings)
        let as_str = json!("{\"decided\":true,\"decision\":\"reject\",\"token\":\"def\",\"wired\":true}");
        let r2 = parse_approval_readback(&as_str);
        assert!(r2.decided && r2.decision == "reject" && r2.token == "def" && r2.wired);
        // a readback reporting no affordance parses wired=false.
        let unwired = parse_approval_readback(&json!({"decided": false, "wired": false}));
        assert!(!unwired.wired);
    }

    #[test]
    fn readback_js_keys_match_parser() {
        // canary: the readback JS must emit exactly the keys the parser reads.
        for k in ["decided", "decision", "token", "wired"] {
            assert!(
                APPROVAL_READBACK_JS.contains(k),
                "APPROVAL_READBACK_JS missing key {k} that parse_approval_readback reads"
            );
        }
    }

    #[test]
    fn build_html_embeds_summary_token_and_buttons() {
        let html = build_approval_html("invoke 'click' on Save in firefox", "deadbeefcafe", None);
        // human surface inside #ab-render
        assert!(html.contains("id=\"ab-render\""));
        assert!(html.contains("id=\"ab-summary\""));
        assert!(html.contains("invoke &#39;click&#39; on Save in firefox")); // summary HTML-escaped
        assert!(html.contains("id=\"ab-token\">deadbeefcafe"));
        // both buttons present + wired to the stamp
        assert!(html.contains("onclick=\"abDecide('approve')\""));
        assert!(html.contains("onclick=\"abDecide('reject')\""));
        // the readback target starts undecided
        assert!(html.contains("id=\"ab-decision\" data-decided=\"0\""));
        // machine chrome carries the token too (dual-encoding convention)
        assert!(html.contains("id=\"ab-payload\""));
        assert!(html.contains("deadbeefcafe"));
    }

    #[test]
    fn build_html_escapes_xss_in_summary() {
        let html = build_approval_html("<img src=x onerror=alert(1)>", "tok", None);
        // the human-visible summary is HTML-escaped (no live tag in the rendered surface)
        assert!(html.contains("&lt;img src=x onerror=alert(1)&gt;"));
        // the rendered region (everything from #ab-render on — AFTER the <head> payload)
        // carries NO raw executable tag; the only raw copy lives in the inert
        // application/json #ab-payload in <head>, which browsers never HTML-parse.
        let render = &html[html.find("id=\"ab-render\"").expect("ab-render")..];
        assert!(
            !render.contains("<img src=x"),
            "raw <img leaked into the rendered region (XSS)"
        );
        // the #ab-payload script cannot be broken out of: no literal </ from the summary
        assert!(!html.contains("</script>alert"));
    }
}
