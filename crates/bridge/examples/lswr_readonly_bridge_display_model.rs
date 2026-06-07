use ab_bridge::lswr_snapshot_display::build_readonly_bridge_display_model_from_packet;
use ab_bridge::lswr_snapshot_report_packet::ReadOnlyBridgeReportPacket;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse(env::args().skip(1))?;
    let packet_json = fs::read_to_string(&args.packet_path)?;
    let packet: ReadOnlyBridgeReportPacket = serde_json::from_str(&packet_json)?;
    let display_model = build_readonly_bridge_display_model_from_packet(&packet);

    println!("{}", serde_json::to_string_pretty(&display_model)?);
    Ok(())
}

struct Args {
    packet_path: PathBuf,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut packet_path = None;

        for arg in raw_args {
            match arg.as_str() {
                "--help" | "-h" => return Err(usage()),
                _ if arg.starts_with('-') => {
                    return Err(format!("unknown option: {arg}\n\n{}", usage()));
                }
                _ if packet_path.is_none() => packet_path = Some(PathBuf::from(arg)),
                _ => return Err(format!("unexpected argument: {arg}\n\n{}", usage())),
            }
        }

        let packet_path = packet_path.ok_or_else(usage)?;
        Ok(Self { packet_path })
    }
}

fn usage() -> String {
    "usage: cargo run -p ab-bridge --example lswr_readonly_bridge_display_model -- <report-packet.json>"
        .to_string()
}
