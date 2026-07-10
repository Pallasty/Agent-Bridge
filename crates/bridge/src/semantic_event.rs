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

/// SSB unified contract — the semantic OBJECT an action targets (roadmap §3.1,
/// minimal producer-known subset). Every producer fills this with the same
/// vocabulary so browser / desktop / … events share one shape.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SemanticObject {
    /// Normalized kind, e.g. "dom_element", "desktop_input_surface".
    pub object_type: String,
    /// Which adapter observed/owns it, e.g. "browser", "desktop".
    pub source_adapter: String,
    /// Human-readable label when known.
    pub label: Option<String>,
    /// Stable reference when the adapter has one (e.g. "@e5"); None for
    /// coordinate/key surfaces with no resolved element.
    pub object_id: Option<String>,
}

/// SSB unified contract — the AFFORDANCE (available action) exercised
/// (roadmap §3.2, minimal producer-known subset).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Affordance {
    /// Action verb, e.g. "click", "type", "key".
    pub action_type: String,
    /// "low" | "medium" | "high".
    pub risk_level: String,
    /// Whether the surface gates this action (host injection, etc.).
    pub requires_gate: bool,
    /// What the action is expected to do, when known.
    pub expected_effect: Option<String>,
}

/// A produced semantic event ready to persist. Field order follows the canonical
/// loop `Object → Affordance → Action → Event → Verification`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SemanticEvent {
    pub ts: i64,
    pub actor: String,
    pub source: String,
    pub action: String,
    pub target: Option<String>,
    pub object: SemanticObject,
    pub affordance: Affordance,
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
        // SSB unified contract: serialize the normalized Object + Affordance into
        // the dedicated `descriptor` column (kept distinct from adapter-specific
        // `facts`). Built explicitly so a serialization slip can never panic.
        let descriptor = {
            let mut d = serde_json::Map::new();
            if let Ok(o) = serde_json::to_value(&self.object) {
                d.insert("object".to_string(), o);
            }
            if let Ok(a) = serde_json::to_value(&self.affordance) {
                d.insert("affordance".to_string(), a);
            }
            serde_json::to_string(&Value::Object(d)).ok()
        };
        let record = SemanticEventRecord {
            ts: self.ts,
            actor: self.actor.clone(),
            source: self.source.clone(),
            action: self.action.clone(),
            target: self.target.clone(),
            verdict_status: self.verdict.status.as_str().to_string(),
            verdict_method: self.verdict.method.clone(),
            evidence,
            facts: self.facts.to_string(),
            descriptor,
        };
        // SSB conformance gate (roadmap Gate E): every produced event MUST satisfy
        // the unified contract. Enforced as a debug assertion so any producer that
        // drifts (or launders a verdict) trips CI/tests; compiled out of release,
        // so deployed behavior is unchanged.
        debug_assert!(
            contract_violations(&record).is_empty(),
            "SemanticEvent violates the unified SSB contract: {:?}",
            contract_violations(&record)
        );
        record
    }
}

