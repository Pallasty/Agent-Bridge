//! Exact named S21B role artifacts with an A8 non-live dry-run surface.
//!
//! These binaries expose deterministic identity and protocol-transition
//! surfaces. They do not read external payloads, inspect the host, launch a
//! runner, sign data, or expose a live adapter.

#![forbid(unsafe_code)]

use std::ffi::OsString;
use std::io::{self, Write};
use std::process::ExitCode;

pub const ROLE_ARTIFACT_FORMAT_ID: &str =
    "agent_bridge.memory_temporal_owned_lab_role_artifact_identity_s21b_a1.v0";
pub const ROLE_ARTIFACT_PACKET_KIND: &str = "S21B_A1_NON_LIVE_ROLE_ARTIFACT_IDENTITY";
pub const ROLE_ARTIFACT_MODE: &str = "NON_LIVE_IDENTITY_ONLY";
pub const ROLE_ARTIFACT_CANONICALIZATION: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S21B_A1_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
pub const ROLE_ARTIFACT_COUNT: usize = 4;

const UNSUPPORTED_COMMAND: &[u8] =
    b"S21B_A1_NON_LIVE_IDENTITY_ONLY: arguments and operational commands are forbidden\n";
const OUTPUT_FAILURE: &[u8] = b"S21B_A1_ROLE_IDENTITY_OUTPUT_FAILED\n";
const DRY_RUN_ARGUMENT: &str = "--dry-run-protocol-v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Role {
    Controller,
    Observer,
    Runner,
    Validator,
}

impl Role {
    pub const ALL: [Self; ROLE_ARTIFACT_COUNT] = [
        Self::Controller,
        Self::Observer,
        Self::Runner,
        Self::Validator,
    ];

    pub const fn binary_name(self) -> &'static str {
        match self {
            Self::Controller => "ab-owned-lab-controller",
            Self::Observer => "ab-owned-lab-observer",
            Self::Runner => "ab-owned-lab-runner",
            Self::Validator => "ab-owned-lab-validator",
        }
    }

    pub const fn role_name(self) -> &'static str {
        match self {
            Self::Controller => "controller",
            Self::Observer => "observer",
            Self::Runner => "runner",
            Self::Validator => "validator",
        }
    }

    /// Canonical, flat, sorted-key ASCII JSON. The terminal LF is emitted by
    /// [`write_identity`] and is not part of this value.
    pub const fn identity_json(self) -> &'static str {
        match self {
            Self::Controller => CONTROLLER_IDENTITY,
            Self::Observer => OBSERVER_IDENTITY,
            Self::Runner => RUNNER_IDENTITY,
            Self::Validator => VALIDATOR_IDENTITY,
        }
    }

    pub const fn dry_run_json(self) -> &'static str {
        match self {
            Self::Controller => CONTROLLER_DRY_RUN,
            Self::Observer => OBSERVER_DRY_RUN,
            Self::Runner => RUNNER_DRY_RUN,
            Self::Validator => VALIDATOR_DRY_RUN,
        }
    }
}

macro_rules! role_identity {
    ($binary_name:literal, $role_name:literal) => {
        concat!(
            "{\"arguments_accepted\":false,",
            "\"artifact_class\":\"DECLARED_CARGO_BINARY\",",
            "\"binary_name\":\"",
            $binary_name,
            "\",",
            "\"canonicalization\":\"AB_RESTRICTED_CANONICAL_JSON_S21B_A1_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT\",",
            "\"credential_access_present\":false,",
            "\"execution_capability_present\":false,",
            "\"external_payload_reader_present\":false,",
            "\"format_id\":\"agent_bridge.memory_temporal_owned_lab_role_artifact_identity_s21b_a1.v0\",",
            "\"implementation_mode\":\"NON_LIVE_IDENTITY_ONLY\",",
            "\"live_adapter_present\":false,",
            "\"network_access_present\":false,",
            "\"operational_role_implemented\":false,",
            "\"owner_authority_present\":false,",
            "\"package_version\":\"",
            env!("CARGO_PKG_VERSION"),
            "\",",
            "\"packet_kind\":\"S21B_A1_NON_LIVE_ROLE_ARTIFACT_IDENTITY\",",
            "\"private_key_access_present\":false,",
            "\"provider_or_production_authority\":false,",
            "\"role\":\"",
            $role_name,
            "\",",
            "\"side_effects_unlocked\":\"NONE\",",
            "\"signing_present\":false,",
            "\"synthetic\":false,",
            "\"test_only\":false}"
        )
    };
}

