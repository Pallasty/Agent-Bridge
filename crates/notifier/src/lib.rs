//! Notification dispatch — turns `NotifyEvent`s into desktop popups,
//! webhook deliveries, mobile pushes, etc.
//!
//! Every backend implements [`Notifier`]; the bridge fans events out to all
//! registered notifiers in parallel.

use ab_core::{NotifyEvent, Result};
use async_trait::async_trait;

pub mod dbus;

pub use dbus::DbusNotifier;

/// A delivery sink for [`NotifyEvent`]s.
///
/// Implementations should be cheap to clone (typically `Arc`-wrapped state).
#[async_trait]
pub trait Notifier: Send + Sync {
    /// Stable identifier (e.g. `"dbus"`, `"slack-webhook"`).
    fn id(&self) -> &str;

    /// Deliver one event. Errors are logged but should not panic.
    async fn send(&self, evt: &NotifyEvent) -> Result<()>;
}
