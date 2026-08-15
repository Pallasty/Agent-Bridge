#[path = "../src/story_contract.rs"]
mod story_contract;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
use story_contract::{
    build_chapter_voice_plan, build_story_command_preflight, canonical_json, ingest_story_source,
    ingest_story_source_with_policy, resolve_story_evidence, run_story_preflight_hardened,
    segment_cache_key, sha256_canonical_json, EvidenceFileSpec, SegmentCacheKeyInput,
    StoryEvidenceBundleConfig, StoryPreflightCancellation, StoryRequest, StorySourcePolicy,
    StoryStart,
};

fn story_fixture_input_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/design/voice-scene/fixtures/story_s1.md")
}

fn canonical_story_fixture_path(input: &Path) -> PathBuf {
    input.canonicalize().expect("canonical story fixture")
}

#[test]
fn typed_request_matches_structured_s5zg_shape() {
    let request: StoryRequest = serde_json::from_value(json!({
        "source_path": "docs/design/voice-scene/fixtures/story_s1.md",
        "start": {"kind": "chapter", "chapter": 2},
        "dry_run": true
    }))
    .expect("typed request");

    assert_eq!(request.start, StoryStart::Chapter { chapter: 2 },);
    request.validate().expect("valid request");
    assert_eq!(
        canonical_json(&serde_json::to_value(&request).expect("request value")).unwrap(),
        r#"{"dry_run":true,"source_path":"docs/design/voice-scene/fixtures/story_s1.md","start":{"chapter":2,"kind":"chapter"}}"#
    );
}

#[test]
fn canonical_json_and_sha256_match_python_oracle() {
    let value = json!({"z": 1, "a": [3, {"β": true, "a": null}]});

    assert_eq!(
        canonical_json(&value).unwrap(),
        r#"{"a":[3,{"a":null,"β":true}],"z":1}"#
    );
    assert_eq!(
        sha256_canonical_json(&value).unwrap(),
        "e1d2acda1cf0ff8dcee119f0c5525cd3107d0b201c559564076a7dac0396fff8"
    );
}

#[test]
fn request_digest_matches_python_oracle() {
    let value = json!({
        "source_path": "docs/design/voice-scene/fixtures/story_s1.md",
        "start": {"kind": "chapter", "chapter": 2},
        "dry_run": true
    });

    assert_eq!(
        sha256_canonical_json(&value).unwrap(),
        "680d34a1b0bf669a1da3c338f4809f655b7ca19306995936b2ca512959ef986e"
    );
}

#[test]
fn segment_cache_key_matches_s5zf_python_evidence() {
    let key = segment_cache_key(&SegmentCacheKeyInput {
        source_sha256: "a485b7f3151f62c5ed0e118a03f66ee3dc3ddb57eb23b5e7ea93e0abb14f6566".into(),
        voice_plan_sha256: "36dc73518b4f166afb98c97403376df05b6245cfdb9d56abd8c2d1981ff120cb"
            .into(),
        event_id: "event_75676e738dacbfa37b90.narration".into(),
        text: "苏岚回答。".into(),
        qwen_speaker: "Vivian".into(),
        style_instruction: "温柔、清晰、克制地叙述，不替角色夸张表演。".into(),
        voice_profile_version: 2,
        model_inference_sha256: "70d3911f6923000d776cd16d575bf6518f6a638ee0adf8c1b60d0e1d34fdeb75"
            .into(),
    })
    .expect("cache key");

    assert_eq!(
        key,
        "cf77113811bd2477b2f848a7c78cf5d641e1e8c1834b6132b9f565f112700a2a"
    );
}

#[test]
fn invalid_requests_fail_closed() {
    for request in [
        StoryRequest {
            source_path: "book.epub".into(),
            start: StoryStart::FromStart,
            dry_run: true,
        },
        StoryRequest {
            source_path: "book.md".into(),
            start: StoryStart::FromStart,
            dry_run: false,
        },
        StoryRequest {
            source_path: "book.md".into(),
            start: StoryStart::Chapter { chapter: 0 },
            dry_run: true,
        },
    ] {
        assert!(request.validate().is_err());
    }
}

