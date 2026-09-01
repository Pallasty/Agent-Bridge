use ab_store::{
    plan_step_contract_id, AgentTaskOutcomeRecord, AgentTaskOutcomeWriteStatus,
    PlanMutationRejectionCode, PlanSaveOutcome, PlanStep, PlanStepCompletionEvidenceRef,
    PlanUpdateOutcome, SqliteStore, StateStore, PLAN_STEP_COMPLETION_CONTRACT_REVISION,
};
use sha2::{Digest, Sha256};

fn bind_record_digest(record: &mut AgentTaskOutcomeRecord) {
    let mut value = serde_json::json!({
        "schema_version": record.schema_version,
        "outcome_id": record.outcome_id,
        "contract_id": record.contract_id,
        "revision": record.contract_revision,
        "status": record.status,
        "verification": record.verification_status,
        "verification_method": record.verification_method,
        "user_acceptance": record.user_acceptance,
        "acceptance_provenance": record.acceptance_provenance,
        "rollback_status": record.rollback_status,
        "provenance": record.provenance,
        "evidence_sha256": record.evidence_sha256,
        "counts": {},
    });
    for (field, identifier) in [
        ("agent_id", record.agent_id.as_ref()),
        ("body_id", record.body_id.as_ref()),
        ("environment_id", record.environment_id.as_ref()),
    ] {
        if let Some(identifier) = identifier {
            value[field] = serde_json::json!(identifier);
        }
    }
    for (field, count) in [
        ("manual_interventions", record.manual_interventions),
        ("owner_restatements", record.owner_restatements),
        (
            "repeated_authorization_prompts",
            record.repeated_authorization_prompts,
        ),
    ] {
        if let Some(count) = count {
            value["counts"][field] = serde_json::json!(count);
        }
    }
    let canonical = serde_json_canonicalizer::to_vec(&value).expect("canonical outcome fixture");
    record.record_sha256 = format!("sha256:{:x}", Sha256::digest(canonical));
}

fn completion_outcome(
    outcome_id: &str,
    contract_id: String,
    provenance: &str,
) -> AgentTaskOutcomeRecord {
    let mut record = AgentTaskOutcomeRecord {
        schema_version: "agent_bridge.agent_task_outcome.v1".to_string(),
        outcome_id: outcome_id.to_string(),
        recorded_at: ab_store::now_secs(),
        contract_id,
        contract_revision: PLAN_STEP_COMPLETION_CONTRACT_REVISION,
        status: "achieved".to_string(),
        verification_status: "verified".to_string(),
        verification_method: "tests".to_string(),
        evidence_sha256: vec![format!("sha256:{}", "a".repeat(64))],
        user_acceptance: "accepted".to_string(),
        acceptance_provenance: "owner_explicit".to_string(),
        manual_interventions: None,
        owner_restatements: None,
        repeated_authorization_prompts: None,
        rollback_status: "not_needed".to_string(),
        provenance: provenance.to_string(),
        agent_id: Some("agent-plan-test".to_string()),
        body_id: Some("body-plan-test".to_string()),
        environment_id: Some("environment-plan-test".to_string()),
        record_sha256: String::new(),
    };
    bind_record_digest(&mut record);
    record
}

async fn seed_outcome(store: &SqliteStore, record: AgentTaskOutcomeRecord) {
    assert_eq!(
        store
            .record_agent_task_outcome(record)
            .await
            .expect("record task outcome"),
        AgentTaskOutcomeWriteStatus::Inserted
    );
}

fn step(id: &str, desc: &str, deps: &[&str]) -> PlanStep {
    PlanStep {
        id: id.to_string(),
        desc: desc.to_string(),
        status: "pending".to_string(),
        deps: deps
            .iter()
            .map(|dependency| (*dependency).to_string())
            .collect(),
        completion_anchor: false,
        completion_contract: None,
        completion_evidence: None,
    }
}

fn assert_save_rejected(outcome: PlanSaveOutcome, code: PlanMutationRejectionCode) {
    assert!(matches!(
        outcome,
        PlanSaveOutcome::Rejected { reason } if reason.code == code
    ));
}

fn assert_update_rejected(outcome: PlanUpdateOutcome, code: PlanMutationRejectionCode) {
    assert!(matches!(
        outcome,
        PlanUpdateOutcome::Rejected { reason } if reason.code == code
    ));
}

async fn overwrite_plan_steps(
    connection: &tokio_rusqlite::Connection,
    plan_id: &str,
    steps: &[PlanStep],
) {
    let plan_id = plan_id.to_string();
    let steps_json = serde_json::to_string(steps).expect("serialize raw plan steps");
    connection
        .call(
            move |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "UPDATE plans SET steps_json=?2 WHERE plan_id=?1",
                    tokio_rusqlite::rusqlite::params![plan_id, steps_json],
                )?;
                Ok(())
            },
        )
        .await
        .expect("overwrite raw plan steps");
}

