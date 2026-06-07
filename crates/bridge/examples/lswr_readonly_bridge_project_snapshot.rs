use ab_bridge::lswr_snapshot_bridge::{
    build_readonly_bridge_snapshot, ReadOnlyBridgeSnapshotOptions,
};
use ab_world_core::WorldLedgerSnapshot;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse(env::args().skip(1))?;
    let snapshot_json = fs::read_to_string(&args.snapshot_path)?;
    let snapshot: WorldLedgerSnapshot = serde_json::from_str(&snapshot_json)?;
    let projection = build_readonly_bridge_snapshot(
        snapshot,
        ReadOnlyBridgeSnapshotOptions {
            include_snapshot: args.include_snapshot,
        },
    )?;

    println!("{}", serde_json::to_string_pretty(&projection)?);
    Ok(())
}

struct Args {
    snapshot_path: PathBuf,
    include_snapshot: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut snapshot_path = None;
        let mut include_snapshot = false;

        for arg in raw_args {
            match arg.as_str() {
                "--include-snapshot" => include_snapshot = true,
                "--help" | "-h" => return Err(usage()),
                _ if arg.starts_with('-') => {
                    return Err(format!("unknown option: {arg}\n\n{}", usage()))
                }
                _ if snapshot_path.is_none() => snapshot_path = Some(PathBuf::from(arg)),
                _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
            }
        }

        let snapshot_path = snapshot_path.ok_or_else(usage)?;
        Ok(Self {
            snapshot_path,
            include_snapshot,
        })
    }
}

fn usage() -> String {
    "usage: cargo run -p ab-bridge --example lswr_readonly_bridge_project_snapshot -- <ledger-snapshot.json> [--include-snapshot]".to_string()
}
