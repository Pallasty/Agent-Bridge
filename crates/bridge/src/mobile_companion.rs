//! Bounded, read-only host support for the recovered Android companion.
//!
//! The phone exposes one authenticated health request on TCP port 17321. IMU
//! capture remains an explicit Android service intent; this module can inspect
//! and authenticate the resulting summary but cannot request capture, discover
//! devices, provision tokens, or grant attention/memory/actuation authority.

use anyhow::{anyhow, bail, Context, Result};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpStream};
use std::time::Duration;

pub const LAN_HEALTH_PORT: u16 = 17_321;
pub const HEALTH_SCHEMA: &str = "agent_bridge.android_companion.health.v1";
pub const IMU_SCHEMA: &str = "agent_bridge.android_companion.imu_summary.v0";
pub const IMU_ATTESTATION_SCHEMA: &str = "agent_bridge.mobile_imu_result_attestation.v0";
const MAX_RESPONSE_BYTES: usize = 2_048;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HealthRequest {
    pub unix_seconds: i64,
    pub nonce: String,
    pub line: String,
}

#[derive(Clone, Debug)]
pub struct MobileCompanionSnapshot {
    pub peer: SocketAddr,
    pub health: Value,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ImuVerification {
    pub consent_receipt_valid: bool,
    pub result_attestation_valid: bool,
    pub authority_absent: bool,
}

pub fn build_health_request(
    token_hex: &str,
    unix_seconds: i64,
    nonce: &str,
) -> Result<HealthRequest> {
    let token = decode_lower_hex_32(token_hex).context("invalid companion token")?;
    if unix_seconds <= 0 {
        bail!("unix_seconds must be positive");
    }
    if !is_lower_hex(nonce, 32) {
        bail!("nonce must be 32 lowercase hex characters");
    }
    let canonical = format!("ABH1\n{unix_seconds}\n{nonce}");
    let mac = hex(&hmac_sha256(&token, canonical.as_bytes()));
    Ok(HealthRequest {
        unix_seconds,
        nonce: nonce.to_owned(),
        line: format!("ABH1 {unix_seconds} {nonce} {mac}"),
    })
}

pub fn query_health(
    address: IpAddr,
    token_hex: &str,
    unix_seconds: i64,
    nonce: &str,
    timeout: Duration,
) -> Result<MobileCompanionSnapshot> {
    if address.is_unspecified() || address.is_loopback() || address.is_multicast() {
        bail!("companion address must be a specific non-loopback unicast address");
    }
    let request = build_health_request(token_hex, unix_seconds, nonce)?;
    let peer = SocketAddr::new(address, LAN_HEALTH_PORT);
    let mut stream = TcpStream::connect_timeout(&peer, timeout)
        .with_context(|| format!("connect companion {peer}"))?;
    stream.set_read_timeout(Some(timeout))?;
    stream.set_write_timeout(Some(timeout))?;
    stream.write_all(request.line.as_bytes())?;
    stream.write_all(b"\n")?;
    stream.flush()?;

    let mut response = Vec::new();
    BufReader::new(stream)
        .take((MAX_RESPONSE_BYTES + 1) as u64)
        .read_until(b'\n', &mut response)?;
    if response.len() > MAX_RESPONSE_BYTES {
        bail!("companion response exceeds {MAX_RESPONSE_BYTES} bytes");
    }
    while matches!(response.last(), Some(b'\n' | b'\r')) {
        response.pop();
    }
    let response = std::str::from_utf8(&response).context("companion response is not UTF-8")?;
    let body = response
        .strip_prefix("OK ")
        .ok_or_else(|| anyhow!("companion rejected health request: {response}"))?;
    let health: Value = serde_json::from_str(body).context("invalid companion health JSON")?;
    if health.get("schema").and_then(Value::as_str) != Some(HEALTH_SCHEMA) {
        bail!("unexpected companion health schema");
    }
    Ok(MobileCompanionSnapshot { peer, health })
}

pub fn verify_imu_summary(
    token_hex: &str,
    expected_challenge: &str,
    summary: &Value,
) -> Result<ImuVerification> {
    let token = decode_lower_hex_32(token_hex).context("invalid companion token")?;
    if summary.get("schema").and_then(Value::as_str) != Some(IMU_SCHEMA)
        || summary.get("status").and_then(Value::as_str) != Some("complete")
        || summary
            .get("result_attestation_schema")
            .and_then(Value::as_str)
            != Some(IMU_ATTESTATION_SCHEMA)
    {
        bail!("not a complete companion IMU summary");
    }

    let request_id = text(summary, "request_id")?;
    let device_id = text(summary, "device_id")?;
    let session_id = text(summary, "session_id")?;
    if !is_lower_hex(expected_challenge, 64) {
        bail!("expected challenge must be 64 lowercase hex characters");
    }
    // The recovered v0 summary intentionally does not echo the challenge.
    // The verifier therefore requires the exact challenge retained by the
    // request issuer and never accepts one supplied by the response.
    let challenge = expected_challenge;
    let sequence = positive_i64(summary, "sequence")?;
    let issued_at = positive_i64(summary, "issued_at_unix_ms")?;
    let expires_at = positive_i64(summary, "expires_at_unix_ms")?;
    if expires_at <= issued_at || expires_at - issued_at > 10_000 {
        bail!("invalid consent receipt lifetime");
    }
    let consent_digest = lower_hex(summary, "consent_digest_sha256", 64)?;
    let receipt_mac = lower_hex(summary, "receipt_mac_sha256", 64)?;
    let duration_ms = positive_i64(summary, "duration_ms")?;
    let sample_rate_hz = positive_i64(summary, "sample_rate_hz")?;
    let maximum_samples = positive_i64(summary, "maximum_samples")?;

    let receipt_key = hmac_sha256(&token, b"agent_bridge.mobile_consent_receipt.key.v0");
    let receipt_message = format!(
        "ABCR1\n{request_id}\n{device_id}\n{session_id}\nimu\n{challenge}\n{sequence}\n{issued_at}\n{expires_at}\n{consent_digest}\n{duration_ms}\n{sample_rate_hz}\n{maximum_samples}"
    );
    let consent_receipt_valid = constant_time_eq(
        &hmac_sha256(&receipt_key, receipt_message.as_bytes()),
        &decode_lower_hex_32(receipt_mac)?,
    );

    let accelerometer_samples = positive_i64(summary, "accelerometer_samples")?;
    let gyroscope_samples = nonnegative_i64(summary, "gyroscope_samples")?;
    let payload_encoding = text(summary, "payload_encoding")?;
    if payload_encoding != "ab_imu_binary_v0" {
        bail!("unexpected IMU payload encoding");
    }
    let payload_byte_length = positive_i64(summary, "payload_byte_length")?;
    let payload_sha256 = lower_hex(summary, "payload_sha256", 64)?;
    let authority_absent = [
        "attention_authority",
        "memory_authority",
        "actuation_authority",
    ]
    .iter()
    .all(|key| summary.get(*key).and_then(Value::as_bool) == Some(false));
    let result_key = hmac_sha256(&token, b"agent_bridge.mobile_imu_result.key.v0");
    let result_message = format!(
        "ABIR1\n{request_id}\n{device_id}\n{session_id}\n{challenge}\n{sequence}\n{issued_at}\n{accelerometer_samples}\n{gyroscope_samples}\n{payload_encoding}\n{payload_byte_length}\n{payload_sha256}\nfalse\nfalse\nfalse"
    );
    let result_mac = lower_hex(summary, "result_attestation_mac_sha256", 64)?;
    let result_attestation_valid = authority_absent
        && constant_time_eq(
            &hmac_sha256(&result_key, result_message.as_bytes()),
            &decode_lower_hex_32(result_mac)?,
        );

    Ok(ImuVerification {
        consent_receipt_valid,
        result_attestation_valid,
        authority_absent,
    })
}

fn text<'a>(value: &'a Value, key: &str) -> Result<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .filter(|v| !v.is_empty())
        .ok_or_else(|| anyhow!("missing or empty {key}"))
}

