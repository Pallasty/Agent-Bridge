#![cfg(target_os = "linux")]

#[path = "../src/story_render_replay_continuity_synthetic.rs"]
mod story_render_replay_continuity_synthetic;

use story_render_replay_continuity_synthetic::{
    StoryRenderReplayContinuityError, StoryRenderReplayContinuityStore,
    StoryRenderSyntheticReplayFault, StoryRenderSyntheticReplayMemory,
};

#[test]
fn reserved_sequence_survives_reopened_synthetic_handle() {
    let memory = StoryRenderSyntheticReplayMemory::new();
    let first = memory.open();
    let reservation = first.reserve(628).expect("initial reservation");

    let reopened = memory.open();
    drop(reservation);
    drop(first);

    assert!(matches!(
        reopened.reserve(628),
        Err(StoryRenderReplayContinuityError::Replay)
    ));
    assert!(reopened.reserve(629).is_ok());
}

#[test]
fn commit_and_abort_are_both_terminal_after_reopen() {
    let memory = StoryRenderSyntheticReplayMemory::new();
    let first = memory.open();
    let committed = first.reserve(630).expect("committed reservation");
    let aborted = first.reserve(631).expect("aborted reservation");
    first.commit(committed).expect("commit reservation");
    first.abort(aborted).expect("abort reservation");

    let reopened = memory.open();
    for sequence in [630, 631] {
        assert!(matches!(
            reopened.reserve(sequence),
            Err(StoryRenderReplayContinuityError::Replay)
        ));
    }
}

#[test]
fn reserve_backend_failure_does_not_create_a_phantom_reservation() {
    let memory = StoryRenderSyntheticReplayMemory::new();
    let unavailable = memory.open_with_fault(StoryRenderSyntheticReplayFault::ReserveUnavailable);

    assert!(matches!(
        unavailable.reserve(632),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    ));
    assert!(memory.open().reserve(632).is_ok());
}

#[test]
fn finalize_failure_leaves_reserved_sequence_fail_closed() {
    let memory = StoryRenderSyntheticReplayMemory::new();
    let unavailable = memory.open_with_fault(StoryRenderSyntheticReplayFault::FinalizeUnavailable);

    let commit = unavailable.reserve(633).expect("commit reservation");
    assert_eq!(
        unavailable.commit(commit),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    );
    let abort = unavailable.reserve(634).expect("abort reservation");
    assert_eq!(
        unavailable.abort(abort),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    );

    let reopened = memory.open();
    for sequence in [633, 634] {
        assert!(matches!(
            reopened.reserve(sequence),
            Err(StoryRenderReplayContinuityError::Replay)
        ));
    }
}

#[test]
fn reservation_cannot_be_finalized_by_another_backing() {
    let first_memory = StoryRenderSyntheticReplayMemory::new();
    let second_memory = StoryRenderSyntheticReplayMemory::new();
    let reservation = first_memory.open().reserve(635).expect("reservation");

    assert_eq!(
        second_memory.open().commit(reservation),
        Err(StoryRenderReplayContinuityError::WrongStore)
    );
    assert!(matches!(
        first_memory.open().reserve(635),
        Err(StoryRenderReplayContinuityError::Replay)
    ));
}

#[test]
fn bounded_namespace_rejects_sequences_at_and_above_capacity() {
    let memory = StoryRenderSyntheticReplayMemory::new();
    let store = memory.open();

    assert!(store.reserve(4_095).is_ok());
    for sequence in [4_096, u64::MAX] {
        assert!(matches!(
            store.reserve(sequence),
            Err(StoryRenderReplayContinuityError::OutOfRange)
        ));
    }
}

#[test]
fn source_is_a_bounded_synchronous_persistence_seam_only() {
    let source = include_str!("../src/story_render_replay_continuity_synthetic.rs");
    for required in [
        "trait StoryRenderReplayContinuityStore",
        "SYNTHETIC_REPLAY_CONTINUITY_CAPACITY",
        "AtomicU8",
        "compare_exchange",
        "STATE_AVAILABLE",
        "STATE_RESERVED",
        "STATE_COMMITTED",
        "STATE_ABORTED",
    ] {
        assert!(source.contains(required), "missing S628 marker: {required}");
    }
    for forbidden in [
        "std::fs",
        "OpenOptions",
        "rusqlite",
        "sqlite",
        "tokio::",
        "mcp_tools",
        "authority-keys",
        "Hmac",
        "onnxruntime",
        "sounddevice",
        "process::Command",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S628 surface: {forbidden}"
        );
    }
}
