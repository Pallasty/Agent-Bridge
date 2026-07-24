//! R27 fixture driver for the separately-built R25 MCP process.
//!
//! It is not a production command and refuses to perform any Keychain or
//! process action unless the explicit R26 execution flag is supplied.  Normal
//! builds do not contain this binary (`required-features` in Cargo.toml).

use ab_store::episode_observation_c2c_keychain_macos_c2c_live_lab::C2cLiveLabCustody;
use clap::Parser;
use serde_json::{json, Value};
use std::io::{BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};

const LIVE_ACK: &str = "r26-c2c-live-authorized";

#[derive(Parser, Debug)]
#[command(about = "default-off R26 disposable C2C Keychain/MCP fixture")]
struct Args {
    /// Separately built agent-bridge executable. Never defaults to PATH.
    #[arg(long)]
    agent_bridge: Option<PathBuf>,
    /// Required one-time acknowledgement for the separately authorized R26 run.
    #[arg(long)]
    execute_r26_live: Option<String>,
}

fn source_only_refusal(args: &Args) -> bool {
    args.execute_r26_live.as_deref() != Some(LIVE_ACK) || args.agent_bridge.is_none()
}

fn rpc_payload() -> String {
    [
        json!({
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "episode-observation-c2c-live-lab", "version": "r27"}
            }
        }),
        json!({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json!({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "session_curate", "arguments": {
                    "conversation_text": "Decision: R26 fixture records one bounded disposable curation batch. Constraint: no production state, secrets, or identity data. Procedure: save this compact synthetic handoff for one observation proof.",
                    "scope": "project:/tmp/ab-r26-c2c-fixture",
                    "max_items": 3
                }
            }
        }),
    ]
    .into_iter()
    .map(|message| message.to_string())
    .collect::<Vec<_>>()
    .join("\n")
        + "\n"
}

fn successful_saved_count(stdout: &str) -> Result<usize, String> {
    let response = stdout
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .find(|value| value.get("id").and_then(Value::as_i64) == Some(2))
        .ok_or_else(|| "missing session_curate response".to_owned())?;
    let text = response["result"]["content"]
        .as_array()
        .and_then(|content| content.first())
        .and_then(|content| content["text"].as_str())
        .ok_or_else(|| "session_curate response has no text result".to_owned())?;
    let result: Value =
        serde_json::from_str(text).map_err(|_| "session_curate result is not JSON")?;
    result["saved_count"]
        .as_u64()
        .filter(|count| *count > 0)
        .map(|count| count as usize)
        .ok_or_else(|| "fixture saved no core memories".to_owned())
}

fn run(args: &Args) -> Result<usize, String> {
    let agent_bridge = args.agent_bridge.as_ref().expect("checked before run");
    let temp_dir = tempfile::Builder::new()
        .prefix("ab-r26-c2c.")
        .tempdir_in("/tmp")
        .map_err(|_| "could not create disposable R26 directory")?;
    let db_path = temp_dir.path().join("state.db");
    let mut custody =
        C2cLiveLabCustody::prepare().map_err(|_| "Keychain custody preparation failed")?;
    let mut child = Command::new(agent_bridge)
        .arg("mcp")
        .arg("--episode-observation")
        .arg("keychain-macos-v1")
        .env_clear()
        .env("AGENT_BRIDGE_DB", &db_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "could not start separately built agent-bridge MCP")?;
    let payload = rpc_payload();
    child
        .stdin
        .take()
        .ok_or_else(|| "missing MCP stdin".to_owned())?
        .write_all(payload.as_bytes())
        .map_err(|_| "could not write MCP fixture")?;
    let mut stdout = String::new();
    BufReader::new(
        child
            .stdout
            .take()
            .ok_or_else(|| "missing MCP stdout".to_owned())?,
    )
    .read_to_string(&mut stdout)
    .map_err(|_| "could not read MCP fixture")?;
    let status = child.wait().map_err(|_| "could not wait for MCP fixture")?;
    let saved_count = if status.success() {
        successful_saved_count(&stdout)?
    } else {
        return Err("MCP fixture process failed".to_owned());
    };
    custody.cleanup().map_err(|_| "Keychain cleanup failed")?;
    Ok(saved_count)
}

fn main() {
    let args = Args::parse();
    if source_only_refusal(&args) {
        eprintln!("R27 source fixture is default-off; R26 needs a separately authorized --agent-bridge path and --execute-r26-live acknowledgement");
        std::process::exit(64);
    }
    match run(&args) {
        Ok(saved_count) => println!("R26 fixture completed with {saved_count} core memory saves"),
        Err(_) => {
            eprintln!("R26 fixture incomplete; cleanup is required before any retry");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_arguments_refuse_before_any_live_action() {
        assert!(source_only_refusal(&Args {
            agent_bridge: None,
            execute_r26_live: None,
        }));
    }

    #[test]
    fn fixture_contains_one_session_curate_request() {
        let payload = rpc_payload();
        assert_eq!(payload.matches("session_curate").count(), 1);
        assert!(payload.contains("notifications/initialized"));
    }

    #[test]
    fn zero_saved_count_is_not_accepted() {
        let stdout = json!({
            "jsonrpc": "2.0", "id": 2, "result": {"content": [{"text": "{\\\"saved_count\\\":0}"}]}
        })
        .to_string();
        assert!(successful_saved_count(&stdout).is_err());
    }
}
