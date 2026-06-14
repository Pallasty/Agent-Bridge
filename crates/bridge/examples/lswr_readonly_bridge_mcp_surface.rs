use ab_bridge::mcp_tools::lswr_readonly_bridge_display_mcp_surface_report;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let report = lswr_readonly_bridge_display_mcp_surface_report();
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
