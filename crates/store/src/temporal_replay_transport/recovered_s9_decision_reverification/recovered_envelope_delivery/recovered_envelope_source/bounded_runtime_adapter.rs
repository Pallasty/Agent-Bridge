//! S15 private bounded runtime-shaped adapter kernel.
//!
//! This module adds an executable exact-open/read/complete state surface for
//! the S14 source trait. It contains no concrete transport, persistence,
//! network, production transport constructor, currentness, admission, or side
//! effect.

#![cfg_attr(not(test), allow(dead_code))]

use super::{
    recovered_source_seal, BoundedRecoveredSourceRecordV1, ExactRecoveredEnvelopeLookupV1,
    ExternalRecoveredEnvelopeSourceFailureV1, ExternalRecoveredEnvelopeSourceV1,
    MAX_SOURCE_RECORD_BYTES,
};
use sha2::{Digest, Sha256};
use std::cell::{Cell, RefCell};
use std::fmt;

#[cfg(feature = "temporal-evidence-s16-recovered-envelope-durability-fault-model-synthetic")]
mod durability_fault_model;

const POLICY_ID: &str = "agent-bridge/track-b/recovered-envelope-bounded-runtime-adapter/v1";
const PROFILE: &str =
    "PRIVATE_ONE_SHOT_EXACT_OPEN_FIXED_BUFFER_RAW_BYTES_UNTRUSTED_COMPLETION_HISTORICAL_ONLY";
const LOOKUP_COMMITMENT_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-bounded-runtime-adapter/exact-lookup/v1";
const MAX_RUNTIME_READ_BUFFER_BYTES: usize = 16 * 1024;
const MAX_RUNTIME_DATA_STEPS: usize = 1024;

const S14_CONTRACT_SHA256: [u8; 32] = [
    0xba, 0x10, 0xe9, 0xf4, 0x33, 0x29, 0x4e, 0x8d, 0x9f, 0x50, 0xf3, 0x34, 0x2f, 0x04, 0xec, 0x14,
    0x0f, 0xf2, 0xf7, 0xfc, 0xe8, 0xe3, 0xf2, 0xc0, 0x21, 0x30, 0xa5, 0xa0, 0xb4, 0xf9, 0x28, 0x99,
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RuntimeExactReadFailureV1 {
    NotFound,
    Pending,
    Conflict,
    Stale,
    Rollback,
    Unavailable,
    Unauthenticated,
    Malformed,
    Indeterminate,
}

#[must_use]
struct RuntimeExactReadCompletionV1 {
    lookup_commitment_sha256: [u8; 32],
    object_revision: u64,
    record_len: u64,
    record_sha256: [u8; 32],
}

impl fmt::Debug for RuntimeExactReadCompletionV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("RuntimeExactReadCompletionV1")
            .field("scope", &"[UNTRUSTED_COMPLETION_METADATA_REDACTED]")
            .finish_non_exhaustive()
    }
}

enum RuntimeExactReadStepV1 {
    Data(usize),
    Complete(RuntimeExactReadCompletionV1),
}

mod runtime_transport_seal {
    pub(super) trait Sealed {}
}

/// Private runtime-shaped byte source. Implementations can only be added in
/// this module subtree; no concrete implementation exists outside tests.
trait RuntimeExactRecoveredEnvelopeTransportV1: runtime_transport_seal::Sealed {
    fn open_exact(
        &mut self,
        lookup: &ExactRecoveredEnvelopeLookupV1,
    ) -> Result<(), RuntimeExactReadFailureV1>;

