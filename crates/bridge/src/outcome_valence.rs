//! Shared outcome→valence derivation rule (`agent_bridge.outcome_valence_rule.v0`).
//!
//! Extracted from the `outcome_valence_shadow` MCP tool so every consumer of the
//! rule — the shadow diagnostic, the gated `outcome_valence_importance_apply`
//! writer, and the ingest path (`present_ingest::build_outcome_memory`) — derives
//! with the SAME reviewed table. Pure functions, no I/O, no store access. The
//! rule is the transparent deterministic map specified in
//! `docs/design/OUTCOMES_VALENCE_TRANSPORT_CONTRACT_DESIGN_2026_06_30.md` §2.4:
//! `(verify_status × decision) → base valence in [-1,1]`, scaled by a
//! method-confidence factor. No model, no learning, no randomness.
//!
//! Revision v0.1 (2026-07-02): `verified` joins `rendered_ok` in the ok-class
//! (session-manual outcome rows use the generic status), and `cargo_test` /
//! `live_mcp` / `golden_gate` get explicit method-confidence factors instead
//! of falling to the `unknown` 0.6. HONEST CHANGE LIST — this is a revision,
//! not a pure widening: inputs carrying those facets DID derive under v0 via
//! the fallback cells and now derive differently:
//!   - `verified+approved`: +0.3 (other class) → +1.0 (ok class)
//!   - `verified+rejected`: −0.5 (other class) → −0.4 (ok class)
//!   - `verified+none`:      non-derivable     → +0.6
//!   - rows with the three new methods: conf 0.6 → 1.0 / 0.9
//! Rows carrying none of those facets (`rendered_ok`/`failed`/`empty`
//! statuses, legacy methods) derive identically to v0 — locked by test.
//! Already-stamped rows whose derivation changed re-qualify automatically
//! (stamp mismatch) and are corrected by the audited apply pass.

/// The normalized outcome facets the rule reads — exactly the
/// `verify:`/`method:`/`decision:`/`embody:` tag prefixes that
/// `present_ingest::build_outcome_memory` writes. Never free-text content.
#[derive(Debug, Clone, Default)]
pub struct OutcomeFacets {
    pub verify_status: String,
    pub method: String,
    pub decision: Option<String>,
    pub embody: Option<String>,
}

/// Parse facets out of a memory record's tag list. Unknown tags are ignored;
/// later duplicates of a prefix win (same as the original inline parser).
pub fn facets_from_tags(tags: &[String]) -> OutcomeFacets {
    let mut f = OutcomeFacets::default();
    for t in tags {
        if let Some(v) = t.strip_prefix("verify:") {
            f.verify_status = v.to_string();
        } else if let Some(m) = t.strip_prefix("method:") {
            f.method = m.to_string();
        } else if let Some(d) = t.strip_prefix("decision:") {
            f.decision = Some(d.to_string());
        } else if let Some(e) = t.strip_prefix("embody:") {
            f.embody = Some(e.to_string());
        }
    }
    f
}

/// One derivation result. `valence == None` means the facets carry insufficient
/// signal (non-derivable); `rule_path` is always populated for auditability.
#[derive(Debug, Clone)]
pub struct ValenceDerivation {
    pub valence: Option<f64>,
    /// `"unknown"` when the method facet is empty — the label used in
    /// rule paths and facet tallies.
    pub method_label: String,
    pub rule_path: String,
}

/// Versioned id of the derivation rule table below, echoed by every consumer
/// (shadow envelope, apply envelope) so an auditor can tie a derivation to the
/// exact table revision that produced it.
pub const OUTCOME_VALENCE_RULE_SCHEMA: &str = "agent_bridge.outcome_valence_rule.v0_1";

