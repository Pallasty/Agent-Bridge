use ab_core::{RpcRequest, RpcResponse};
use anyhow::{Context, Result};
use std::fs::Permissions;
use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
use std::path::Path;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tracing::{error, info, warn};

use crate::router::Router;

/// Bind the Unix socket and serve forever.
pub async fn serve(socket_path: &Path, router: Router) -> Result<()> {
    if let Some(parent) = socket_path.parent() {
        tokio::fs::create_dir_all(parent)
            .await
            .with_context(|| format!("create socket dir {parent:?}"))?;
    }
    remove_owned_stale_socket(socket_path).await?;

    let listener =
        UnixListener::bind(socket_path).with_context(|| format!("bind {socket_path:?}"))?;
    restrict_socket_permissions(socket_path)?;
    info!(socket = %socket_path.display(), "agent-bridge listening");

    loop {
        match listener.accept().await {
            Ok((stream, _addr)) => {
                let peer_uid = match kernel_peer_uid(&stream) {
                    Ok(uid) => Some(uid),
                    Err(e) => {
                        warn!(error = %e, "could not read Unix peer credentials");
                        None
                    }
                };
                let router = router.clone();
                tokio::spawn(async move {
                    if let Err(e) = handle_conn(stream, router, peer_uid).await {
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

fn restrict_socket_permissions(socket_path: &Path) -> Result<()> {
    std::fs::set_permissions(socket_path, Permissions::from_mode(0o600))
        .with_context(|| format!("chmod 0600 {socket_path:?}"))
}

async fn remove_owned_stale_socket(socket_path: &Path) -> Result<()> {
    let metadata = match tokio::fs::symlink_metadata(socket_path).await {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(error) => {
            return Err(error).with_context(|| format!("inspect socket path {socket_path:?}"));
        }
    };
    if !metadata.file_type().is_socket() {
        anyhow::bail!(
            "refusing to remove non-socket or symlink at configured socket path {socket_path:?}"
        );
    }
    if metadata.uid() != unsafe { libc::geteuid() } {
        anyhow::bail!("refusing to remove socket not owned by the current uid: {socket_path:?}");
    }
    tokio::fs::remove_file(socket_path)
        .await
        .with_context(|| format!("remove owned stale socket {socket_path:?}"))
}

fn kernel_peer_uid(stream: &UnixStream) -> std::io::Result<u32> {
    stream.peer_cred().map(|credentials| credentials.uid())
}

async fn handle_conn(stream: UnixStream, router: Router, peer_uid: Option<u32>) -> Result<()> {
    let (read_half, mut write_half) = stream.into_split();
    let mut reader = BufReader::new(read_half).lines();

    while let Some(line) = reader.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }
        let resp = match serde_json::from_str::<RpcRequest>(&line) {
            Ok(req) => router.dispatch_from_peer(req, peer_uid).await,
            Err(e) => RpcResponse::fail(0, -32700, format!("parse error: {e}")),
        };

        let mut bytes = serde_json::to_vec(&resp)?;
        bytes.push(b'\n');
        write_half.write_all(&bytes).await?;
        write_half.flush().await?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn socket_permissions_are_restricted_to_the_owner() {
        let dir = tempfile::tempdir().expect("temp dir");
        let socket_path = dir.path().join("bridge.sock");
        let listener = UnixListener::bind(&socket_path).expect("bind test socket");

        restrict_socket_permissions(&socket_path).expect("restrict socket permissions");

        let mode = std::fs::metadata(&socket_path)
            .expect("socket metadata")
            .permissions()
            .mode();
        assert_eq!(mode & 0o777, 0o600);
        drop(listener);
    }

    #[tokio::test]
    async fn peer_uid_comes_from_kernel_credentials() {
        let (stream, _peer) = UnixStream::pair().expect("Unix stream pair");

        let uid = kernel_peer_uid(&stream).expect("kernel peer credentials");

        assert_eq!(uid, unsafe { libc::geteuid() });
    }

    #[tokio::test]
    async fn stale_socket_cleanup_refuses_regular_files() {
        let dir = tempfile::tempdir().expect("temp dir");
        let path = dir.path().join("bridge.sock");
        std::fs::write(&path, b"owner data").expect("write sentinel");

        let error = remove_owned_stale_socket(&path)
            .await
            .expect_err("regular file must be preserved");

        assert!(error.to_string().contains("refusing to remove non-socket"));
        assert_eq!(
            std::fs::read(&path).expect("sentinel preserved"),
            b"owner data"
        );
    }

    #[tokio::test]
    async fn stale_socket_cleanup_removes_only_owned_socket_nodes() {
        let dir = tempfile::tempdir().expect("temp dir");
        let path = dir.path().join("bridge.sock");
        let listener = UnixListener::bind(&path).expect("bind stale socket");
        drop(listener);

        remove_owned_stale_socket(&path)
            .await
            .expect("owned stale socket removed");

        assert!(!path.exists());
    }
}
