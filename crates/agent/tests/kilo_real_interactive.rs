//! Real-binary verification for the kilo interactive submit profile.
//!
//! Ignored by default: needs the real `kilo` CLI installed (it resolves from
//! PATH or the kilocode VS Code/Cursor extension) and makes live calls through
//! the free Kilo Gateway. This is the gold-standard check behind the family's
//! `SubmitProfile::ENTER` — `/bin/cat` unit tests prove the PTY plumbing but
//! cannot prove that a turn actually *submits* in kilo's full-screen TUI.
//!
//! Unlike codex (which enables the Kitty keyboard protocol and only submits on
//! CSI-u Enter), kilo's TUI emits no Kitty-enable and uses bracketed paste, so a
//! bare CR submits — this test is what verified that.
//!
//! Run with:
//!   cargo test -p ab-agent --test kilo_real_interactive -- --ignored --nocapture

use ab_agent::{AgentRuntime, OpenCodeFamilyRuntime, SpawnConfig};
use std::time::Duration;

#[tokio::test]
#[ignore]
async fn kilo_real_multi_turn_round_trip() {
    let rt = OpenCodeFamilyRuntime::kilo();
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
            eprintln!("SKIP: kilo not spawnable ({e})");
            return;
        }
    };

    // Let the kilo TUI boot + the free gateway settle before driving it.
    tokio::time::sleep(Duration::from_secs(20)).await;

    // Poll the merged PTY output for `needle`, up to `secs`.
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
        "turn 1 should submit + round-trip 42 through real kilo"
    );
    assert!(
        ok2,
        "turn 2 should submit + round-trip 99 (multi-turn liveness)"
    );
}

#[tokio::test]
#[ignore]
async fn kilo_real_initial_prompt_round_trip() {
    let rt = OpenCodeFamilyRuntime::kilo();
    let sess = match rt
        .spawn(SpawnConfig {
            cwd: "/Data/CascadeProjects/agent-bridge".into(),
            interactive: true,
            initial_prompt: Some(
                "Reply with exactly: AB_KILO_INITIAL_PROMPT_OK. No extra words.".into(),
            ),
            ..Default::default()
        })
        .await
    {
        Ok(s) => s,
        Err(e) => {
            eprintln!("SKIP: kilo not spawnable ({e})");
            return;
        }
    };

    let mut ok = false;
    for _ in 0..240 {
        if rt
            .read_interactive_output(&sess.id)
            .map(|o| o.contains("AB_KILO_INITIAL_PROMPT_OK"))
            .unwrap_or(false)
        {
            ok = true;
            break;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }

    let _ = rt.kill(&sess.id).await;

    assert!(
        ok,
        "initial prompt should submit after the real kilo boot settle"
    );
}
