//! R27's default-off, disposable C2C live-lab Keychain custody.
//!
//! This module is deliberately separate from the R25 runtime reader.  It can
//! create only the two R26 accounts, only after both metadata-only absence
//! preflights succeed, and its public guard deletes only the accounts that this
//! invocation created.  Nothing here is called by normal Agent-Bridge startup.

use ring::rand::{SecureRandom, SystemRandom};
use security_framework::item::{ItemClass, ItemSearchOptions};
use security_framework::os::macos::keychain::SecKeychain;
use security_framework::passwords::delete_generic_password;
use zeroize::Zeroize;

const SERVICE: &str = "com.agent-bridge.episode-ref.v1";
const ACTIVE_EPOCH_ACCOUNT: &str = "active-epoch";
const ERR_SEC_ITEM_NOT_FOUND: i32 = -25_300;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum C2cLiveLabError {
    Preflight,
    Create,
    Cleanup,
}

trait KeychainIo {
    fn account_exists_without_data(&self, account: &str) -> Result<bool, C2cLiveLabError>;
    fn create_only(&self, account: &str, value: &[u8]) -> Result<(), C2cLiveLabError>;
    fn delete_exact(&self, account: &str) -> Result<(), C2cLiveLabError>;
}

struct MacOsKeychainIo {
    keychain: SecKeychain,
}

impl MacOsKeychainIo {
    fn open() -> Result<Self, C2cLiveLabError> {
        SecKeychain::default()
            .map(|keychain| Self { keychain })
            .map_err(|_| C2cLiveLabError::Preflight)
    }
}

impl KeychainIo for MacOsKeychainIo {
    fn account_exists_without_data(&self, account: &str) -> Result<bool, C2cLiveLabError> {
        let mut query = ItemSearchOptions::new();
        query
            .class(ItemClass::generic_password())
            .service(SERVICE)
            .account(account)
            .load_attributes(true);
        match query.search() {
            Ok(results) => Ok(!results.is_empty()),
            Err(error) if error.code() == ERR_SEC_ITEM_NOT_FOUND => Ok(false),
            Err(_) => Err(C2cLiveLabError::Preflight),
        }
    }

    fn create_only(&self, account: &str, value: &[u8]) -> Result<(), C2cLiveLabError> {
        self.keychain
            .add_generic_password(SERVICE, account, value)
            .map_err(|_| C2cLiveLabError::Create)
    }

    fn delete_exact(&self, account: &str) -> Result<(), C2cLiveLabError> {
        delete_generic_password(SERVICE, account).map_err(|_| C2cLiveLabError::Cleanup)
    }
}

#[derive(Debug)]
struct CustodyState {
    key_account: String,
    key_written: bool,
    active_written: bool,
    cleaned: bool,
}

impl CustodyState {
    fn new(key_account: String) -> Self {
        Self {
            key_account,
            key_written: false,
            active_written: false,
            cleaned: false,
        }
    }
}

fn random_epoch(rng: &SystemRandom) -> Result<String, C2cLiveLabError> {
    let mut suffix = [0_u8; 8];
    rng.fill(&mut suffix).map_err(|_| C2cLiveLabError::Create)?;
    let mut suffix = suffix
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    let epoch = format!("c2c-live-{suffix}");
    suffix.zeroize();
    Ok(epoch)
}