#[test]
fn source_ingest_matches_python_chapter_two_oracle() {
    let fixture_input = story_fixture_input_path();
    assert!(fixture_input
        .components()
        .any(|component| matches!(component, std::path::Component::ParentDir)));
    let canonical_fixture = canonical_story_fixture_path(&fixture_input);
    let ingest = ingest_story_source(&fixture_input, &StoryStart::Chapter { chapter: 2 })
        .expect("fixture ingest");
    let actual = serde_json::to_value(ingest).unwrap();
    let expected_uri = canonical_fixture.to_string_lossy().into_owned();
    let mut expected: Value = serde_json::from_str(
        r#"{"chapters":[{"chapter_id":"chapter_f29cded10e417c151b85","ordinal":1,"selected":false,"source_span":{"char_end":53,"char_start":0,"line_end":6,"line_start":1,"source_id":"source_4982d79cfc3172771f4a"},"title":"第一章 夜雨"},{"chapter_id":"chapter_dea6e639ff06f2cc5ce9","ordinal":2,"selected":true,"source_span":{"char_end":88,"char_start":53,"line_end":10,"line_start":7,"source_id":"source_4982d79cfc3172771f4a"},"title":"第二章 回声"}],"selection":{"first_chapter":2,"selected_chapter_ids":["chapter_dea6e639ff06f2cc5ce9"]},"source":{"byte_length":232,"char_length":88,"encoding":"utf-8","format":"md","kind":"novel","sha256":"a485b7f3151f62c5ed0e118a03f66ee3dc3ddb57eb23b5e7ea93e0abb14f6566","source_id":"source_4982d79cfc3172771f4a","uri":null,"version":"source-v1"}}"#,
    )
    .expect("source ingest oracle");

    assert_eq!(
        actual.pointer("/source/uri").and_then(Value::as_str),
        Some(expected_uri.as_str())
    );
    expected["source"]["uri"] = Value::String(expected_uri);

    assert_eq!(
        canonical_json(&actual).unwrap(),
        canonical_json(&expected).unwrap()
    );
}

#[test]
fn source_ingest_from_start_selects_every_chapter() {
    let ingest = ingest_story_source(
        Path::new("../../docs/design/voice-scene/fixtures/story_s1.md"),
        &StoryStart::FromStart,
    )
    .expect("fixture ingest");

    assert_eq!(ingest.selection.first_chapter, 1);
    assert_eq!(
        ingest.selection.selected_chapter_ids,
        vec![
            "chapter_f29cded10e417c151b85",
            "chapter_dea6e639ff06f2cc5ce9"
        ]
    );
    assert!(ingest.chapters.iter().all(|chapter| chapter.selected));
}

#[test]
fn source_ingest_fails_closed_for_missing_chapter_and_non_utf8() {
    let fixture = Path::new("../../docs/design/voice-scene/fixtures/story_s1.md");
    assert!(ingest_story_source(fixture, &StoryStart::Chapter { chapter: 99 }).is_err());

    let invalid = std::env::temp_dir().join(format!(
        "ab-s5zk-invalid-utf8-{}-{}.md",
        std::process::id(),
        std::thread::current().name().unwrap_or("test")
    ));
    std::fs::write(&invalid, [0xff, 0xfe]).expect("write invalid fixture");
    let result = ingest_story_source(&invalid, &StoryStart::FromStart);
    std::fs::remove_file(&invalid).expect("remove invalid fixture");
    assert!(result.is_err());
}

