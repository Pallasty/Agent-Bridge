// Shared reducer regressions for the installed-source fix and current source.
// These fixture anchors exercise projection only; they are not task evidence.
fn actionability_plan(steps: Value) -> PlanRecord {
    serde_json::from_value(json!({
        "plan_id": "actionability-regression",
        "title": "Choose only work that can start",
        "steps": steps,
        "created_at": 1,
        "updated_at": 2
    }))
    .unwrap()
}

#[test]
fn plan_actionability_respects_both_completion_modes() {
    for mode in ["agent_reported", "evidence_gated"] {
        let mut rec = actionability_plan(json!([
            {"id": "finished", "desc": "Reported only", "status": "done"},
            {"id": "waiting", "desc": "External input", "status": "waiting_real_player"},
            {"id": "ready", "desc": "Next work", "deps": ["finished"]}
        ]));
        rec.completion_mode = serde_json::from_value(json!(mode)).unwrap();
        let payload = enrich_plan_json(&rec);
        assert_eq!(payload["verified_done_count"], 0);
        assert_eq!(payload["steps"][1]["status"], "waiting_real_player");
        if mode == "agent_reported" {
            assert_eq!(payload["next_step_id"], "ready");
            assert_eq!(payload["done_count"], 1);
        } else {
            assert_eq!(payload["next_step_id"], "finished");
            assert_eq!(payload["done_count"], 0);
        }
    }
}

#[test]
fn plan_actionability_preserves_waiting_and_unknown_states_without_suggesting_them() {
    for status in [
        "blocked",
        "waiting_real_player",
        "waiting_real_viewer",
        "waiting",
        "ready_on_natural_task",
        "existing_workflow_reused_no_new_extraction",
        "cancelled",
        "canceled",
        "obsolete",
        "completed",
        "",
        "PENDING",
    ] {
        let rec = actionability_plan(json!([
            {"id": "wait", "desc": "Needs external input", "status": status},
            {"id": "dependent", "desc": "Fix observed issue", "deps": ["wait"]}
        ]));
        let payload = enrich_plan_json(&rec);
        assert!(payload["next_step_id"].is_null(), "status: {status}");
        assert_eq!(payload["steps"][0]["status"], status);
        assert_eq!(payload["done_count"], 0);
    }
}

#[test]
fn plan_actionability_selects_independent_work_after_unready_dependencies() {
    let rec = actionability_plan(json!([
        {"id": "wait", "desc": "Real viewer", "status": "waiting_real_viewer"},
        {"id": "edit", "desc": "Needs viewer result", "deps": ["wait"]},
        {"id": "missing", "desc": "Unknown dependency", "deps": ["absent"]},
        {"id": "active", "desc": "Real independent fix", "status": "in_progress"},
        {"id": "later", "desc": "Preserve listed order", "status": "pending"}
    ]));
    assert_eq!(enrich_plan_json(&rec)["next_step_id"], "active");
}

#[test]
fn plan_actionability_requires_every_dependency_and_keeps_completion_counts() {
    let rec = actionability_plan(json!([
        {"id": "complete", "desc": "Fixture completion", "status": "done",
         "completion_anchor": true,
         "completion_evidence": {"outcome_id": "fixture-only", "record_sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}},
        {"id": "mixed", "desc": "One dependency still missing", "deps": ["complete", "absent"]},
        {"id": "ready", "desc": "Completed dependency", "deps": ["complete"]}
    ]));
    let payload = enrich_plan_json(&rec);
    assert_eq!(payload["next_step_id"], "ready");
    assert_eq!(payload["done_count"], 1);
    assert_eq!(payload["total_steps"], 3);
}

#[test]
fn plan_actionability_does_not_start_cycles_or_self_dependencies() {
    let rec = actionability_plan(json!([
        {"id": "a", "desc": "Cycle a", "deps": ["b"]},
        {"id": "b", "desc": "Cycle b", "deps": ["a"]},
        {"id": "self", "desc": "Self dependency", "deps": ["self"]}
    ]));
    assert!(enrich_plan_json(&rec)["next_step_id"].is_null());
}

#[test]
fn plan_actionability_keeps_empty_plans_without_a_next_step() {
    let payload = enrich_plan_json(&actionability_plan(json!([])));
    assert!(payload["next_step_id"].is_null());
    assert_eq!(payload["done_count"], 0);
    assert_eq!(payload["total_steps"], 0);
}
