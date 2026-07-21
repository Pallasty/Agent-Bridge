//! Default-off, hash-pinned WASI component host for the G1.4 typed-report proof.
//!
//! This is deliberately a narrow runtime seam, not a general plugin system:
//! the caller supplies an artifact path and its expected SHA-256, and the host
//! registers only WASI clocks/io. No filesystem, network, stdio, or MCP tool
//! surface is granted to the component.

use anyhow::{anyhow, bail, Context, Result};
use sha2::{Digest, Sha256};
use std::path::Path;
use wasmtime::component::{Component, Linker, Val};
use wasmtime::{Config, Engine, Store};
use wasmtime_wasi::{ResourceTable, WasiCtx, WasiCtxView, WasiView};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TypedReport {
    pub wall_epoch_seconds: u64,
    pub logical_nanoseconds: u64,
    pub quantum_nanoseconds: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BusinessReport {
    pub revision: u64,
    pub entity_count: u32,
    pub occupied_cells: u32,
    pub transition_count: u32,
    pub occupancy_per_mille: u32,
    pub report_code: String,
}

struct HostState {
    table: ResourceTable,
    wasi: WasiCtx,
}

impl WasiView for HostState {
    fn ctx(&mut self) -> WasiCtxView<'_> {
        WasiCtxView {
            ctx: &mut self.wasi,
            table: &mut self.table,
        }
    }
}

pub struct G14ComponentRuntime {
    engine: Engine,
}

impl G14ComponentRuntime {
    pub fn new() -> Result<Self> {
        let mut config = Config::new();
        config.wasm_component_model(true);
        Ok(Self {
            engine: Engine::new(&config)?,
        })
    }

    pub fn execute_typed_report(
        &self,
        artifact: impl AsRef<Path>,
        expected_sha256: &str,
    ) -> Result<TypedReport> {
        let artifact = artifact.as_ref();
        let bytes = std::fs::read(artifact)
            .with_context(|| format!("read component {}", artifact.display()))?;
        let actual = hex_sha256(&bytes);
        if !constant_time_hex_eq(&actual, expected_sha256) {
            bail!(
                "component SHA-256 mismatch: expected {}, actual {}",
                expected_sha256,
                actual
            );
        }

        let component = Component::new(&self.engine, &bytes)
            .map_err(|error| anyhow!("parse component {}: {error}", artifact.display()))?;
        let mut linker = Linker::<HostState>::new(&self.engine);
        wasmtime_wasi::p2::add_to_linker_sync(&mut linker)
            .map_err(|error| anyhow!("register WASI preview-2 host interfaces: {error}"))?;
        let wasi = wasmtime_wasi::WasiCtxBuilder::new().build();
        let mut store = Store::new(
            &self.engine,
            HostState {
                table: ResourceTable::new(),
                wasi,
            },
        );
        let instance = linker
            .instantiate(&mut store, &component)
            .map_err(|error| anyhow!("instantiate G1.4 component: {error}"))?;
        let func = instance
            .get_func(&mut store, "typed-report")
            .ok_or_else(|| anyhow!("component has no typed-report export"))?;
        let mut results = [Val::Record(Vec::new())];
        func.call(&mut store, &[], &mut results)
            .map_err(|error| anyhow!("invoke typed-report: {error}"))?;
        parse_typed_report(results.into_iter().next().expect("one result"))
    }

    pub fn execute_business_transform(
        &self,
        artifact: impl AsRef<Path>,
        expected_sha256: &str,
        revision: u64,
        entity_count: u32,
        occupied_cells: u32,
        transition_count: u32,
    ) -> Result<BusinessReport> {
        if entity_count > 100_000 {
            bail!("business input out of bounds: entity-count > 100000");
        }
        if occupied_cells > 100_000 {
            bail!("business input out of bounds: occupied-cells > 100000");
        }
        if transition_count > 1_000_000 {
            bail!("business input out of bounds: transition-count > 1000000");
        }
        let artifact = artifact.as_ref();
        let bytes = std::fs::read(artifact)
            .with_context(|| format!("read component {}", artifact.display()))?;
        let actual = hex_sha256(&bytes);
        if !constant_time_hex_eq(&actual, expected_sha256) {
            bail!(
                "component SHA-256 mismatch: expected {}, actual {}",
                expected_sha256,
                actual
            );
        }

        let component = Component::new(&self.engine, &bytes)
            .map_err(|error| anyhow!("parse component {}: {error}", artifact.display()))?;
        let mut linker = Linker::<HostState>::new(&self.engine);
        wasmtime_wasi::p2::add_to_linker_sync(&mut linker)
            .map_err(|error| anyhow!("register WASI preview-2 host interfaces: {error}"))?;
        let wasi = wasmtime_wasi::WasiCtxBuilder::new().build();
        let mut store = Store::new(
            &self.engine,
            HostState {
                table: ResourceTable::new(),
                wasi,
            },
        );
        let instance = linker
            .instantiate(&mut store, &component)
            .map_err(|error| anyhow!("instantiate business component: {error}"))?;
        let func = instance
            .get_func(&mut store, "evaluate")
            .ok_or_else(|| anyhow!("component has no evaluate export"))?;
        let input = Val::Record(vec![
            ("revision".into(), Val::U64(revision)),
            ("entity-count".into(), Val::U32(entity_count)),
            ("occupied-cells".into(), Val::U32(occupied_cells)),
            ("transition-count".into(), Val::U32(transition_count)),
        ]);
        let mut results = [Val::Record(Vec::new())];
        func.call(&mut store, &[input], &mut results)
            .map_err(|error| anyhow!("invoke business evaluate: {error}"))?;
        parse_business_report(results.into_iter().next().expect("one result"))
    }
}

