//! Default-off fake remote-provider laboratory for C3 recovery vectors.
//! Local memory and test keys make this categorically non-production.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use ring::signature::Ed25519KeyPair;

use crate::invocation_guardian_protected_witness_v2::{
    ProtectedWitnessReply, ProtectedWitnessRequest, ProtectedWitnessTransport,
    ProtectedWitnessTransportError,
};
use crate::invocation_guardian_receipt_v2::{
    provider_key_commitment, ProviderReceipt, ReceiptDisposition, SignedProviderReceipt,
};
use crate::invocation_lease_scope::{domain_hash, Commitment};

#[derive(Clone)]
struct CommitRecord {
    epoch: u64,
    revision: u64,
    previous_head: Commitment,
    new_head: Commitment,
    exact_scope_commitment: Commitment,
}

#[derive(Clone)]
struct LabState {
    epoch: u64,
    revision: u64,
    head: Commitment,
    commits: HashMap<Commitment, CommitRecord>,
    lose_next_response: bool,
}

pub(crate) struct FakeRemoteProviderLab {
    namespace: String,
    provider_key_generation: u64,
    provider_key_commitment: Commitment,
    provider_identity_commitment: Commitment,
    signing_key: Arc<Ed25519KeyPair>,
    state: Mutex<LabState>,
}

impl FakeRemoteProviderLab {
    pub(crate) fn new(
        namespace: String,
        epoch: u64,
        head: Commitment,
        provider_key_generation: u64,
        provider_identity_commitment: Commitment,
        signing_key: Arc<Ed25519KeyPair>,
    ) -> Self {
        use ring::signature::KeyPair as _;
        let verify_key: [u8; 32] = signing_key
            .public_key()
            .as_ref()
            .try_into()
            .expect("ed25519 key");
        Self {
            namespace,
            provider_key_generation,
            provider_key_commitment: provider_key_commitment(&verify_key),
            provider_identity_commitment,
            signing_key,
            state: Mutex::new(LabState {
                epoch,
                revision: 0,
                head,
                commits: HashMap::new(),
                lose_next_response: false,
            }),
        }
    }

    pub(crate) fn inject_response_loss_once(&self) {
        self.state.lock().expect("lab mutex").lose_next_response = true;
    }

    pub(crate) fn stale_replica(&self) -> Self {
        Self {
            namespace: self.namespace.clone(),
            provider_key_generation: self.provider_key_generation,
            provider_key_commitment: self.provider_key_commitment,
            provider_identity_commitment: self.provider_identity_commitment,
            signing_key: self.signing_key.clone(),
            state: Mutex::new(self.state.lock().expect("lab mutex").clone()),
        }
    }

    pub(crate) fn failover(&self) {
        let mut state = self.state.lock().expect("lab mutex");
        state.epoch = state.epoch.saturating_add(1);
        state.revision = 0;
    }

    fn signed_reply(
        &self,
        request: &ProtectedWitnessRequest,
        record: &CommitRecord,
        disposition: ReceiptDisposition,
    ) -> Result<SignedProviderReceipt, ProtectedWitnessTransportError> {
        let receipt = ProviderReceipt {
            provider_key_generation: self.provider_key_generation,
            provider_key_commitment: self.provider_key_commitment,
            provider_identity_commitment: self.provider_identity_commitment,
            namespace: self.namespace.clone(),
            epoch: record.epoch,
            revision: record.revision,
            previous_head: record.previous_head,
            new_head: record.new_head,
            token_commitment: request.token_commitment,
            use_index: 1,
            exact_scope_commitment: record.exact_scope_commitment,
            request_challenge: request.request_challenge,
            guardian_session_commitment: request.guardian_session_commitment,
            provider_time_unix: now(),
            disposition,
        };
        SignedProviderReceipt::sign(receipt, &self.signing_key)
            .map_err(|_| ProtectedWitnessTransportError::InvalidResponse)
    }
}

#[async_trait]
impl ProtectedWitnessTransport for FakeRemoteProviderLab {
    async fn consume_exact(
        &self,
        request: ProtectedWitnessRequest,
    ) -> Result<ProtectedWitnessReply, ProtectedWitnessTransportError> {
        if request.namespace != self.namespace {
            return Ok(ProtectedWitnessReply::Denied(
                crate::invocation_guardian_protected_witness_v2::ProtectedWitnessDeny::Hold,
            ));
        }
        let (record, fresh, lose) = {
            let mut state = self
                .state
                .lock()
                .map_err(|_| ProtectedWitnessTransportError::Unavailable)?;
            if let Some(record) = state.commits.get(&request.token_commitment).cloned() {
                if record.exact_scope_commitment != request.exact_scope_commitment {
                    return Ok(ProtectedWitnessReply::Denied(crate::invocation_guardian_protected_witness_v2::ProtectedWitnessDeny::Conflict));
                }
                (record, false, false)
            } else {
                state.revision = state.revision.saturating_add(1);
                let mut material = Vec::new();
                material.extend_from_slice(&state.head);
                material.extend_from_slice(&request.token_commitment);
                material.extend_from_slice(&request.exact_scope_commitment);
                let new_head = domain_hash(
                    b"agent_bridge.invocation_guardian.provider_lab_head.v2\0",
                    &material,
                );
                let record = CommitRecord {
                    epoch: state.epoch,
                    revision: state.revision,
                    previous_head: state.head,
                    new_head,
                    exact_scope_commitment: request.exact_scope_commitment,
                };
                state.head = new_head;
                state
                    .commits
                    .insert(request.token_commitment, record.clone());
                let lose = std::mem::take(&mut state.lose_next_response);
                (record, true, lose)
            }
        };
        if lose {
            return Err(ProtectedWitnessTransportError::Deadline);
        }
        let disposition = if fresh {
            ReceiptDisposition::FreshCommitted
        } else {
            ReceiptDisposition::AlreadyCommitted
        };
        let signed = self.signed_reply(&request, &record, disposition)?;
        Ok(if fresh {
            ProtectedWitnessReply::FreshCommitted(signed)
        } else {
            ProtectedWitnessReply::AlreadyCommitted(signed)
        })
    }

