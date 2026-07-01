//! Real-binary verification for the gemini interactive submit profile.
//!
//! Ignored by default: needs the real `gemini` CLI installed and a working
//! `GEMINI_API_KEY` in the environment (it makes live Google AI Studio calls).
//! This is the gold-standard check behind gemini's `SubmitProfile::ENTER_SETTLED`:
//! `/bin/cat` unit tests prove the PTY plumbing but cannot prove that a turn
//! actually *submits* in gemini's full-screen Ink/React TUI.
//!
//! The important, non-obvious result this locked in: gemini **enables the Kitty
//! keyboard protocol** (just like codex) yet still submits on a **bare CR**, not
//! CSI-u Enter. Kitty-enable does NOT imply Kitty-Enter — the submit key and
//! settle shape had to be probed empirically, and it is `ENTER_SETTLED`.
//!
//! To skip gemini's first-run auth dialog headlessly, the test points `HOME` at
//! a throwaway dir seeded with a `.gemini/settings.json` that pre-selects the
//! `gemini-api-key` auth type, and passes `GEMINI_CLI_TRUST_WORKSPACE=true`.
//!
//! Run with:
//!   GEMINI_API_KEY=… cargo test -p ab-agent --test gemini_real_interactive -- --ignored --nocapture

use ab_agent::{AgentRuntime, GeminiRuntime, SpawnConfig};
use std::collections::HashMap;
use std::time::Duration;

#[tokio::test]
#[ignore]
async fn gemini_real_multi_turn_round_trip() {
    let api_key = match std::env::var("GEMINI_API_KEY") {
        Ok(k) if !k.trim().is_empty() => k,
        _ => {
            eprintln!("SKIP: set GEMINI_API_KEY to run the real gemini interactive test");
            return;
        }
    };

    // Throwaway HOME seeded to skip gemini's first-run onboarding (auth dialog,
    // tips) so the bare TUI drops straight into the chat input.
    let home = std::env::temp_dir().join(format!("gemini-gold-{}", std::process::id()));
    let gemini_dir = home.join(".gemini");
    std::fs::create_dir_all(&gemini_dir).expect("create temp .gemini");
    std::fs::write(
        gemini_dir.join("settings.json"),
        r#"{"security":{"auth":{"selectedType":"gemini-api-key"}},"general":{"defaultApprovalMode":"yolo"},"ide":{"hasSeenNudge":true}}"#,
    )
    .expect("write settings.json");
    std::fs::write(
        gemini_dir.join("state.json"),
        r#"{"tipsShown":10,"terminalSetupPromptShown":true,"focusUiEnabled":true}"#,
    )
    .expect("write state.json");

    let mut env = HashMap::new();
    env.insert("HOME".to_string(), home.display().to_string());
    env.insert("GEMINI_API_KEY".to_string(), api_key);
    env.insert("GEMINI_CLI_TRUST_WORKSPACE".to_string(), "true".to_string());

    let rt = GeminiRuntime::new();
    let sess = match rt
        .spawn(SpawnConfig {
            cwd: home.display().to_string(),
            env,
            interactive: true,
            ..Default::default()
        })
        .await
    {
        Ok(s) => s,
        Err(e) => {
            eprintln!("SKIP: gemini not spawnable ({e})");
            let _ = std::fs::remove_dir_all(&home);
            return;
        }
    };

    // Let the gemini Ink TUI boot + the API settle before driving it.
    tokio::time::sleep(Duration::from_secs(25)).await;

    async fn wait(
        rt: &GeminiRuntime,
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
    let _ = std::fs::remove_dir_all(&home);

    assert!(
        ok1,
        "turn 1 should submit + round-trip 42 through real gemini (bare CR)"
    );
    assert!(
        ok2,
        "turn 2 should submit + round-trip 99 (multi-turn liveness)"
    );
}
