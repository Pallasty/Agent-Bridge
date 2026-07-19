//! G2E public synthetic component source. This file is deliberately source-only:
//! no manifest, generated bindings, binary, build, or execution exists in G2E.

#![forbid(unsafe_code)]

pub const G2E_COMPONENT_SOURCE_ONLY_NOT_BUILT: &str =
    "agent-bridge:g14-clock-probe/probe@0.1.0";
pub const WALL_EPOCH_SECONDS: u64 = 946_684_800;
pub const QUANTUM_NANOSECONDS: u64 = 1_000_000;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TypedReport {
    pub wall_epoch_seconds: u64,
    pub logical_nanoseconds: u64,
    pub quantum_nanoseconds: u64,
}

/// The future generated WIT export is intentionally represented as plain,
/// public source until a separately authorized build gate selects bindings.
pub fn typed_report(logical_nanoseconds: u64) -> TypedReport {
    TypedReport {
        wall_epoch_seconds: WALL_EPOCH_SECONDS,
        logical_nanoseconds,
        quantum_nanoseconds: QUANTUM_NANOSECONDS,
    }
}