/// Derive a candidate valence from outcome facets via the versioned rule
/// table ([`OUTCOME_VALENCE_RULE_SCHEMA`]). Deterministic; result is rounded
/// to 1e-6 like the shadow tool always did.
pub fn derive_valence(facets: &OutcomeFacets) -> ValenceDerivation {
    let method_label = if facets.method.is_empty() {
        "unknown".to_string()
    } else {
        facets.method.clone()
    };
    let dec_class = match facets.decision.as_deref() {
        Some("approved") => "approved",
        Some("rejected") => "rejected",
        _ => "none",
    };
    let vs_class = match facets.verify_status.as_str() {
        // `verified` = the generic honest status session-manual outcome rows
        // carry (tests + live verification) — same epistemic weight as a
        // programmatic render verification. v0.1 widening.
        "rendered_ok" | "verified" => "ok",
        "failed" | "error" => "failed",
        "" => "empty",
        _ => "other",
    };
    // Deterministic (verify_status × decision) → base valence. See §2.4 of the
    // design doc. `_` arms collapse unrecognized decisions into "none".
    let base: Option<f64> = match (vs_class, dec_class) {
        ("ok", "approved") => Some(1.0),
        ("ok", "rejected") => Some(-0.4),
        ("ok", _) => Some(0.6),
        ("failed", "approved") => Some(-0.2),
        ("failed", "rejected") => Some(-1.0),
        ("failed", _) => Some(-0.7),
        ("empty", "approved") => Some(0.3),
        ("empty", "rejected") => Some(-0.6),
        ("empty", _) => None,
        ("other", "approved") => Some(0.3),
        ("other", "rejected") => Some(-0.5),
        _ => None,
    };
    let conf = match method_label.as_str() {
        // live_mcp = end-to-end through the deployed daemon: the strongest
        // verification this system produces. v0.1 widening.
        "browser_eval" | "macos_ax_verify" | "live_mcp" => 1.0,
        // deterministic but indirect (verifies what the suite covers).
        "desktop_verify" | "cargo_test" | "golden_gate" => 0.9,
        "lite_probe" => 0.7,
        "self_report" => 0.5,
        _ => 0.6,
    };
    let vs_disp = if facets.verify_status.is_empty() {
        "<empty>"
    } else {
        facets.verify_status.as_str()
    };
    match base {
        Some(b) => {
            let v = (b * conf).clamp(-1.0, 1.0);
            let v = (v * 1_000_000.0).round() / 1_000_000.0;
            ValenceDerivation {
                valence: Some(v),
                method_label: method_label.clone(),
                rule_path: format!(
                    "verify={vs_disp}+decision={dec_class} -> base={b:+.1} * conf({method_label}={conf:.1}) = {v:+.3}"
                ),
            }
        }
        None => ValenceDerivation {
            valence: None,
            method_label,
            rule_path: format!(
                "verify={vs_disp}+decision={dec_class} -> insufficient signal (not derivable)"
            ),
        },
    }
}

/// Default clamp bounds for the valence→importance map. The floor matches the
/// `memory_decay_unused` floor (a valence-scored record never ranks below a
/// fully-decayed one); the ceiling stays below 1.0 so hand-pinned
/// `importance=1.0` records always outrank derived scores.
pub const IMPORTANCE_FLOOR_DEFAULT: f64 = 0.1;
pub const IMPORTANCE_CEILING_DEFAULT: f64 = 0.9;

/// Map a valence scalar in [-1,1] onto the importance scale [0,1] with an
/// affine transform, clamped to `[floor, ceiling]`:
/// `importance = clamp((valence + 1) / 2, floor, ceiling)`.
/// v=-1 → floor, v=0 → 0.5 (the current hardcoded default — a neutral outcome
/// keeps today's rank), v=+0.6 → 0.8, v=+1 → ceiling.
pub fn importance_from_valence(valence: f64, floor: f64, ceiling: f64) -> f64 {
    let raw = (valence.clamp(-1.0, 1.0) + 1.0) / 2.0;
    raw.clamp(floor, ceiling)
}

