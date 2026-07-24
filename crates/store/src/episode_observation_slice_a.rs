//! Default-off, source-only episode observation primitives.
//!
//! This module intentionally has no persistence or producer integration.

use ring::hmac;

const ITEM_REF_DOMAIN: &[u8] = b"agent-bridge/episode-item-ref/v1";
const MIN_KEY_BYTES: usize = 32;
const MIN_MEMORY_KEY_BYTES: usize = 1;
const MAX_MEMORY_KEY_BYTES: usize = 4096;
const MAX_EPOCH_BYTES: usize = 32;

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum EpisodeItemRefError {
    MissingKeyProvider,
    UnknownKeyEpoch,
    KeyTooShort,
    InvalidKeyEpoch,
    InvalidMemoryKeyLength,
}

/// Borrowed key material. Deliberately not `Clone`, `Debug`, or serializable.
pub(crate) struct EpisodeRefKeyMaterial<'a> {
    epoch: &'a str,
    key_bytes: &'a [u8],
}

impl<'a> EpisodeRefKeyMaterial<'a> {
    pub(crate) fn new(epoch: &'a str, key_bytes: &'a [u8]) -> Self {
        Self { epoch, key_bytes }
    }
}

pub(crate) trait EpisodeRefKeyProvider {
    fn active_key(&self) -> Option<EpisodeRefKeyMaterial<'_>>;
    fn key_for_epoch(&self, epoch: &str) -> Option<EpisodeRefKeyMaterial<'_>>;
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum EpisodeObservationSourceKind {
    Session,
    CurationBatch,
    OwnerBundle,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum EpisodeObservationKind<'a> {
    Open,
    Item {
        item_ref: &'a str,
        episode_position: u32,
    },
    Close {
        item_count: u32,
    },
}

pub(crate) struct EpisodeObservationEvent<'a> {
    pub(crate) event_id: &'a str,
    pub(crate) episode_id: &'a str,
    pub(crate) producer_run_id: &'a str,
    pub(crate) source_kind: EpisodeObservationSourceKind,
    pub(crate) kind: EpisodeObservationKind<'a>,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum EpisodeObservationSinkDisposition {
    Disabled,
}

pub(crate) trait EpisodeObservationSink {
    fn observe(&self, event: &EpisodeObservationEvent<'_>) -> EpisodeObservationSinkDisposition;
}

pub(crate) struct NoopEpisodeObservationSink;

impl EpisodeObservationSink for NoopEpisodeObservationSink {
    fn observe(&self, _event: &EpisodeObservationEvent<'_>) -> EpisodeObservationSinkDisposition {
        EpisodeObservationSinkDisposition::Disabled
    }
}

fn valid_epoch(epoch: &str) -> bool {
    let bytes = epoch.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= MAX_EPOCH_BYTES
        && bytes
            .iter()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || *byte == b'-')
}

fn update_framed(context: &mut hmac::Context, bytes: &[u8]) {
    context.update(&(bytes.len() as u64).to_be_bytes());
    context.update(bytes);
}

fn lower_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn derive_with_material(
    material: EpisodeRefKeyMaterial<'_>,
    memory_key: &str,
) -> Result<String, EpisodeItemRefError> {
    if material.key_bytes.len() < MIN_KEY_BYTES {
        return Err(EpisodeItemRefError::KeyTooShort);
    }
    if !valid_epoch(material.epoch) {
        return Err(EpisodeItemRefError::InvalidKeyEpoch);
    }
    let memory_key_bytes = memory_key.as_bytes();
    if !(MIN_MEMORY_KEY_BYTES..=MAX_MEMORY_KEY_BYTES).contains(&memory_key_bytes.len()) {
        return Err(EpisodeItemRefError::InvalidMemoryKeyLength);
    }

    let key = hmac::Key::new(hmac::HMAC_SHA256, material.key_bytes);
    let mut context = hmac::Context::with_key(&key);
    update_framed(&mut context, ITEM_REF_DOMAIN);
    update_framed(&mut context, material.epoch.as_bytes());
    update_framed(&mut context, memory_key_bytes);
    let digest = context.sign();
    Ok(format!(
        "epr_v1_{}_{}",
        material.epoch,
        lower_hex(digest.as_ref())
    ))
}

pub(crate) fn derive_active_item_ref(
    provider: Option<&dyn EpisodeRefKeyProvider>,
    memory_key: &str,
) -> Result<String, EpisodeItemRefError> {
    let provider = provider.ok_or(EpisodeItemRefError::MissingKeyProvider)?;
    let material = provider
        .active_key()
        .ok_or(EpisodeItemRefError::MissingKeyProvider)?;
    derive_with_material(material, memory_key)
}

