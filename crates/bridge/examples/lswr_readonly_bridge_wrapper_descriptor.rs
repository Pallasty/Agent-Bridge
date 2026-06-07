use ab_bridge::lswr_snapshot_wrapper_descriptor::build_readonly_bridge_wrapper_descriptor;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    println!("{}", serde_json::to_string_pretty(&descriptor)?);
    Ok(())
}