/// Env gate for the INGEST-side derivation: when truthy, new
/// `present_outcome` records get `importance = importance_from_valence(...)`
/// instead of the hardcoded 0.5. Default OFF — code behavior is unchanged
/// unless the operator opts in. The retro `outcome_valence_importance_apply`
/// tool is gated per-call (`confirm_apply`) instead.
pub const OUTCOME_VALENCE_IMPORTANCE_ENV: &str = "AB_OUTCOME_VALENCE_IMPORTANCE";

/// Canonical fixed-precision rendering of a valence scalar for tag values —
/// the SAME string everywhere (`+0.600`), so label and stamp comparisons are
/// exact string equality, never float comparison.
pub fn format_valence(valence: f64) -> String {
    format!("{valence:+.3}")
}

/// Tag prefix carrying the derived valence scalar as a DURABLE LABEL,
/// independent of the importance lifecycle. `importance` doubles as retrieval
/// rank and is owned by decay/reinforce/archival — a floor-negative row gets
/// archived ~3x sooner than baseline, silently skewing the valence corpus
/// positive (survivorship bias). The label tag survives archival, so the
/// corpus stays honest even for rows the lifecycle retires.
pub const VALENCE_TAG_PREFIX: &str = "valence:";
/// Tag prefix for the coarse class (`positive`/`neutral`/`negative`), the
/// cheap scan key for consumers that don't need the scalar.
pub const VALENCE_CLASS_TAG_PREFIX: &str = "valence_class:";
/// Tag prefix recording that importance WAS applied for a given derived
/// valence (`valence_applied:+0.600`). The stamp makes the retro apply pass
/// one-shot per row: a stamped row whose facets still derive the same valence
/// is skipped, so decay/reinforce own the trajectory after the initial
/// valence stamp (no undamped restoring force, no reinforcement claw-back).
/// A facet change (e.g. a decision landing later) derives a DIFFERENT
/// valence, the stamp no longer matches, and the row re-qualifies on its own.
pub const VALENCE_APPLIED_TAG_PREFIX: &str = "valence_applied:";

/// Coarse class label for a valence scalar — same thresholds as the shadow
/// tool's `valence_class` field.
pub fn valence_class(valence: f64) -> &'static str {
    if valence > 0.05 {
        "positive"
    } else if valence < -0.05 {
        "negative"
    } else {
        "neutral"
    }
}

/// The durable label tags for a derived valence: scalar + class.
pub fn valence_label_tags(valence: f64) -> Vec<String> {
    vec![
        format!("{VALENCE_TAG_PREFIX}{}", format_valence(valence)),
        format!("{VALENCE_CLASS_TAG_PREFIX}{}", valence_class(valence)),
    ]
}

/// The applied-stamp tag for a derived valence.
pub fn valence_applied_tag(valence: f64) -> String {
    format!("{VALENCE_APPLIED_TAG_PREFIX}{}", format_valence(valence))
}