const CONTROLLER_IDENTITY: &str = role_identity!("ab-owned-lab-controller", "controller");
const OBSERVER_IDENTITY: &str = role_identity!("ab-owned-lab-observer", "observer");
const RUNNER_IDENTITY: &str = role_identity!("ab-owned-lab-runner", "runner");
const VALIDATOR_IDENTITY: &str = role_identity!("ab-owned-lab-validator", "validator");

macro_rules! role_dry_run {
    ($role:literal, $next:literal, $operation:literal, $state:literal) => {
        concat!(
            "{\"arguments_accepted\":true,",
            "\"credential_access_present\":false,",
            "\"execution_capability_present\":false,",
            "\"external_input_read\":false,",
            "\"format_id\":\"agent_bridge.memory_temporal_owned_lab_role_dry_run_s21b_a8.v0\",",
            "\"live_execution_permitted\":false,",
            "\"network_access_present\":false,",
            "\"next_role\":",
            $next,
            ",",
            "\"operation\":\"",
            $operation,
            "\",",
            "\"operational_mode\":\"NON_LIVE_PROTOCOL_DRY_RUN_ONLY\",",
            "\"role\":\"",
            $role,
            "\",",
            "\"side_effects_unlocked\":\"NONE\",",
            "\"state\":\"",
            $state,
            "\",",
            "\"test_only\":true}"
        )
    };
}

const CONTROLLER_DRY_RUN: &str = role_dry_run!(
    "controller",
    "\"observer\"",
    "VALIDATE_PLAN_SHAPE_WITHOUT_INPUT",
    "PLAN_SHAPE_READY_NO_INPUT"
);
const OBSERVER_DRY_RUN: &str = role_dry_run!(
    "observer",
    "\"runner\"",
    "DECLARE_OBSERVATION_SURFACE_WITHOUT_READING",
    "OBSERVATION_SURFACE_READY_NO_INPUT"
);
const RUNNER_DRY_RUN: &str = role_dry_run!(
    "runner",
    "\"validator\"",
    "SIMULATE_DISPATCH_WITHOUT_EXECUTION",
    "DISPATCH_SIMULATED_NO_EXECUTION"
);
const VALIDATOR_DRY_RUN: &str = role_dry_run!(
    "validator",
    "null",
    "DENY_ADMISSION_PENDING_REAL_EVIDENCE",
    "ADMISSION_DENIED_FAIL_CLOSED"
);

fn write_all(stream: &mut impl Write, bytes: &[u8]) -> io::Result<()> {
    stream.write_all(bytes)?;
    stream.flush()
}

pub fn write_identity(role: Role, stdout: &mut impl Write) -> io::Result<()> {
    write_all(stdout, role.identity_json().as_bytes())?;
    write_all(stdout, b"\n")
}

pub fn write_dry_run(role: Role, stdout: &mut impl Write) -> io::Result<()> {
    write_all(stdout, role.dry_run_json().as_bytes())?;
    write_all(stdout, b"\n")
}

