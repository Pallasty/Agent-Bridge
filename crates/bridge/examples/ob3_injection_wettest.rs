//! OB-3 wet-test: exercise `remote_steer::send` / `send_profiled` end-to-end
//! against a real LOCAL tmux session running a controlled `bash` — NO agent CLI,
//! no production writes. This verifies the injection *mechanism* (the async
//! composition unit tests can't reach), NOT a per-backend C-table row.
//!
//!   A — default profile submits with `Enter` (executed output lands in pane);
//!   B — a non-`Enter` submit_key drives the split type-then-key path & submits;
//!   C — a `LaunchOnly` profile refuses runtime injection without touching pane.
//!
//! Run: `cargo run -p ab-bridge --example ob3_injection_wettest`
//! (needs tmux on PATH; uses a throwaway session and kills it on exit).

use ab_bridge::remote_steer::{
    capture, has_session, injection_profile, launch, send, send_profiled, InjectionMode,
    InjectionProfile, Target, TmuxBackend,
};
use std::process::Command as StdCommand;
use std::time::Duration;

const SESSION: &str = "ab__ob3wettest__probe";

fn kill_session() {
    let _ = StdCommand::new("tmux")
        .args(["kill-session", "-t", SESSION])
        .status();
}

#[tokio::main]
async fn main() {
    let target = Target::local();
    let mux = TmuxBackend::default();
    let mut failures: Vec<String> = Vec::new();

    kill_session(); // clean slate

    // Controlled interactive bash: a submitted command prints output into the
    // pane; an unsubmitted one leaves only the typed line.
    let launched = launch(
        &target,
        &mux,
        SESSION,
        "bash --norc --noprofile -i",
        Some("/tmp"),
        &[],
    )
    .await
    .unwrap_or_else(|e| {
        eprintln!("launch error: {e}");
        false
    });
    if !launched || !has_session(&target, &mux, SESSION).await {
        eprintln!("FATAL: could not launch tmux probe session");
        kill_session();
        std::process::exit(2);
    }
    tokio::time::sleep(Duration::from_millis(700)).await; // let bash present a prompt

    // ── A: default send() submits with Enter ────────────────────────────────
    let _ = send(
        &target,
        &mux,
        SESSION,
        "printf 'RESULTA:%s\\n' OB3DEFAULT",
        true,
    )
    .await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    let cap_a = capture(&target, &mux, SESSION, 40).await.unwrap_or_default();
    if cap_a.contains("RESULTA:OB3DEFAULT") {
        println!("PASS A: default profile (Enter) submitted — executed output present");
    } else {
        failures.push("A: default Enter submit did not execute".into());
        println!("FAIL A: no 'RESULTA:OB3DEFAULT' in pane:\n{cap_a}");
    }

    // ── B: send_profiled non-Enter submit_key drives the split path ─────────
    // "C-m" is carriage-return (== Enter in bash) but != "Enter", so it routes
    // through the split branch (type literally, then send the key separately).
    let split = InjectionProfile {
        mode: InjectionMode::FlagInteractive,
        submit_key: "C-m".to_string(),
        needs_quiet_render: false,
        paste_safe: false,
    };
    let _ = send_profiled(
        &target,
        &mux,
        SESSION,
        "printf 'RESULTB:%s\\n' OB3SPLIT",
        true,
        &split,
    )
    .await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    let cap_b = capture(&target, &mux, SESSION, 40).await.unwrap_or_default();
    if cap_b.contains("RESULTB:OB3SPLIT") {
        println!(
            "PASS B: split path (type + separate '{}') submitted",
            split.submit_key
        );
    } else {
        failures.push("B: split submit path did not execute".into());
        println!("FAIL B: no 'RESULTB:OB3SPLIT' in pane:\n{cap_b}");
    }

    // ── C: LaunchOnly profile refuses runtime injection ─────────────────────
    let launch_only = InjectionProfile {
        mode: InjectionMode::LaunchOnly,
        ..InjectionProfile::default()
    };
    let res_c = send_profiled(
        &target,
        &mux,
        SESSION,
        "printf 'SHOULD_NOT_RUN\\n'",
        true,
        &launch_only,
    )
    .await;
    tokio::time::sleep(Duration::from_millis(300)).await;
    let after = capture(&target, &mux, SESSION, 40).await.unwrap_or_default();
    if res_c.is_err() && !after.contains("SHOULD_NOT_RUN") {
        println!(
            "PASS C: LaunchOnly refused runtime send ({})",
            res_c.unwrap_err()
        );
    } else {
        failures.push("C: LaunchOnly did not refuse / leaked injection".into());
        println!("FAIL C: res={res_c:?}; pane unexpectedly shows the marker");
    }

    // ── D: classifier honest pending-wet-test state ─────────────────────────
    if injection_profile("claude-code") == InjectionProfile::default() {
        println!("PASS D: injection_profile(claude-code) == default (honest pending-wet-test)");
    } else {
        failures.push("D: classifier diverged from default unexpectedly".into());
    }

    kill_session(); // teardown

    if failures.is_empty() {
        println!("\nOB-3 WET-TEST: ALL PASS");
    } else {
        println!("\nOB-3 WET-TEST: {} FAILURE(S):", failures.len());
        for f in &failures {
            println!("  - {f}");
        }
        std::process::exit(1);
    }
}