fn parse_typed_report(value: Val) -> Result<TypedReport> {
    let Val::Record(fields) = value else {
        bail!("typed-report result is not a record");
    };
    let mut wall = None;
    let mut logical = None;
    let mut quantum = None;
    for (name, value) in fields {
        let Val::U64(value) = value else {
            bail!("typed-report field {name} is not u64");
        };
        match name.as_str() {
            "wall-epoch-seconds" if wall.is_none() => wall = Some(value),
            "logical-nanoseconds" if logical.is_none() => logical = Some(value),
            "quantum-nanoseconds" if quantum.is_none() => quantum = Some(value),
            _ => bail!("unexpected or duplicate typed-report field {name}"),
        }
    }
    Ok(TypedReport {
        wall_epoch_seconds: wall.ok_or_else(|| anyhow!("missing wall-epoch-seconds"))?,
        logical_nanoseconds: logical.ok_or_else(|| anyhow!("missing logical-nanoseconds"))?,
        quantum_nanoseconds: quantum.ok_or_else(|| anyhow!("missing quantum-nanoseconds"))?,
    })
}

fn parse_business_report(value: Val) -> Result<BusinessReport> {
    let Val::Record(fields) = value else {
        bail!("business report result is not a record");
    };
    let mut revision = None;
    let mut entity_count = None;
    let mut occupied_cells = None;
    let mut transition_count = None;
    let mut occupancy_per_mille = None;
    let mut report_code = None;
    for (name, value) in fields {
        match (name.as_str(), value) {
            ("revision", Val::U64(value)) if revision.is_none() => revision = Some(value),
            ("entity-count", Val::U32(value)) if entity_count.is_none() => {
                entity_count = Some(value)
            }
            ("occupied-cells", Val::U32(value)) if occupied_cells.is_none() => {
                occupied_cells = Some(value)
            }
            ("transition-count", Val::U32(value)) if transition_count.is_none() => {
                transition_count = Some(value)
            }
            ("occupancy-per-mille", Val::U32(value)) if occupancy_per_mille.is_none() => {
                occupancy_per_mille = Some(value)
            }
            ("report-code", Val::String(value)) if report_code.is_none() => {
                report_code = Some(value)
            }
            (name, _) => bail!("unexpected, duplicate, or mistyped business report field {name}"),
        }
    }
    Ok(BusinessReport {
        revision: revision.ok_or_else(|| anyhow!("missing revision"))?,
        entity_count: entity_count.ok_or_else(|| anyhow!("missing entity-count"))?,
        occupied_cells: occupied_cells.ok_or_else(|| anyhow!("missing occupied-cells"))?,
        transition_count: transition_count.ok_or_else(|| anyhow!("missing transition-count"))?,
        occupancy_per_mille: occupancy_per_mille
            .ok_or_else(|| anyhow!("missing occupancy-per-mille"))?,
        report_code: report_code.ok_or_else(|| anyhow!("missing report-code"))?,
    })
}

fn hex_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn constant_time_hex_eq(actual: &str, expected: &str) -> bool {
    actual.len() == expected.len()
        && actual
            .bytes()
            .zip(expected.bytes())
            .fold(0u8, |diff, (a, b)| diff | (a ^ b))
            == 0
}

#[cfg(test)]
mod tests {
    use super::{
        constant_time_hex_eq, parse_business_report, parse_typed_report, BusinessReport,
        TypedReport,
    };
    use wasmtime::component::Val;

    #[test]
    fn parses_canonical_typed_report() {
        let value = Val::Record(vec![
            ("wall-epoch-seconds".into(), Val::U64(946_684_800)),
            ("logical-nanoseconds".into(), Val::U64(0)),
            ("quantum-nanoseconds".into(), Val::U64(1_000_000)),
        ]);
        assert_eq!(
            parse_typed_report(value).unwrap(),
            TypedReport {
                wall_epoch_seconds: 946_684_800,
                logical_nanoseconds: 0,
                quantum_nanoseconds: 1_000_000,
            }
        );
    }

    #[test]
    fn hash_comparison_is_exact_and_case_sensitive() {
        assert!(constant_time_hex_eq("00ff", "00ff"));
        assert!(!constant_time_hex_eq("00ff", "00FF"));
        assert!(!constant_time_hex_eq("00ff", "00ff00"));
    }

    #[test]
    fn parses_canonical_business_report() {
        let value = Val::Record(vec![
            ("revision".into(), Val::U64(7)),
            ("entity-count".into(), Val::U32(12)),
            ("occupied-cells".into(), Val::U32(9)),
            ("transition-count".into(), Val::U32(4)),
            ("occupancy-per-mille".into(), Val::U32(750)),
            ("report-code".into(), Val::String("WORLD_STATE_V0".into())),
        ]);
        assert_eq!(
            parse_business_report(value).unwrap(),
            BusinessReport {
                revision: 7,
                entity_count: 12,
                occupied_cells: 9,
                transition_count: 4,
                occupancy_per_mille: 750,
                report_code: "WORLD_STATE_V0".into(),
            }
        );
    }
}
