//! Domain types shared across all agent-bridge crates.
//!
//! This crate has zero runtime dependencies — only `serde`, `uuid`, `thiserror`.

pub mod error;
pub mod ids;
pub mod events;
pub mod rpc;

pub use error::{Error, Result};
pub use ids::{SessionId, PaneId, WorktreeId, PageId, ToolInvocationId};
pub use events::{NotifyEvent, NotifySource, NotifySeverity};
pub use rpc::{RpcRequest, RpcResponse, RpcError};
