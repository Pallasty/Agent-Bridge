//! Cargo-run path for the standing continuity `U` report. The logic lives in
//! `ab_bridge::continuity`; prefer the shipped `agent-bridge continuity-report`
//! CLI subcommand (and the `/continuity` skill) for daily use. Read-only.
//!
//!   cargo run -p ab-bridge --example continuity_report --release
//!   cargo run -p ab-bridge --example continuity_report --release -- --json

use ab_store::default_db_path;
use std::path::PathBuf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let as_json = std::env::args().any(|a| a == "--json");
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let report = ab_bridge::continuity::build_report(&db_path).await?;
    if as_json {
        println!("{}", report.to_json());
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}