    fn read_into(
        &mut self,
        destination: &mut [u8],
    ) -> Result<RuntimeExactReadStepV1, RuntimeExactReadFailureV1>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum AdapterStateV1 {
    Fresh,
    Opening,
    Streaming,
    Completed,
    TerminalFailed,
}

/// One-shot local adapter state. The one-shot property is not a global replay
/// fence and says nothing about a future transport's external durability.
struct BoundedRuntimeRecoveredEnvelopeAdapterV1<T> {
    transport: RefCell<T>,
    state: Cell<AdapterStateV1>,
}

impl<T> fmt::Debug for BoundedRuntimeRecoveredEnvelopeAdapterV1<T> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("BoundedRuntimeRecoveredEnvelopeAdapterV1")
            .field("scope", &"[ONE_SHOT_RUNTIME_ADAPTER_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl<T> BoundedRuntimeRecoveredEnvelopeAdapterV1<T> {
    #[cfg(test)]
    fn new(transport: T) -> Self {
        Self {
            transport: RefCell::new(transport),
            state: Cell::new(AdapterStateV1::Fresh),
        }
    }
}

impl<T: RuntimeExactRecoveredEnvelopeTransportV1> recovered_source_seal::Sealed
    for BoundedRuntimeRecoveredEnvelopeAdapterV1<T>
{
}

impl<T: RuntimeExactRecoveredEnvelopeTransportV1> ExternalRecoveredEnvelopeSourceV1
    for BoundedRuntimeRecoveredEnvelopeAdapterV1<T>
{
    fn read_exact(
        &self,
        lookup: &ExactRecoveredEnvelopeLookupV1,
        sink: &mut BoundedRecoveredSourceRecordV1,
    ) -> Result<(), ExternalRecoveredEnvelopeSourceFailureV1> {
        if self.state.replace(AdapterStateV1::Opening) != AdapterStateV1::Fresh {
            self.state.set(AdapterStateV1::TerminalFailed);
            return Err(ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate);
        }

        match self.read_once(lookup, sink) {
            Ok(()) if self.state.get() == AdapterStateV1::Streaming => {
                self.state.set(AdapterStateV1::Completed);
                Ok(())
            }
            Ok(()) => {
                self.state.set(AdapterStateV1::TerminalFailed);
                Err(ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate)
            }
            Err(error) => {
                self.state.set(AdapterStateV1::TerminalFailed);
                Err(error)
            }
        }
    }
}

impl<T: RuntimeExactRecoveredEnvelopeTransportV1> BoundedRuntimeRecoveredEnvelopeAdapterV1<T> {
    fn read_once(
        &self,
        lookup: &ExactRecoveredEnvelopeLookupV1,
        sink: &mut BoundedRecoveredSourceRecordV1,
    ) -> Result<(), ExternalRecoveredEnvelopeSourceFailureV1> {
        let mut transport = self
            .transport
            .try_borrow_mut()
            .map_err(|_| ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate)?;
        transport
            .open_exact(lookup)
            .map_err(map_transport_failure)?;
        if self.state.get() != AdapterStateV1::Opening {
            return Err(ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate);
        }
        self.state.set(AdapterStateV1::Streaming);

        let lookup_commitment_sha256 = exact_lookup_commitment_v1(lookup);
        let mut hasher = Sha256::new();
        let mut observed_len = 0usize;
        let mut data_steps = 0usize;
        let mut buffer = [0u8; MAX_RUNTIME_READ_BUFFER_BYTES];

        loop {
            let step = transport
                .read_into(&mut buffer)
                .map_err(map_transport_failure)?;
            if self.state.get() != AdapterStateV1::Streaming {
                return Err(ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate);
            }
            match step {
                RuntimeExactReadStepV1::Data(written) => {
                    if written == 0 || written > buffer.len() {
                        return Err(ExternalRecoveredEnvelopeSourceFailureV1::Malformed);
                    }
                    if data_steps == MAX_RUNTIME_DATA_STEPS {
                        return Err(ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate);
                    }
                    data_steps += 1;
                    observed_len = observed_len
                        .checked_add(written)
                        .ok_or(ExternalRecoveredEnvelopeSourceFailureV1::Malformed)?;
                    if observed_len > MAX_SOURCE_RECORD_BYTES {
                        return Err(ExternalRecoveredEnvelopeSourceFailureV1::Malformed);
                    }
                    sink.push_chunk(&buffer[..written])
                        .map_err(|_| ExternalRecoveredEnvelopeSourceFailureV1::Malformed)?;
                    hasher.update(&buffer[..written]);
                }
                RuntimeExactReadStepV1::Complete(completion) => {
                    if observed_len == 0 {
                        return Err(ExternalRecoveredEnvelopeSourceFailureV1::Malformed);
                    }
                    let observed_sha256: [u8; 32] = hasher.finalize().into();
                    if completion.lookup_commitment_sha256 != lookup_commitment_sha256
                        || completion.object_revision != lookup.object_revision
                        || completion.record_len
                            != u64::try_from(observed_len)
                                .map_err(|_| ExternalRecoveredEnvelopeSourceFailureV1::Malformed)?
                        || completion.record_sha256 != observed_sha256
                        || observed_sha256 != lookup.expected_record_sha256
                    {
                        return Err(ExternalRecoveredEnvelopeSourceFailureV1::Conflict);
                    }
                    return Ok(());
                }
            }
        }
    }
}

fn map_transport_failure(
    failure: RuntimeExactReadFailureV1,
) -> ExternalRecoveredEnvelopeSourceFailureV1 {
    match failure {
        RuntimeExactReadFailureV1::NotFound => ExternalRecoveredEnvelopeSourceFailureV1::NotFound,
        RuntimeExactReadFailureV1::Pending => ExternalRecoveredEnvelopeSourceFailureV1::Pending,
        RuntimeExactReadFailureV1::Conflict => ExternalRecoveredEnvelopeSourceFailureV1::Conflict,
        RuntimeExactReadFailureV1::Stale => ExternalRecoveredEnvelopeSourceFailureV1::Stale,
        RuntimeExactReadFailureV1::Rollback => ExternalRecoveredEnvelopeSourceFailureV1::Rollback,
        RuntimeExactReadFailureV1::Unavailable => {
            ExternalRecoveredEnvelopeSourceFailureV1::Unavailable
        }
        RuntimeExactReadFailureV1::Unauthenticated => {
            ExternalRecoveredEnvelopeSourceFailureV1::Unauthenticated
        }
        RuntimeExactReadFailureV1::Malformed => ExternalRecoveredEnvelopeSourceFailureV1::Malformed,
        RuntimeExactReadFailureV1::Indeterminate => {
            ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate
        }
    }
}

fn hash_frame(hasher: &mut Sha256, value: &[u8]) {
    hasher.update(u64::try_from(value.len()).unwrap_or(u64::MAX).to_be_bytes());
    hasher.update(value);
}

fn exact_lookup_commitment_v1(lookup: &ExactRecoveredEnvelopeLookupV1) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hash_frame(&mut hasher, LOOKUP_COMMITMENT_DOMAIN);
    hash_frame(&mut hasher, POLICY_ID.as_bytes());
    hash_frame(&mut hasher, PROFILE.as_bytes());
    hash_frame(&mut hasher, &S14_CONTRACT_SHA256);
    hash_frame(&mut hasher, lookup.source_profile_id.as_bytes());
    hash_frame(&mut hasher, lookup.source_namespace_id.as_bytes());
    hash_frame(&mut hasher, lookup.tenant_id.as_bytes());
    hash_frame(&mut hasher, lookup.audience.as_bytes());
    hash_frame(&mut hasher, lookup.source_cluster_id.as_bytes());
    hash_frame(&mut hasher, &lookup.source_incarnation);
    hash_frame(&mut hasher, &lookup.source_generation_id);
    hash_frame(&mut hasher, &lookup.object_id);
    hash_frame(&mut hasher, &lookup.object_revision.to_be_bytes());
    hash_frame(&mut hasher, &lookup.expected_record_sha256);
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::super::tests::s15_fixture_parts;
    use super::*;
    use std::collections::VecDeque;
    use std::rc::{Rc, Weak};

