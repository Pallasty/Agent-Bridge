//! Default-off, read-only macOS Keychain custody adapter for episode refs.
//!
//! Normal startup does not construct this module. Keychain bytes stay inside
//! the store crate, are used for one derivation, and are zeroized immediately.

use crate::episode_observation_slice_a::{
    derive_item_ref_for_epoch, EpisodeRefKeyMaterial, EpisodeRefKeyProvider,
};
use security_framework::passwords::{generic_password, PasswordOptions};
use zeroize::Zeroize;

const SERVICE: &str = "com.agent-bridge.episode-ref.v1";
const ACTIVE_EPOCH_ACCOUNT: &str = "active-epoch";
const KEY_ACCOUNT_PREFIX: &str = "key:";
const KEY_BYTES: usize = 32;
const MAX_EPOCH_BYTES: usize = 32;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum KeychainCustodyError {
    Unavailable,
    InvalidEpoch,
    InvalidKeyLength,
    DerivationFailed,
}

#[derive(Clone, Copy)]
struct ReaderFailure;

trait KeychainSecretReader {
    fn read(&self, account: &str) -> Result<Vec<u8>, ReaderFailure>;
}

struct MacOsKeychainReader;

impl KeychainSecretReader for MacOsKeychainReader {
    fn read(&self, account: &str) -> Result<Vec<u8>, ReaderFailure> {
        generic_password(PasswordOptions::new_generic_password(SERVICE, account))
            .map_err(|_| ReaderFailure)
    }
}

struct SecretBytes {
    bytes: Vec<u8>,
    cleared: bool,
}

impl SecretBytes {
    fn new(bytes: Vec<u8>) -> Self {
        Self {
            bytes,
            cleared: false,
        }
    }

    fn expose(&self) -> &[u8] {
        &self.bytes
    }

    fn clear(&mut self) {
        if self.cleared {
            return;
        }
        self.bytes.zeroize();
        self.cleared = true;
        #[cfg(test)]
        ZEROIZE_COUNT.with(|count| count.set(count.get() + 1));
    }
}

impl Drop for SecretBytes {
    fn drop(&mut self) {
        self.clear();
    }
}

struct BorrowedProvider<'a> {
    epoch: &'a str,
    key: &'a [u8],
}

impl EpisodeRefKeyProvider for BorrowedProvider<'_> {
    fn active_key(&self) -> Option<EpisodeRefKeyMaterial<'_>> {
        Some(EpisodeRefKeyMaterial::new(self.epoch, self.key))
    }

    fn key_for_epoch(&self, epoch: &str) -> Option<EpisodeRefKeyMaterial<'_>> {
        (epoch == self.epoch).then(|| EpisodeRefKeyMaterial::new(self.epoch, self.key))
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

fn derive_with_reader(
    reader: &dyn KeychainSecretReader,
    memory_key: &str,
) -> Result<String, KeychainCustodyError> {
    let mut epoch_bytes = SecretBytes::new(
        reader
            .read(ACTIVE_EPOCH_ACCOUNT)
            .map_err(|_| KeychainCustodyError::Unavailable)?,
    );
    let epoch = std::str::from_utf8(epoch_bytes.expose())
        .map_err(|_| KeychainCustodyError::InvalidEpoch)?
        .to_owned();
    if !valid_epoch(&epoch) {
        return Err(KeychainCustodyError::InvalidEpoch);
    }
    epoch_bytes.clear();

    let account = format!("{KEY_ACCOUNT_PREFIX}{epoch}");
    let mut key_bytes = SecretBytes::new(
        reader
            .read(&account)
            .map_err(|_| KeychainCustodyError::Unavailable)?,
    );
    if key_bytes.expose().len() != KEY_BYTES {
        return Err(KeychainCustodyError::InvalidKeyLength);
    }

    let provider = BorrowedProvider {
        epoch: &epoch,
        key: key_bytes.expose(),
    };
    let result = derive_item_ref_for_epoch(Some(&provider), &epoch, memory_key)
        .map_err(|_| KeychainCustodyError::DerivationFailed);
    key_bytes.clear();
    result
}

/// Reserved for a separately authorized C2C runtime packet.
pub(crate) fn derive_active_item_ref_from_keychain(
    memory_key: &str,
) -> Result<String, KeychainCustodyError> {
    derive_with_reader(&MacOsKeychainReader, memory_key)
}

