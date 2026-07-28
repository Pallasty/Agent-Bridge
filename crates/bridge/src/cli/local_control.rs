use ab_bridge::a2ui;
use ab_bridge::operator_request::{OperatorDecision, OperatorRequestStore, OperatorRequestView};
use anyhow::{Context, Result};
use clap::Subcommand;
use serde_json::json;
use std::io::Read as _;

#[derive(Subcommand, Debug)]
pub(crate) enum OperatorRequestOp {
    /// List recent staged requests without changing them.
    List {
        #[arg(long, default_value_t = 20)]
        limit: usize,
        #[arg(long)]
        json: bool,
    },
    /// Show one exact request and any local decision evidence.
    Show {
        request_id: String,
        #[arg(long)]
        json: bool,
    },
    /// Record approval evidence for separate executor review.
    Approve {
        request_id: String,
        /// Human/operator identifier to record with the decision.
        #[arg(long)]
        operator: String,
        /// Why this exact request digest is approved for executor review.
        #[arg(long)]
        reason: String,
        #[arg(long)]
        json: bool,
    },
    /// Reject a pending request. Rejected requests cannot be revived.
    Reject {
        request_id: String,
        /// Human/operator identifier to record with the decision.
        #[arg(long)]
        operator: String,
        /// Why this exact request digest is rejected.
        #[arg(long)]
        reason: String,
        #[arg(long)]
        json: bool,
    },
}

#[derive(Subcommand, Debug)]
pub(crate) enum A2uiOp {
    /// Validate a JSON array, single message, or JSONL stream. Use `-` for stdin.
    Validate {
        /// Input path, or `-` to read stdin.
        input: String,
        /// Emit the complete machine-readable validation report.
        #[arg(long)]
        json: bool,
    },
}

pub(crate) fn run_a2ui(op: &A2uiOp) -> Result<()> {
    match op {
        A2uiOp::Validate { input, json } => {
            let raw = if input == "-" {
                let mut raw = String::new();
                std::io::stdin()
                    .read_to_string(&mut raw)
                    .context("read A2UI stream from stdin")?;
                raw
            } else {
                std::fs::read_to_string(input)
                    .with_context(|| format!("read A2UI stream {input}"))?
            };
            let report = a2ui::validate_stream(&raw);
            if *json {
                println!("{}", serde_json::to_string_pretty(&report)?);
            } else if report.valid {
                println!(
                    "A2UI {} valid: {} messages, {} surfaces, {} components, {} described actions; execution=false rendering=false",
                    report.protocol_version,
                    report.message_count,
                    report.surface_count,
                    report.component_count,
                    report.action_count
                );
            } else {
                eprintln!(
                    "A2UI {} invalid: {} error(s); execution=false rendering=false",
                    report.protocol_version,
                    report.errors.len()
                );
                for issue in &report.errors {
                    eprintln!("- {}: {}", issue.code, issue.message);
                }
            }
            if !report.valid {
                std::process::exit(2);
            }
            Ok(())
        }
    }
}

pub(crate) fn run_operator_request(op: &OperatorRequestOp) -> Result<()> {
    let store = OperatorRequestStore::default();
    match op {
        OperatorRequestOp::List { limit, json } => {
            let views = store.list(*limit)?;
            if *json {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&json!({
                        "schema": "agent_bridge.operator_request_list.v0",
                        "store": store.root(),
                        "requests": views,
                    }))?
                );
            } else if views.is_empty() {
                println!("No staged operator requests in {}.", store.root().display());
            } else {
                println!(
                    "{:<38}  {:<28}  {:<20}  DIGEST",
                    "REQUEST ID", "STATUS", "CAPABILITY"
                );
                for view in views {
                    println!(
                        "{:<38}  {:<28}  {:<20}  {}",
                        view.request.request_id,
                        view.status,
                        view.request.requested_capability.as_str(),
                        &view.request.request_digest[..12]
                    );
                }
            }
        }
        OperatorRequestOp::Show { request_id, json } => {
            print_operator_request_view(&store.get(request_id)?, *json)?;
        }
        OperatorRequestOp::Approve {
            request_id,
            operator,
            reason,
            json,
        } => {
            let view = store.decide(request_id, OperatorDecision::Approve, operator, reason)?;
            print_operator_request_view(&view, *json)?;
        }
        OperatorRequestOp::Reject {
            request_id,
            operator,
            reason,
            json,
        } => {
            let view = store.decide(request_id, OperatorDecision::Reject, operator, reason)?;
            print_operator_request_view(&view, *json)?;
        }
    }
    Ok(())
}

fn print_operator_request_view(view: &OperatorRequestView, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(view)?);
        return Ok(());
    }
    println!("Request: {}", view.request.request_id);
    println!("Status: {}", view.status);
    println!("Digest: {}", view.request.request_digest);
    println!("Capability: {}", view.request.requested_capability.as_str());
    println!("Target: {}", view.request.target);
    println!("Channel: {}", view.request.channel_id);
    println!("Identity strength: {}", view.request.identity_strength);
    println!("Created: {}", view.request.created_at);
    println!("Expires: {}", view.request.expires_at);
    println!("Execution allowed: {}", view.execution_allowed);
    println!(
        "Canonical write performed: {}",
        view.request.canonical_write_performed
    );
    if let Some(decision) = &view.decision {
        println!("Decision: {}", decision.decision.as_str());
        println!("Operator: {}", decision.operator_id);
        println!("Reason: {}", decision.reason);
        println!("Approval scope: {}", decision.approval_scope);
        println!(
            "Separate executor gate required: {}",
            decision.requires_separate_executor_gate
        );
    }
    println!("Next step: {}", view.next_step);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{A2uiOp, OperatorRequestOp};
    use clap::Parser;

    #[derive(Debug, Parser)]
    struct A2uiCli {
        #[command(subcommand)]
        op: A2uiOp,
    }

    #[derive(Debug, Parser)]
    struct OperatorRequestCli {
        #[command(subcommand)]
        op: OperatorRequestOp,
    }

    #[test]
    fn a2ui_schema_preserves_validate_spelling_and_json_flag() {
        let parsed = A2uiCli::try_parse_from(["a2ui", "validate", "fixture.jsonl", "--json"])
            .expect("a2ui validate schema should parse");

        assert!(matches!(
            parsed.op,
            A2uiOp::Validate {
                input,
                json: true
            } if input == "fixture.jsonl"
        ));
    }

    #[test]
    fn operator_request_schema_preserves_approval_arguments() {
        let parsed = OperatorRequestCli::try_parse_from([
            "operator-request",
            "approve",
            "request-1",
            "--operator",
            "owner",
            "--reason",
            "reviewed",
            "--json",
        ])
        .expect("operator-request approve schema should parse");

        assert!(matches!(
            parsed.op,
            OperatorRequestOp::Approve {
                request_id,
                operator,
                reason,
                json: true,
            } if request_id == "request-1" && operator == "owner" && reason == "reviewed"
        ));
    }
}
