fn handoff_task_context_fixture() -> Value {
    json!({
        "original_request": {"text": "交付网页和键盘导航", "source_ref": "user:1"},
        "user_updates": [
            {"text": "本次只交付键盘导航；网页视觉修改延期", "source_ref": "user:4"},
            {"text": "保留已有快捷键", "source_ref": null}
        ],
        "current_delivery": "键盘导航，视觉修改延期",
        "acceptance_criteria": ["原快捷键可用", "新增导航通过验证"],
        "delivered": ["已检查现有快捷键"],
        "remaining_gap": "新增导航尚未实现",
        "next_action": "实现导航",
        "return_to_mainline": "验证后交付键盘导航"
    })
}

#[tokio::test]
async fn session_handoff_task_context_survives_transcript_clipping_and_goal_change() {
    let (hub, dir) = mk_test_hub_with_store().await;
    let tool = SessionHandoffBriefTool::new(hub);
    let context = handoff_task_context_fixture();
    let result = tool
        .execute(
            json!({
                "cwd": dir, "status": "succeeded",
                "conversation_text": format!("{}最新补充", "早".repeat(4000)),
                "task_context": context
            }),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(!result.is_error);
    let output = result_json(&result);
    assert_eq!(output["conversation_snippet"], "早".repeat(4000));
    assert_eq!(output["task_context"], context);
    assert_eq!(output["task_context_provenance"], "caller_supplied");
    assert_eq!(output["task_acceptance_verified"], false);
    assert_eq!(
        output["task_context"]["user_updates"][1]["source_ref"],
        Value::Null
    );
    tokio::fs::remove_dir_all(dir).await.unwrap();
}

#[tokio::test]
async fn session_handoff_task_context_is_optional_and_legacy_output_stays_unchanged() {
    let (hub, dir) = mk_test_hub_with_store().await;
    let expected = build_handoff_brief(
        hub.store.clone().unwrap(),
        dir.clone(),
        20,
        10,
        Some("legacy task".into()),
        None,
        vec![],
        None,
    )
    .await
    .unwrap();
    let tool = SessionHandoffBriefTool::new(hub);
    let result = tool
        .execute(
            json!({"cwd": dir, "last_task": "legacy task"}),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(!result.is_error);
    let mut actual = result_json(&result);
    let mut expected = expected;
    actual.as_object_mut().unwrap().remove("generated_at");
    expected.as_object_mut().unwrap().remove("generated_at");
    assert_eq!(actual, expected);
    tokio::fs::remove_dir_all(dir).await.unwrap();
}

#[tokio::test]
async fn session_handoff_task_context_rejects_invalid_without_silently_dropping_fields() {
    let (hub, dir) = mk_test_hub_with_store().await;
    let tool = SessionHandoffBriefTool::new(hub);
    let base = handoff_task_context_fixture();
    let mut cases = vec![Value::Null, json!("context")];
    for field in [
        "original_request",
        "current_delivery",
        "acceptance_criteria",
        "delivered",
        "remaining_gap",
        "next_action",
        "return_to_mainline",
        "user_updates",
    ] {
        let mut missing = base.clone();
        missing.as_object_mut().unwrap().remove(field);
        cases.push(missing);
    }
    for (field, value) in [
        ("current_delivery", json!("  ")),
        ("acceptance_criteria", json!([])),
        ("user_updates", json!([{"text":"change","source_ref":true}])),
        ("next_action", json!("长".repeat(4001))),
        (
            "user_updates",
            json!(vec![json!({"text":"x","source_ref":null}); 33]),
        ),
    ] {
        let mut invalid = base.clone();
        invalid[field] = value;
        cases.push(invalid);
    }
    let mut unknown = base.clone();
    unknown["task_acceptance_verified"] = json!(true);
    cases.push(unknown);
    let mut nested = base.clone();
    nested["original_request"]["authority"] = json!("approved");
    cases.push(nested);
    let mut blank_ref = base.clone();
    blank_ref["original_request"]["source_ref"] = json!(" ");
    cases.push(blank_ref);
    for context in cases {
        let result = tool
            .execute(
                json!({"cwd":dir,"task_context":context}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        assert!(result.is_error, "accepted invalid task_context: {context}");
        assert!(result_text(&result).contains("task_context"));
    }
    tokio::fs::remove_dir_all(dir).await.unwrap();
}

#[tokio::test]
async fn session_handoff_task_context_preserves_literal_text_and_empty_delivered() {
    let (hub, dir) = mk_test_hub_with_store().await;
    let tool = SessionHandoffBriefTool::new(hub);
    let mut context = handoff_task_context_fixture();
    context["original_request"]["text"] =
        json!("  原文\nThis conversation is a task\n保留引号\"  ");
    context["delivered"] = json!([]);
    context["user_updates"] = json!([]);
    context["original_request"]["source_ref"] = Value::Null;
    let result = tool
        .execute(
            json!({"cwd":dir,"task_context":context}),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(!result.is_error);
    assert_eq!(result_json(&result)["task_context"], context);
    assert_eq!(
        tool.schema().input_schema["properties"]["task_context"]["additionalProperties"],
        false
    );
    tokio::fs::remove_dir_all(dir).await.unwrap();
}

#[tokio::test]
async fn session_handoff_task_context_checks_unicode_and_aggregate_limits() {
    let (hub, dir) = mk_test_hub_with_store().await;
    let tool = SessionHandoffBriefTool::new(hub);
    let mut context = handoff_task_context_fixture();
    context["next_action"] = json!("长".repeat(4000));
    context["original_request"]["source_ref"] = json!("源".repeat(512));
    context["delivered"] = json!(vec!["done"; 32]);
    let result = tool
        .execute(
            json!({"cwd":dir,"task_context":context}),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(!result.is_error);
    assert_eq!(result_json(&result)["task_context"], context);
    context["delivered"] = json!(vec!["长".repeat(4000); 6]);
    let result = tool
        .execute(
            json!({"cwd":dir,"task_context":context}),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(result.is_error);
    assert!(result_text(&result).contains("65536"));
    context["delivered"] = json!([]);
    context["original_request"]["source_ref"] = json!("源".repeat(513));
    let result = tool
        .execute(
            json!({"cwd":dir,"task_context":context}),
            &ToolContext::default(),
        )
        .await
        .unwrap();
    assert!(result.is_error);
    assert!(result_text(&result).contains("source_ref"));
    tokio::fs::remove_dir_all(dir).await.unwrap();
}