fn lower_hex<'a>(value: &'a Value, key: &str, len: usize) -> Result<&'a str> {
    let value = text(value, key)?;
    if !is_lower_hex(value, len) {
        bail!("invalid {key}");
    }
    Ok(value)
}

fn positive_i64(value: &Value, key: &str) -> Result<i64> {
    let value = value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("missing {key}"))?;
    if value <= 0 {
        bail!("{key} must be positive");
    }
    Ok(value)
}

fn nonnegative_i64(value: &Value, key: &str) -> Result<i64> {
    let value = value
        .get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| anyhow!("missing {key}"))?;
    if value < 0 {
        bail!("{key} must be nonnegative");
    }
    Ok(value)
}

fn decode_lower_hex_32(value: &str) -> Result<[u8; 32]> {
    if !is_lower_hex(value, 64) {
        bail!("expected 64 lowercase hex characters");
    }
    let mut out = [0u8; 32];
    for (index, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16)?;
    }
    Ok(out)
}

fn is_lower_hex(value: &str, len: usize) -> bool {
    value.len() == len
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    const BLOCK: usize = 64;
    let mut normalized = [0u8; BLOCK];
    if key.len() > BLOCK {
        normalized[..32].copy_from_slice(&Sha256::digest(key));
    } else {
        normalized[..key.len()].copy_from_slice(key);
    }
    let mut inner_pad = [0x36u8; BLOCK];
    let mut outer_pad = [0x5cu8; BLOCK];
    for index in 0..BLOCK {
        inner_pad[index] ^= normalized[index];
        outer_pad[index] ^= normalized[index];
    }
    let mut inner = Sha256::new();
    inner.update(inner_pad);
    inner.update(message);
    let inner = inner.finalize();
    let mut outer = Sha256::new();
    outer.update(outer_pad);
    outer.update(inner);
    outer.finalize().into()
}

fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    left.len() == right.len()
        && left
            .iter()
            .zip(right)
            .fold(0u8, |diff, (a, b)| diff | (a ^ b))
            == 0
}

fn hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn health_request_known_answer() {
        let request = build_health_request(
            &"11".repeat(32),
            1_700_000_000,
            "0123456789abcdef0123456789abcdef",
        )
        .unwrap();
        assert_eq!(request.line, "ABH1 1700000000 0123456789abcdef0123456789abcdef bc00ae05bf0091b3cdeef4ca66077ae9fe1b7088b8fa61beb0166e722f5cf955");
    }

    #[test]
    fn health_request_rejects_weak_shapes() {
        assert!(build_health_request("11", 1, &"0".repeat(32)).is_err());
        assert!(build_health_request(&"11".repeat(32), 1, &"G".repeat(32)).is_err());
    }

    #[test]
    fn imu_verifier_requires_challenge_and_no_authority() {
        let summary = json!({
            "schema": IMU_SCHEMA,
            "status": "complete",
            "result_attestation_schema": IMU_ATTESTATION_SCHEMA
        });
        assert!(verify_imu_summary(&"11".repeat(32), &"22".repeat(32), &summary).is_err());
    }

    #[test]
    fn imu_verifier_accepts_bound_zero_authority_summary() {
        let token_hex = "11".repeat(32);
        let token = decode_lower_hex_32(&token_hex).unwrap();
        let challenge = "22".repeat(32);
        let consent_digest = "33".repeat(32);
        let payload_digest = "44".repeat(32);
        let receipt_message = format!(
            "ABCR1\nreq-1\ndevice-1\nsession-1\nimu\n{challenge}\n7\n1000\n9000\n{consent_digest}\n500\n20\n10"
        );
        let receipt_key = hmac_sha256(&token, b"agent_bridge.mobile_consent_receipt.key.v0");
        let receipt_mac = hex(&hmac_sha256(&receipt_key, receipt_message.as_bytes()));
        let result_message = format!(
            "ABIR1\nreq-1\ndevice-1\nsession-1\n{challenge}\n7\n1000\n10\n4\nab_imu_binary_v0\n336\n{payload_digest}\nfalse\nfalse\nfalse"
        );
        let result_key = hmac_sha256(&token, b"agent_bridge.mobile_imu_result.key.v0");
        let result_mac = hex(&hmac_sha256(&result_key, result_message.as_bytes()));
        let summary = json!({
            "schema": IMU_SCHEMA,
            "status": "complete",
            "result_attestation_schema": IMU_ATTESTATION_SCHEMA,
            "request_id": "req-1",
            "device_id": "device-1",
            "session_id": "session-1",
            "sequence": 7,
            "issued_at_unix_ms": 1000,
            "expires_at_unix_ms": 9000,
            "consent_digest_sha256": consent_digest,
            "receipt_mac_sha256": receipt_mac,
            "duration_ms": 500,
            "sample_rate_hz": 20,
            "maximum_samples": 10,
            "accelerometer_samples": 10,
            "gyroscope_samples": 4,
            "payload_encoding": "ab_imu_binary_v0",
            "payload_byte_length": 336,
            "payload_sha256": payload_digest,
            "attention_authority": false,
            "memory_authority": false,
            "actuation_authority": false,
            "result_attestation_mac_sha256": result_mac
        });

        assert_eq!(
            verify_imu_summary(&token_hex, &challenge, &summary).unwrap(),
            ImuVerification {
                consent_receipt_valid: true,
                result_attestation_valid: true,
                authority_absent: true,
            }
        );
    }

    #[test]
    fn hmac_matches_rfc_4231_case_one() {
        assert_eq!(
            hex(&hmac_sha256(&[0x0b; 20], b"Hi There")),
            "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
        );
    }
}
