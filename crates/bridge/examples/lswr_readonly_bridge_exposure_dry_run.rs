use ab_bridge::lswr_snapshot_wrapper_exposure_dry_run::build_readonly_bridge_wrapper_exposure_dry_run;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let dry_run = build_readonly_bridge_wrapper_exposure_dry_run();
    println!("{}", serde_json::to_string_pretty(&dry_run)?);
    Ok(())
}
