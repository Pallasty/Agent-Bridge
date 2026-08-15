include!("../../../bridge/examples/agent_authority_signed_trust_root_s3.rs.inc");

#[derive(Clone, Debug)]
pub(super) struct EvaluatedS3Case {
    pub(super) case_id: String,
    pub(super) receipt_id: String,
    pub(super) nonce: String,
    pub(super) issued_at_unix: u64,
    pub(super) expires_at_unix: u64,
    pub(super) canonical_claims_bytes: Vec<u8>,
    pub(super) scope_fields: [String; 18],
    pub(super) derived_verified: bool,
    pub(super) signature_verified: bool,
    pub(super) reasons: Vec<String>,
}

pub(super) fn evaluate_frozen_cases() -> anyhow::Result<Vec<EvaluatedS3Case>> {
    let registry = load_registry(TRUST_REGISTRY_BYTES)?;
    let corpus = load_corpus(SIGNED_RECEIPTS_BYTES)?;
    let sources = embedded_sources(
        S2_DESIGN_BYTES,
        S2_FIXTURE_BYTES,
        S2_RESULT_BYTES,
        TRUST_REGISTRY_BYTES,
    );
    let report = evaluate_suite(
        &registry,
        &corpus,
        &sources,
        TRUST_REGISTRY_BYTES,
        SIGNED_RECEIPTS_BYTES,
    )?;
    anyhow::ensure!(
        report.status == "pass_offline_signed_preflight_only",
        "frozen S3 verifier did not pass its independent suite"
    );

    corpus
        .cases
        .iter()
        .map(|case| {
            let claims = claims_for_case(&corpus, case);
            let canonical_claims_bytes = canonical_claims_bytes(&claims);
            let result = evaluate_case(&registry, &corpus, case)?;
            anyhow::ensure!(
                result.canonical_claims_sha256 == sha256(&canonical_claims_bytes),
                "{} canonical claims digest changed between S3 evaluations",
                case.id
            );
            Ok(EvaluatedS3Case {
                case_id: case.id.clone(),
                receipt_id: claims.receipt_id,
                nonce: claims.nonce,
                issued_at_unix: claims.issued_at_unix,
                expires_at_unix: claims.expires_at_unix,
                canonical_claims_bytes,
                scope_fields: [
                    claims.claims_schema,
                    claims.envelope_version,
                    claims.issuer_id,
                    claims.principal_id,
                    claims.action_class,
                    claims.target_digest,
                    claims.scope_digest,
                    claims.decision_source_digest,
                    claims.session_epoch_digest,
                    claims.resume_parent_digest,
                    claims.adapter_id,
                    claims.adapter_build_digest,
                    claims.adapter_capabilities_digest,
                    claims.evidence_digest,
                    claims.verifier_id,
                    claims.policy_version,
                    claims.key_id,
                    claims.algorithm,
                ],
                derived_verified: result.derived_status == VerificationStatus::Verified,
                signature_verified: result.signature_outcome == SignatureOutcome::Verified,
                reasons: result.reasons,
            })
        })
        .collect()
}