    const LOOKUP_KAT: [u8; 32] = [
        0x86, 0x6e, 0x01, 0x6c, 0xe6, 0x31, 0x43, 0x3e, 0x3e, 0x27, 0x2d, 0x08, 0x58, 0x90, 0x6f,
        0x3c, 0x76, 0xc6, 0x72, 0x04, 0xcd, 0x74, 0xb7, 0x3a, 0xb1, 0x1b, 0x73, 0x53, 0xe5, 0x7e,
        0xae, 0x00,
    ];

    enum ScriptStep {
        Data(Vec<u8>),
        Reported(usize),
        Complete(RuntimeExactReadCompletionV1),
        Fail(RuntimeExactReadFailureV1),
    }

    struct ScriptedTransport {
        expected_open_lookup: [u8; 32],
        open_failure: Option<RuntimeExactReadFailureV1>,
        steps: VecDeque<ScriptStep>,
        opens: usize,
        reads: usize,
        completions: usize,
    }

    impl ScriptedTransport {
        fn new(lookup: &ExactRecoveredEnvelopeLookupV1, steps: Vec<ScriptStep>) -> Self {
            Self {
                expected_open_lookup: exact_lookup_commitment_v1(lookup),
                open_failure: None,
                steps: steps.into(),
                opens: 0,
                reads: 0,
                completions: 0,
            }
        }

