//! Read-only EAP-1C observations for a bounded Linux avatar trial.
//!
//! These counters describe sidecar polling and this process. They do not prove
//! compositor pixels, physical display output, or audible sound.

use serde_json::{json, Value};
use std::time::Duration;

const MAX_TRANSITION_SAMPLES: usize = 32;

#[derive(Debug)]
pub struct LiveObservation {
    initial_mode: String,
    current_mode: String,
    poll_count: u64,
    read_failures: u64,
    transition_count: u64,
    eligible_transition_count: u64,
    max_poll_gap_ms: u64,
    last_poll_elapsed_ms: Option<u64>,
    peak_process_rss_bytes: Option<u64>,
    transitions: Vec<Value>,
    transitions_truncated: bool,
}

impl LiveObservation {
    pub fn new(initial_mode: impl Into<String>) -> Self {
        let initial_mode = initial_mode.into();
        Self {
            current_mode: initial_mode.clone(),
            initial_mode,
            poll_count: 0,
            read_failures: 0,
            transition_count: 0,
            eligible_transition_count: 0,
            max_poll_gap_ms: 0,
            last_poll_elapsed_ms: None,
            peak_process_rss_bytes: current_process_rss_bytes(),
            transitions: Vec::new(),
            transitions_truncated: false,
        }
    }

    pub fn observe(&mut self, mode: &str, elapsed: Duration) {
        let elapsed_ms = elapsed.as_millis().min(u64::MAX as u128) as u64;
        self.poll_count += 1;
        if let Some(previous) = self.last_poll_elapsed_ms {
            self.max_poll_gap_ms = self
                .max_poll_gap_ms
                .max(elapsed_ms.saturating_sub(previous));
        }
        self.last_poll_elapsed_ms = Some(elapsed_ms);
        if let Some(rss) = current_process_rss_bytes() {
            self.peak_process_rss_bytes = Some(self.peak_process_rss_bytes.unwrap_or(0).max(rss));
        }
        if mode == self.current_mode {
            return;
        }
        self.transition_count += 1;
        if crate::avatar_live_voice::allowed_mode(mode) {
            self.eligible_transition_count += 1;
        }
        if self.transitions.len() < MAX_TRANSITION_SAMPLES {
            self.transitions.push(json!({
                "sequence": self.transition_count,
                "from": self.current_mode,
                "to": mode,
                "observed_elapsed_ms": elapsed_ms,
                "voice_eligible_mode": crate::avatar_live_voice::allowed_mode(mode),
            }));
        } else {
            self.transitions_truncated = true;
        }
        self.current_mode = mode.to_string();
    }

    pub fn record_read_failure(&mut self, elapsed: Duration) {
        self.read_failures += 1;
        self.observe(&self.current_mode.clone(), elapsed);
    }

    pub fn receipt(&self, configured_poll_ms: u64, elapsed: Duration) -> Value {
        json!({
            "surface": "linux_avatar_live_observation",
            "schema": 1,
            "read_only": true,
            "elapsed_ms": elapsed.as_millis().min(u64::MAX as u128) as u64,
            "sidecar": {
                "configured_poll_ms": configured_poll_ms,
                "poll_count": self.poll_count,
                "read_failures": self.read_failures,
                "transition_count": self.transition_count,
                "eligible_transition_count": self.eligible_transition_count,
                "initial_mode": self.initial_mode,
                "final_mode": self.current_mode,
                "max_observed_poll_gap_ms": self.max_poll_gap_ms,
                "transition_samples": self.transitions,
                "transition_samples_truncated": self.transitions_truncated,
            },
            "resources": {
                "process_peak_rss_bytes": self.peak_process_rss_bytes,
                "worker_vram_bytes": Value::Null,
                "worker_vram_observed": false,
            },
            "claims": {
                "sidecar_polling_observed": self.poll_count > 0,
                "sidecar_transitions_observed": self.transition_count > 0,
                "compositor_pixels_observed": false,
                "physical_display_observed": false,
                "physical_audio_observed": false,
            },
        })
    }
}

#[cfg(target_os = "linux")]
fn current_process_rss_bytes() -> Option<u64> {
    let status = std::fs::read_to_string("/proc/self/status").ok()?;
    let kib = status
        .lines()
        .find_map(|line| line.strip_prefix("VmHWM:"))?
        .split_whitespace()
        .next()?
        .parse::<u64>()
        .ok()?;
    kib.checked_mul(1024)
}

#[cfg(not(target_os = "linux"))]
fn current_process_rss_bytes() -> Option<u64> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observation_counts_transitions_without_claiming_pixels_or_audio() {
        let mut observation = LiveObservation::new("idle");
        observation.observe("idle", Duration::from_millis(100));
        observation.observe("working", Duration::from_millis(230));
        observation.observe("verified", Duration::from_millis(410));
        let receipt = observation.receipt(100, Duration::from_millis(500));
        assert_eq!(receipt["sidecar"]["poll_count"], 3);
        assert_eq!(receipt["sidecar"]["transition_count"], 2);
        assert_eq!(receipt["sidecar"]["eligible_transition_count"], 1);
        assert_eq!(receipt["sidecar"]["max_observed_poll_gap_ms"], 180);
        assert_eq!(receipt["claims"]["compositor_pixels_observed"], false);
        assert_eq!(receipt["claims"]["physical_audio_observed"], false);
    }

    #[test]
    fn failures_are_counted_as_polls_without_inventing_a_transition() {
        let mut observation = LiveObservation::new("working");
        observation.record_read_failure(Duration::from_millis(120));
        let receipt = observation.receipt(100, Duration::from_millis(150));
        assert_eq!(receipt["sidecar"]["poll_count"], 1);
        assert_eq!(receipt["sidecar"]["read_failures"], 1);
        assert_eq!(receipt["sidecar"]["transition_count"], 0);
    }
}