async fn load_raw_plan_steps(
    connection: &tokio_rusqlite::Connection,
    plan_id: &str,
) -> Vec<PlanStep> {
    let plan_id = plan_id.to_string();
    let steps_json = connection
        .call(
            move |connection| -> Result<String, tokio_rusqlite::rusqlite::Error> {
                connection.query_row(
                    "SELECT steps_json FROM plans WHERE plan_id=?1",
                    tokio_rusqlite::rusqlite::params![plan_id],
                    |row| row.get(0),
                )
            },
        )
        .await
        .expect("load raw plan steps JSON");
    serde_json::from_str(&steps_json).expect("deserialize raw plan steps")
}

#[tokio::test]
async fn save_cannot_bypass_structure_or_completion_evidence_validation() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let store = SqliteStore::open(&fixture.path().join("state.db"))
        .await
        .expect("open store");

    assert_save_rejected(
        store
            .plan_save("empty", "empty", &[])
            .await
            .expect("empty plan rejection"),
        PlanMutationRejectionCode::EmptySteps,
    );
    let duplicate = vec![step("same", "first", &[]), step("same", "second", &[])];
    assert_save_rejected(
        store
            .plan_save("duplicate", "duplicate", &duplicate)
            .await
            .expect("duplicate rejection"),
        PlanMutationRejectionCode::DuplicateStepId,
    );
    let cycle = vec![step("a", "a", &["b"]), step("b", "b", &["a"])];
    assert_save_rejected(
        store
            .plan_save("cycle", "cycle", &cycle)
            .await
            .expect("cycle rejection"),
        PlanMutationRejectionCode::DependencyCycle,
    );

    let mut done_without_evidence = step("one", "one", &[]);
    done_without_evidence.status = "DONE".to_string();
    done_without_evidence.completion_anchor = true;
    assert_save_rejected(
        store
            .plan_save("done-bypass", "done bypass", &[done_without_evidence])
            .await
            .expect("DONE without evidence rejection"),
        PlanMutationRejectionCode::CompletionEvidenceRequired,
    );
    let mut pending_with_evidence = step("one", "one", &[]);
    pending_with_evidence.completion_evidence = Some(PlanStepCompletionEvidenceRef {
        outcome_id: "forged".to_string(),
        record_sha256: String::new(),
    });
    assert_save_rejected(
        store
            .plan_save(
                "evidence-bypass",
                "evidence bypass",
                &[pending_with_evidence],
            )
            .await
            .expect("non-DONE evidence rejection"),
        PlanMutationRejectionCode::CompletionEvidenceForbidden,
    );

    let mut caller_anchored_pending = step("one", "one", &[]);
    caller_anchored_pending.completion_anchor = true;
    let caller_anchor_save = store
        .plan_save("caller-anchor", "caller anchor", &[caller_anchored_pending])
        .await
        .expect("save caller-supplied marker");
    let caller_anchor_plan = match caller_anchor_save {
        PlanSaveOutcome::Saved { plan } => plan,
        PlanSaveOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert!(!caller_anchor_plan.steps[0].completion_anchor);

    let saved = store
        .plan_save("editable", "editable", &[step("one", "before", &[])])
        .await
        .expect("save editable plan");
    let mut roundtrip = match saved {
        PlanSaveOutcome::Saved { plan } => plan.steps,
        PlanSaveOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    let old_contract = roundtrip[0]
        .completion_contract
        .as_ref()
        .expect("saved completion contract")
        .contract_id
        .clone();
    roundtrip[0].desc = "after".to_string();
    let edited = store
        .plan_save("editable", "editable", &roundtrip)
        .await
        .expect("save edited non-DONE plan");
    let new_contract = match edited {
        PlanSaveOutcome::Saved { plan } => plan.steps[0]
            .completion_contract
            .as_ref()
            .expect("rebound completion contract")
            .contract_id
            .clone(),
        PlanSaveOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert_ne!(old_contract, new_contract);

    let canonicalized = store
        .plan_save(
            "trim-roundtrip",
            "trim roundtrip",
            &[
                step(" s1 ", "first trimmed step", &[]),
                step(" s2 ", "second trimmed step", &[" s1 "]),
            ],
        )
        .await
        .expect("save whitespace-padded step ids");
    let canonicalized = match canonicalized {
        PlanSaveOutcome::Saved { plan } => plan,
        PlanSaveOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert_eq!(canonicalized.steps[0].id, "s1");
    assert_eq!(canonicalized.steps[1].id, "s2");
    assert_eq!(canonicalized.steps[1].deps, vec!["s1"]);
    assert_eq!(
        canonicalized.steps[1]
            .completion_contract
            .as_ref()
            .expect("canonical completion contract")
            .contract_id,
        plan_step_contract_id(
            "trim-roundtrip",
            "s2",
            "second trimmed step",
            &["s1".to_string()],
        )
    );
    assert!(matches!(
        store
            .plan_update_step("trim-roundtrip", " s1 ", "IN_PROGRESS", None)
            .await
            .expect("update with whitespace-padded step id"),
        PlanUpdateOutcome::Updated { .. }
    ));

    assert_update_rejected(
        store
            .plan_update_step("trim-roundtrip", "   ", "pending", None)
            .await
            .expect("empty normalized step id rejection"),
        PlanMutationRejectionCode::EmptyStepId,
    );

    let completed_plan_id = "save-completed";
    let mut completed_first = step("first", "saved first", &[]);
    completed_first.status = "DONE".to_string();
    completed_first.completion_evidence = Some(PlanStepCompletionEvidenceRef {
        outcome_id: "saved-first".to_string(),
        record_sha256: String::new(),
    });
    let mut completed_second = step("second", "saved second", &["first"]);
    completed_second.status = "DONE".to_string();
    completed_second.completion_evidence = Some(PlanStepCompletionEvidenceRef {
        outcome_id: "saved-second".to_string(),
        record_sha256: String::new(),
    });
    seed_outcome(
        &store,
        completion_outcome(
            "saved-first",
            plan_step_contract_id(completed_plan_id, "first", "saved first", &[]),
            "harness_verified",
        ),
    )
    .await;
    seed_outcome(
        &store,
        completion_outcome(
            "saved-second",
            plan_step_contract_id(
                completed_plan_id,
                "second",
                "saved second",
                &["first".to_string()],
            ),
            "harness_verified",
        ),
    )
    .await;
    let completed_save = store
        .plan_save(
            completed_plan_id,
            "completed save",
            &[completed_first, completed_second],
        )
        .await
        .expect("save fully evidenced completed plan");
    let completed_plan = match completed_save {
        PlanSaveOutcome::Saved { plan } => plan,
        PlanSaveOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert!(completed_plan.steps.iter().all(|step| {
        step.status == "done"
            && step.completion_anchor
            && step
                .completion_evidence
                .as_ref()
                .is_some_and(|evidence| !evidence.record_sha256.is_empty())
    }));
}

#[tokio::test]
async fn done_requires_exact_trusted_harness_outcome_and_is_atomic_on_rejection() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let plan_id = "trust-gate";
    let task = step("task", "verify task", &[]);
    assert!(matches!(
        store
            .plan_save(plan_id, "trust gate", &[task.clone()])
            .await
            .expect("save plan"),
        PlanSaveOutcome::Saved { .. }
    ));

    assert_update_rejected(
        store
            .plan_update_step(plan_id, "task", "DONE", None)
            .await
            .expect("missing evidence rejection"),
        PlanMutationRejectionCode::CompletionEvidenceRequired,
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "task", "DONE", Some("bad outcome id"))
            .await
            .expect("malformed outcome id rejection"),
        PlanMutationRejectionCode::CompletionOutcomeIdInvalid,
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "task", "DONE", Some("missing-outcome"))
            .await
            .expect("missing outcome rejection"),
        PlanMutationRejectionCode::CompletionOutcomeNotFound,
    );

    seed_outcome(
        &store,
        completion_outcome(
            "wrong-contract",
            "plan-step:wrong".to_string(),
            "harness_verified",
        ),
    )
    .await;
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "task", "DONE", Some("wrong-contract"))
            .await
            .expect("wrong contract rejection"),
        PlanMutationRejectionCode::CompletionOutcomeContractMismatch,
    );

    let contract_id = plan_step_contract_id(plan_id, "task", "verify task", &[]);
    for (outcome_id, provenance) in [
        ("agent-reported", "agent_reported"),
        ("owner-attested", "owner_attested"),
    ] {
        seed_outcome(
            &store,
            completion_outcome(outcome_id, contract_id.clone(), provenance),
        )
        .await;
        assert_update_rejected(
            store
                .plan_update_step(plan_id, "task", "DONE", Some(outcome_id))
                .await
                .expect("untrusted outcome rejection"),
            PlanMutationRejectionCode::CompletionOutcomeUntrusted,
        );
    }

    let corrupt = completion_outcome("corrupt-outcome", contract_id.clone(), "harness_verified");
    seed_outcome(&store, corrupt).await;
    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open corruption fixture connection");
    direct
        .call(
            |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "UPDATE agent_task_outcomes
                    SET record_sha256=?1
                  WHERE outcome_id='corrupt-outcome'",
                    tokio_rusqlite::rusqlite::params![format!("sha256:{}", "f".repeat(64))],
                )?;
                Ok(())
            },
        )
        .await
        .expect("corrupt canonical record digest");
    assert!(store
        .load_agent_task_outcome("corrupt-outcome")
        .await
        .is_err());
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "task", "DONE", Some("corrupt-outcome"))
            .await
            .expect("corrupt outcome rejection"),
        PlanMutationRejectionCode::CompletionOutcomeInvalid,
    );

    let loaded = store
        .plan_load(plan_id)
        .await
        .expect("load after rejections")
        .expect("plan exists");
    assert_eq!(loaded.steps[0].status, "pending");
    assert!(!loaded.steps[0].completion_anchor);
    assert!(loaded.steps[0].completion_evidence.is_none());
}