pub(crate) fn derive_item_ref_for_epoch(
    provider: Option<&dyn EpisodeRefKeyProvider>,
    epoch: &str,
    memory_key: &str,
) -> Result<String, EpisodeItemRefError> {
    if !valid_epoch(epoch) {
        return Err(EpisodeItemRefError::InvalidKeyEpoch);
    }
    let provider = provider.ok_or(EpisodeItemRefError::MissingKeyProvider)?;
    let material = provider
        .key_for_epoch(epoch)
        .ok_or(EpisodeItemRefError::UnknownKeyEpoch)?;
    if material.epoch != epoch {
        return Err(EpisodeItemRefError::UnknownKeyEpoch);
    }
    derive_with_material(material, memory_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct SyntheticProvider {
        epoch: &'static str,
        key: [u8; 32],
    }

    impl EpisodeRefKeyProvider for SyntheticProvider {
        fn active_key(&self) -> Option<EpisodeRefKeyMaterial<'_>> {
            Some(EpisodeRefKeyMaterial::new(self.epoch, &self.key))
        }

        fn key_for_epoch(&self, epoch: &str) -> Option<EpisodeRefKeyMaterial<'_>> {
            (epoch == self.epoch).then(|| EpisodeRefKeyMaterial::new(self.epoch, &self.key))
        }
    }

    fn provider() -> SyntheticProvider {
        let mut key = [0u8; 32];
        for (index, byte) in key.iter_mut().enumerate() {
            *byte = index as u8;
        }
        SyntheticProvider {
            epoch: "epoch-test-0001",
            key,
        }
    }

    #[test]
    fn public_synthetic_known_answer() {
        let actual = derive_active_item_ref(Some(&provider()), "curated_decision_测试_01")
            .expect("synthetic derivation");
        assert_eq!(
            actual,
            "epr_v1_epoch-test-0001_a90c09a8eb687d7d9858979d1dbb9801ec68e73628053a7200609e8a341b9c04"
        );
    }

    #[test]
    fn provider_and_epoch_fail_closed() {
        assert_eq!(
            derive_active_item_ref(None, "memory"),
            Err(EpisodeItemRefError::MissingKeyProvider)
        );
        assert_eq!(
            derive_item_ref_for_epoch(Some(&provider()), "epoch-test-0002", "memory"),
            Err(EpisodeItemRefError::UnknownKeyEpoch)
        );
        assert_eq!(
            derive_item_ref_for_epoch(Some(&provider()), "bad_epoch", "memory"),
            Err(EpisodeItemRefError::InvalidKeyEpoch)
        );
    }

    #[test]
    fn key_and_memory_key_bounds_fail_closed() {
        struct WeakProvider;
        impl EpisodeRefKeyProvider for WeakProvider {
            fn active_key(&self) -> Option<EpisodeRefKeyMaterial<'_>> {
                Some(EpisodeRefKeyMaterial::new("epoch-1", b"short"))
            }
            fn key_for_epoch(&self, _epoch: &str) -> Option<EpisodeRefKeyMaterial<'_>> {
                self.active_key()
            }
        }

        assert_eq!(
            derive_active_item_ref(Some(&WeakProvider), "memory"),
            Err(EpisodeItemRefError::KeyTooShort)
        );
        assert_eq!(
            derive_active_item_ref(Some(&provider()), ""),
            Err(EpisodeItemRefError::InvalidMemoryKeyLength)
        );
        assert_eq!(
            derive_active_item_ref(Some(&provider()), &"x".repeat(4097)),
            Err(EpisodeItemRefError::InvalidMemoryKeyLength)
        );
    }

    #[test]
    fn epoch_and_memory_key_are_bound() {
        let first = provider();
        let mut second = provider();
        second.epoch = "epoch-test-0002";
        assert_ne!(
            derive_active_item_ref(Some(&first), "memory-a").unwrap(),
            derive_active_item_ref(Some(&second), "memory-a").unwrap()
        );
        assert_ne!(
            derive_active_item_ref(Some(&first), "memory-a").unwrap(),
            derive_active_item_ref(Some(&first), "memory-b").unwrap()
        );
    }

    #[test]
    fn noop_sink_reports_disabled() {
        let event = EpisodeObservationEvent {
            event_id: "event-1",
            episode_id: "episode-1",
            producer_run_id: "run-1",
            source_kind: EpisodeObservationSourceKind::CurationBatch,
            kind: EpisodeObservationKind::Open,
        };
        assert_eq!(
            NoopEpisodeObservationSink.observe(&event),
            EpisodeObservationSinkDisposition::Disabled
        );
    }
}