#[cfg(test)]
thread_local! {
    static ZEROIZE_COUNT: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::collections::HashMap;

    enum FakeValue {
        Bytes(Vec<u8>),
        Error(&'static str),
    }

    #[derive(Default)]
    struct FakeReader {
        entries: RefCell<HashMap<String, FakeValue>>,
        reads: RefCell<Vec<String>>,
    }

    impl FakeReader {
        fn insert_bytes(&self, account: &str, bytes: impl Into<Vec<u8>>) {
            self.entries
                .borrow_mut()
                .insert(account.to_owned(), FakeValue::Bytes(bytes.into()));
        }

        fn insert_error(&self, account: &str, detail: &'static str) {
            self.entries
                .borrow_mut()
                .insert(account.to_owned(), FakeValue::Error(detail));
        }

        fn read_accounts(&self) -> Vec<String> {
            self.reads.borrow().clone()
        }
    }

    impl KeychainSecretReader for FakeReader {
        fn read(&self, account: &str) -> Result<Vec<u8>, ReaderFailure> {
            self.reads.borrow_mut().push(account.to_owned());
            match self.entries.borrow().get(account) {
                Some(FakeValue::Bytes(bytes)) => Ok(bytes.clone()),
                Some(FakeValue::Error(detail)) => {
                    let _redacted = detail.len();
                    Err(ReaderFailure)
                }
                None => Err(ReaderFailure),
            }
        }
    }

    fn valid_reader(epoch: &str, key: Vec<u8>) -> FakeReader {
        let reader = FakeReader::default();
        reader.insert_bytes(ACTIVE_EPOCH_ACCOUNT, epoch.as_bytes());
        reader.insert_bytes(&format!("{KEY_ACCOUNT_PREFIX}{epoch}"), key);
        reader
    }

    fn zeroize_count() -> usize {
        ZEROIZE_COUNT.with(std::cell::Cell::get)
    }

    #[test]
    fn valid_key_derives_once_and_zeroizes_both_keychain_buffers() {
        let reader = valid_reader("epoch-test-0001", vec![0x5a; KEY_BYTES]);
        let before = zeroize_count();
        let item_ref = derive_with_reader(&reader, "memory-a").expect("derive");
        assert!(item_ref.starts_with("epr_v1_epoch-test-0001_"));
        assert_eq!(zeroize_count(), before + 2);
        assert_eq!(
            reader.read_accounts(),
            vec![ACTIVE_EPOCH_ACCOUNT, "key:epoch-test-0001"]
        );
    }

    #[test]
    fn malformed_or_missing_custody_inputs_fail_closed() {
        let missing_epoch = FakeReader::default();
        assert_eq!(
            derive_with_reader(&missing_epoch, "memory-a"),
            Err(KeychainCustodyError::Unavailable)
        );

        let invalid_utf8 = FakeReader::default();
        invalid_utf8.insert_bytes(ACTIVE_EPOCH_ACCOUNT, vec![0xff]);
        assert_eq!(
            derive_with_reader(&invalid_utf8, "memory-a"),
            Err(KeychainCustodyError::InvalidEpoch)
        );

        let invalid_epoch = FakeReader::default();
        invalid_epoch.insert_bytes(ACTIVE_EPOCH_ACCOUNT, b"Epoch_UPPER".to_vec());
        assert_eq!(
            derive_with_reader(&invalid_epoch, "memory-a"),
            Err(KeychainCustodyError::InvalidEpoch)
        );

        let missing_key = FakeReader::default();
        missing_key.insert_bytes(ACTIVE_EPOCH_ACCOUNT, b"epoch-test-0001".to_vec());
        assert_eq!(
            derive_with_reader(&missing_key, "memory-a"),
            Err(KeychainCustodyError::Unavailable)
        );

        for key_len in [KEY_BYTES - 1, KEY_BYTES + 1] {
            let reader = valid_reader("epoch-test-0001", vec![0x5a; key_len]);
            assert_eq!(
                derive_with_reader(&reader, "memory-a"),
                Err(KeychainCustodyError::InvalidKeyLength)
            );
        }
    }

    #[test]
    fn epoch_rotation_reads_the_new_account_without_rewriting_old_refs() {
        let reader = valid_reader("epoch-test-0001", vec![0x11; KEY_BYTES]);
        let old_ref = derive_with_reader(&reader, "memory-a").expect("old derive");
        reader.insert_bytes(ACTIVE_EPOCH_ACCOUNT, b"epoch-test-0002".to_vec());
        reader.insert_bytes("key:epoch-test-0002", vec![0x22; KEY_BYTES]);
        let new_ref = derive_with_reader(&reader, "memory-a").expect("new derive");
        assert_ne!(old_ref, new_ref);
        assert!(old_ref.starts_with("epr_v1_epoch-test-0001_"));
        assert!(new_ref.starts_with("epr_v1_epoch-test-0002_"));
    }

    #[test]
    fn backend_detail_and_secret_sentinel_never_cross_the_error_boundary() {
        let backend = FakeReader::default();
        backend.insert_error(ACTIVE_EPOCH_ACCOUNT, "backend-sentinel-detail");
        let backend_error = derive_with_reader(&backend, "memory-a").expect_err("backend error");
        assert!(!format!("{backend_error:?}").contains("sentinel"));

        let secret = b"secret-sentinel-secret-sentinel!".to_vec();
        assert_eq!(secret.len(), KEY_BYTES);
        let reader = valid_reader("epoch-test-0001", secret);
        let derivation_error = derive_with_reader(&reader, "").expect_err("invalid memory key");
        assert!(!format!("{derivation_error:?}").contains("sentinel"));
    }

    #[test]
    fn default_fake_construction_performs_zero_reads() {
        let reader = FakeReader::default();
        assert!(reader.read_accounts().is_empty());
    }
}
