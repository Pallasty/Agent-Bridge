//! Ignored, disposable macOS Keychain validation for the accepted C2B reader.
//!
//! This module is test-only and feature-gated. It never updates an existing
//! item: metadata-only preflights must prove both exact accounts absent before
//! the create-only writes begin.

#[cfg(test)]
mod tests {
    use crate::episode_observation_c2_keychain_macos::derive_active_item_ref_from_keychain;
    use ring::rand::{SecureRandom, SystemRandom};
    use security_framework::item::{ItemClass, ItemSearchOptions};
    use security_framework::os::macos::keychain::SecKeychain;
    use security_framework::passwords::delete_generic_password;
    use zeroize::Zeroize;

    const SERVICE: &str = "com.agent-bridge.episode-ref.v1";
    const ACTIVE_EPOCH_ACCOUNT: &str = "active-epoch";
    const MEMORY_KEY: &str = "c2b-live-disposable-memory";
    const ERR_SEC_ITEM_NOT_FOUND: i32 = -25_300;

    fn account_exists_without_data(account: &str) -> Result<bool, ()> {
        let mut query = ItemSearchOptions::new();
        query
            .class(ItemClass::generic_password())
            .service(SERVICE)
            .account(account)
            .load_attributes(true);
        match query.search() {
            Ok(results) => Ok(!results.is_empty()),
            Err(error) if error.code() == ERR_SEC_ITEM_NOT_FOUND => Ok(false),
            Err(_) => Err(()),
        }
    }

    struct CleanupGuard {
        key_account: String,
        key_written: bool,
        active_written: bool,
        cleaned: bool,
    }

    impl CleanupGuard {
        fn new(key_account: String) -> Self {
            Self {
                key_account,
                key_written: false,
                active_written: false,
                cleaned: false,
            }
        }

        fn cleanup(&mut self) -> bool {
            let mut ok = true;
            if self.active_written {
                if delete_generic_password(SERVICE, ACTIVE_EPOCH_ACCOUNT).is_ok() {
                    self.active_written = false;
                } else {
                    ok = false;
                }
            }
            if self.key_written {
                if delete_generic_password(SERVICE, &self.key_account).is_ok() {
                    self.key_written = false;
                } else {
                    ok = false;
                }
            }
            self.cleaned = ok && !self.active_written && !self.key_written;
            self.cleaned
        }
    }

    impl Drop for CleanupGuard {
        fn drop(&mut self) {
            if !self.cleaned {
                let _ = self.cleanup();
            }
        }
    }

    #[test]
    #[ignore = "requires explicit R20 disposable macOS Keychain authorization"]
    fn disposable_keychain_round_trip_cleans_up() {
        let rng = SystemRandom::new();
        let mut suffix = [0_u8; 8];
        rng.fill(&mut suffix)
            .expect("R20 random epoch generation failed");
        let epoch = suffix
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        let epoch = format!("c2b-live-{epoch}");
        suffix.zeroize();
        let key_account = format!("key:{epoch}");

        assert_eq!(
            account_exists_without_data(ACTIVE_EPOCH_ACCOUNT),
            Ok(false),
            "R20 active account preflight was not absent"
        );
        assert_eq!(
            account_exists_without_data(&key_account),
            Ok(false),
            "R20 random key account preflight was not absent"
        );

        let mut guard = CleanupGuard::new(key_account.clone());
        let mut key = [0_u8; 32];
        rng.fill(&mut key)
            .expect("R20 random key generation failed");

        let keychain = SecKeychain::default().expect("R20 default Keychain unavailable");
        let key_write = keychain.add_generic_password(SERVICE, &key_account, &key);
        key.zeroize();
        assert!(key_write.is_ok(), "R20 disposable key create failed");
        guard.key_written = true;

        assert!(
            keychain
                .add_generic_password(SERVICE, ACTIVE_EPOCH_ACCOUNT, epoch.as_bytes())
                .is_ok(),
            "R20 disposable active pointer create failed"
        );
        guard.active_written = true;

        let item_ref = derive_active_item_ref_from_keychain(MEMORY_KEY)
            .expect("R20 accepted reader derivation failed");
        let expected_prefix = format!("epr_v1_{epoch}_");
        assert!(
            item_ref.starts_with(&expected_prefix) && item_ref.len() > expected_prefix.len(),
            "R20 derived item reference shape mismatch"
        );

        assert!(
            guard.cleanup(),
            "R20 cleanup failed; exact public key account: {key_account}"
        );
        assert_eq!(
            account_exists_without_data(ACTIVE_EPOCH_ACCOUNT),
            Ok(false),
            "R20 active account remained after cleanup"
        );
        assert_eq!(
            account_exists_without_data(&key_account),
            Ok(false),
            "R20 key account remained after cleanup: {key_account}"
        );
    }
}