fn voice_plan_inputs() -> (
    serde_json::Value,
    serde_json::Value,
    serde_json::Value,
    serde_json::Value,
) {
    let plan = json!({
        "status": "story_plan_reviewable",
        "source": {"sha256": "1".repeat(64)},
        "chapters": [
            {"chapter_id": "chapter_1", "selected": true, "source_span": {"line_start": 1, "line_end": 5}},
            {"chapter_id": "chapter_2", "selected": true, "source_span": {"line_start": 6, "line_end": 9}}
        ],
        "voice_scene": {"timeline": [
            {"event_id": "event_1", "sequence": 1, "source_ref": {"locator": "line=2;chars=5:10"}, "utterance": {"speaker_id": "narrator", "text": "雨声渐近。"}},
            {"event_id": "event_2", "sequence": 2, "source_ref": {"locator": "line=4;chars=11:20"}, "utterance": {"speaker_id": "lin", "text": "林默说：“快走。”"}},
            {"event_id": "event_3", "sequence": 3, "source_ref": {"locator": "line=5;chars=21:30"}, "utterance": {"speaker_id": "su", "text": "等等。"}},
            {"event_id": "event_4", "sequence": 4, "source_ref": {"locator": "line=7;chars=31:40"}, "utterance": {"speaker_id": "narrator", "text": "门开了。"}}
        ]}
    });
    let mapping = json!({
        "source_sha256": "1".repeat(64),
        "mapping_sha256": "2".repeat(64),
        "roles": [
            {"speaker_id": "narrator", "display_name": "旁白", "role_kind": "narrator", "qwen_speaker": "Vivian", "style_instruction": "旁白风格。", "voice_profile_version": 2},
            {"speaker_id": "lin", "display_name": "林默", "role_kind": "character", "qwen_speaker": "Dylan", "style_instruction": "林默风格。", "voice_profile_version": 2},
            {"speaker_id": "su", "display_name": "苏岚", "role_kind": "character", "qwen_speaker": "Serena", "style_instruction": "苏岚风格。", "voice_profile_version": 2}
        ]
    });
    let role_acceptance = json!({
        "mapping_sha256": "2".repeat(64),
        "claims": {"owner_accepted_both": true, "voices_distinguishable": true, "chapter_render_ready": true}
    });
    let pacing = json!({
        "policy": {"same_paragraph": 0.65, "speaker_turn": 1.0, "paragraph_break": 1.4, "scene_break": 2.2, "selection_authority": "explicit_structural_label", "freeform_model_guessing": false},
        "claims": {"owner_pacing_accepted": true}
    });
    (plan, mapping, role_acceptance, pacing)
}

#[test]
fn voice_plan_transitions_and_digest_match_python_oracle() {
    let (plan, mapping, role_acceptance, pacing) = voice_plan_inputs();
    let result =
        build_chapter_voice_plan(&plan, &mapping, &role_acceptance, &pacing).expect("voice plan");

    assert_eq!(
        result["plan_sha256"],
        "f6cbc5aa1eba5b4b5a722fe3be6224a17b8ffd14c95325b31d0ed060ad6a0113"
    );
    assert_eq!(
        result["segments"]
            .as_array()
            .unwrap()
            .iter()
            .map(|row| row["text"].as_str().unwrap())
            .collect::<Vec<_>>(),
        vec!["雨声渐近。", "林默说。", "快走。", "等等。", "门开了。"]
    );
    assert_eq!(
        result["segments"].as_array().unwrap()[1]["source_span"],
        json!({"line": 4, "char_start": 11, "char_end": 15, "source_text": "林默说：", "normalization": "terminal_colon_to_full_stop"})
    );
    assert_eq!(
        result["segments"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|row| row["transition_after"].as_str())
            .collect::<Vec<_>>(),
        vec![
            "paragraph_break",
            "speaker_turn",
            "speaker_turn",
            "scene_break"
        ]
    );
}

#[test]
fn voice_plan_segment_cache_key_matches_python_oracle() {
    let (plan, mapping, role_acceptance, pacing) = voice_plan_inputs();
    let result =
        build_chapter_voice_plan(&plan, &mapping, &role_acceptance, &pacing).expect("voice plan");
    let segment = &result["segments"][0];
    let key = segment_cache_key(&SegmentCacheKeyInput {
        source_sha256: result["source_sha256"].as_str().unwrap().into(),
        voice_plan_sha256: result["plan_sha256"].as_str().unwrap().into(),
        event_id: segment["event_id"].as_str().unwrap().into(),
        text: segment["text"].as_str().unwrap().into(),
        qwen_speaker: segment["qwen_speaker"].as_str().unwrap().into(),
        style_instruction: segment["style_instruction"].as_str().unwrap().into(),
        voice_profile_version: segment["voice_profile_version"].as_u64().unwrap() as u32,
        model_inference_sha256: "70d3911f6923000d776cd16d575bf6518f6a638ee0adf8c1b60d0e1d34fdeb75"
            .into(),
    })
    .unwrap();

    assert_eq!(
        key,
        "5599579c3cc255c44ba645750dc1fafa0d12904ecc158e85905c7f506703a7b6"
    );
}

#[test]
fn voice_plan_fails_closed_on_unaccepted_pacing() {
    let (plan, mapping, role_acceptance, mut pacing) = voice_plan_inputs();
    pacing["claims"]["owner_pacing_accepted"] = json!(false);

    assert!(build_chapter_voice_plan(&plan, &mapping, &role_acceptance, &pacing).is_err());
}

