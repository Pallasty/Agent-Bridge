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
    use super::{constant_time_hex_eq, parse_typed_report, TypedReport};
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
}