/// Extract the applied-stamp value (the `+0.600` string) from a tag list, if
/// present. Later duplicates win, mirroring `facets_from_tags`.
pub fn applied_stamp(tags: &[String]) -> Option<String> {
    let mut out = None;
    for t in tags {
        if let Some(v) = t.strip_prefix(VALENCE_APPLIED_TAG_PREFIX) {
            out = Some(v.to_string());
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn facets(verify: &str, decision: Option<&str>, method: &str) -> OutcomeFacets {
        OutcomeFacets {
            verify_status: verify.to_string(),
            method: method.to_string(),
            decision: decision.map(str::to_string),
            embody: None,
        }
    }

    #[test]
    fn rule_table_spot_checks() {
        // verified + approved + full-confidence method → +1.0
        let d = derive_valence(&facets("rendered_ok", Some("approved"), "browser_eval"));
        assert_eq!(d.valence, Some(1.0));
        // failed + rejected → -1.0
        let d = derive_valence(&facets("failed", Some("rejected"), "browser_eval"));
        assert_eq!(d.valence, Some(-1.0));
        // verified, no decision → +0.6
        let d = derive_valence(&facets("rendered_ok", None, "browser_eval"));
        assert_eq!(d.valence, Some(0.6));
        assert!(d.rule_path.contains("base=+0.6"));
        // low-confidence method scales magnitude down
        let d = derive_valence(&facets("rendered_ok", None, "self_report"));
        assert_eq!(d.valence, Some(0.3));
        // no verify + no decision → non-derivable
        let d = derive_valence(&facets("", None, ""));
        assert_eq!(d.valence, None);
        assert_eq!(d.method_label, "unknown");
        assert!(d.rule_path.contains("not derivable"));
    }

    #[test]
    fn rule_v0_1_widening_verified_and_new_methods() {
        // `verified` joins the ok-class: derivable WITHOUT a decision…
        let d = derive_valence(&facets("verified", None, "live_mcp"));
        assert_eq!(d.valence, Some(0.6));
        // …and verified+approved reaches full strength at live_mcp conf 1.0.
        let d = derive_valence(&facets("verified", Some("approved"), "live_mcp"));
        assert_eq!(d.valence, Some(1.0));
        // verified+rejected = display/claim contradicted by the owner.
        let d = derive_valence(&facets("verified", Some("rejected"), "live_mcp"));
        assert_eq!(d.valence, Some(-0.4));
        // cargo_test / golden_gate: deterministic-but-indirect at 0.9.
        let d = derive_valence(&facets("verified", Some("approved"), "cargo_test"));
        assert_eq!(d.valence, Some(0.9));
        let d = derive_valence(&facets("failed", None, "golden_gate"));
        assert_eq!(d.valence, Some(-0.63));
        // Cells NOT carrying the widened facets derive identically to v0
        // (the honest invariance — verified/new-method cells DID change, see
        // the module-header change list).
        let d = derive_valence(&facets("rendered_ok", None, "browser_eval"));
        assert_eq!(d.valence, Some(0.6));
        let d = derive_valence(&facets("rendered_ok", None, "self_report"));
        assert_eq!(d.valence, Some(0.3));
    }

    #[test]
    fn facets_parse_from_tag_prefixes() {
        let tags = vec![
            "present_outcome".to_string(),
            "verify:rendered_ok".to_string(),
            "method:browser_eval".to_string(),
            "decision:approved".to_string(),
            "embody:embodied".to_string(),
        ];
        let f = facets_from_tags(&tags);
        assert_eq!(f.verify_status, "rendered_ok");
        assert_eq!(f.method, "browser_eval");
        assert_eq!(f.decision.as_deref(), Some("approved"));
        assert_eq!(f.embody.as_deref(), Some("embodied"));
    }

    #[test]
    fn label_and_stamp_tags_render_canonically() {
        assert_eq!(format_valence(0.6), "+0.600");
        assert_eq!(format_valence(-1.0), "-1.000");
        assert_eq!(
            valence_label_tags(0.6),
            vec![
                "valence:+0.600".to_string(),
                "valence_class:positive".to_string()
            ]
        );
        assert_eq!(valence_class(-0.4), "negative");
        assert_eq!(valence_class(0.0), "neutral");
        assert_eq!(valence_applied_tag(-1.0), "valence_applied:-1.000");

        let tags = vec![
            "verify:rendered_ok".to_string(),
            "valence_applied:+0.300".to_string(),
            "valence_applied:+0.600".to_string(),
        ];
        assert_eq!(applied_stamp(&tags).as_deref(), Some("+0.600"));
        assert_eq!(applied_stamp(&[]), None);
    }

    #[test]
    fn importance_map_is_affine_and_clamped() {
        let (f, c) = (IMPORTANCE_FLOOR_DEFAULT, IMPORTANCE_CEILING_DEFAULT);
        assert_eq!(importance_from_valence(0.0, f, c), 0.5); // neutral keeps today's default
        assert_eq!(importance_from_valence(0.6, f, c), 0.8);
        assert_eq!(importance_from_valence(1.0, f, c), c); // ceiling
        assert_eq!(importance_from_valence(-1.0, f, c), f); // floor
        assert_eq!(importance_from_valence(2.0, f, c), c); // out-of-range input clamped
    }
}
