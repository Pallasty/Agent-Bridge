//! Real-binary verification for the opencode interactive submit profile.
//!
//! Ignored by default: needs the real `opencode` CLI installed and authenticated
//! (an OpenCode Zen credential in `~/.local/share/opencode/auth.json`) with a
//! default model configured in `~/.config/opencode/opencode.json` (a free Zen
//! model such as `opencode/deepseek-v4-flash-free` keeps this test free).
//!
//! This is the gold-standard check behind opencode's `SubmitProfile::KITTY_ENTER`.
//! It corrected a real bug: opencode's submit key was previously *inferred* as
//! bare `ENTER` from its downstream fork kilo — but opencode, unlike kilo,
//! **enables the Kitty keyboard protocol**, so a zero-settle combined `text\r`
//! write is typed and never submits. Empirically both `KITTY_ENTER` and a
//! CR-after-settle round-trip; opencode uses `KITTY_ENTER` (Kitty-native, matches
//! codex). `/bin/cat` unit tests prove the PTY plumbing but cannot prove submit.
//!
//! Run with:
//!   cargo test -p ab-agent --test opencode_real_interactive -- --ignored --nocapture

use ab_agent::{AgentRuntime, OpenCodeFamilyRuntime, SpawnConfig};
use std::time::Duration;

#[tokio::test]
#[ignore]
async fn opencode_real_multi_turn_round_trip() {
    let rt = OpenCodeFamilyRuntime::opencode();
    let sess = match rt
        .spawn(SpawnConfig {
            cwd: "/Data/CascadeProjects/agent-bridge".into(),
            interactive: true,
            ..Default::default()
        })
        .await
    {
        Ok(s) => s,
        Err(e) => {
            eprintln!("SKIP: opencode not spawnable ({e})");
            return;
        }
    };

    // Let the opencode TUI boot + the Zen provider settle before driving it.
    tokio::time::sleep(Duration::from_secs(18)).await;

    async fn wait(
        rt: &OpenCodeFamilyRuntime,
        sess: &ab_agent::AgentSession,
        needle: &str,
        secs: u64,
    ) -> bool {
        let mut waited = 0u64;
        while waited <= secs * 1000 {
            if rt
                .read_interactive_output(&sess.id)
                .map(|o| o.contains(needle))
                .unwrap_or(false)
            {
                return true;
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
            waited += 500;
        }
        false
    }

    rt.send_input(
        &sess.id,
        "What is 6 multiplied by 7? Reply with only the number.",
    )
    .await
    .expect("send turn 1");
    let ok1 = wait(&rt, &sess, "42", 120).await;
    eprintln!(
        "turn1 (expect 42): {}",
        if ok1 { "ROUND-TRIP OK" } else { "FAILED" }
    );

    // A second turn proves the session stayed live across submits.
    rt.send_input(&sess.id, "What is 100 minus 1? Reply with only the number.")
        .await
        .expect("send turn 2");
    let ok2 = wait(&rt, &sess, "99", 120).await;
    eprintln!(
        "turn2 (expect 99): {}",
        if ok2 { "ROUND-TRIP OK" } else { "FAILED" }
    );

    let _ = rt.kill(&sess.id).await;

    assert!(
        ok1,
        "turn 1 should submit + round-trip 42 through real opencode (KITTY_ENTER)"
    );
    assert!(
        ok2,
        "turn 2 should submit + round-trip 99 (multi-turn liveness)"
    );
}
