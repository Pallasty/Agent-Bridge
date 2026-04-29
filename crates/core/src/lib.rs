//! Domain types shared across all agent-bridge crates.
//!
//! This crate has zero runtime dependencies — only `serde`, `uuid`, `thiserror`.

pub mod error;
pub mod events;
pub mod ids;
pub mod rpc;

pub use error::{Error, Result};
pub use events::{NotifyEvent, NotifySeverity, NotifySource};
pub use ids::{PageId, PaneId, SessionId, ToolInvocationId, WorktreeId};
pub use rpc::{RpcError, RpcRequest, RpcResponse};
