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
use std::thread;
use std::time::{Duration, Instant};

const LIVE_ACK: &str = "r26-c2c-live-authorized";
const MCP_TIMEOUT: Duration = Duration::from_secs(30);

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

#[derive(Debug, PartialEq, Eq)]
struct DbEvent {
    episode_id: String,
    event_type: String,
    source_kind: String,
    episode_position: Option<i64>,
    item_count: Option<i64>,
}

#[derive(Debug, PartialEq, Eq)]
struct Receipt {
    item_count: usize,
}

#[derive(Debug, PartialEq, Eq)]
enum ChildOutcome {
    ExitedSuccess,
    ExitedFailure,
    TimedOut,
    WaitFailure,
}

fn classify_mcp_phase(stdout: &str) -> &'static str {
    let mut initialized = false;
    let mut curate_responded = false;
    for value in stdout
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
    {
        if value.get("id").and_then(Value::as_i64) == Some(1) && value.get("result").is_some() {
            initialized = true;
        }
        if value.get("id").and_then(Value::as_i64) == Some(2) && value.get("result").is_some() {
            curate_responded = true;
        }
    }
    if curate_responded {
        "after_curate_response_before_exit"
    } else if initialized {
        "after_initialize_before_curate_response"
    } else {
        "before_initialize_response"
    }
}

fn validate_receipt(events: &[DbEvent], expected_item_count: usize) -> Result<Receipt, String> {
    let Some(first) = events.first() else {
        return Err("episode receipt is empty".to_owned());
    };
    if events
        .iter()
        .any(|event| event.episode_id != first.episode_id || event.source_kind != "curation_batch")
    {
        return Err("episode receipt is not one CurationBatch episode".to_owned());
    }
    if first.event_type != "episode.open"
        || first.episode_position.is_some()
        || first.item_count.is_some()
    {
        return Err("episode receipt has no valid open".to_owned());
    }
    let Some(close) = events.last() else {
        return Err("episode receipt has no close".to_owned());
    };
    if close.event_type != "episode.close"
        || close.episode_position.is_some()
        || close.item_count != Some(expected_item_count as i64)
    {
        return Err("episode receipt has no matching close".to_owned());
    }
    let items = &events[1..events.len().saturating_sub(1)];
    if items.len() != expected_item_count
        || items.iter().enumerate().any(|(position, event)| {
            event.event_type != "episode.item"
                || event.episode_position != Some(position as i64)
                || event.item_count.is_some()
        })
    {
        return Err("episode receipt item positions are not contiguous".to_owned());
    }
    Ok(Receipt {
        item_count: expected_item_count,
    })
}

fn read_receipt(db_path: &std::path::Path, expected_item_count: usize) -> Result<Receipt, String> {
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|_| "could not create receipt runtime")?;
    let events = runtime.block_on(async {
        let connection = tokio_rusqlite::Connection::open(db_path)
            .await
            .map_err(|_| "could not open disposable receipt database")?;
        connection
            .call(|connection| {
                let mut statement = connection.prepare(
                    "SELECT episode_id, event_type, source_kind, episode_position, item_count \
                     FROM episode_observation_events ORDER BY episode_id ASC, rowid ASC",
                )?;
                let events = statement
                    .query_map([], |row| {
                        Ok(DbEvent {
                            episode_id: row.get(0)?,
                            event_type: row.get(1)?,
                            source_kind: row.get(2)?,
                            episode_position: row.get(3)?,
                            item_count: row.get(4)?,
                        })
                    })?
                    .collect::<Result<Vec<_>, _>>();
                events
            })
            .await
            .map_err(|_| "could not query disposable receipt database")
    })?;
    validate_receipt(&events, expected_item_count)
}

fn wait_for_child(child: &mut std::process::Child) -> ChildOutcome {
    wait_for_child_with_timeout(child, MCP_TIMEOUT)
}

fn wait_for_child_with_timeout(child: &mut std::process::Child, timeout: Duration) -> ChildOutcome {
    let deadline = Instant::now() + timeout;
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return ChildOutcome::ExitedSuccess,
            Ok(Some(_)) => return ChildOutcome::ExitedFailure,
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(25)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return ChildOutcome::TimedOut;
            }
            Err(_) => return ChildOutcome::WaitFailure,
        }
    }
}

