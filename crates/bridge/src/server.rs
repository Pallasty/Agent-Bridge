use ab_core::{RpcRequest, RpcResponse};
use anyhow::{Context, Result};
use std::path::Path;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tracing::{error, info};

use crate::router::Router;

/// Bind the Unix socket and serve forever.
pub async fn serve(socket_path: &Path, router: Router) -> Result<()> {
    if let Some(parent) = socket_path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .with_context(|| format!("create socket dir {parent:?}"))?;
    }
    if socket_path.exists() {
        // Stale socket — remove before binding.
        let _ = tokio::fs::remove_file(socket_path).await;
    }

    let listener =
        UnixListener::bind(socket_path).with_context(|| format!("bind {socket_path:?}"))?;
    info!(socket = %socket_path.display(), "agent-bridge listening");

    loop {
        match listener.accept().await {
            Ok((stream, _addr)) => {
                let router = router.clone();
                tokio::spawn(async move {
                    if let Err(e) = handle_conn(stream, router).await {
                        error!(error = %e, "connection terminated with error");
                    }
                });
            }
            Err(e) => {
                error!(error = %e, "accept failed");
            }
        }
    }
}

async fn handle_conn(stream: UnixStream, router: Router) -> Result<()> {
    let (read_half, mut write_half) = stream.into_split();
    let mut reader = BufReader::new(read_half).lines();

    while let Some(line) = reader.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }
        let resp = match serde_json::from_str::<RpcRequest>(&line) {
            Ok(req) => router.dispatch(req).await,
            Err(e) => RpcResponse::fail(0, -32700, format!("parse error: {e}")),
        };

        let mut bytes = serde_json::to_vec(&resp)?;
        bytes.push(b'\n');
        write_half.write_all(&bytes).await?;
        write_half.flush().await?;
    }
    Ok(())
}
