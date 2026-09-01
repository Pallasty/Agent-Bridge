use std::path::PathBuf;

use ab_bridge::invocation_guardian_service::{GuardianService, VolatileLabConfig};
use anyhow::{bail, Context, Result};
use clap::Parser;

#[derive(Debug, Parser)]
#[command(
    name = "invocation-guardian",
    about = "Non-authoritative invocation guardian lab candidate"
)]
struct Args {
    /// Explicitly run the volatile, rollbackable, non-authoritative lab witness.
    #[arg(long)]
    volatile_lab: bool,

    /// Permit guardian and configured client to share a UID in volatile lab mode.
    #[arg(long, requires = "volatile_lab")]
    allow_same_uid_lab: bool,

    /// Absolute socket path inside a guardian-owned protected directory.
    #[arg(long, requires = "volatile_lab")]
    socket: Option<PathBuf>,

    /// Only this kernel peer UID is admitted by the lab service.
    #[arg(long, requires = "volatile_lab")]
    expected_client_uid: Option<u32>,

    /// Dedicated non-root group inherited from the pre-created setgid parent.
    #[arg(long, requires = "volatile_lab")]
    socket_gid: Option<u32>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    if !args.volatile_lab {
        bail!(
            "HOLD: no production monotonic invocation witness is available; \
             use --volatile-lab only for non-authoritative testing"
        );
    }
    let socket = args
        .socket
        .context("--socket is required with --volatile-lab")?;
    let expected_client_uid = args
        .expected_client_uid
        .context("--expected-client-uid is required with --volatile-lab")?;
    let expected_socket_gid = args
        .socket_gid
        .context("--socket-gid is required with --volatile-lab")?;
    let service = GuardianService::volatile_lab(VolatileLabConfig {
        expected_client_uid,
        expected_socket_gid,
        allow_same_uid_lab: args.allow_same_uid_lab,
    })?;
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();
    service.serve(&socket).await?;
    Ok(())
}