/// SSB unified-contract conformance check (roadmap Gate E). Returns the list of
/// contract violations for a persisted [`SemanticEventRecord`] (empty = conformant).
///
/// This codifies the unified Object/Affordance contract as an executable spec so
/// a future producer cannot silently emit a non-conformant — or laundered —
/// event. Every producer (browser / desktop / mobile / …) must pass it.
pub fn contract_violations(rec: &SemanticEventRecord) -> Vec<String> {
    let mut v = Vec::new();
    // Verdict must be one of the three honest states (no green laundering).
    if !matches!(
        rec.verdict_status.as_str(),
        "verified" | "not_verified" | "unknown"
    ) {
        v.push(format!(
            "verdict_status not in {{verified,not_verified,unknown}}: {:?}",
            rec.verdict_status
        ));
    }
    if rec.verdict_method.trim().is_empty() {
        v.push("verdict_method is empty".to_string());
    }
    // The unified contract requires the typed descriptor.
    let Some(desc_str) = rec.descriptor.as_deref() else {
        v.push("descriptor missing (the unified contract requires it)".to_string());
        return v;
    };
    let desc: Value = match serde_json::from_str(desc_str) {
        Ok(d) => d,
        Err(e) => {
            v.push(format!("descriptor is not valid JSON: {e}"));
            return v;
        }
    };
    // Object: object_type + source_adapter required; adapter must match the event.
    let obj = &desc["object"];
    for field in ["object_type", "source_adapter"] {
        if !obj
            .get(field)
            .and_then(|x| x.as_str())
            .map(|s| !s.is_empty())
            .unwrap_or(false)
        {
            v.push(format!("descriptor.object.{field} missing/empty"));
        }
    }
    if let Some(adapter) = obj.get("source_adapter").and_then(|x| x.as_str()) {
        if adapter != rec.source {
            v.push(format!(
                "source '{}' != descriptor.object.source_adapter '{}'",
                rec.source, adapter
            ));
        }
    }
    // Affordance: action_type + a valid risk_level + a boolean requires_gate.
    let aff = &desc["affordance"];
    if !aff
        .get("action_type")
        .and_then(|x| x.as_str())
        .map(|s| !s.is_empty())
        .unwrap_or(false)
    {
        v.push("descriptor.affordance.action_type missing/empty".to_string());
    }
    if !matches!(
        aff.get("risk_level").and_then(|x| x.as_str()),
        Some("low" | "medium" | "high")
    ) {
        v.push("descriptor.affordance.risk_level not in {low,medium,high}".to_string());
    }
    if !aff
        .get("requires_gate")
        .map(|x| x.is_boolean())
        .unwrap_or(false)
    {
        v.push("descriptor.affordance.requires_gate missing/not boolean".to_string());
    }
    v
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

/// Classify a `mobile_click` (adb `input tap`) outcome into a verify-first
/// verdict. Like the CSS-click and desktop-injection paths, an adb tap
/// dispatches input with NO readback, so a successful tap is honestly Unknown —
/// never Verified. A failed tap (no device, adb error, unmatched selector) is
/// NotVerified — the anti-laundering signal (a tap that never landed on a device
/// must never read as a green success).
pub fn classify_mobile(ok: bool, err_msg: &str) -> Verdict {
    if ok {
        return Verdict {
            status: VerdictStatus::Unknown,
            method: "adb_tap_no_readback".to_string(),
            evidence: json!({ "note": "adb input tap dispatched; effect not read back" }),
        };
    }
    let lc = err_msg.to_ascii_lowercase();
    let method = if lc.contains("device") || lc.contains("no android") {
        "no_device"
    } else {
        "adb_tap_failed"
    };
    Verdict {
        status: VerdictStatus::NotVerified,
        method: method.to_string(),
        evidence: json!({ "error": err_msg }),
    }
}

/// Classify a session-lifecycle step (`session_bootstrap`, `session_finalize`)
/// into a verify-first verdict. This is the distinguishing property of lifecycle
/// producers versus input taps: a tap dispatches with NO readback (→ Unknown),
/// but a lifecycle step HAS readback — the concrete effect count (memory rows
/// injected at bootstrap, memories compacted at finalize). So:
///
/// - ran + produced a concrete effect → Verified (the readback confirms it)
/// - ran + no effect (empty scope / dry-run) → Unknown (honest: nothing to
///   verify, but the step did NOT fail — never laundered to a green success)
/// - the step itself failed → NotVerified (anti-laundering)
///
/// Rich domain counts belong in the event's `facts` field; this verdict carries
/// only the generic lifecycle method/evidence (mirrors the sibling classifiers).
pub fn classify_lifecycle(ran: bool, made_effect: bool, err_msg: &str) -> Verdict {
    if !ran {
        return Verdict {
            status: VerdictStatus::NotVerified,
            method: "lifecycle_failed".to_string(),
            evidence: json!({ "error": err_msg }),
        };
    }
    if made_effect {
        Verdict {
            status: VerdictStatus::Verified,
            method: "lifecycle_readback".to_string(),
            evidence: json!({ "note": "lifecycle step produced a readable effect" }),
        }
    } else {
        Verdict {
            status: VerdictStatus::Unknown,
            method: "lifecycle_no_effect".to_string(),
            evidence: json!({ "note": "lifecycle step ran but produced no effect (empty scope / dry-run)" }),
        }
    }
}

/// A distilled recurring-failure pattern over the persisted semantic-event log
/// — the SSB "memory" arm of the canonical loop (`… → Verification → Memory`).
///
/// Where the recent-inert consumer surfaces the *last few* NotVerified events
/// (recency), this groups the whole retained log by failure MODE
/// `(source, action, verdict_method)` and keeps the modes that recur — turning a
/// stream of one-off inert events into a learned, durable lesson ("this
/// affordance keeps going inert this way; here is the fix").
///
/// The event log itself IS the cross-session memory substrate (append-only,
/// ring-capped, node-local), so the pattern is *computed from live evidence*
/// each time rather than written as a separate (launder-able) memory record:
/// the `count` is always the real recurrence, never a stale or faked claim.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct InertPattern {
    pub source: String,
    pub action: String,
    pub verdict_method: String,
    /// How many NotVerified events share this `(source, action, method)` signature.
    pub count: usize,
    /// Newest occurrence `ts` (for age display / sort tiebreak).
    pub last_ts: i64,
    /// A few distinct non-empty example targets (evidence the pattern is real).
    pub examples: Vec<String>,
}

