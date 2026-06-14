//! SSB Phase-1 typed semantic event — the produced (not derived) end of the
//! canonical loop `Semantic Object → Affordance → Action → Event → Verification`.
//!
//! [`crate::event_spine`] derives an after-the-fact hash chain over telemetry
//! rows. This module is the other half: a real producer emits a [`SemanticEvent`]
//! AT ACTION TIME carrying a verify-first [`Verdict`], so the "no green
//! laundering" invariant becomes a recorded mechanism rather than a convention —
//! an action that would be inert is stamped [`VerdictStatus::NotVerified`] and is
//! never reported as a silent success.
//!
//! v0 wires exactly one producer (`browser_click` / `click_by_ref`). The typed
//! event is persisted via `StateStore::record_semantic_event` and surfaced as a
//! real-producer source inside `event_spine_snapshot`.

use ab_store::SemanticEventRecord;
use serde::Serialize;
use serde_json::{json, Value};

/// Verify-first outcome of an action. The whole point of the event spine: a
/// verdict that propagates end-to-end and is never faked to green.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum VerdictStatus {
    /// The action was positively confirmed to have had its intended effect.
    Verified,
    /// The action was determined to be (or to have been) inert / to have failed
    /// — recorded honestly instead of as success.
    NotVerified,
    /// The action was dispatched but we have no readback to confirm its effect.
    Unknown,
}

impl VerdictStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            VerdictStatus::Verified => "verified",
            VerdictStatus::NotVerified => "not_verified",
            VerdictStatus::Unknown => "unknown",
        }
    }

    /// Map to the event-spine `ok` tri-state: verified=true, not_verified=false,
    /// unknown=None (so the hash-chain projection keeps the honesty distinction).
    pub fn as_ok(self) -> Option<bool> {
        match self {
            VerdictStatus::Verified => Some(true),
            VerdictStatus::NotVerified => Some(false),
            VerdictStatus::Unknown => None,
        }
    }
}

/// A verdict plus how it was reached and the evidence behind it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Verdict {
    pub status: VerdictStatus,
    /// How the verdict was reached, e.g. "cdp_actionability_probe".
    pub method: String,
    /// Evidence behind the verdict (may be `Value::Null`).
    pub evidence: Value,
}

/// A produced semantic event ready to persist.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SemanticEvent {
    pub ts: i64,
    pub actor: String,
    pub source: String,
    pub action: String,
    pub target: Option<String>,
    pub verdict: Verdict,
    pub facts: Value,
}

impl SemanticEvent {
    /// Convert to the storage record (`StateStore::record_semantic_event`).
    pub fn to_record(&self) -> SemanticEventRecord {
        let evidence = if self.verdict.evidence.is_null() {
            None
        } else {
            Some(self.verdict.evidence.to_string())
        };
        SemanticEventRecord {
            ts: self.ts,
            actor: self.actor.clone(),
            source: self.source.clone(),
            action: self.action.clone(),
            target: self.target.clone(),
            verdict_status: self.verdict.status.as_str().to_string(),
            verdict_method: self.verdict.method.clone(),
            evidence,
            facts: self.facts.to_string(),
        }
    }
}

