use ab_bridge::mobile_projection::{
    ProjectionEvent, ProjectionFrame, ProjectionSession, MAX_SESSION_SECONDS,
};
use anyhow::{bail, Context, Result};
use clap::Parser;
use std::net::IpAddr;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[derive(Debug, Parser)]
#[command(about = "Serve one short-lived, read-only mobile projection session")]
struct Args {
    #[arg(long)]
    bind: IpAddr,
    #[arg(long, default_value_t = 17322)]
    port: u16,
    #[arg(long)]
    session: String,
    #[arg(long, default_value_t = 300, value_parser = clap::value_parser!(i64).range(1..=600))]
    ttl_seconds: i64,
    #[arg(long)]
    title: String,
    #[arg(long)]
    body: String,
}

fn main() -> Result<()> {
    let args = Args::parse();
    if args.ttl_seconds > MAX_SESSION_SECONDS {
        bail!("session exceeds maximum lifetime");
    }
    let token = std::env::var("AGENT_BRIDGE_MOBILE_PROJECTION_TOKEN")
        .context("set AGENT_BRIDGE_MOBILE_PROJECTION_TOKEN to 64 lowercase hex characters")?;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .context("system clock before Unix epoch")?
        .as_secs() as i64;
    let expires = now + args.ttl_seconds;
    let session = ProjectionSession::bind(args.bind, args.port, &token, &args.session, expires)?;
    let frame = ProjectionFrame::new(&args.session, 1, expires, &args.title, &args.body)?;
    println!(
        "endpoint={} session={} expires_at={expires}",
        session.local_addr()?,
        args.session
    );
    while (SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs() as i64) < expires {
        match session.serve_next(&frame, Duration::from_secs(1)) {
            Ok(Some(ProjectionEvent::FramePulled { peer })) => {
                eprintln!("served read-only frame to {peer}")
            }
            Ok(Some(ProjectionEvent::TextSubmitted { peer, observation })) => eprintln!(
                "accepted ephemeral text observation from {peer} digest={} chars={}",
                observation.payload_sha256,
                observation.text.chars().count()
            ),
            Ok(None) => {}
            Err(error) => eprintln!("rejected projection pull: {error:#}"),
        }
    }
    Ok(())
}
