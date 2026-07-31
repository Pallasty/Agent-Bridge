#[path = "../src/story_contract.rs"]
mod story_contract;

use serde_json::json;
use story_contract::{
    canonical_json, segment_cache_key, sha256_canonical_json, SegmentCacheKeyInput, StoryRequest,
    StoryStart,
};

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