/// Distill recurring inert/failed patterns from a slice of semantic-event
/// records. Considers ONLY `verdict_status == "not_verified"` (the verify-first
/// anti-laundering signal — never the green/unknown rows), groups by
/// `(source, action, verdict_method)`, and returns the groups whose recurrence
/// reaches `min_count`, most-recurring first (tiebreak: most-recent first).
///
/// Pure + total so the distillation is unit-testable without a store.
/// `min_count` is floored at 1; at most 3 distinct example targets are kept per
/// pattern.
pub fn cluster_inert_patterns(
    events: &[SemanticEventRecord],
    min_count: usize,
) -> Vec<InertPattern> {
    use std::collections::HashMap;
    let min_count = min_count.max(1);
    type Sig = (String, String, String);
    // Preserve first-seen signature order so output is deterministic before sort.
    let mut order: Vec<Sig> = Vec::new();
    let mut agg: HashMap<Sig, (usize, i64, Vec<String>)> = HashMap::new();
    for e in events.iter().filter(|e| e.verdict_status == "not_verified") {
        let key: Sig = (e.source.clone(), e.action.clone(), e.verdict_method.clone());
        if !agg.contains_key(&key) {
            order.push(key.clone());
        }
        let entry = agg.entry(key).or_insert((0usize, i64::MIN, Vec::new()));
        entry.0 += 1;
        entry.1 = entry.1.max(e.ts);
        if let Some(t) = e.target.as_deref().map(str::trim).filter(|t| !t.is_empty()) {
            if entry.2.len() < 3 && !entry.2.iter().any(|x| x == t) {
                entry.2.push(t.to_string());
            }
        }
    }
    let mut out: Vec<InertPattern> = order
        .into_iter()
        .filter_map(|key| {
            let (count, last_ts, examples) = agg.remove(&key)?;
            (count >= min_count).then_some(InertPattern {
                source: key.0,
                action: key.1,
                verdict_method: key.2,
                count,
                last_ts,
                examples,
            })
        })
        .collect();
    out.sort_by(|a, b| b.count.cmp(&a.count).then(b.last_ts.cmp(&a.last_ts)));
    out
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

    fn sample_event() -> SemanticEvent {
        SemanticEvent {
            ts: 100,
            actor: "mcp".to_string(),
            source: "browser".to_string(),
            action: "click".to_string(),
            target: Some("@e5".to_string()),
            object: SemanticObject {
                object_type: "dom_element".to_string(),
                source_adapter: "browser".to_string(),
                label: None,
                object_id: Some("@e5".to_string()),
            },
            affordance: Affordance {
                action_type: "click".to_string(),
                risk_level: "low".to_string(),
                requires_gate: false,
                expected_effect: Some("the targeted DOM element receives a click".to_string()),
            },
            verdict: Verdict {
                status: VerdictStatus::Verified,
                method: "m".to_string(),
                evidence: Value::Null,
            },
            facts: json!({"selector": "@e5"}),
        }
    }

    #[test]
    fn to_record_serializes_verdict_and_drops_null_evidence() {
        let rec = sample_event().to_record();
        assert_eq!(rec.verdict_status, "verified");
        assert_eq!(rec.target.as_deref(), Some("@e5"));
        assert!(rec.evidence.is_none());
        assert!(rec.facts.contains("@e5"));
    }

    #[test]
    fn to_record_emits_unified_object_affordance_descriptor() {
        let rec = sample_event().to_record();
        let d = rec.descriptor.expect("descriptor present");
        let v: Value = serde_json::from_str(&d).expect("descriptor is valid JSON");
        // The unified contract shape both producers must share.
        assert_eq!(v["object"]["object_type"], "dom_element");
        assert_eq!(v["object"]["source_adapter"], "browser");
        assert_eq!(v["object"]["object_id"], "@e5");
        assert_eq!(v["affordance"]["action_type"], "click");
        assert_eq!(v["affordance"]["risk_level"], "low");
        assert_eq!(v["affordance"]["requires_gate"], false);
        // descriptor is the contract; facts stays adapter-specific.
        assert!(rec.facts.contains("selector"));
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

    #[test]
    fn mobile_ok_is_unknown_never_faked_verified() {
        // adb tap has no readback, so a dispatched tap is honestly Unknown.
        let v = classify_mobile(true, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert_eq!(v.status.as_ok(), None);
    }

    #[test]
    fn mobile_no_device_is_not_verified_not_green() {
        // The falsifier: a tap with no device attached never landed — it MUST be
        // not_verified, never a green success.
        let v = classify_mobile(false, "no devices/emulators found");
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.status.as_ok(), Some(false));
        assert_eq!(v.method, "no_device");
    }

    #[test]
    fn mobile_adb_failure_is_not_verified() {
        let v = classify_mobile(false, "selector matched 0 node(s)");
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.method, "adb_tap_failed");
    }

    #[test]
    fn lifecycle_with_effect_is_verified() {
        // A bootstrap that injected memory rows (or a finalize that compacted
        // some) HAS readback, so it is honestly Verified.
        let v = classify_lifecycle(true, true, "");
        assert_eq!(v.status, VerdictStatus::Verified);
        assert_eq!(v.status.as_ok(), Some(true));
        assert_eq!(v.method, "lifecycle_readback");
    }

    #[test]
    fn lifecycle_empty_scope_is_unknown_not_green() {
        // The falsifier: a bootstrap over an empty scope injected nothing. It
        // did NOT fail, but it MUST NOT be laundered to a green Verified — an
        // inert lifecycle step is honestly Unknown.
        let v = classify_lifecycle(true, false, "");
        assert_eq!(v.status, VerdictStatus::Unknown);
        assert_eq!(v.status.as_ok(), None);
        assert_eq!(v.method, "lifecycle_no_effect");
    }

    #[test]
    fn lifecycle_failed_is_not_verified() {
        // A lifecycle step that errored out never produced its effect.
        let v = classify_lifecycle(false, false, "store unavailable");
        assert_eq!(v.status, VerdictStatus::NotVerified);
        assert_eq!(v.status.as_ok(), Some(false));
        assert_eq!(v.method, "lifecycle_failed");
    }

    // ---- SSB conformance gate (roadmap Gate E) ----

    fn event_for(
        source: &str,
        action: &str,
        object_type: &str,
        action_type: &str,
        risk: &str,
        gated: bool,
        verdict: VerdictStatus,
    ) -> SemanticEvent {
        SemanticEvent {
            ts: 1,
            actor: "mcp".to_string(),
            source: source.to_string(),
            action: action.to_string(),
            target: None,
            object: SemanticObject {
                object_type: object_type.to_string(),
                source_adapter: source.to_string(),
                label: None,
                object_id: None,
            },
            affordance: Affordance {
                action_type: action_type.to_string(),
                risk_level: risk.to_string(),
                requires_gate: gated,
                expected_effect: None,
            },
            verdict: Verdict {
                status: verdict,
                method: "m".to_string(),
                evidence: Value::Null,
            },
            facts: json!({}),
        }
    }

    #[test]
    fn all_three_adapter_shapes_conform_to_contract() {
        // The exact shapes the three live producers emit must all pass.
        let browser = event_for(
            "browser",
            "click",
            "dom_element",
            "click",
            "low",
            false,
            VerdictStatus::Verified,
        );
        let desktop = event_for(
            "desktop",
            "click",
            "desktop_input_surface",
            "click",
            "high",
            true,
            VerdictStatus::NotVerified,
        );
        let mobile = event_for(
            "mobile",
            "tap",
            "mobile_ui_node",
            "tap",
            "medium",
            false,
            VerdictStatus::Unknown,
        );
        for ev in [browser, desktop, mobile] {
            let rec = ev.to_record();
            assert!(
                contract_violations(&rec).is_empty(),
                "{}: {:?}",
                rec.source,
                contract_violations(&rec)
            );
        }
    }

    #[test]
    fn legacy_record_without_descriptor_is_flagged() {
        let rec = SemanticEventRecord {
            ts: 1,
            actor: "mcp".to_string(),
            source: "browser".to_string(),
            action: "click".to_string(),
            target: None,
            verdict_status: "verified".to_string(),
            verdict_method: "m".to_string(),
            evidence: None,
            facts: "{}".to_string(),
            descriptor: None,
        };
        let viol = contract_violations(&rec);
        assert!(viol.iter().any(|s| s.contains("descriptor missing")));
    }

    #[test]
    fn laundered_verdict_is_flagged() {
        // A status outside {verified,not_verified,unknown} (e.g. a faked "green")
        // must be caught — the gate refuses laundering.
        let mut rec = sample_event().to_record();
        rec.verdict_status = "green".to_string();
        assert!(contract_violations(&rec)
            .iter()
            .any(|s| s.contains("verdict_status not in")));
    }

    #[test]
    fn adapter_mismatch_is_flagged() {
        // descriptor.object.source_adapter must agree with the event source.
        // Build a conformant record (passes to_record's debug assert), then break
        // the source after the fact so the validator sees the mismatch.
        let mut rec = sample_event().to_record(); // browser / object.source_adapter=browser
        rec.source = "desktop".to_string();
        assert!(contract_violations(&rec)
            .iter()
            .any(|s| s.contains("!= descriptor.object.source_adapter")));
    }

    // ---- SSB "memory" arm: recurring inert-pattern distillation ----

    fn rec(
        source: &str,
        action: &str,
        status: &str,
        method: &str,
        target: Option<&str>,
        ts: i64,
    ) -> SemanticEventRecord {
        SemanticEventRecord {
            ts,
            actor: "mcp".to_string(),
            source: source.to_string(),
            action: action.to_string(),
            target: target.map(str::to_string),
            verdict_status: status.to_string(),
            verdict_method: method.to_string(),
            evidence: None,
            facts: "{}".to_string(),
            descriptor: None,
        }
    }

    #[test]
    fn cluster_groups_by_mode_and_applies_threshold() {
        // 3× the same failure MODE + 1 one-off. With min_count=3 only the
        // recurring mode survives — a single failure is not yet a "pattern".
        let evs = vec![
            rec(
                "browser",
                "click",
                "not_verified",
                "cdp_actionability_probe",
                Some("@e5"),
                300,
            ),
            rec(
                "browser",
                "click",
                "not_verified",
                "cdp_actionability_probe",
                Some("@e9"),
                200,
            ),
            rec(
                "browser",
                "click",
                "not_verified",
                "cdp_actionability_probe",
                Some("@e5"),
                100,
            ),
            rec(
                "mobile",
                "tap",
                "not_verified",
                "no_device",
                Some("@n1"),
                50,
            ),
        ];
        let pats = cluster_inert_patterns(&evs, 3);
        assert_eq!(pats.len(), 1, "only the ≥3 mode is a pattern: {pats:?}");
        let p = &pats[0];
        assert_eq!(
            (
                p.source.as_str(),
                p.action.as_str(),
                p.verdict_method.as_str()
            ),
            ("browser", "click", "cdp_actionability_probe")
        );
        assert_eq!(p.count, 3);
        assert_eq!(p.last_ts, 300, "last_ts is the newest occurrence");
        // Distinct example targets only (@e5 appeared twice → once).
        assert_eq!(p.examples, vec!["@e5".to_string(), "@e9".to_string()]);
    }

    #[test]
    fn cluster_ignores_verified_and_unknown_rows() {
        // The falsifier: only the verify-first NotVerified signal feeds the
        // memory arm — a green/unknown row must never become a "failure pattern".
        let evs = vec![
            rec("browser", "click", "verified", "ref_ok", Some("@e1"), 300),
            rec("browser", "click", "verified", "ref_ok", Some("@e2"), 200),
            rec("browser", "click", "verified", "ref_ok", Some("@e3"), 100),
            rec(
                "desktop",
                "action",
                "unknown",
                "isolated_injected_no_readback",
                None,
                90,
            ),
            rec(
                "desktop",
                "action",
                "unknown",
                "isolated_injected_no_readback",
                None,
                80,
            ),
            rec(
                "desktop",
                "action",
                "unknown",
                "isolated_injected_no_readback",
                None,
                70,
            ),
        ];
        assert!(
            cluster_inert_patterns(&evs, 3).is_empty(),
            "no NotVerified → no pattern"
        );
    }

    #[test]
    fn cluster_sorts_by_count_then_recency() {
        let mut evs = Vec::new();
        // mode A: 2 occurrences (older)
        evs.push(rec(
            "desktop",
            "action",
            "not_verified",
            "preflight_refusal",
            None,
            10,
        ));
        evs.push(rec(
            "desktop",
            "action",
            "not_verified",
            "preflight_refusal",
            None,
            20,
        ));
        // mode B: 4 occurrences (clearly more recurrent → must sort first)
        for ts in [100, 110, 120, 130] {
            evs.push(rec(
                "browser",
                "click",
                "not_verified",
                "css_selector_dispatch",
                Some("div.x"),
                ts,
            ));
        }
        let pats = cluster_inert_patterns(&evs, 2);
        assert_eq!(pats.len(), 2);
        assert_eq!(
            pats[0].verdict_method, "css_selector_dispatch",
            "higher count first"
        );
        assert_eq!(pats[0].count, 4);
        assert_eq!(pats[1].count, 2);
    }

    #[test]
    fn cluster_caps_examples_at_three_distinct() {
        let evs: Vec<_> = (0..6)
            .map(|i| {
                rec(
                    "browser",
                    "click",
                    "not_verified",
                    "cdp_actionability_probe",
                    Some(&format!("@e{i}")),
                    100 + i as i64,
                )
            })
            .collect();
        let pats = cluster_inert_patterns(&evs, 1);
        assert_eq!(pats[0].count, 6);
        assert_eq!(
            pats[0].examples.len(),
            3,
            "examples capped at 3: {:?}",
            pats[0].examples
        );
    }

    #[test]
    fn cluster_empty_and_min_count_floor() {
        assert!(cluster_inert_patterns(&[], 3).is_empty());
        // min_count is floored at 1, so a single failure with min_count=0 still
        // surfaces (caller never accidentally disables the threshold to nothing).
        let evs = vec![rec("mobile", "tap", "not_verified", "no_device", None, 5)];
        assert_eq!(cluster_inert_patterns(&evs, 0).len(), 1);
    }
}
