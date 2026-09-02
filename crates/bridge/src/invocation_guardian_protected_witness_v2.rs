//! C3 protected-witness contract and monotonic receipt verifier.
//!
//! This is a default-off source contract. It contains no network endpoint,
//! credentials, durable backend, or production constructor. Local fakes can
//! exercise rollback/failover semantics but can never satisfy C3 deployment.

use async_trait::async_trait;

use crate::invocation_guardian_receipt_v2::{
    ExpectedProviderReceipt, ProviderTrustPins, ReceiptDisposition, ReceiptError,
    SignedProviderReceipt, VerifiedProviderReceipt,
};
use crate::invocation_lease_scope::Commitment;

pub const PROTECTED_WITNESS_CONTRACT: &str =
    "agent_bridge.invocation_guardian.protected_witness.v2";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProtectedWitnessRequest {
    pub namespace: String,
    pub token_commitment: Commitment,
    pub exact_scope_commitment: Commitment,
    pub request_challenge: Commitment,
    pub guardian_session_commitment: Commitment,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProtectedWitnessDeny {
    Conflict,
    Exhausted,
    Expired,
    Revoked,
    Indeterminate,
    Hold,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProtectedWitnessReply {
    FreshCommitted(SignedProviderReceipt),
    AlreadyCommitted(SignedProviderReceipt),
    Denied(ProtectedWitnessDeny),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ProtectedWitnessTransportError {
    #[error("deadline")]
    Deadline,
    #[error("cancelled")]
    Cancelled,
    #[error("unavailable")]
    Unavailable,
    #[error("invalid_response")]
    InvalidResponse,
}

#[async_trait]
pub trait ProtectedWitnessTransport: Send + Sync {
    async fn consume_exact(
        &self,
        request: ProtectedWitnessRequest,
    ) -> Result<ProtectedWitnessReply, ProtectedWitnessTransportError>;

    async fn lookup_exact(
        &self,
        request: ProtectedWitnessRequest,
    ) -> Result<ProtectedWitnessReply, ProtectedWitnessTransportError>;
}

/// Dynamic anti-rollback floor retained by the independently operated
/// guardian. The floor is evidence state, never dispatch authority.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProtectedWitnessFloor {
    pub epoch: u64,
    pub revision: u64,
    pub head: Commitment,
    pub provider_time_unix: i64,
}

#[derive(Clone, Debug)]
pub struct ProtectedWitnessVerifierConfig {
    pub pins: ProviderTrustPins,
    pub maximum_past_skew_seconds: i64,
    pub maximum_future_skew_seconds: i64,
}

#[derive(Debug)]
pub enum VerifiedProtectedWitnessReply {
    FreshCommitted {
        receipt: VerifiedProviderReceipt,
        next_floor: ProtectedWitnessFloor,
    },
    AlreadyCommitted {
        receipt: VerifiedProviderReceipt,
        next_floor: ProtectedWitnessFloor,
    },
    Denied(ProtectedWitnessDeny),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ProtectedWitnessVerifyError {
    #[error("invalid_configuration")]
    InvalidConfiguration,
    #[error("receipt:{0}")]
    Receipt(ReceiptError),
    #[error("provider_time_outside_window")]
    ProviderTimeOutsideWindow,
    #[error("provider_time_rollback")]
    ProviderTimeRollback,
    #[error("provider_position_rollback")]
    ProviderPositionRollback,
    #[error("provider_history_fork")]
    ProviderHistoryFork,
    #[error("invalid_epoch_transition")]
    InvalidEpochTransition,
    #[error("invalid_revision_transition")]
    InvalidRevisionTransition,
}

impl From<ReceiptError> for ProtectedWitnessVerifyError {
    fn from(value: ReceiptError) -> Self {
        Self::Receipt(value)
    }
}

pub fn verify_protected_reply(
    reply: ProtectedWitnessReply,
    request: &ProtectedWitnessRequest,
    config: &ProtectedWitnessVerifierConfig,
    floor: &ProtectedWitnessFloor,
    guardian_time_unix: i64,
) -> Result<VerifiedProtectedWitnessReply, ProtectedWitnessVerifyError> {
    if config.maximum_past_skew_seconds < 0
        || config.maximum_future_skew_seconds < 0
        || request.namespace != config.pins.namespace
    {
        return Err(ProtectedWitnessVerifyError::InvalidConfiguration);
    }
    let (signed, disposition) = match reply {
        ProtectedWitnessReply::FreshCommitted(receipt) => {
            (receipt, ReceiptDisposition::FreshCommitted)
        }
        ProtectedWitnessReply::AlreadyCommitted(receipt) => {
            (receipt, ReceiptDisposition::AlreadyCommitted)
        }
        ProtectedWitnessReply::Denied(reason) => {
            return Ok(VerifiedProtectedWitnessReply::Denied(reason));
        }
    };
    let raw = signed.receipt.clone();
    let verified = signed.verify(
        &config.pins,
        &ExpectedProviderReceipt {
            disposition,
            token_commitment: request.token_commitment,
            exact_scope_commitment: request.exact_scope_commitment,
            request_challenge: request.request_challenge,
            guardian_session_commitment: request.guardian_session_commitment,
        },
    )?;
    if raw.provider_time_unix < guardian_time_unix.saturating_sub(config.maximum_past_skew_seconds)
        || raw.provider_time_unix
            > guardian_time_unix.saturating_add(config.maximum_future_skew_seconds)
    {
        return Err(ProtectedWitnessVerifyError::ProviderTimeOutsideWindow);
    }
    if raw.provider_time_unix < floor.provider_time_unix {
        return Err(ProtectedWitnessVerifyError::ProviderTimeRollback);
    }
    let next_floor = validate_monotonic_transition(&raw, disposition, floor)?;
    Ok(match disposition {
        ReceiptDisposition::FreshCommitted => VerifiedProtectedWitnessReply::FreshCommitted {
            receipt: verified,
            next_floor,
        },
        ReceiptDisposition::AlreadyCommitted => VerifiedProtectedWitnessReply::AlreadyCommitted {
            receipt: verified,
            next_floor,
        },
    })
}

fn validate_monotonic_transition(
    receipt: &crate::invocation_guardian_receipt_v2::ProviderReceipt,
    disposition: ReceiptDisposition,
    floor: &ProtectedWitnessFloor,
) -> Result<ProtectedWitnessFloor, ProtectedWitnessVerifyError> {
    if receipt.epoch < floor.epoch
        || (receipt.epoch == floor.epoch && receipt.revision < floor.revision)
    {
        return Err(ProtectedWitnessVerifyError::ProviderPositionRollback);
    }
    if receipt.epoch == floor.epoch && receipt.revision == floor.revision {
        if receipt.new_head != floor.head {
            return Err(ProtectedWitnessVerifyError::ProviderHistoryFork);
        }
        if disposition == ReceiptDisposition::FreshCommitted {
            return Err(ProtectedWitnessVerifyError::InvalidRevisionTransition);
        }
        return Ok(ProtectedWitnessFloor {
            provider_time_unix: receipt.provider_time_unix,
            ..floor.clone()
        });
    }
    if receipt.epoch == floor.epoch {
        if receipt.revision != floor.revision.saturating_add(1)
            || receipt.previous_head != floor.head
        {
            return Err(ProtectedWitnessVerifyError::InvalidRevisionTransition);
        }
    } else if receipt.epoch == floor.epoch.saturating_add(1) {
        if receipt.revision != 1 || receipt.previous_head != floor.head {
            return Err(ProtectedWitnessVerifyError::InvalidEpochTransition);
        }
    } else {
        return Err(ProtectedWitnessVerifyError::InvalidEpochTransition);
    }
    Ok(ProtectedWitnessFloor {
        epoch: receipt.epoch,
        revision: receipt.revision,
        head: receipt.new_head,
        provider_time_unix: receipt.provider_time_unix,
    })
}

/// Production construction remains unavailable until an independently
/// operated provider and its deployment evidence are configured and reviewed.
pub fn production_transport_hold(
) -> Result<Box<dyn ProtectedWitnessTransport>, ProtectedWitnessTransportError> {
    Err(ProtectedWitnessTransportError::Unavailable)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::rand::SystemRandom;
    use ring::signature::{Ed25519KeyPair, KeyPair as _};

    use crate::invocation_guardian_receipt_v2::{
        provider_key_commitment, ProviderReceipt, SignedProviderReceipt,
    };
    use crate::invocation_lease_scope::domain_hash;

    struct Fixture {
        key: Ed25519KeyPair,
        config: ProtectedWitnessVerifierConfig,
        request: ProtectedWitnessRequest,
        floor: ProtectedWitnessFloor,
    }

    impl Fixture {
        fn new() -> Self {
            let document = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
            let key = Ed25519KeyPair::from_pkcs8(document.as_ref()).unwrap();
            let verify_key: [u8; 32] = key.public_key().as_ref().try_into().unwrap();
            let provider_identity_commitment =
                domain_hash(b"c3/provider/identity\0", b"provider-a");
            Self {
                config: ProtectedWitnessVerifierConfig {
                    pins: ProviderTrustPins {
                        provider_key_generation: 7,
                        provider_verify_key: verify_key,
                        provider_key_commitment: provider_key_commitment(&verify_key),
                        provider_identity_commitment,
                        namespace: "canary/c3".into(),
                        minimum_epoch: 4,
                        minimum_revision: 9,
                    },
                    maximum_past_skew_seconds: 30,
                    maximum_future_skew_seconds: 5,
                },
                request: ProtectedWitnessRequest {
                    namespace: "canary/c3".into(),
                    token_commitment: [3; 32],
                    exact_scope_commitment: [4; 32],
                    request_challenge: [5; 32],
                    guardian_session_commitment: [6; 32],
                },
                floor: ProtectedWitnessFloor {
                    epoch: 4,
                    revision: 9,
                    head: [9; 32],
                    provider_time_unix: 990,
                },
                key,
            }
        }

        fn signed(
            &self,
            epoch: u64,
            revision: u64,
            previous_head: Commitment,
            new_head: Commitment,
            time: i64,
            disposition: ReceiptDisposition,
        ) -> SignedProviderReceipt {
            SignedProviderReceipt::sign(
                ProviderReceipt {
                    provider_key_generation: 7,
                    provider_key_commitment: self.config.pins.provider_key_commitment,
                    provider_identity_commitment: self.config.pins.provider_identity_commitment,
                    namespace: self.request.namespace.clone(),
                    epoch,
                    revision,
                    previous_head,
                    new_head,
                    token_commitment: self.request.token_commitment,
                    use_index: 1,
                    exact_scope_commitment: self.request.exact_scope_commitment,
                    request_challenge: self.request.request_challenge,
                    guardian_session_commitment: self.request.guardian_session_commitment,
                    provider_time_unix: time,
                    disposition,
                },
                &self.key,
            )
            .unwrap()
        }
    }

    #[test]
    fn fresh_commit_advances_exactly_one_revision() {
        let fixture = Fixture::new();
        let signed = fixture.signed(
            4,
            10,
            fixture.floor.head,
            [10; 32],
            1_000,
            ReceiptDisposition::FreshCommitted,
        );
        let result = verify_protected_reply(
            ProtectedWitnessReply::FreshCommitted(signed),
            &fixture.request,
            &fixture.config,
            &fixture.floor,
            1_000,
        )
        .unwrap();
        let VerifiedProtectedWitnessReply::FreshCommitted { next_floor, .. } = result else {
            panic!("expected fresh");
        };
        assert_eq!(next_floor.revision, 10);
        assert_eq!(next_floor.head, [10; 32]);
    }

    #[test]
    fn replay_at_current_floor_is_evidence_without_freshness() {
        let fixture = Fixture::new();
        let signed = fixture.signed(
            4,
            9,
            [8; 32],
            fixture.floor.head,
            1_000,
            ReceiptDisposition::AlreadyCommitted,
        );
        let result = verify_protected_reply(
            ProtectedWitnessReply::AlreadyCommitted(signed),
            &fixture.request,
            &fixture.config,
            &fixture.floor,
            1_000,
        )
        .unwrap();
        assert!(matches!(
            result,
            VerifiedProtectedWitnessReply::AlreadyCommitted { .. }
        ));
    }

    #[test]
    fn rollback_fork_time_and_epoch_jump_fail_closed() {
        let fixture = Fixture::new();
        let cases = [
            (
                fixture.signed(
                    4,
                    8,
                    [7; 32],
                    [8; 32],
                    1_000,
                    ReceiptDisposition::AlreadyCommitted,
                ),
                ProtectedWitnessVerifyError::Receipt(ReceiptError::StaleProviderPosition),
            ),
            (
                fixture.signed(
                    4,
                    9,
                    [8; 32],
                    [77; 32],
                    1_000,
                    ReceiptDisposition::AlreadyCommitted,
                ),
                ProtectedWitnessVerifyError::ProviderHistoryFork,
            ),
            (
                fixture.signed(
                    4,
                    10,
                    fixture.floor.head,
                    [10; 32],
                    989,
                    ReceiptDisposition::FreshCommitted,
                ),
                ProtectedWitnessVerifyError::ProviderTimeRollback,
            ),
            (
                fixture.signed(
                    6,
                    1,
                    fixture.floor.head,
                    [10; 32],
                    1_000,
                    ReceiptDisposition::FreshCommitted,
                ),
                ProtectedWitnessVerifyError::InvalidEpochTransition,
            ),
        ];
        for (signed, expected) in cases {
            let reply = if signed.receipt.disposition == ReceiptDisposition::FreshCommitted {
                ProtectedWitnessReply::FreshCommitted(signed)
            } else {
                ProtectedWitnessReply::AlreadyCommitted(signed)
            };
            assert_eq!(
                verify_protected_reply(
                    reply,
                    &fixture.request,
                    &fixture.config,
                    &fixture.floor,
                    1_000
                )
                .unwrap_err(),
                expected
            );
        }
    }

    #[test]
    fn failover_requires_single_epoch_step_and_head_continuity() {
        let fixture = Fixture::new();
        let accepted = fixture.signed(
            5,
            1,
            fixture.floor.head,
            [11; 32],
            1_001,
            ReceiptDisposition::FreshCommitted,
        );
        assert!(verify_protected_reply(
            ProtectedWitnessReply::FreshCommitted(accepted),
            &fixture.request,
            &fixture.config,
            &fixture.floor,
            1_001,
        )
        .is_ok());
        let fork = fixture.signed(
            5,
            1,
            [44; 32],
            [11; 32],
            1_001,
            ReceiptDisposition::FreshCommitted,
        );
        assert_eq!(
            verify_protected_reply(
                ProtectedWitnessReply::FreshCommitted(fork),
                &fixture.request,
                &fixture.config,
                &fixture.floor,
                1_001,
            )
            .unwrap_err(),
            ProtectedWitnessVerifyError::InvalidEpochTransition
        );
    }

    #[test]
    fn denial_and_production_constructor_never_create_authority() {
        let fixture = Fixture::new();
        let denied = verify_protected_reply(
            ProtectedWitnessReply::Denied(ProtectedWitnessDeny::Indeterminate),
            &fixture.request,
            &fixture.config,
            &fixture.floor,
            1_000,
        )
        .unwrap();
        assert!(matches!(
            denied,
            VerifiedProtectedWitnessReply::Denied(ProtectedWitnessDeny::Indeterminate)
        ));
        assert!(matches!(
            production_transport_hold(),
            Err(ProtectedWitnessTransportError::Unavailable)
        ));
    }
}