/// Classify a browser-click outcome into a verify-first verdict. Pure + total so
/// the "no green laundering" guarantee is unit-testable without a live browser.
///
/// - `is_ref`  — true when the click went through the `@eN` ref path
///   (`click_by_ref`), which probes actionability (connected/visible/enabled)
///   before dispatching a real mouse event.
/// - `ok`      — whether the click call returned success.
/// - `err_msg` — the error text when `ok` is false (empty otherwise).
///
/// Mapping:
/// - ref + ok                              → Verified (probe confirmed + real mouse)
/// - ref + refused/detached (would no-op)  → NotVerified (the inert case is caught)
/// - ref + other failure                   → Unknown (ref-resolution / transport)
/// - css + ok                              → Unknown (dispatched, no readback)
/// - css + failure                         → NotVerified (the click did not occur)
pub fn classify_click(is_ref: bool, ok: bool, err_msg: &str) -> Verdict {
    if is_ref {
        if ok {
            return Verdict {
                status: VerdictStatus::Verified,
                method: "cdp_actionability_probe+real_mouse".to_string(),
                evidence: json!({ "probe": "connected+visible+enabled", "dispatched": "mousePressed+mouseReleased" }),
            };
        }
        // The actionability probe loudly refuses a no-op (disabled / zero-box) or
        // a detached ref; that refusal is a real NOT-VERIFIED signal, not noise.
        let lc = err_msg.to_ascii_lowercase();
        let refused = lc.contains("refused")
            || lc.contains("detached from the dom")
            || lc.contains("disabled")
            || lc.contains("zero render box");
        if refused {
            return Verdict {
                status: VerdictStatus::NotVerified,
                method: "cdp_actionability_probe".to_string(),
                evidence: json!({ "reason": err_msg }),
            };
        }
        return Verdict {
            status: VerdictStatus::Unknown,
            method: "ref_resolution_or_transport".to_string(),
            evidence: json!({ "error": err_msg }),
        };
    }
    if ok {
        Verdict {
            status: VerdictStatus::Unknown,
            method: "css_selector_dispatch_no_readback".to_string(),
            evidence: json!({ "note": "dispatched via CSS selector; effect not read back" }),
        }
    } else {
        Verdict {
            status: VerdictStatus::NotVerified,
            method: "css_selector_dispatch".to_string(),
            evidence: json!({ "error": err_msg }),
        }
    }
}