fn load_voice_scene_json(name: &str) -> serde_json::Value {
    let path = Path::new("../../docs/design/voice-scene").join(name);
    serde_json::from_slice(&std::fs::read(path).expect("fixture read")).expect("fixture json")
}

#[test]
fn full_preflight_matches_s5zf_python_receipt() {
    let fixture_input = story_fixture_input_path();
    assert!(fixture_input
        .components()
        .any(|component| matches!(component, std::path::Component::ParentDir)));
    let canonical_fixture = canonical_story_fixture_path(&fixture_input);
    let expected_source_path = canonical_fixture.to_string_lossy().into_owned();
    let request = StoryRequest {
        source_path: fixture_input.to_string_lossy().into_owned(),
        start: StoryStart::Chapter { chapter: 2 },
        dry_run: true,
    };
    let result = build_story_command_preflight(
        "/story \"docs/design/voice-scene/fixtures/story_s1.md\" chapter 2",
        &request,
        &load_voice_scene_json("s5zc_source_grounded_utterance_plan_receipt.json"),
        &load_voice_scene_json("s5x_story_voice_mapping_receipt.json"),
        &load_voice_scene_json("s5y_character_voice_audition_receipt.json"),
        &load_voice_scene_json("s5ze_cross_chapter_continuity_receipt.json"),
    )
    .expect("preflight");
    let mut expected =
        load_voice_scene_json("s5zf_story_command_integration_preflight_receipt.json");

    assert_eq!(
        result
            .pointer("/command/source_path")
            .and_then(Value::as_str),
        Some(expected_source_path.as_str())
    );
    expected["command"]["source_path"] = Value::String(expected_source_path);

    assert_eq!(result, expected);
    assert_eq!(
        result["preflight_sha256"],
        "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
    );
}

#[test]
fn full_preflight_from_start_selects_first_bounded_chapter() {
    let request = StoryRequest {
        source_path: "../../docs/design/voice-scene/fixtures/story_s1.md".into(),
        start: StoryStart::FromStart,
        dry_run: true,
    };
    let result = build_story_command_preflight(
        "/story \"docs/design/voice-scene/fixtures/story_s1.md\" from-start",
        &request,
        &load_voice_scene_json("s5zc_source_grounded_utterance_plan_receipt.json"),
        &load_voice_scene_json("s5x_story_voice_mapping_receipt.json"),
        &load_voice_scene_json("s5y_character_voice_audition_receipt.json"),
        &load_voice_scene_json("s5ze_cross_chapter_continuity_receipt.json"),
    )
    .expect("preflight");

    assert_eq!(result["command"]["chapter_number"], 1);
    assert_eq!(result["selection"]["selected_segments"], 4);
    assert!(result["selection"]["preceding_scene_gap_seconds"].is_null());
}

#[test]
fn full_preflight_fails_closed_on_runtime_flag_and_evidence_drift() {
    let request = StoryRequest {
        source_path: "../../docs/design/voice-scene/fixtures/story_s1.md".into(),
        start: StoryStart::Chapter { chapter: 2 },
        dry_run: true,
    };
    let voice_plan = load_voice_scene_json("s5zc_source_grounded_utterance_plan_receipt.json");
    let mapping = load_voice_scene_json("s5x_story_voice_mapping_receipt.json");
    let role = load_voice_scene_json("s5y_character_voice_audition_receipt.json");
    let mut continuity = load_voice_scene_json("s5ze_cross_chapter_continuity_receipt.json");
    assert!(build_story_command_preflight(
        "/story book.md chapter 2 --play",
        &request,
        &voice_plan,
        &mapping,
        &role,
        &continuity,
    )
    .is_err());

    continuity["claims"]["owner_accepted"] = json!(false);
    assert!(build_story_command_preflight(
        "/story \"docs/design/voice-scene/fixtures/story_s1.md\" chapter 2",
        &request,
        &voice_plan,
        &mapping,
        &role,
        &continuity,
    )
    .is_err());
}

fn file_sha256(path: &Path) -> String {
    let mut digest = Sha256::new();
    digest.update(std::fs::read(path).expect("fixture bytes"));
    format!("{:x}", digest.finalize())
}

