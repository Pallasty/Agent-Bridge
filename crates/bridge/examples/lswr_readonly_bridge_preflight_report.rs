use ab_bridge::lswr_snapshot_wrapper_preflight_report::build_readonly_bridge_wrapper_preflight_report;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let report = build_readonly_bridge_wrapper_preflight_report();
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