    async fn lookup_exact(
        &self,
        request: ProtectedWitnessRequest,
    ) -> Result<ProtectedWitnessReply, ProtectedWitnessTransportError> {
        let record = self
            .state
            .lock()
            .map_err(|_| ProtectedWitnessTransportError::Unavailable)?
            .commits
            .get(&request.token_commitment)
            .cloned();
        match record {
            Some(record) if record.exact_scope_commitment == request.exact_scope_commitment => {
                Ok(ProtectedWitnessReply::AlreadyCommitted(self.signed_reply(
                    &request,
                    &record,
                    ReceiptDisposition::AlreadyCommitted,
                )?))
            }
            Some(_) => Ok(ProtectedWitnessReply::Denied(
                crate::invocation_guardian_protected_witness_v2::ProtectedWitnessDeny::Conflict,
            )),
            None => Ok(ProtectedWitnessReply::Denied(
                crate::invocation_guardian_protected_witness_v2::ProtectedWitnessDeny::Hold,
            )),
        }
    }
}

fn now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::invocation_guardian_protected_witness_v2::{
        verify_protected_reply, ProtectedWitnessFloor, ProtectedWitnessVerifierConfig,
        ProtectedWitnessVerifyError, VerifiedProtectedWitnessReply,
    };
    use crate::invocation_guardian_receipt_v2::ProviderTrustPins;
    use ring::rand::SystemRandom;
    use ring::signature::KeyPair as _;

    fn request(token: u8) -> ProtectedWitnessRequest {
        ProtectedWitnessRequest {
            namespace: "provider/lab".into(),
            token_commitment: [token; 32],
            exact_scope_commitment: [token.saturating_add(10); 32],
            request_challenge: [token.saturating_add(20); 32],
            guardian_session_commitment: [30; 32],
        }
    }

    fn next_floor(
        reply: ProtectedWitnessReply,
        request: &ProtectedWitnessRequest,
        config: &ProtectedWitnessVerifierConfig,
        floor: &ProtectedWitnessFloor,
    ) -> ProtectedWitnessFloor {
        match verify_protected_reply(reply, request, config, floor, now()).unwrap() {
            VerifiedProtectedWitnessReply::FreshCommitted { next_floor, .. }
            | VerifiedProtectedWitnessReply::AlreadyCommitted { next_floor, .. } => next_floor,
            VerifiedProtectedWitnessReply::Denied(_) => panic!("unexpected denial"),
        }
    }

    #[tokio::test]
    async fn response_loss_stale_replica_and_failover_vectors_fail_closed() {
        let document = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
        let key = Arc::new(Ed25519KeyPair::from_pkcs8(document.as_ref()).unwrap());
        let verify_key: [u8; 32] = key.public_key().as_ref().try_into().unwrap();
        let identity = domain_hash(b"c3/provider/identity\0", b"provider-lab");
        let provider =
            FakeRemoteProviderLab::new("provider/lab".into(), 4, [1; 32], 7, identity, key);
        let config = ProtectedWitnessVerifierConfig {
            pins: ProviderTrustPins {
                provider_key_generation: 7,
                provider_verify_key: verify_key,
                provider_key_commitment: provider_key_commitment(&verify_key),
                provider_identity_commitment: identity,
                namespace: "provider/lab".into(),
                minimum_epoch: 4,
                minimum_revision: 0,
            },
            maximum_past_skew_seconds: 30,
            maximum_future_skew_seconds: 5,
        };
        let mut floor = ProtectedWitnessFloor {
            epoch: 4,
            revision: 0,
            head: [1; 32],
            provider_time_unix: now() - 1,
        };

        let first = request(3);
        provider.inject_response_loss_once();
        assert_eq!(
            provider.consume_exact(first.clone()).await.unwrap_err(),
            ProtectedWitnessTransportError::Deadline
        );
        floor = next_floor(
            provider.lookup_exact(first.clone()).await.unwrap(),
            &first,
            &config,
            &floor,
        );
        assert_eq!(floor.revision, 1);

        let stale = provider.stale_replica();
        let second = request(4);
        floor = next_floor(
            provider.consume_exact(second.clone()).await.unwrap(),
            &second,
            &config,
            &floor,
        );
        assert_eq!(floor.revision, 2);
        let stale_reply = stale.lookup_exact(first.clone()).await.unwrap();
        assert_eq!(
            verify_protected_reply(stale_reply, &first, &config, &floor, now()).unwrap_err(),
            ProtectedWitnessVerifyError::ProviderPositionRollback
        );

        provider.failover();
        let third = request(5);
        floor = next_floor(
            provider.consume_exact(third.clone()).await.unwrap(),
            &third,
            &config,
            &floor,
        );
        assert_eq!((floor.epoch, floor.revision), (5, 1));
    }
}