pub fn run<I>(role: Role, arguments: I) -> ExitCode
where
    I: IntoIterator<Item = OsString>,
{
    let arguments: Vec<OsString> = arguments.into_iter().collect();
    if arguments.is_empty() {
        if write_identity(role, &mut io::stdout().lock()).is_err() {
            let _ = write_all(&mut io::stderr().lock(), OUTPUT_FAILURE);
            return ExitCode::from(74);
        }
        return ExitCode::SUCCESS;
    }
    if arguments.len() == 1 && arguments[0] == DRY_RUN_ARGUMENT {
        if write_dry_run(role, &mut io::stdout().lock()).is_err() {
            let _ = write_all(&mut io::stderr().lock(), OUTPUT_FAILURE);
            return ExitCode::from(74);
        }
        return ExitCode::SUCCESS;
    }
    {
        let _ = write_all(&mut io::stderr().lock(), UNSUPPORTED_COMMAND);
        return ExitCode::from(64);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    fn top_level_keys(value: &str) -> Vec<&str> {
        value[2..value.len() - 1]
            .split(",\"")
            .map(|field| field.split_once("\":").unwrap().0)
            .collect()
    }

    #[test]
    fn all_role_identities_are_ascii_flat_canonical_and_distinct() {
        let mut identities = BTreeSet::new();
        let mut binary_names = BTreeSet::new();
        for role in Role::ALL {
            let identity = role.identity_json();
            assert!(identity.is_ascii());
            assert!(identity.starts_with('{') && identity.ends_with('}'));
            assert!(!identity.contains(['\n', '\r', '\t']));
            assert!(identity.contains(&format!("\"binary_name\":\"{}\"", role.binary_name())));
            assert!(identity.contains(&format!("\"role\":\"{}\"", role.role_name())));
            assert!(identity.contains(&format!("\"format_id\":\"{ROLE_ARTIFACT_FORMAT_ID}\"")));
            assert!(identity.contains("\"implementation_mode\":\"NON_LIVE_IDENTITY_ONLY\""));
            assert!(identity.contains("\"operational_role_implemented\":false"));
            assert!(identity.contains(concat!(
                "\"package_version\":\"",
                env!("CARGO_PKG_VERSION"),
                "\""
            )));
            assert!(identity.contains("\"side_effects_unlocked\":\"NONE\""));
            assert!(!identity.contains(":true"));

            let keys = top_level_keys(identity);
            let mut sorted = keys.clone();
            sorted.sort_unstable();
            assert_eq!(keys, sorted);
            assert_eq!(keys.len(), 22);
            assert_eq!(
                keys.iter().copied().collect::<BTreeSet<_>>().len(),
                keys.len()
            );

            assert!(identities.insert(identity));
            assert!(binary_names.insert(role.binary_name()));
        }
        assert_eq!(identities.len(), ROLE_ARTIFACT_COUNT);
        assert_eq!(binary_names.len(), ROLE_ARTIFACT_COUNT);
    }

    #[test]
    fn identity_writer_adds_exactly_one_terminal_lf() {
        for role in Role::ALL {
            let mut output = Vec::new();
            write_identity(role, &mut output).unwrap();
            assert_eq!(output, format!("{}\n", role.identity_json()).as_bytes());
        }
    }

    #[test]
    fn dry_run_packets_are_canonical_distinct_and_fail_closed() {
        let mut packets = BTreeSet::new();
        for role in Role::ALL {
            let packet = role.dry_run_json();
            assert!(packet.is_ascii());
            assert!(packet.starts_with('{') && packet.ends_with('}'));
            assert!(!packet.contains(['\n', '\r', '\t']));
            assert!(packet.contains(&format!("\"role\":\"{}\"", role.role_name())));
            assert!(packet.contains("\"execution_capability_present\":false"));
            assert!(packet.contains("\"external_input_read\":false"));
            assert!(packet.contains("\"live_execution_permitted\":false"));
            assert!(packet.contains("\"network_access_present\":false"));
            assert!(packet.contains("\"side_effects_unlocked\":\"NONE\""));
            let keys = top_level_keys(packet);
            let mut sorted = keys.clone();
            sorted.sort_unstable();
            assert_eq!(keys, sorted);
            assert_eq!(keys.len(), 14);
            assert!(packets.insert(packet));
        }
        assert_eq!(packets.len(), ROLE_ARTIFACT_COUNT);
    }
}