fn run_fixture(
    agent_bridge: &std::path::Path,
    db_path: &std::path::Path,
) -> Result<Receipt, String> {
    let mut child = Command::new(agent_bridge)
        .arg("mcp")
        .arg("--episode-observation")
        .arg("keychain-macos-v1")
        .env_clear()
        .env("AGENT_BRIDGE_DB", db_path)
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
    let stdout_pipe = child
        .stdout
        .take()
        .ok_or_else(|| "missing MCP stdout".to_owned())?;
    let stdout_handle = thread::spawn(move || {
        let mut stdout = String::new();
        BufReader::new(stdout_pipe)
            .read_to_string(&mut stdout)
            .map(|_| stdout)
            .map_err(|_| "could not read MCP fixture".to_owned())
    });
    let outcome = wait_for_child(&mut child);
    let stdout = stdout_handle
        .join()
        .map_err(|_| "MCP stdout reader panicked".to_owned())??;
    match outcome {
        ChildOutcome::TimedOut => {
            return Err(format!(
                "MCP fixture process timed out ({})",
                classify_mcp_phase(&stdout)
            ));
        }
        ChildOutcome::ExitedFailure => return Err("MCP fixture process failed".to_owned()),
        ChildOutcome::WaitFailure => return Err("could not wait for MCP fixture".to_owned()),
        ChildOutcome::ExitedSuccess => {}
    }
    let saved_count = successful_saved_count(&stdout)?;
    read_receipt(db_path, saved_count)
}

fn run(args: &Args) -> Result<Receipt, String> {
    let agent_bridge = args.agent_bridge.as_ref().expect("checked before run");
    let temp_dir = tempfile::Builder::new()
        .prefix("ab-r26-c2c.")
        .tempdir_in("/tmp")
        .map_err(|_| "could not create disposable R26 directory")?;
    let db_path = temp_dir.path().join("state.db");
    let mut custody =
        C2cLiveLabCustody::prepare().map_err(|_| "Keychain custody preparation failed")?;
    let fixture_result = run_fixture(agent_bridge, &db_path);
    let cleanup_result = custody.cleanup();
    match (fixture_result, cleanup_result) {
        (Ok(receipt), Ok(())) => Ok(receipt),
        (_, Err(_)) => Err(format!(
            "Keychain cleanup unconfirmed; recover only {} and active-epoch",
            custody.key_account()
        )),
        (Err(error), Ok(())) => Err(error),
    }
}

fn main() {
    let args = Args::parse();
    if source_only_refusal(&args) {
        eprintln!("R27 source fixture is default-off; R26 needs a separately authorized --agent-bridge path and --execute-r26-live acknowledgement");
        std::process::exit(64);
    }
    match run(&args) {
        Ok(receipt) => println!(
            "R26 fixture receipt: one finalized CurationBatch with {} items",
            receipt.item_count
        ),
        Err(error) => {
            eprintln!("R26 fixture incomplete: {error}");
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

    #[test]
    fn receipt_requires_one_finalized_contiguous_curation_batch() {
        let events = vec![
            DbEvent {
                episode_id: "ep".into(),
                event_type: "episode.open".into(),
                source_kind: "curation_batch".into(),
                episode_position: None,
                item_count: None,
            },
            DbEvent {
                episode_id: "ep".into(),
                event_type: "episode.item".into(),
                source_kind: "curation_batch".into(),
                episode_position: Some(0),
                item_count: None,
            },
            DbEvent {
                episode_id: "ep".into(),
                event_type: "episode.close".into(),
                source_kind: "curation_batch".into(),
                episode_position: None,
                item_count: Some(1),
            },
        ];
        assert_eq!(validate_receipt(&events, 1), Ok(Receipt { item_count: 1 }));
    }

    #[test]
    fn receipt_rejects_noncontiguous_or_multiple_episodes() {
        let events = vec![
            DbEvent {
                episode_id: "ep".into(),
                event_type: "episode.open".into(),
                source_kind: "curation_batch".into(),
                episode_position: None,
                item_count: None,
            },
            DbEvent {
                episode_id: "other".into(),
                event_type: "episode.item".into(),
                source_kind: "curation_batch".into(),
                episode_position: Some(1),
                item_count: None,
            },
            DbEvent {
                episode_id: "ep".into(),
                event_type: "episode.close".into(),
                source_kind: "curation_batch".into(),
                episode_position: None,
                item_count: Some(1),
            },
        ];
        assert!(validate_receipt(&events, 1).is_err());
    }

    #[test]
    fn timeout_phase_classifier_never_returns_raw_mcp_content() {
        assert_eq!(classify_mcp_phase(""), "before_initialize_response");
        assert_eq!(
            classify_mcp_phase(r#"{"jsonrpc":"2.0","id":1,"result":{}}"#),
            "after_initialize_before_curate_response"
        );
        assert_eq!(
            classify_mcp_phase(
                r#"{"jsonrpc":"2.0","id":1,"result":{}}
{"jsonrpc":"2.0","id":2,"result":{"content":[{"text":"sensitive"}]}}"#
            ),
            "after_curate_response_before_exit"
        );
    }

    #[cfg(unix)]
    #[test]
    fn timeout_kills_and_reaps_child_before_returning() {
        let mut child = Command::new("sh")
            .args(["-c", "sleep 2"])
            .spawn()
            .expect("sleep child");
        assert_eq!(
            wait_for_child_with_timeout(&mut child, Duration::from_millis(10)),
            ChildOutcome::TimedOut
        );
        assert!(child.try_wait().expect("reaped child").is_some());
    }
}