        fn bytes(lookup: &ExactRecoveredEnvelopeLookupV1, bytes: &[u8], chunk_size: usize) -> Self {
            let mut steps = bytes
                .chunks(chunk_size.max(1))
                .map(|chunk| ScriptStep::Data(chunk.to_vec()))
                .collect::<Vec<_>>();
            steps.push(ScriptStep::Complete(completion_for(lookup, bytes)));
            Self::new(lookup, steps)
        }

        fn open_failure(
            lookup: &ExactRecoveredEnvelopeLookupV1,
            failure: RuntimeExactReadFailureV1,
        ) -> Self {
            let mut output = Self::new(lookup, Vec::new());
            output.open_failure = Some(failure);
            output
        }
    }

    impl runtime_transport_seal::Sealed for ScriptedTransport {}

    impl RuntimeExactRecoveredEnvelopeTransportV1 for ScriptedTransport {
        fn open_exact(
            &mut self,
            lookup: &ExactRecoveredEnvelopeLookupV1,
        ) -> Result<(), RuntimeExactReadFailureV1> {
            self.opens += 1;
            if let Some(failure) = self.open_failure {
                return Err(failure);
            }
            if exact_lookup_commitment_v1(lookup) != self.expected_open_lookup {
                return Err(RuntimeExactReadFailureV1::Conflict);
            }
            Ok(())
        }

        fn read_into(
            &mut self,
            destination: &mut [u8],
        ) -> Result<RuntimeExactReadStepV1, RuntimeExactReadFailureV1> {
            self.reads += 1;
            match self.steps.pop_front() {
                Some(ScriptStep::Data(bytes)) => {
                    if bytes.len() > destination.len() {
                        return Ok(RuntimeExactReadStepV1::Data(bytes.len()));
                    }
                    destination[..bytes.len()].copy_from_slice(&bytes);
                    Ok(RuntimeExactReadStepV1::Data(bytes.len()))
                }
                Some(ScriptStep::Reported(written)) => Ok(RuntimeExactReadStepV1::Data(written)),
                Some(ScriptStep::Complete(completion)) => {
                    self.completions += 1;
                    Ok(RuntimeExactReadStepV1::Complete(completion))
                }
                Some(ScriptStep::Fail(failure)) => Err(failure),
                None => Err(RuntimeExactReadFailureV1::Indeterminate),
            }
        }
    }

    #[derive(Clone, Copy)]
    enum ReentryCut {
        Open,
        Read,
    }

    struct ReentrantTransport {
        target: RefCell<Weak<BoundedRuntimeRecoveredEnvelopeAdapterV1<Self>>>,
        cut: ReentryCut,
        nested_attempts: Cell<usize>,
    }

    impl ReentrantTransport {
        fn invoke_nested(&self, lookup: &ExactRecoveredEnvelopeLookupV1) {
            let target = self.target.borrow().upgrade().unwrap();
            let mut nested_sink = BoundedRecoveredSourceRecordV1::new();
            assert!(target.read_exact(lookup, &mut nested_sink).is_err());
            self.nested_attempts.set(self.nested_attempts.get() + 1);
        }
    }

    impl runtime_transport_seal::Sealed for ReentrantTransport {}

    impl RuntimeExactRecoveredEnvelopeTransportV1 for ReentrantTransport {
        fn open_exact(
            &mut self,
            lookup: &ExactRecoveredEnvelopeLookupV1,
        ) -> Result<(), RuntimeExactReadFailureV1> {
            if matches!(self.cut, ReentryCut::Open) {
                self.invoke_nested(lookup);
            }
            Ok(())
        }

        fn read_into(
            &mut self,
            _destination: &mut [u8],
        ) -> Result<RuntimeExactReadStepV1, RuntimeExactReadFailureV1> {
            if matches!(self.cut, ReentryCut::Read) {
                let target = self.target.borrow().upgrade().unwrap();
                let lookup = lookup_for_bytes(b"reentry");
                let mut nested_sink = BoundedRecoveredSourceRecordV1::new();
                assert!(target.read_exact(&lookup, &mut nested_sink).is_err());
                self.nested_attempts.set(self.nested_attempts.get() + 1);
            }
            Ok(RuntimeExactReadStepV1::Data(1))
        }
    }

