use std::collections::BTreeMap;
use std::fmt;
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;

use crate::avatar_renderer::{AuraIoReadCapability, SanitizedAuraIoReport};

const ENABLE_KEY: &str = "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE";
const ROOT_KEY: &str = "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT";
const ENTRY_KEY: &str = "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AvatarAuraIoStartupError {
    code: String,
}

impl AvatarAuraIoStartupError {
    fn new(code: impl Into<String>) -> Self {
        Self { code: code.into() }
    }

    pub fn code(&self) -> &str {
        &self.code
    }
}

impl fmt::Display for AvatarAuraIoStartupError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.code)
    }
}

impl std::error::Error for AvatarAuraIoStartupError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AvatarAuraIoStartupConfig {
    Disabled,
    Enabled { root: PathBuf, entry: PathBuf },
}

impl AvatarAuraIoStartupConfig {
    pub fn disabled() -> Self {
        Self::Disabled
    }

    pub fn from_values(
        values: &BTreeMap<String, String>,
    ) -> Result<Self, AvatarAuraIoStartupError> {
        let activation = values
            .get(ENABLE_KEY)
            .map(String::as_str)
            .unwrap_or("")
            .trim();
        if activation.is_empty() || activation == "0" {
            if values.contains_key(ROOT_KEY) || values.contains_key(ENTRY_KEY) {
                return Err(AvatarAuraIoStartupError::new(
                    "avatar_aura_io_config_without_activation",
                ));
            }
            return Ok(Self::Disabled);
        }
        if activation != "1" {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_activation_invalid",
            ));
        }

        let root = values
            .get(ROOT_KEY)
            .map(String::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| AvatarAuraIoStartupError::new("avatar_aura_io_config_root_missing"))?;
        let entry = values
            .get(ENTRY_KEY)
            .map(String::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| AvatarAuraIoStartupError::new("avatar_aura_io_config_entry_missing"))?;

        let root = PathBuf::from(root);
        if !root.is_absolute() {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_root_not_absolute",
            ));
        }
        if root
            .components()
            .any(|component| matches!(component, Component::CurDir | Component::ParentDir))
        {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_root_not_normalized",
            ));
        }
        if !root
            .components()
            .any(|component| matches!(component, Component::Normal(_)))
        {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_root_is_filesystem_root",
            ));
        }
        if values
            .get("HOME")
            .map(String::as_str)
            .map(str::trim)
            .filter(|home| !home.is_empty())
            .is_some_and(|home| root == Path::new(home))
        {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_root_is_home",
            ));
        }

        let entry = PathBuf::from(entry);
        if entry.is_absolute() {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_entry_not_relative",
            ));
        }
        if entry
            .components()
            .any(|component| matches!(component, Component::ParentDir))
        {
            return Err(AvatarAuraIoStartupError::new(
                "avatar_aura_io_config_entry_parent_component",
            ));
        }

        Ok(Self::Enabled { root, entry })
    }
}

pub async fn preload_avatar_aura_io(
    config: AvatarAuraIoStartupConfig,
) -> Result<Option<Arc<SanitizedAuraIoReport>>, AvatarAuraIoStartupError> {
    preload_avatar_aura_io_with_loader(config, |root, entry| {
        let capability = AuraIoReadCapability::open(&root).map_err(|error| {
            AvatarAuraIoStartupError::new(format!(
                "avatar_aura_io_startup_preload_{}",
                error.code()
            ))
        })?;
        let entry = capability.parse_entry(&entry).map_err(|error| {
            AvatarAuraIoStartupError::new(format!(
                "avatar_aura_io_startup_preload_{}",
                error.code()
            ))
        })?;
        capability.load_snapshot(&entry).map_err(|error| {
            AvatarAuraIoStartupError::new(format!(
                "avatar_aura_io_startup_preload_{}",
                error.code()
            ))
        })
    })
    .await
}

async fn preload_avatar_aura_io_with_loader<F>(
    config: AvatarAuraIoStartupConfig,
    loader: F,
) -> Result<Option<Arc<SanitizedAuraIoReport>>, AvatarAuraIoStartupError>
where
    F: FnOnce(PathBuf, PathBuf) -> Result<SanitizedAuraIoReport, AvatarAuraIoStartupError>
        + Send
        + 'static,
{
    let AvatarAuraIoStartupConfig::Enabled { root, entry } = config else {
        return Ok(None);
    };

    let report = tokio::task::spawn_blocking(move || loader(root, entry).map(Arc::new))
        .await
        .map_err(|_| AvatarAuraIoStartupError::new("avatar_aura_io_startup_worker_failed"))??;
    Ok(Some(report))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[tokio::test]
    async fn disabled_config_never_invokes_platform_loader() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed_calls = calls.clone();
        let result = preload_avatar_aura_io_with_loader(
            AvatarAuraIoStartupConfig::Disabled,
            move |_root, _entry| {
                calls.fetch_add(1, Ordering::SeqCst);
                Err(AvatarAuraIoStartupError::new(
                    "avatar_aura_io_startup_preload_unsupported_platform",
                ))
            },
        )
        .await
        .expect("disabled startup must not inspect platform support");

        assert!(result.is_none());
        assert_eq!(observed_calls.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn enabled_config_propagates_platform_loader_failure() {
        let calls = Arc::new(AtomicUsize::new(0));
        let observed_calls = calls.clone();
        let error = preload_avatar_aura_io_with_loader(
            AvatarAuraIoStartupConfig::Enabled {
                root: PathBuf::from("/srv/avatar-aura"),
                entry: PathBuf::from("aura.json"),
            },
            move |_root, _entry| {
                calls.fetch_add(1, Ordering::SeqCst);
                Err(AvatarAuraIoStartupError::new(
                    "avatar_aura_io_startup_preload_unsupported_platform",
                ))
            },
        )
        .await
        .expect_err("enabled unsupported platform must fail closed");

        assert_eq!(
            error.code(),
            "avatar_aura_io_startup_preload_unsupported_platform"
        );
        assert_eq!(observed_calls.load(Ordering::SeqCst), 1);
    }
}
