//! macOS Notification Center backend via `osascript`.

use ab_core::{Error, NotifyEvent, NotifySeverity, Result};
use async_trait::async_trait;
use tracing::debug;

use crate::Notifier;

#[derive(Clone)]
pub struct MacOsNotifier;

#[async_trait]
impl Notifier for MacOsNotifier {
    fn id(&self) -> &str {
        "macos"
    }

    async fn send(&self, evt: &NotifyEvent) -> Result<()> {
        let subtitle = match evt.severity {
            NotifySeverity::Error => "Error",
            NotifySeverity::Warning => "Warning",
            NotifySeverity::Success => "Success",
            NotifySeverity::Attention => "Attention",
            NotifySeverity::Info => "Info",
        };

        // Escape double-quotes to avoid breaking the AppleScript string literals.
        let title = evt.title.replace('\\', "\\\\").replace('"', "\\\"");
        let body = evt.body.replace('\\', "\\\\").replace('"', "\\\"");

        let script =
            format!(r#"display notification "{body}" with title "{title}" subtitle "{subtitle}""#);

        let status = tokio::process::Command::new("osascript")
            .arg("-e")
            .arg(&script)
            .status()
            .await
            .map_err(|e| Error::Backend(format!("osascript spawn: {e}")))?;

        if !status.success() {
            return Err(Error::Backend(format!(
                "osascript exited {:?}",
                status.code()
            )));
        }

        debug!(source = ?evt.source, "delivered via Notification Center");
        Ok(())
    }
}