/// Classify a `desktop_action` outcome into a verify-first verdict. Pure + total
/// so the "no green laundering" guarantee is unit-testable without a live desktop.
///
/// `desktop_action` injects input but never reads back the resulting UI state
/// (that is `desktop_verify`'s separate job), so a *successful injection* is
/// honestly [`VerdictStatus::Unknown`], NOT `Verified` — the same anti-laundering
/// distinction as the CSS-click path in [`classify_click`].
///
/// - `mode`    — the execution mode the wrapper resolved:
///   `"dry-run"`, `"isolated"`, `"host-grant"`, `"pending-host-confirm"`, or
///   `"refused"` (a preflight block such as host injection not being exposed).
/// - `ok`      — whether the underlying call/script reported success.
/// - `err_msg` — the error/stderr text when `ok` is false (empty otherwise).
///
/// Mapping:
/// - refused                                  → NotVerified (the action never ran)
/// - dry-run / pending-host-confirm + ok      → Unknown (no input injected by design)
/// - dry-run / pending-host-confirm + !ok     → NotVerified (the stage/dry-run failed)
/// - isolated / host-grant + ok               → Unknown (injected, effect not read back)
/// - isolated / host-grant + !ok              → NotVerified (the injection failed/blocked)
pub fn classify_action(mode: &str, ok: bool, err_msg: &str) -> Verdict {
    match mode {
        // Preflight refusal: the action never ran (host injection not exposed,
        // bad target, missing script...). It did NOT take effect, so it is
        // recorded honestly as not_verified — never laundered to a green success.
        "refused" => Verdict {
            status: VerdictStatus::NotVerified,
            method: "preflight_refusal".to_string(),
            evidence: json!({ "reason": err_msg }),
        },
        // No input was injected by design: dry-run logs intent only;
        // pending-host-confirm just stages a token for a later human confirm.
        "dry-run" | "pending-host-confirm" => {
            if ok {
                Verdict {
                    status: VerdictStatus::Unknown,
                    method: format!("{mode}_no_injection"),
                    evidence: json!({ "note": "no input injected; action effect not produced" }),
                }
            } else {
                Verdict {
                    status: VerdictStatus::NotVerified,
                    method: format!("{mode}_failed"),
                    evidence: json!({ "error": err_msg }),
                }
            }
        }
        // Input was actually injected — isolated nested compositor, or host via a
        // human-minted grant. desktop_action has no readback, so a successful
        // injection is Unknown (not Verified); a failed/blocked one is NotVerified.
        _ => {
            if ok {
                Verdict {
                    status: VerdictStatus::Unknown,
                    method: format!("{mode}_injected_no_readback"),
                    evidence: json!({ "note": "input injected; effect not read back (use desktop_verify)" }),
                }
            } else {
                Verdict {
                    status: VerdictStatus::NotVerified,
                    method: format!("{mode}_injection_failed"),
                    evidence: json!({ "error": err_msg }),
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ref_ok_is_verified() {
        let v = classify_click(true, true, "");
        assert_eq!(v.status, VerdictStatus::Verified);
        assert_eq!(v.status.as_ok(), Some(true));
    }

    #[test]
    fn ref_disabled_is_not_verified_not_green() {
        // The falsifier: a click that would no-op MUST be not_verified, never
        // reported as a green success.
        let v = classify_click(
            true,
            false,
            "ref @e5 element is disabled — click refused (it would no-op)",
        );
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.status.as_ok(), Some(false));
    }

    #[test]
    fn ref_zero_box_is_not_verified() {
        let v = classify_click(
            true,
            false,
            "ref @e9 element has a zero render box (hidden/occluded) — click refused",
        );
        assert_eq!(v.status, VerdictStatus::NotVerified);
    }

    #[test]
    fn ref_detached_is_not_verified() {
        let v = classify_click(
            true,
            false,
            "ref @e2 element is detached from the DOM — re-snapshot the page",
        );
        assert_eq!(v.status, VerdictStatus::NotVerified);
    }

    #[test]
    fn ref_unknown_ref_is_unknown_not_false_green() {
        // A ref-resolution failure is genuinely unknown (we never probed an
        // element), distinct from a confirmed no-op.
        let v = classify_click(true, false, "unknown ref @e1 — call browser_snapshot first");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert_eq!(v.status.as_ok(), None);
    }

    #[test]
    fn css_ok_is_unknown_never_faked_verified() {
        // CSS path has no readback, so an ok dispatch is honestly Unknown, NOT
        // Verified — that distinction is the anti-laundering property.
        let v = classify_click(false, true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
    }

    #[test]
    fn css_failure_is_not_verified() {
        let v = classify_click(false, false, "click div.missing: node not found");
        assert_eq!(v.status, VerdictStatus::NotVerified);
    }

    #[test]
    fn to_record_serializes_verdict_and_drops_null_evidence() {
        let ev = SemanticEvent {
            ts: 100,
            actor: "mcp".to_string(),
            source: "browser".to_string(),
            action: "click".to_string(),
            target: Some("@e5".to_string()),
            verdict: Verdict {
                status: VerdictStatus::Verified,
                method: "m".to_string(),
                evidence: Value::Null,
            },
            facts: json!({"selector": "@e5"}),
        };
        let rec = ev.to_record();
        assert_eq!(rec.verdict_status, "verified");
        assert_eq!(rec.target.as_deref(), Some("@e5"));
        assert!(rec.evidence.is_none());
        assert!(rec.facts.contains("@e5"));
    }

    #[test]
    fn action_isolated_ok_is_unknown_never_faked_verified() {
        // Injection succeeded but desktop_action has no readback, so the honest
        // verdict is Unknown — claiming Verified here would be laundering.
        let v = classify_action("isolated", true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert_eq!(v.status.as_ok(), None);
    }

    #[test]
    fn action_isolated_failure_is_not_verified() {
        let v = classify_action("isolated", false, "sway-ipc backend refused output socket");
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.status.as_ok(), Some(false));
    }

    #[test]
    fn action_refused_host_is_not_verified_not_green() {
        // The falsifier: a host action that was refused (never injected) MUST be
        // not_verified, never reported as a green success.
        let v = classify_action("refused", false, "host_mutation_not_exposed");
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.status.as_ok(), Some(false));
    }

    #[test]
    fn action_dry_run_ok_is_unknown_no_injection() {
        // Dry-run injects nothing by design; it is not a success and not a
        // failure — honestly Unknown.
        let v = classify_action("dry-run", true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert!(v.method.contains("no_injection"));
    }

    #[test]
    fn action_pending_host_confirm_ok_is_unknown_no_injection() {
        // Staging a confirm token injects nothing; the effect is deferred, so
        // Unknown, never Verified.
        let v = classify_action("pending-host-confirm", true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
    }

    #[test]
    fn action_host_grant_ok_is_unknown_no_readback() {
        let v = classify_action("host-grant", true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert!(v.method.contains("injected_no_readback"));
    }

    #[test]
    fn action_dry_run_failure_is_not_verified() {
        let v = classify_action("dry-run", false, "script crashed");
        assert_eq!(v.status, VerdictStatus::NotVerified);
    }
}
