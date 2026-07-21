//! G2G compiles the exact reviewed G2E logical-clock host, without running it.

#[path = "../../engram_g14_wasi_g2e_public_source_v0/host/src/lib.rs"]
pub mod logical_clock_host;

pub use logical_clock_host::*;