    fn completion_for(
        lookup: &ExactRecoveredEnvelopeLookupV1,
        bytes: &[u8],
    ) -> RuntimeExactReadCompletionV1 {
        RuntimeExactReadCompletionV1 {
            lookup_commitment_sha256: exact_lookup_commitment_v1(lookup),
            object_revision: lookup.object_revision,
            record_len: u64::try_from(bytes.len()).unwrap(),
            record_sha256: super::super::sha256_bytes(bytes),
        }
    }

    fn direct_read(
        adapter: &BoundedRuntimeRecoveredEnvelopeAdapterV1<ScriptedTransport>,
        lookup: &ExactRecoveredEnvelopeLookupV1,
    ) -> Result<Box<[u8]>, ExternalRecoveredEnvelopeSourceFailureV1> {
        let mut sink = BoundedRecoveredSourceRecordV1::new();
        adapter.read_exact(lookup, &mut sink)?;
        sink.finish()
            .map_err(|_| ExternalRecoveredEnvelopeSourceFailureV1::Malformed)
    }

    fn lookup_for_bytes(bytes: &[u8]) -> ExactRecoveredEnvelopeLookupV1 {
        ExactRecoveredEnvelopeLookupV1::try_new(
            "durable-source-profile-a",
            "durable-source-namespace-a",
            "tenant-a",
            "agent-bridge",
            "durable-source-cluster-a",
            [0x81; 32],
            [0x82; 32],
            [0x83; 32],
            17,
            super::super::sha256_bytes(bytes),
        )
        .unwrap()
    }

