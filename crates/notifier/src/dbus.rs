//! `org.freedesktop.Notifications` (libnotify) D-Bus backend.
//!
//! Pure Rust via `zbus` — no `libdbus` system dependency.

use ab_core::{Error, NotifyEvent, NotifySeverity, Result};
use async_trait::async_trait;
use std::collections::HashMap;
use tracing::debug;
use zbus::{proxy, zvariant::Value, Connection};

use crate::Notifier;

#[proxy(
    interface = "org.freedesktop.Notifications",
    default_service = "org.freedesktop.Notifications",
    default_path = "/org/freedesktop/Notifications"
)]
trait Notifications {
    #[allow(clippy::too_many_arguments)]
    fn notify(
        &self,
        app_name: &str,
        replaces_id: u32,
        app_icon: &str,
        summary: &str,
        body: &str,
        actions: &[&str],
        hints: HashMap<&str, &Value<'_>>,
        expire_timeout: i32,
    ) -> zbus::Result<u32>;
}

#[derive(Clone)]
pub struct DbusNotifier {
    conn: Connection,
}

impl DbusNotifier {
    pub async fn connect() -> Result<Self> {
        let conn = Connection::session()
            .await
            .map_err(|e| Error::Backend(format!("dbus session connect: {e}")))?;
        Ok(Self { conn })
    }
}

#[async_trait]
impl Notifier for DbusNotifier {
    fn id(&self) -> &str {
        "dbus"
    }

    async fn send(&self, evt: &NotifyEvent) -> Result<()> {
        let proxy = NotificationsProxy::new(&self.conn)
            .await
            .map_err(|e| Error::Backend(format!("dbus proxy: {e}")))?;

        let icon = match evt.severity {
            NotifySeverity::Error => "dialog-error",
            NotifySeverity::Warning => "dialog-warning",
            NotifySeverity::Success => "emblem-default",
            NotifySeverity::Attention => "dialog-question",
            NotifySeverity::Info => "dialog-information",
        };

        let urgency: u8 = match evt.severity {
            NotifySeverity::Error | NotifySeverity::Attention => 2, // critical
            NotifySeverity::Warning => 1,
            _ => 0,
        };
        let urgency_val = Value::U8(urgency);
        let mut hints: HashMap<&str, &Value<'_>> = HashMap::new();
        hints.insert("urgency", &urgency_val);

        let id = proxy
            .notify(
                "agent-bridge",
                0,
                icon,
                &evt.title,
                &evt.body,
                &[],
                hints,
                -1,
            )
            .await
            .map_err(|e| Error::Backend(format!("dbus notify: {e}")))?;

        debug!(notification_id = id, source = ?evt.source, "delivered to dbus");
        Ok(())
    }
}