#[tokio::test]
async fn dependencies_success_durability_irreversibility_and_anchor_rules_are_enforced() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let plan_id = "dependency-gate";
    let first = step("first", "first task", &[]);
    let second = step("second", "second task", &["first"]);
    assert!(matches!(
        store
            .plan_save(plan_id, "dependency gate", &[first.clone(), second.clone()])
            .await
            .expect("save plan"),
        PlanSaveOutcome::Saved { .. }
    ));

    let first_contract = plan_step_contract_id(plan_id, "first", "first task", &[]);
    let second_contract =
        plan_step_contract_id(plan_id, "second", "second task", &["first".to_string()]);
    seed_outcome(
        &store,
        completion_outcome("first-ok", first_contract.clone(), "harness_verified"),
    )
    .await;
    seed_outcome(
        &store,
        completion_outcome("second-ok", second_contract, "harness_verified"),
    )
    .await;
    seed_outcome(
        &store,
        completion_outcome("first-other", first_contract, "harness_verified"),
    )
    .await;

    assert_update_rejected(
        store
            .plan_update_step(plan_id, "second", "DONE", Some("second-ok"))
            .await
            .expect("dependency rejection"),
        PlanMutationRejectionCode::DependencyNotCompleted,
    );
    let first_done = store
        .plan_update_step(plan_id, "first", "DONE", Some("first-ok"))
        .await
        .expect("complete first");
    assert!(matches!(
        first_done,
        PlanUpdateOutcome::Updated { ref plan } if plan.steps[0].completion_anchor
    ));
    let first_done_retry = store
        .plan_update_step(plan_id, "first", "done", Some("first-ok"))
        .await
        .expect("idempotent completion retry");
    assert!(matches!(
        first_done_retry,
        PlanUpdateOutcome::Updated { .. }
    ));
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "first", "done", Some("first-other"))
            .await
            .expect("completion anchor conflict"),
        PlanMutationRejectionCode::CompletionOutcomeConflict,
    );
    assert!(matches!(
        store
            .plan_update_step(plan_id, "second", "DONE", Some("second-ok"))
            .await
            .expect("complete second"),
        PlanUpdateOutcome::Updated { .. }
    ));

    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open completion corruption fixture connection");
    direct
        .call(
            |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "UPDATE agent_task_outcomes
                        SET record_sha256=?1
                      WHERE outcome_id='first-ok'",
                    tokio_rusqlite::rusqlite::params![format!("sha256:{}", "e".repeat(64))],
                )?;
                Ok(())
            },
        )
        .await
        .expect("corrupt completed outcome after anchor persistence");
    let corrupted_projection = store
        .plan_load(plan_id)
        .await
        .expect("load post-completion corruption projection")
        .expect("corrupted completed plan exists");
    assert!(corrupted_projection.steps[0].completion_evidence.is_none());
    assert!(corrupted_projection.steps[0].completion_anchor);
    assert_eq!(
        corrupted_projection.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionOutcomeInvalid
    );
    assert_eq!(
        corrupted_projection.completion_diagnostics[0]
            .step_id
            .as_deref(),
        Some("first")
    );

    assert_update_rejected(
        store
            .plan_update_step(plan_id, "first", "IN_PROGRESS", None)
            .await
            .expect("irreversible completion rejection"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "first", "done", Some("first-other"))
            .await
            .expect("old outcome replay rejection"),
        PlanMutationRejectionCode::CompletionOutcomeConflict,
    );

    drop(store);
    let reopened = SqliteStore::open(&db_path).await.expect("reopen store");
    let durable = reopened
        .plan_load(plan_id)
        .await
        .expect("load durable plan")
        .expect("durable plan exists");
    assert!(durable.steps.iter().all(|step| step.status == "done"));
    assert!(durable.steps.iter().all(|step| step.completion_anchor));
    assert!(durable.steps[0].completion_evidence.is_none());
    assert!(durable.steps[1].completion_evidence.is_some());
    assert_eq!(
        durable.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionOutcomeInvalid
    );

    assert_update_rejected(
        reopened
            .plan_update_step(plan_id, "second", "OBSOLETE", None)
            .await
            .expect("irreversible dependent completion rejection"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_update_rejected(
        reopened
            .plan_update_step(plan_id, "first", "NOT_YET", None)
            .await
            .expect("irreversible dependency completion rejection"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );

    assert_save_rejected(
        reopened
            .plan_save(
                plan_id,
                "attempt delete verified done",
                &[durable.steps[0].clone()],
            )
            .await
            .expect("reject deleting verified DONE step through plan_save"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    let mut reopen_by_save = durable.steps.clone();
    reopen_by_save[1].status = "obsolete".to_string();
    reopen_by_save[1].completion_evidence = None;
    assert_save_rejected(
        reopened
            .plan_save(plan_id, "attempt reopen by save", &reopen_by_save)
            .await
            .expect("reject reopening verified DONE step through plan_save"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );

    let still_closed = reopened
        .plan_load(plan_id)
        .await
        .expect("load immutable completed plan")
        .expect("immutable completed plan exists");
    assert_eq!(still_closed.title, durable.title);
    assert_eq!(still_closed.updated_at, durable.updated_at);
    assert!(still_closed.steps.iter().all(|step| step.status == "done"));
    assert!(still_closed.steps[0].completion_evidence.is_none());
    assert!(still_closed.steps[1].completion_evidence.is_some());
    assert_eq!(
        still_closed.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionOutcomeInvalid
    );
}

#[tokio::test]
async fn update_cannot_wash_a_tampered_same_id_completion_digest() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let plan_id = "update-anchor-digest";
    assert!(matches!(
        store
            .plan_save(plan_id, "update digest", &[step("closed", "task", &[])])
            .await
            .expect("save plan"),
        PlanSaveOutcome::Saved { .. }
    ));
    let contract = plan_step_contract_id(plan_id, "closed", "task", &[]);
    seed_outcome(
        &store,
        completion_outcome("update-anchor-a", contract.clone(), "harness_verified"),
    )
    .await;
    seed_outcome(
        &store,
        completion_outcome("update-anchor-b", contract, "harness_verified"),
    )
    .await;
    let completed = store
        .plan_update_step(plan_id, "closed", "DONE", Some("update-anchor-a"))
        .await
        .expect("complete with outcome A");
    let completed = match completed {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };

    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open direct fixture connection");
    let mut tampered = completed.steps;
    tampered[0]
        .completion_evidence
        .as_mut()
        .expect("completion evidence")
        .outcome_id = "update-anchor-b".to_string();
    overwrite_plan_steps(&direct, plan_id, &tampered).await;
    let raw_before = load_raw_plan_steps(&direct, plan_id).await;
    let projected_before = store
        .plan_load(plan_id)
        .await
        .expect("load tampered plan")
        .expect("tampered plan exists");
    assert_eq!(
        projected_before.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionEvidenceDigestMismatch
    );

    assert_update_rejected(
        store
            .plan_update_step(plan_id, "closed", "DONE", Some("update-anchor-b"))
            .await
            .expect("reject same-id digest wash"),
        PlanMutationRejectionCode::CompletionEvidenceDigestMismatch,
    );
    assert_eq!(load_raw_plan_steps(&direct, plan_id).await, raw_before);
    assert_eq!(
        store
            .plan_load(plan_id)
            .await
            .expect("load after rejected update")
            .expect("plan remains"),
        projected_before
    );
}

#[tokio::test]
async fn save_cannot_wash_a_tampered_same_id_completion_digest() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let plan_id = "save-anchor-digest";
    assert!(matches!(
        store
            .plan_save(plan_id, "save digest", &[step("closed", "task", &[])])
            .await
            .expect("save plan"),
        PlanSaveOutcome::Saved { .. }
    ));
    let contract = plan_step_contract_id(plan_id, "closed", "task", &[]);
    seed_outcome(
        &store,
        completion_outcome("save-anchor-a", contract.clone(), "harness_verified"),
    )
    .await;
    let outcome_b = completion_outcome("save-anchor-b", contract, "harness_verified");
    let outcome_b_digest = outcome_b.record_sha256.clone();
    seed_outcome(&store, outcome_b).await;
    let completed = store
        .plan_update_step(plan_id, "closed", "DONE", Some("save-anchor-a"))
        .await
        .expect("complete with outcome A");
    let completed = match completed {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };

    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open direct fixture connection");
    let mut tampered = completed.steps.clone();
    tampered[0]
        .completion_evidence
        .as_mut()
        .expect("completion evidence")
        .outcome_id = "save-anchor-b".to_string();
    overwrite_plan_steps(&direct, plan_id, &tampered).await;
    let raw_before = load_raw_plan_steps(&direct, plan_id).await;
    let projected_before = store
        .plan_load(plan_id)
        .await
        .expect("load tampered plan")
        .expect("tampered plan exists");

    let mut submitted = completed.steps;
    submitted[0].completion_evidence = Some(PlanStepCompletionEvidenceRef {
        outcome_id: "save-anchor-b".to_string(),
        record_sha256: outcome_b_digest,
    });
    assert_save_rejected(
        store
            .plan_save(plan_id, "attempt digest wash", &submitted)
            .await
            .expect("reject full-save digest wash"),
        PlanMutationRejectionCode::CompletionEvidenceDigestMismatch,
    );
    assert_eq!(load_raw_plan_steps(&direct, plan_id).await, raw_before);
    assert_eq!(
        store
            .plan_load(plan_id)
            .await
            .expect("load after rejected save")
            .expect("plan remains"),
        projected_before
    );
}

#[tokio::test]
async fn completion_marker_survives_legacy_ref_and_integrity_corruption() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let plan_id = "anchor-integrity";
    assert!(matches!(
        store
            .plan_save(
                plan_id,
                "anchor integrity",
                &[
                    step("closed", "closed task", &[]),
                    step("probe", "probe task", &[]),
                ],
            )
            .await
            .expect("save anchor fixture"),
        PlanSaveOutcome::Saved { .. }
    ));
    seed_outcome(
        &store,
        completion_outcome(
            "closed-outcome",
            plan_step_contract_id(plan_id, "closed", "closed task", &[]),
            "harness_verified",
        ),
    )
    .await;
    let completed = store
        .plan_update_step(plan_id, "closed", "DONE", Some("closed-outcome"))
        .await
        .expect("complete anchored step");
    let completed = match completed {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert!(completed.steps[0].completion_anchor);
    let trusted_evidence = completed.steps[0]
        .completion_evidence
        .clone()
        .expect("trusted completion evidence");

    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open anchor corruption fixture connection");

    // Pre-marker evidence rows remain compatible: reads project the marker,
    // and the next successful update persists the additive marker.
    let mut pre_marker = completed.steps.clone();
    pre_marker[0].completion_anchor = false;
    overwrite_plan_steps(&direct, plan_id, &pre_marker).await;
    let projected_old_ref = store
        .plan_load(plan_id)
        .await
        .expect("load pre-marker completion")
        .expect("pre-marker plan exists");
    assert!(projected_old_ref.steps[0].completion_anchor);
    assert!(projected_old_ref.steps[0].completion_evidence.is_some());
    assert!(projected_old_ref.completion_diagnostics.is_empty());
    assert!(matches!(
        store
            .plan_update_step(plan_id, "probe", "IN_PROGRESS", None)
            .await
            .expect("backfill old completion marker"),
        PlanUpdateOutcome::Updated { .. }
    ));
    let raw_backfilled = load_raw_plan_steps(&direct, plan_id).await;
    assert!(raw_backfilled[0].completion_anchor);

    // A corrupted status cannot erase the irreversible marker. Projection
    // fails closed, while the same outcome may repair the status atomically.
    let mut status_corrupted = raw_backfilled;
    status_corrupted[0].status = "blocked".to_string();
    overwrite_plan_steps(&direct, plan_id, &status_corrupted).await;
    let status_projection = store
        .plan_load(plan_id)
        .await
        .expect("load status-corrupted anchor")
        .expect("status-corrupted plan exists");
    assert!(status_projection.steps[0].completion_anchor);
    assert!(status_projection.steps[0].completion_evidence.is_none());
    assert_eq!(
        status_projection.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionAnchorInvalid
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "closed", "BLOCKED", None)
            .await
            .expect("reject corrupted anchored non-DONE update"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "closed", "BLOCKED", Some("closed-outcome"))
            .await
            .expect("anchored non-DONE always rejects as reopen"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_save_rejected(
        store
            .plan_save(
                plan_id,
                "reject anchored removal",
                &[status_projection.steps[1].clone()],
            )
            .await
            .expect("reject status-corrupted anchor removal"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    let repaired = store
        .plan_update_step(plan_id, "closed", "DONE", Some("closed-outcome"))
        .await
        .expect("repair status with identical outcome");
    let repaired = match repaired {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert!(repaired.steps[0].completion_anchor);
    assert!(repaired.steps[0].completion_evidence.is_some());

    // If the evidence ref itself is lost, the marker still prevents reopen,
    // removal, or rebinding through either update or full-save surfaces.
    let mut reference_corrupted = repaired.steps.clone();
    reference_corrupted[0].completion_evidence = None;
    overwrite_plan_steps(&direct, plan_id, &reference_corrupted).await;
    let reference_projection = store
        .plan_load(plan_id)
        .await
        .expect("load reference-corrupted anchor")
        .expect("reference-corrupted plan exists");
    assert!(reference_projection.steps[0].completion_anchor);
    assert!(reference_projection.steps[0].completion_evidence.is_none());
    assert_eq!(
        reference_projection.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionAnchorInvalid
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "closed", "DONE", Some("closed-outcome"))
            .await
            .expect("reject missing-anchor-reference rebind"),
        PlanMutationRejectionCode::CompletionAnchorInvalid,
    );
    assert_update_rejected(
        store
            .plan_update_step(plan_id, "closed", "pending", None)
            .await
            .expect("reject missing-reference reopen"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_save_rejected(
        store
            .plan_save(
                plan_id,
                "reject missing-reference removal",
                &[reference_projection.steps[1].clone()],
            )
            .await
            .expect("reject missing-reference anchor removal"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    let mut replay = reference_projection.steps.clone();
    replay[0].completion_evidence = Some(trusted_evidence);
    assert_save_rejected(
        store
            .plan_save(plan_id, "reject missing-reference replay", &replay)
            .await
            .expect("reject replay against marker-only anchor"),
        PlanMutationRejectionCode::CompletionAnchorInvalid,
    );
}

#[tokio::test]
async fn legacy_done_is_not_evidence_and_can_be_backfilled_without_silent_upgrade() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let store = SqliteStore::open(&db_path).await.expect("open store");
    let now = ab_store::now_secs();
    let legacy_json = serde_json::json!([
        {
            "id": "legacy",
            "desc": "legacy task",
            "status": "done",
            "deps": []
        },
        {
            "id": "repair-probe",
            "desc": "repair projection probe",
            "status": "pending",
            "deps": []
        }
    ])
    .to_string();
    let direct = tokio_rusqlite::Connection::open(&db_path)
        .await
        .expect("open direct fixture connection");
    direct
        .call(
            move |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "INSERT INTO plans (plan_id, title, steps_json, created_at, updated_at)
                 VALUES ('legacy-plan', 'legacy', ?1, ?2, ?2)",
                    tokio_rusqlite::rusqlite::params![legacy_json, now],
                )?;
                Ok(())
            },
        )
        .await
        .expect("insert legacy plan");

    let legacy = store
        .plan_load("legacy-plan")
        .await
        .expect("load legacy plan")
        .expect("legacy plan exists");
    assert_eq!(legacy.steps[0].status, "done");
    assert!(!legacy.steps[0].completion_anchor);
    assert!(legacy.steps[0].completion_contract.is_some());
    assert!(legacy.steps[0].completion_evidence.is_none());

    let legacy_downgrade = store
        .plan_update_step("legacy-plan", "legacy", "BLOCKED", None)
        .await
        .expect("legacy unverified DONE may be downgraded");
    let legacy_downgrade = match legacy_downgrade {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    assert_eq!(legacy_downgrade.steps[0].status, "blocked");
    assert!(!legacy_downgrade.steps[0].completion_anchor);
    assert!(legacy_downgrade.steps[0].completion_evidence.is_none());

    let contract = plan_step_contract_id("legacy-plan", "legacy", "legacy task", &[]);
    let record = completion_outcome("legacy-backfill", contract.clone(), "harness_verified");
    let expected_record_sha256 = record.record_sha256.clone();
    seed_outcome(&store, record).await;
    assert!(matches!(
        store
            .plan_update_step("legacy-plan", "legacy", "DONE", Some("legacy-backfill"),)
            .await
            .expect("backfill legacy completion"),
        PlanUpdateOutcome::Updated { .. }
    ));

    let tampered_json = serde_json::json!([
        {
            "id": "legacy",
            "desc": "legacy task",
            "status": "done",
            "deps": [],
            "completion_contract": {"contract_id": "plan-step:stale", "revision": 1},
            "completion_evidence": {
                "outcome_id": "legacy-backfill",
                "record_sha256": expected_record_sha256
            }
        },
        {
            "id": "repair-probe",
            "desc": "repair projection probe",
            "status": "pending",
            "deps": []
        }
    ])
    .to_string();
    direct
        .call(
            move |connection| -> Result<(), tokio_rusqlite::rusqlite::Error> {
                connection.execute(
                    "UPDATE plans SET steps_json=?1 WHERE plan_id='legacy-plan'",
                    tokio_rusqlite::rusqlite::params![tampered_json],
                )?;
                Ok(())
            },
        )
        .await
        .expect("tamper plan completion projection");
    let projected = store
        .plan_load("legacy-plan")
        .await
        .expect("load tampered plan")
        .expect("tampered plan exists");
    assert!(projected.steps[0].completion_evidence.is_none());
    assert!(projected.steps[0].completion_anchor);
    assert_eq!(projected.completion_diagnostics.len(), 1);
    assert_eq!(
        projected.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionContractMismatch
    );
    assert_eq!(
        projected.completion_diagnostics[0].step_id.as_deref(),
        Some("legacy")
    );
    assert_eq!(
        projected.steps[0]
            .completion_contract
            .as_ref()
            .expect("current repair contract")
            .contract_id,
        contract
    );
    assert_update_rejected(
        store
            .plan_update_step("legacy-plan", "legacy", "BLOCKED", None)
            .await
            .expect("stale-contract anchor remains irreversible"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );
    assert_save_rejected(
        store
            .plan_save(
                "legacy-plan",
                "attempt removal after contract corruption",
                &[projected.steps[1].clone()],
            )
            .await
            .expect("stale-contract anchor removal rejection"),
        PlanMutationRejectionCode::CompletionReopenForbidden,
    );

    let update_projection = store
        .plan_update_step("legacy-plan", "repair-probe", "IN_PROGRESS", None)
        .await
        .expect("update alongside stale completion");
    let update_projection = match update_projection {
        PlanUpdateOutcome::Updated { plan } => plan,
        PlanUpdateOutcome::Rejected { reason } => panic!("unexpected rejection: {reason:?}"),
    };
    let legacy_projection = update_projection
        .steps
        .iter()
        .find(|step| step.id == "legacy")
        .expect("legacy step in update projection");
    assert!(legacy_projection.completion_evidence.is_none());
    assert_eq!(update_projection.completion_diagnostics.len(), 1);
    assert_eq!(
        update_projection.completion_diagnostics[0].code,
        PlanMutationRejectionCode::CompletionContractMismatch
    );
    assert_eq!(
        legacy_projection
            .completion_contract
            .as_ref()
            .expect("current contract in update projection")
            .contract_id,
        contract
    );
}

#[tokio::test]
async fn immediate_updates_do_not_lose_concurrent_step_completions() {
    let fixture = tempfile::tempdir().expect("temporary plan fixture");
    let db_path = fixture.path().join("state.db");
    let first_store = SqliteStore::open(&db_path).await.expect("open first store");
    let second_store = SqliteStore::open(&db_path)
        .await
        .expect("open second store");
    let plan_id = "concurrent-plan";
    let first = step("first", "first concurrent task", &[]);
    let second = step("second", "second concurrent task", &[]);
    assert!(matches!(
        first_store
            .plan_save(plan_id, "concurrent", &[first, second])
            .await
            .expect("save concurrent plan"),
        PlanSaveOutcome::Saved { .. }
    ));
    seed_outcome(
        &first_store,
        completion_outcome(
            "concurrent-first",
            plan_step_contract_id(plan_id, "first", "first concurrent task", &[]),
            "harness_verified",
        ),
    )
    .await;
    seed_outcome(
        &first_store,
        completion_outcome(
            "concurrent-second",
            plan_step_contract_id(plan_id, "second", "second concurrent task", &[]),
            "harness_verified",
        ),
    )
    .await;

    let (first_result, second_result) = tokio::join!(
        first_store.plan_update_step(plan_id, "first", "DONE", Some("concurrent-first")),
        second_store.plan_update_step(plan_id, "second", "DONE", Some("concurrent-second"))
    );
    assert!(matches!(
        first_result.expect("first concurrent update"),
        PlanUpdateOutcome::Updated { .. }
    ));
    assert!(matches!(
        second_result.expect("second concurrent update"),
        PlanUpdateOutcome::Updated { .. }
    ));
    let final_plan = first_store
        .plan_load(plan_id)
        .await
        .expect("load concurrent plan")
        .expect("concurrent plan exists");
    assert!(final_plan
        .steps
        .iter()
        .all(|step| step.status == "done" && step.completion_evidence.is_some()));
}
