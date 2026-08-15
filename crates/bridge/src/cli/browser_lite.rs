use ab_bridge::browser_lite as browser_lite_impl;
use clap::{Subcommand, ValueEnum};
use std::path::PathBuf;

#[derive(Subcommand, Debug)]
pub(crate) enum BrowserLiteOp {
    /// Probe an optional browser-lite backend and print a capability report.
    Probe {
        /// Backend to probe. Defaults to obscura.
        #[arg(value_enum, default_value = "obscura")]
        backend: BrowserLiteBackend,
        /// Override backend binary path. Otherwise uses AGENT_BRIDGE_OBSCURA_BIN, then PATH.
        #[arg(long)]
        bin: Option<PathBuf>,
        /// Probe MCP tools/list in addition to `--help`.
        ///
        /// Enabled by default because tool count is part of the provenance
        /// evidence for external browser-lite routing decisions.
        #[arg(long = "no-mcp-tools", default_value_t = false)]
        no_mcp_tools: bool,
        /// Per-probe timeout for backend commands.
        #[arg(long, default_value_t = 5_000)]
        timeout_ms: u64,
        /// Emit raw JSON payload instead of a command line summary.
        #[arg(long)]
        json: bool,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub(crate) enum BrowserLiteBackend {
    Obscura,
}

pub(crate) fn run_browser_lite(op: &BrowserLiteOp) -> anyhow::Result<()> {
    match op {
        BrowserLiteOp::Probe {
            backend: BrowserLiteBackend::Obscura,
            bin,
            no_mcp_tools,
            timeout_ms,
            json,
        } => browser_lite_impl::run_obscura_probe(browser_lite_impl::ObscuraProbeOptions {
            bin: bin.clone(),
            timeout_ms: *timeout_ms,
            probe_mcp_tools: !*no_mcp_tools,
            json: *json,
        }),
    }
}
