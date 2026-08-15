#![cfg(target_os = "linux")]

#[path = "../src/story_render_fixed_synthetic_provider.rs"]
mod story_render_fixed_synthetic_provider;
#[allow(dead_code)]
#[path = "../src/story_render_guardian.rs"]
mod story_render_guardian;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_protocol.rs"]
mod story_render_guardian_protocol;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_supervision.rs"]
mod story_render_guardian_supervision;
#[allow(dead_code)]
#[path = "../src/story_render_supervisor.rs"]
mod story_render_supervisor;
#[path = "../src/story_render_synthetic_admission.rs"]
mod story_render_synthetic_admission;
#[allow(dead_code)]
#[path = "../src/story_render_synthetic_composition.rs"]
mod story_render_synthetic_composition;

use std::sync::{Arc, Barrier};
use std::thread;

use story_render_fixed_synthetic_provider::StoryRenderFixedSyntheticProvider;
use story_render_synthetic_admission::StoryRenderSyntheticAdmissionProvider;

fn request_id(provider: &mut StoryRenderFixedSyntheticProvider) -> String {
    provider
        .generate_request_id()
        .expect("fixed synthetic request identity")
}

fn grant_is_issued(provider: &mut StoryRenderFixedSyntheticProvider) -> bool {
    let request_id = request_id(provider);
    provider.issue_grant(&request_id).is_some()
}

#[test]
fn same_sequence_is_rejected_across_fresh_provider_instances() {
    let mut first = StoryRenderFixedSyntheticProvider::new(627);
    let mut replay = StoryRenderFixedSyntheticProvider::new(627);
    let mut distinct = StoryRenderFixedSyntheticProvider::new(628);

    assert!(grant_is_issued(&mut first));
    assert!(!grant_is_issued(&mut replay));
    assert!(grant_is_issued(&mut distinct));
}

#[test]
fn wrong_identity_does_not_reserve_the_process_sequence() {
    let mut wrong_identity = StoryRenderFixedSyntheticProvider::new(629);
    let mut fresh_instance = StoryRenderFixedSyntheticProvider::new(629);

    assert!(wrong_identity.issue_grant(&"0".repeat(32)).is_none());
    assert!(grant_is_issued(&mut fresh_instance));
}

#[test]
fn concurrent_fresh_instances_have_exactly_one_grant_winner() {
    const CONTENDERS: usize = 16;
    let barrier = Arc::new(Barrier::new(CONTENDERS));
    let handles = (0..CONTENDERS)
        .map(|_| {
            let barrier = Arc::clone(&barrier);
            thread::spawn(move || {
                let mut provider = StoryRenderFixedSyntheticProvider::new(630);
                let request_id = request_id(&mut provider);
                barrier.wait();
                provider.issue_grant(&request_id).is_some()
            })
        })
        .collect::<Vec<_>>();

    let winners = handles
        .into_iter()
        .map(|handle| handle.join().expect("synthetic contender thread"))
        .filter(|won| *won)
        .count();
    assert_eq!(winners, 1);
}

#[test]
fn bounded_sequence_namespace_fails_closed_at_capacity() {
    let mut final_in_range = StoryRenderFixedSyntheticProvider::new(4_095);
    let mut first_out_of_range = StoryRenderFixedSyntheticProvider::new(4_096);
    let mut maximum = StoryRenderFixedSyntheticProvider::new(u64::MAX);

    assert!(grant_is_issued(&mut final_in_range));
    assert!(!grant_is_issued(&mut first_out_of_range));
    assert!(!grant_is_issued(&mut maximum));
}

#[test]
fn source_uses_only_a_bounded_process_local_atomic_replay_surface() {
    let source = include_str!("../src/story_render_fixed_synthetic_provider.rs");
    for required in [
        "SYNTHETIC_REPLAY_LEDGER_CAPACITY",
        "AtomicU64",
        "fetch_or",
        "reserve_sequence",
    ] {
        assert!(source.contains(required), "missing S627 marker: {required}");
    }
    for forbidden in [
        "HashSet",
        "Mutex",
        "OnceLock",
        "std::fs",
        "tokio::",
        "mcp_tools",
        "authority-keys.v1.json",
        "Hmac",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S627 surface: {forbidden}"
        );
    }
}
