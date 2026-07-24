//! R31-only redacted phase checkpoints for the disposable C2C live lab.
//!
//! This module is compiled only with the separately opted-in live-lab feature.
//! It writes no memory, Keychain material, request data, or arbitrary error
//! text: callers may record only one of the fixed labels below to a driver-made
//! temporary file.

use std::fs::OpenOptions;
use std::io::Write;

const PHASE_PATH_ENV: &str = "AGENT_BRIDGE_C2C_LIVE_LAB_PHASE_PATH";

pub(crate) fn mark(label: &'static str) {
    if !matches!(
        label,
        "curate_entered"
            | "candidates_ready"
            | "observation_begin_enter"
            | "observation_begin_done"
            | "core_save_enter"
            | "core_save_done"
            | "observation_item_enter"
            | "observation_item_done"
            | "item_derivation_enter"
            | "item_derivation_done"
            | "item_append_enter"
            | "item_append_done"
            | "observation_finish_enter"
            | "observation_finish_done"
            | "curate_response_ready"
    ) {
        return;
    }
    let Some(path) = std::env::var_os(PHASE_PATH_ENV) else {
        return;
    };
    let Ok(mut file) = OpenOptions::new().append(true).open(path) else {
        return;
    };
    let _ = writeln!(file, "{label}");
}