    #[test]
    fn s15_lookup_commitment_and_full_historical_chain_are_stable() {
        let (record, lookup, source_permit, base, s10_permit) = s15_fixture_parts();
        assert_eq!(exact_lookup_commitment_v1(&lookup), LOOKUP_KAT);
        let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::bytes(
            &lookup, &record, 113,
        ));
        let result = super::super::recover_historical_from_external_source_v1(
            &adapter,
            lookup,
            &source_permit,
            &base.s9_permit,
            &s10_permit,
            &base.s11_request,
            &base.s11_permit,
            &base.s11_record,
        )
        .unwrap();
        assert_eq!(
            result.historical_source_chain_sha256,
            [
                0xd2, 0x9d, 0xa2, 0xa0, 0x81, 0xb0, 0x9b, 0x2b, 0x12, 0x42, 0x98, 0xea, 0xe4, 0x0b,
                0x15, 0xad, 0xa5, 0x55, 0x19, 0x6c, 0xc5, 0xe3, 0xfd, 0x52, 0xd8, 0xe4, 0xdf, 0xad,
                0xf3, 0xf2, 0x14, 0x9b,
            ]
        );
        let transport = adapter.transport.borrow();
        assert_eq!((transport.opens, transport.completions), (1, 1));
        assert_eq!(adapter.state.get(), AdapterStateV1::Completed);
    }

    #[test]
    fn s15_every_two_chunk_cut_preserves_exact_bytes() {
        let bytes = (0..257).map(|value| value as u8).collect::<Vec<_>>();
        let lookup = lookup_for_bytes(&bytes);
        for cut in 0..=bytes.len() {
            let mut steps = Vec::new();
            if cut != 0 {
                steps.push(ScriptStep::Data(bytes[..cut].to_vec()));
            }
            if cut != bytes.len() {
                steps.push(ScriptStep::Data(bytes[cut..].to_vec()));
            }
            steps.push(ScriptStep::Complete(completion_for(&lookup, &bytes)));
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::new(
                &lookup, steps,
            ));
            assert_eq!(direct_read(&adapter, &lookup).unwrap().as_ref(), bytes);
        }
    }

    #[test]
    fn s15_every_partial_cut_failure_is_terminal_without_retry() {
        let bytes = (0..97).map(|value| value as u8).collect::<Vec<_>>();
        let lookup = lookup_for_bytes(&bytes);
        for cut in 0..=bytes.len() {
            let mut steps = Vec::new();
            if cut != 0 {
                steps.push(ScriptStep::Data(bytes[..cut].to_vec()));
            }
            steps.push(ScriptStep::Fail(RuntimeExactReadFailureV1::Unavailable));
            steps.push(ScriptStep::Complete(completion_for(&lookup, &bytes)));
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::new(
                &lookup, steps,
            ));
            assert!(direct_read(&adapter, &lookup).is_err());
            let transport = adapter.transport.borrow();
            assert_eq!(transport.opens, 1);
            assert_eq!(transport.completions, 0);
            assert_eq!(adapter.state.get(), AdapterStateV1::TerminalFailed);
        }
    }

    #[test]
    fn s15_second_read_and_opening_reentry_are_terminal_without_second_open() {
        let bytes = b"one-shot".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::bytes(
            &lookup, &bytes, 3,
        ));
        assert!(direct_read(&adapter, &lookup).is_ok());
        assert!(direct_read(&adapter, &lookup).is_err());
        assert_eq!(adapter.transport.borrow().opens, 1);

        let other = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::bytes(
            &lookup, &bytes, 3,
        ));
        other.state.set(AdapterStateV1::Opening);
        assert!(direct_read(&other, &lookup).is_err());
        assert_eq!(other.transport.borrow().opens, 0);
    }

    #[test]
    fn s15_real_open_or_read_callback_reentry_cannot_restore_outer_success() {
        let bytes = b"reentry".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        for cut in [ReentryCut::Open, ReentryCut::Read] {
            let adapter = Rc::new(BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
                ReentrantTransport {
                    target: RefCell::new(Weak::new()),
                    cut,
                    nested_attempts: Cell::new(0),
                },
            ));
            *adapter.transport.borrow().target.borrow_mut() = Rc::downgrade(&adapter);
            let mut sink = BoundedRecoveredSourceRecordV1::new();
            assert!(adapter.read_exact(&lookup, &mut sink).is_err());
            assert_eq!(adapter.state.get(), AdapterStateV1::TerminalFailed);
            assert_eq!(adapter.transport.borrow().nested_attempts.get(), 1);
        }
    }

    #[test]
    fn s15_open_and_read_failure_matrix_never_retries() {
        let bytes = b"failure-matrix".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        let failures = [
            RuntimeExactReadFailureV1::NotFound,
            RuntimeExactReadFailureV1::Pending,
            RuntimeExactReadFailureV1::Conflict,
            RuntimeExactReadFailureV1::Stale,
            RuntimeExactReadFailureV1::Rollback,
            RuntimeExactReadFailureV1::Unavailable,
            RuntimeExactReadFailureV1::Unauthenticated,
            RuntimeExactReadFailureV1::Malformed,
            RuntimeExactReadFailureV1::Indeterminate,
        ];
        for failure in failures {
            let open_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
                ScriptedTransport::open_failure(&lookup, failure),
            );
            assert!(direct_read(&open_adapter, &lookup).is_err());
            assert_eq!(open_adapter.transport.borrow().opens, 1);
            assert_eq!(open_adapter.transport.borrow().reads, 0);

            let read_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
                ScriptedTransport::new(&lookup, vec![ScriptStep::Fail(failure)]),
            );
            assert!(direct_read(&read_adapter, &lookup).is_err());
            assert_eq!(read_adapter.transport.borrow().opens, 1);
            assert_eq!(read_adapter.transport.borrow().reads, 1);
        }
    }

    #[test]
    fn s15_zero_progress_oversize_and_empty_completion_fail() {
        let bytes = b"bounds".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        let cases = vec![
            vec![ScriptStep::Reported(0)],
            vec![ScriptStep::Reported(MAX_RUNTIME_READ_BUFFER_BYTES + 1)],
            vec![ScriptStep::Complete(RuntimeExactReadCompletionV1 {
                lookup_commitment_sha256: exact_lookup_commitment_v1(&lookup),
                object_revision: lookup.object_revision,
                record_len: 0,
                record_sha256: super::super::sha256_bytes(&[]),
            })],
        ];
        for steps in cases {
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::new(
                &lookup, steps,
            ));
            assert!(direct_read(&adapter, &lookup).is_err());
            assert_eq!(adapter.state.get(), AdapterStateV1::TerminalFailed);
        }
    }

    #[test]
    fn s15_1024_data_steps_then_completion_passes_and_1025th_data_fails() {
        let accepted = vec![0x5a; MAX_RUNTIME_DATA_STEPS];
        let accepted_lookup = lookup_for_bytes(&accepted);
        let accepted_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
            ScriptedTransport::bytes(&accepted_lookup, &accepted, 1),
        );
        assert!(direct_read(&accepted_adapter, &accepted_lookup).is_ok());
        assert_eq!(accepted_adapter.transport.borrow().reads, 1025);

        let rejected = vec![0x5a; MAX_RUNTIME_DATA_STEPS + 1];
        let rejected_lookup = lookup_for_bytes(&rejected);
        let rejected_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
            ScriptedTransport::bytes(&rejected_lookup, &rejected, 1),
        );
        assert!(direct_read(&rejected_adapter, &rejected_lookup).is_err());
        assert_eq!(rejected_adapter.transport.borrow().reads, 1025);
        assert_eq!(rejected_adapter.transport.borrow().completions, 0);
    }

    #[test]
    fn s15_total_cap_exact_passes_and_cap_plus_one_fails_before_completion() {
        let exact = vec![0x41; MAX_SOURCE_RECORD_BYTES];
        let exact_lookup = lookup_for_bytes(&exact);
        let exact_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
            ScriptedTransport::bytes(&exact_lookup, &exact, MAX_RUNTIME_READ_BUFFER_BYTES),
        );
        assert_eq!(
            direct_read(&exact_adapter, &exact_lookup).unwrap().len(),
            exact.len()
        );

        let oversized = vec![0x41; MAX_SOURCE_RECORD_BYTES + 1];
        let oversized_lookup = lookup_for_bytes(&oversized);
        let oversized_adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
            ScriptedTransport::bytes(&oversized_lookup, &oversized, MAX_RUNTIME_READ_BUFFER_BYTES),
        );
        assert!(direct_read(&oversized_adapter, &oversized_lookup).is_err());
        assert_eq!(oversized_adapter.transport.borrow().completions, 0);
    }

    #[test]
    fn s15_each_completion_binding_mismatch_fails_closed() {
        let bytes = b"completion-bindings".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        for index in 0..4 {
            let mut completion = completion_for(&lookup, &bytes);
            match index {
                0 => completion.lookup_commitment_sha256[0] ^= 1,
                1 => completion.object_revision += 1,
                2 => completion.record_len += 1,
                _ => completion.record_sha256[0] ^= 1,
            }
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::new(
                &lookup,
                vec![
                    ScriptStep::Data(bytes.clone()),
                    ScriptStep::Complete(completion),
                ],
            ));
            assert!(direct_read(&adapter, &lookup).is_err());
        }
    }

    #[test]
    fn s15_tampered_or_mixed_bytes_fail_even_with_locally_matching_completion() {
        let expected = b"snapshot-a".to_vec();
        let lookup = lookup_for_bytes(&expected);
        for actual in [b"snapshot-b".to_vec(), b"snapshot-bsnapshot-a".to_vec()] {
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::new(
                &lookup,
                vec![
                    ScriptStep::Data(actual.clone()),
                    ScriptStep::Complete(RuntimeExactReadCompletionV1 {
                        lookup_commitment_sha256: exact_lookup_commitment_v1(&lookup),
                        object_revision: lookup.object_revision,
                        record_len: u64::try_from(actual.len()).unwrap(),
                        record_sha256: super::super::sha256_bytes(&actual),
                    }),
                ],
            ));
            assert!(direct_read(&adapter, &lookup).is_err());
        }
    }

    #[test]
    fn s15_valid_completion_cannot_bypass_unchanged_s14_record_verification() {
        let (mut record, _, _, _, _) = s15_fixture_parts();
        let midpoint = record.len() / 2;
        record[midpoint] ^= 1;
        let lookup = lookup_for_bytes(&record);
        let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::bytes(
            &lookup, &record, 97,
        ));
        let mut sink = BoundedRecoveredSourceRecordV1::new();
        assert!(adapter.read_exact(&lookup, &mut sink).is_ok());
        let raw = sink.finish().unwrap();
        assert!(super::super::decode_and_verify_source_record_v1(
            &raw,
            &lookup,
            &s15_fixture_parts().2,
        )
        .is_err());
    }

    #[test]
    fn s15_debug_redacts_transport_completion_and_adapter_state() {
        let bytes = b"redacted".to_vec();
        let lookup = lookup_for_bytes(&bytes);
        let completion = completion_for(&lookup, &bytes);
        let completion_debug = format!("{completion:?}");
        assert!(completion_debug.contains("UNTRUSTED_COMPLETION_METADATA_REDACTED"));
        assert!(!completion_debug.contains(&format!("{:02x?}", lookup.object_id)));

        let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ScriptedTransport::bytes(
            &lookup, &bytes, 4,
        ));
        let adapter_debug = format!("{adapter:?}");
        assert!(adapter_debug.contains("ONE_SHOT_RUNTIME_ADAPTER_REDACTED"));
        assert!(!adapter_debug.contains("redacted"));
    }
}
