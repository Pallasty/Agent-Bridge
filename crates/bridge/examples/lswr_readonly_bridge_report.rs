use ab_bridge::lswr_snapshot_bridge::build_readonly_bridge_snapshot;
use ab_bridge::lswr_snapshot_consumer::{
    build_readonly_bridge_consumer_summary, default_consumer_projection_options,
};
use ab_bridge::lswr_snapshot_report::render_readonly_bridge_report;
use ab_world_core::WorldLedgerSnapshot;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse(env::args().skip(1))?;
    let snapshot_json = fs::read_to_string(&args.snapshot_path)?;
    let snapshot: WorldLedgerSnapshot = serde_json::from_str(&snapshot_json)?;
    let projection =
        build_readonly_bridge_snapshot(snapshot, default_consumer_projection_options())?;
    let summary = build_readonly_bridge_consumer_summary(&projection);

    print!("{}", render_readonly_bridge_report(&summary));
    Ok(())
}

struct Args {
    snapshot_path: PathBuf,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut snapshot_path = None;

        for arg in raw_args {
            match arg.as_str() {
                "--help" | "-h" => return Err(usage()),
                _ if arg.starts_with('-') => {
                    return Err(format!("unknown option: {arg}\n\n{}", usage()));
                }
                _ if snapshot_path.is_none() => snapshot_path = Some(PathBuf::from(arg)),
                _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
            }
        }

        let snapshot_path = snapshot_path.ok_or_else(usage)?;
        Ok(Self { snapshot_path })
    }
}

fn usage() -> String {
    "usage: cargo run -p ab-bridge --example lswr_readonly_bridge_report -- <ledger-snapshot.json>"
        .to_string()
}