fn valid_epoch(epoch: &str) -> bool {
    epoch.len() == "c2c-live-".len() + 16
        && epoch.starts_with("c2c-live-")
        && epoch["c2c-live-".len()..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn prepare_with(
    io: &impl KeychainIo,
    epoch: &str,
    key: &[u8],
) -> Result<CustodyState, C2cLiveLabError> {
    if !valid_epoch(epoch) || key.len() != 32 {
        return Err(C2cLiveLabError::Preflight);
    }
    let key_account = format!("key:{epoch}");
    if io.account_exists_without_data(ACTIVE_EPOCH_ACCOUNT)?
        || io.account_exists_without_data(&key_account)?
    {
        return Err(C2cLiveLabError::Preflight);
    }

    let mut state = CustodyState::new(key_account);
    io.create_only(&state.key_account, key)?;
    state.key_written = true;
    if io
        .create_only(ACTIVE_EPOCH_ACCOUNT, epoch.as_bytes())
        .is_err()
    {
        let _ = cleanup_with(io, &mut state);
        return Err(C2cLiveLabError::Create);
    }
    state.active_written = true;
    Ok(state)
}

fn cleanup_with(io: &impl KeychainIo, state: &mut CustodyState) -> Result<(), C2cLiveLabError> {
    if state.active_written {
        io.delete_exact(ACTIVE_EPOCH_ACCOUNT)?;
        state.active_written = false;
    }
    if state.key_written {
        io.delete_exact(&state.key_account)?;
        state.key_written = false;
    }
    if io.account_exists_without_data(ACTIVE_EPOCH_ACCOUNT)?
        || io.account_exists_without_data(&state.key_account)?
    {
        return Err(C2cLiveLabError::Cleanup);
    }
    state.cleaned = true;
    Ok(())
}

/// Owns only the two disposable R26 accounts after successful preparation.
///
/// Calling [`Self::prepare`] is a live Keychain action.  The R27 source gate
/// compiles and unit-tests this module through fake I/O; it does not call this
/// method.  The driver separately requires its explicit execution flag.
pub struct C2cLiveLabCustody {
    io: MacOsKeychainIo,
    state: CustodyState,
}

impl C2cLiveLabCustody {
    pub fn prepare() -> Result<Self, C2cLiveLabError> {
        let io = MacOsKeychainIo::open()?;
        let rng = SystemRandom::new();
        let epoch = random_epoch(&rng)?;
        let mut key = [0_u8; 32];
        let result = rng
            .fill(&mut key)
            .map_err(|_| C2cLiveLabError::Create)
            .and_then(|_| prepare_with(&io, &epoch, &key));
        key.zeroize();
        result.map(|state| Self { io, state })
    }

    pub fn key_account(&self) -> &str {
        &self.state.key_account
    }

    pub fn cleanup(&mut self) -> Result<(), C2cLiveLabError> {
        cleanup_with(&self.io, &mut self.state)
    }
}

impl Drop for C2cLiveLabCustody {
    fn drop(&mut self) {
        if !self.state.cleaned {
            let _ = cleanup_with(&self.io, &mut self.state);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::collections::BTreeSet;

    #[derive(Default)]
    struct FakeKeychain {
        accounts: RefCell<BTreeSet<String>>,
        calls: RefCell<Vec<String>>,
        fail_active_create: bool,
        fail_delete: bool,
    }

    impl KeychainIo for FakeKeychain {
        fn account_exists_without_data(&self, account: &str) -> Result<bool, C2cLiveLabError> {
            self.calls.borrow_mut().push(format!("exists:{account}"));
            Ok(self.accounts.borrow().contains(account))
        }
        fn create_only(&self, account: &str, value: &[u8]) -> Result<(), C2cLiveLabError> {
            self.calls
                .borrow_mut()
                .push(format!("create:{account}:{}", value.len()));
            if self.fail_active_create && account == ACTIVE_EPOCH_ACCOUNT {
                return Err(C2cLiveLabError::Create);
            }
            self.accounts.borrow_mut().insert(account.to_owned());
            Ok(())
        }
        fn delete_exact(&self, account: &str) -> Result<(), C2cLiveLabError> {
            self.calls.borrow_mut().push(format!("delete:{account}"));
            if self.fail_delete {
                return Err(C2cLiveLabError::Cleanup);
            }
            self.accounts.borrow_mut().remove(account);
            Ok(())
        }
    }

    #[test]
    fn fake_custody_is_create_only_and_cleans_pointer_before_key() {
        let io = FakeKeychain::default();
        let epoch = "c2c-live-0123456789abcdef";
        let mut state = prepare_with(&io, epoch, &[7; 32]).expect("prepare");
        assert_eq!(state.key_account, "key:c2c-live-0123456789abcdef");
        cleanup_with(&io, &mut state).expect("cleanup");
        assert!(state.cleaned);
        assert_eq!(
            *io.calls.borrow(),
            vec![
                "exists:active-epoch",
                "exists:key:c2c-live-0123456789abcdef",
                "create:key:c2c-live-0123456789abcdef:32",
                "create:active-epoch:25",
                "delete:active-epoch",
                "delete:key:c2c-live-0123456789abcdef",
                "exists:active-epoch",
                "exists:key:c2c-live-0123456789abcdef",
            ]
        );
    }

    #[test]
    fn existing_account_blocks_before_any_create() {
        let io = FakeKeychain::default();
        io.accounts
            .borrow_mut()
            .insert(ACTIVE_EPOCH_ACCOUNT.to_owned());
        assert!(matches!(
            prepare_with(&io, "c2c-live-0123456789abcdef", &[7; 32]),
            Err(C2cLiveLabError::Preflight)
        ));
        assert!(io
            .calls
            .borrow()
            .iter()
            .all(|call| !call.starts_with("create:")));
    }

    #[test]
    fn raw_suffix_cannot_diverge_from_the_prefixed_active_epoch() {
        let io = FakeKeychain::default();
        assert!(matches!(
            prepare_with(&io, "0123456789abcdef", &[7; 32]),
            Err(C2cLiveLabError::Preflight)
        ));
        assert!(io
            .calls
            .borrow()
            .iter()
            .all(|call| !call.starts_with("create:")));
    }

    #[test]
    fn active_create_failure_removes_only_created_key() {
        let io = FakeKeychain {
            fail_active_create: true,
            ..Default::default()
        };
        assert!(matches!(
            prepare_with(&io, "c2c-live-0123456789abcdef", &[7; 32]),
            Err(C2cLiveLabError::Create)
        ));
        assert!(io.accounts.borrow().is_empty());
        assert!(io
            .calls
            .borrow()
            .iter()
            .any(|call| call == "delete:key:c2c-live-0123456789abcdef"));
    }
}
