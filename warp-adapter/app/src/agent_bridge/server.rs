use std::os::unix::net::UnixListener;
use std::os::unix::fs::PermissionsExt;

use std::sync::Arc;

use warp_agent_bridge::{
    default_ipc_socket_path,
    protocol::{BridgeError, BridgeRequest, BridgeResponse, ReadScrollbackParams},
};
use warpui::r#async::executor::Background;
use warpui::ModelSpawner;

use super::AgentBridgeRegistry;

/// Start the Agent-Bridge IPC server.
///
/// Binds `XDG_RUNTIME_DIR/warp-agent-bridge.sock`, spawns an async accept
/// loop on the background executor, and handles each connection in its own
/// task.  All terminal operations are dispatched back to the main thread via
/// `registry_spawner`.
pub fn start(spawner: ModelSpawner<AgentBridgeRegistry>, bg: Arc<Background>) {
    let socket_path = default_ipc_socket_path();

    // Remove stale socket from a previous run.
    let _ = std::fs::remove_file(&socket_path);

    // Create parent directory if it does not exist (XDG_RUNTIME_DIR should,
    // but be defensive).
    if let Some(parent) = socket_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

    let listener = match UnixListener::bind(&socket_path) {
        Ok(l) => l,
        Err(e) => {
            log::error!("agent-bridge: failed to bind IPC socket at {}: {e}", socket_path.display());
            return;
        }
    };
    // Owner-only access — the socket carries terminal I/O.
    let _ = std::fs::set_permissions(&socket_path, std::fs::Permissions::from_mode(0o600));
    listener.set_nonblocking(true).ok();

    log::info!("agent-bridge: IPC server listening on {}", socket_path.display());

    let bg_clone = bg.clone();
    bg.spawn(async move {
        let listener = match async_io::Async::new(listener) {
            Ok(l) => l,
            Err(e) => {
                log::error!("agent-bridge: async listener error: {e}");
                return;
            }
        };
        loop {
            match listener.accept().await {
                Ok((stream, _)) => {
                    let sp = spawner.clone();
                    bg_clone
                        .spawn(handle_connection(stream, sp))
                        .detach();
                }
                Err(e) => {
                    log::warn!("agent-bridge: accept error: {e}");
                }
            }
        }
    })
    .detach();
}

async fn handle_connection(
    stream: async_io::Async<std::os::unix::net::UnixStream>,
    spawner: ModelSpawner<AgentBridgeRegistry>,
) {
    use futures_lite::AsyncBufReadExt;
    let stream = async_io::Async::new(stream.into_inner().unwrap()).unwrap();
    let (reader, mut writer) = futures_lite::io::split(stream);
    let mut lines = futures_lite::io::BufReader::new(reader).lines();

    while let Some(line) = futures_lite::StreamExt::next(&mut lines).await {
        let line = match line {
            Ok(l) if !l.trim().is_empty() => l,
            Ok(_) => continue,
            Err(e) => {
                log::debug!("agent-bridge: connection read error: {e}");
                break;
            }
        };

        let req: BridgeRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(e) => {
                let resp = BridgeResponse {
                    id: "?".into(),
                    result: None,
                    error: Some(BridgeError {
                        code: -32700,
                        message: format!("parse error: {e}"),
                    }),
                };
                let _ = write_response(&mut writer, &resp).await;
                continue;
            }
        };

        let resp = dispatch(req, &spawner).await;
        if write_response(&mut writer, &resp).await.is_err() {
            break;
        }
    }
}

async fn dispatch(
    req: BridgeRequest,
    spawner: &ModelSpawner<AgentBridgeRegistry>,
) -> BridgeResponse {
    let id = req.id.clone();

    match req.method.as_str() {
        "list_sessions" => {
            let result = spawner
                .spawn(|registry, _ctx| registry.list_sessions())
                .await;
            match result {
                Ok(sessions) => ok_response(id, serde_json::to_value(sessions).unwrap()),
                Err(_) => err_response(id, -32603, "registry unavailable"),
            }
        }

        "send_text" => {
            #[derive(serde::Deserialize)]
            struct Params {
                session_id: String,
                text: String,
            }
            let params: Params = match serde_json::from_value(req.params.clone()) {
                Ok(p) => p,
                Err(e) => return err_response(id, -32602, &format!("invalid params: {e}")),
            };
            let result = spawner
                .spawn(move |registry, _ctx| registry.send_text(&params.session_id, &params.text))
                .await;
            match result {
                Ok(Ok(())) => ok_response(id, serde_json::json!({ "ok": true })),
                Ok(Err(e)) => err_response(id, -32603, &e.to_string()),
                Err(_) => err_response(id, -32603, "registry unavailable"),
            }
        }

        "read_scrollback" => {
            let params: ReadScrollbackParams = match serde_json::from_value(req.params.clone()) {
                Ok(p) => p,
                Err(e) => return err_response(id, -32602, &format!("invalid params: {e}")),
            };
            let result = spawner
                .spawn(move |registry, _ctx| {
                    registry.read_scrollback(&params.session_id, params.last_n_lines)
                })
                .await;
            match result {
                Ok(Ok(lines)) => ok_response(id, serde_json::to_value(lines).unwrap()),
                Ok(Err(e)) => err_response(id, -32603, &e.to_string()),
                Err(_) => err_response(id, -32603, "registry unavailable"),
            }
        }

        method => err_response(id, -32601, &format!("unknown method: {method}")),
    }
}

async fn write_response(
    writer: &mut (impl futures_lite::AsyncWrite + Unpin),
    resp: &BridgeResponse,
) -> std::io::Result<()> {
    use futures_lite::AsyncWriteExt;
    let mut line = serde_json::to_string(resp).unwrap();
    line.push('\n');
    writer.write_all(line.as_bytes()).await
}

fn ok_response(id: String, result: serde_json::Value) -> BridgeResponse {
    BridgeResponse {
        id,
        result: Some(result),
        error: None,
    }
}

fn err_response(id: String, code: i32, message: &str) -> BridgeResponse {
    BridgeResponse {
        id,
        result: None,
        error: Some(BridgeError {
            code,
            message: message.to_owned(),
        }),
    }
}
