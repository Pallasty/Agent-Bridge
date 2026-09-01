//! Explicit source-canary MCP composition root. Required configuration is
//! accepted only from the operator/test environment; this binary is omitted
//! unless the default-off `invocation-guardian-v2-canary` feature is enabled.

use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Context, Result};
use base64::engine::general_purpose::STANDARD_NO_PAD;
use base64::Engine as _;
use ring::signature::Ed25519KeyPair;

use ab_bridge::invocation_guardian_canary::{
    build_canary_registry, CanarySourceConfig, FakeProtectedWitness,
};
use ab_bridge::invocation_lease_scope::{domain_hash, CanaryTrustPins};

#[tokio::main]
async fn main() -> Result<()> {
    let namespace = required("AB_CANARY_NAMESPACE")?;
    let key_generation = parse_u64("AB_CANARY_ISSUER_KEY_GENERATION")?;
    let issuer_verify_key = decode_32(&required("AB_CANARY_ISSUER_VERIFY_KEY_HEX")?)?;
    let ledger_generation = decode_32(&required("AB_CANARY_LEDGER_GENERATION_HEX")?)?;
    let principal_commitment = decode_32(&required("AB_CANARY_PRINCIPAL_COMMITMENT_HEX")?)?;
    let provider_key_generation = parse_u64("AB_CANARY_PROVIDER_KEY_GENERATION")?;
    let provider_pkcs8 = STANDARD_NO_PAD
        .decode(required("AB_CANARY_PROVIDER_PKCS8_B64")?)
        .map_err(|_| anyhow!("AB_CANARY_PROVIDER_PKCS8_B64 is invalid"))?;
    let provider_signing_key = Arc::new(
        Ed25519KeyPair::from_pkcs8(&provider_pkcs8)
            .map_err(|_| anyhow!("provider PKCS#8 is invalid"))?,
    );
    let marker_root = PathBuf::from(required("AB_CANARY_MARKER_ROOT")?);
    let instance_id = required("AB_CANARY_STDIO_INSTANCE_ID")?;
    let witness = Arc::new(FakeProtectedWitness::new(
        namespace.clone(),
        provider_key_generation,
        provider_signing_key.clone(),
    ));
    let registry = build_canary_registry(CanarySourceConfig {
        enabled: required("AB_CANARY_ENABLE")? == "1",
        trust_pins: CanaryTrustPins {
            key_generation,
            issuer_verify_key,
            issuer_key_commitment: domain_hash(
                b"agent_bridge.invocation_guardian.issuer_key.v2\0",
                &issuer_verify_key,
            ),
            ledger_generation,
            namespace,
        },
        principal_kind: "service".into(),
        principal_commitment,
        provider_key_generation,
        provider_signing_key,
        witness,
        marker_root,
        witness_timeout: Duration::from_secs(1),
    })?;
    ab_mcp::server::serve_stdio_invocation_guardian_canary(
        registry,
        None,
        "invocation-guardian-canary-mcp",
        env!("CARGO_PKG_VERSION"),
        None,
        instance_id,
    )
    .await;
    Ok(())
}

fn required(name: &str) -> Result<String> {
    std::env::var(name)
        .with_context(|| format!("{name} is required"))
        .and_then(|value| {
            (!value.trim().is_empty())
                .then_some(value)
                .ok_or_else(|| anyhow!("{name} must not be empty"))
        })
}

fn parse_u64(name: &str) -> Result<u64> {
    required(name)?
        .parse::<u64>()
        .with_context(|| format!("{name} must be an unsigned integer"))
        .and_then(|value| {
            (value > 0)
                .then_some(value)
                .ok_or_else(|| anyhow!("{name} must be nonzero"))
        })
}

fn decode_32(value: &str) -> Result<[u8; 32]> {
    if value.len() != 64 {
        return Err(anyhow!("expected 64 lowercase hex characters"));
    }
    let mut output = [0; 32];
    for (index, pair) in value.as_bytes().chunks_exact(2).enumerate() {
        output[index] = (nibble(pair[0])? << 4) | nibble(pair[1])?;
    }
    Ok(output)
}

fn nibble(value: u8) -> Result<u8> {
    match value {
        b'0'..=b'9' => Ok(value - b'0'),
        b'a'..=b'f' => Ok(value - b'a' + 10),
        _ => Err(anyhow!("expected lowercase hex")),
    }
}