fn evidence_config(root: &Path) -> StoryEvidenceBundleConfig {
    let spec = |name: &str| {
        let path = root.join(name);
        EvidenceFileSpec {
            sha256: file_sha256(&path),
            path,
        }
    };
    StoryEvidenceBundleConfig {
        voice_plan: spec("s5zc_source_grounded_utterance_plan_receipt.json"),
        mapping: spec("s5x_story_voice_mapping_receipt.json"),
        role_acceptance: spec("s5y_character_voice_audition_receipt.json"),
        continuity_acceptance: spec("s5ze_cross_chapter_continuity_receipt.json"),
        allowed_root: root.to_path_buf(),
        max_file_bytes: 1_048_576,
    }
}

#[test]
fn hardened_source_admission_rejects_escape_and_oversize() {
    let root = std::env::temp_dir().join(format!("ab-s5zo-root-{}", std::process::id()));
    std::fs::create_dir_all(&root).expect("create root");
    let inside = root.join("inside.md");
    std::fs::write(&inside, "# 第一章\n内容。\n").expect("write inside");
    let policy = StorySourcePolicy {
        allowed_root: root.clone(),
        max_bytes: 8,
    };
    let outside = root.with_extension("md");
    std::fs::write(&outside, "# 第一章\n外部。\n").expect("write outside");

    let oversized = ingest_story_source_with_policy(
        &inside,
        &StoryStart::FromStart,
        &policy,
        &StoryPreflightCancellation::new(),
    );
    let escaped = ingest_story_source_with_policy(
        &outside,
        &StoryStart::FromStart,
        &StorySourcePolicy {
            max_bytes: 1024,
            ..policy
        },
        &StoryPreflightCancellation::new(),
    );

    std::fs::remove_file(inside).expect("remove inside");
    std::fs::remove_file(outside).expect("remove outside");
    std::fs::remove_dir(root).expect("remove root");
    assert!(oversized.unwrap_err().to_string().contains("byte_limit"));
    assert!(escaped.unwrap_err().to_string().contains("allowed_root"));
}

#[test]
fn configured_evidence_resolver_is_root_and_hash_bound() {
    let root = Path::new("../../docs/design/voice-scene")
        .canonicalize()
        .expect("voice scene root");
    let config = evidence_config(&root);
    let bundle = resolve_story_evidence(&config, &StoryPreflightCancellation::new())
        .expect("resolved evidence");
    assert_eq!(bundle.voice_plan["status"], "chapter_voice_plan_reviewable");

    let mut drifted = config;
    drifted.mapping.sha256 = "0".repeat(64);
    assert!(
        resolve_story_evidence(&drifted, &StoryPreflightCancellation::new())
            .unwrap_err()
            .to_string()
            .contains("SHA-256")
    );
}

#[tokio::test]
async fn hardened_preflight_honors_pre_cancel_without_runtime_effects() {
    let root = Path::new("../../docs/design/voice-scene")
        .canonicalize()
        .expect("voice scene root");
    let cancellation = Arc::new(StoryPreflightCancellation::new());
    cancellation.cancel();
    let request = StoryRequest {
        source_path: root.join("fixtures/story_s1.md").display().to_string(),
        start: StoryStart::Chapter { chapter: 2 },
        dry_run: true,
    };
    let error = run_story_preflight_hardened(
        "/story fixtures/story_s1.md chapter 2",
        request,
        StorySourcePolicy {
            allowed_root: root.clone(),
            max_bytes: 1_048_576,
        },
        evidence_config(&root),
        cancellation,
    )
    .await
    .unwrap_err();

    assert!(error.to_string().contains("cancelled"));
}

#[tokio::test]
async fn hardened_preflight_preserves_s5zf_parity() {
    let root = Path::new("../../docs/design/voice-scene")
        .canonicalize()
        .expect("voice scene root");
    let request = StoryRequest {
        source_path: root.join("fixtures/story_s1.md").display().to_string(),
        start: StoryStart::Chapter { chapter: 2 },
        dry_run: true,
    };
    let result = run_story_preflight_hardened(
        "/story fixtures/story_s1.md chapter 2",
        request,
        StorySourcePolicy {
            allowed_root: root.clone(),
            max_bytes: 1_048_576,
        },
        evidence_config(&root),
        Arc::new(StoryPreflightCancellation::new()),
    )
    .await
    .expect("hardened preflight");

    assert_eq!(
        result["preflight_sha256"],
        "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
    );
    assert!(result["execution_authorized"] == false);
    assert!(result["runtime_effects"]
        .as_object()
        .expect("runtime effects")
        .values()
        .all(|value| value == false));
}
