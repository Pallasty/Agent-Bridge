//! Real-binary verification for the codex interactive submit profile.
//!
//! Ignored by default: needs the real `codex` CLI installed + authed and makes
//! live API calls. This is the gold-standard check behind `SubmitProfile::KITTY_ENTER`
//! — `/bin/cat` unit tests prove the PTY plumbing but cannot prove that a turn
//! actually *submits* in codex's Kitty-keyboard TUI.
//!
//! Run with:
//!   cargo test -p ab-agent --test codex_real_interactive -- --ignored --nocapture

use ab_agent::{AgentRuntime, CodexRuntime, SpawnConfig};
use std::time::Duration;

#[tokio::test]
#[ignore]
async fn codex_real_multi_turn_round_trip() {
    let rt = CodexRuntime::new();
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
            eprintln!("SKIP: codex not spawnable ({e})");
            return;
        }
    };

    // Let codex boot its TUI + MCP servers before driving it.
    tokio::time::sleep(Duration::from_secs(15)).await;

    // Poll the merged PTY output for `needle`, up to `secs`.
    async fn wait(
        rt: &CodexRuntime,
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
    let ok1 = wait(&rt, &sess, "42", 90).await;
    eprintln!(
        "turn1 (expect 42): {}",
        if ok1 { "ROUND-TRIP OK" } else { "FAILED" }
    );

    // A second turn proves the session stayed live across submits.
    rt.send_input(&sess.id, "What is 100 minus 1? Reply with only the number.")
        .await
        .expect("send turn 2");
    let ok2 = wait(&rt, &sess, "99", 90).await;
    eprintln!(
        "turn2 (expect 99): {}",
        if ok2 { "ROUND-TRIP OK" } else { "FAILED" }
    );

    let _ = rt.kill(&sess.id).await;

    assert!(
        ok1,
        "turn 1 should submit + round-trip 42 through real codex"
    );
    assert!(
        ok2,
        "turn 2 should submit + round-trip 99 (multi-turn liveness)"
    );
}
