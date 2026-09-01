#![cfg(feature = "invocation-guardian-v2-canary")]

use std::fs::Permissions;
use std::io::{Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use base64::engine::general_purpose::STANDARD_NO_PAD;
use base64::Engine as _;
use ring::rand::SystemRandom;
use ring::signature::{Ed25519KeyPair, KeyPair as _};
use serde_json::{json, Value};

use ab_bridge::invocation_guardian_canary::{
    arguments_jcs_sha256, build_canary_registry, canary_authorization_meta, canary_target_sha256,
    CanarySourceConfig, FakeProtectedWitness, CANARY_TOOL_NAME,
};
use ab_bridge::invocation_lease_scope::{
    domain_hash, CanaryLeaseScope, CanaryTrustPins, SignedCanaryLease,
};

#[test]
fn actual_stdio_tools_call_creates_at_most_one_marker() {
    let directory = tempfile::tempdir().unwrap();
    let marker_root = directory.path().join("markers");
    std::fs::create_dir(&marker_root).unwrap();
    std::fs::set_permissions(&marker_root, Permissions::from_mode(0o700)).unwrap();

    let issuer_document = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
    let issuer = Ed25519KeyPair::from_pkcs8(issuer_document.as_ref()).unwrap();
    let issuer_public: [u8; 32] = issuer.public_key().as_ref().try_into().unwrap();
    let provider_document = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
    let provider = Arc::new(Ed25519KeyPair::from_pkcs8(provider_document.as_ref()).unwrap());
    let namespace = "canary/stdio-e2e".to_string();
    let principal_commitment = [7; 32];
    let ledger_generation = [2; 32];
    let pins = CanaryTrustPins {
        key_generation: 1,
        issuer_verify_key: issuer_public,
        issuer_key_commitment: domain_hash(
            b"agent_bridge.invocation_guardian.issuer_key.v2\0",
            &issuer_public,
        ),
        ledger_generation,
        namespace: namespace.clone(),
    };
    let parent_registry = build_canary_registry(CanarySourceConfig {
        enabled: true,
        trust_pins: pins.clone(),
        principal_kind: "service".into(),
        principal_commitment,
        provider_key_generation: 1,
        provider_signing_key: provider.clone(),
        witness: Arc::new(FakeProtectedWitness::new(
            namespace.clone(),
            1,
            provider.clone(),
        )),
        marker_root: marker_root.clone(),
        witness_timeout: Duration::from_secs(1),
    })
    .unwrap();
    assert_eq!(parent_registry.list().len(), 1);
    let registry_digest = decode_hex_32(parent_registry.snapshot().digest_sha256());
    let instance_id = "server-owned-c1-stdio-instance";
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;
    let scope = CanaryLeaseScope {
        key_generation: 1,
        issuer_key_commitment: pins.issuer_key_commitment,
        ledger_generation,
        token_commitment: [3; 32],
        lease_id: "lease-stdio-e2e".into(),
        tool_name: CANARY_TOOL_NAME.into(),
        arguments_jcs_sha256: arguments_jcs_sha256(&json!({})).unwrap(),
        target_sha256: canary_target_sha256(),
        registry_sha256: registry_digest,
        namespace: namespace.clone(),
        principal_kind: "service".into(),
        principal_commitment,
        connection_commitment: ab_mcp::stdio_connection_commitment(instance_id),
        issued_at_unix: now - 1,
        not_before_unix: now - 1,
        expires_at_unix: now + 59,
        max_uses: 1,
    };
    let signed = SignedCanaryLease::sign(scope, &issuer).unwrap();
    let authorization_meta = canary_authorization_meta(&signed).unwrap();

    let mut child = Command::new(env!("CARGO_BIN_EXE_invocation-guardian-canary-mcp"))
        .env("AB_CANARY_ENABLE", "1")
        .env("AB_CANARY_NAMESPACE", &namespace)
        .env("AB_CANARY_ISSUER_KEY_GENERATION", "1")
        .env("AB_CANARY_ISSUER_VERIFY_KEY_HEX", hex(&issuer_public))
        .env("AB_CANARY_LEDGER_GENERATION_HEX", hex(&ledger_generation))
        .env(
            "AB_CANARY_PRINCIPAL_COMMITMENT_HEX",
            hex(&principal_commitment),
        )
        .env("AB_CANARY_PROVIDER_KEY_GENERATION", "1")
        .env(
            "AB_CANARY_PROVIDER_PKCS8_B64",
            STANDARD_NO_PAD.encode(provider_document.as_ref()),
        )
        .env("AB_CANARY_MARKER_ROOT", &marker_root)
        .env("AB_CANARY_STDIO_INSTANCE_ID", instance_id)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut stdin = child.stdin.take().unwrap();
    let requests = [
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"c1-e2e","version":"0"}}}),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":CANARY_TOOL_NAME,"arguments":{}}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":CANARY_TOOL_NAME,"arguments":{"_meta":authorization_meta.clone()}}}),
        json!({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":CANARY_TOOL_NAME,"arguments":{},"_meta":authorization_meta.clone()}}),
        json!({"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":CANARY_TOOL_NAME,"arguments":{},"_meta":authorization_meta}}),
    ];
    for request in requests {
        writeln!(stdin, "{}", request).unwrap();
    }
    drop(stdin);
    let stdout_reader = reader(child.stdout.take().unwrap());
    let stderr_reader = reader(child.stderr.take().unwrap());
    let status = wait_timeout(&mut child, Duration::from_secs(20));
    let stdout = stdout_reader.join().unwrap();
    let stderr = stderr_reader.join().unwrap();
    assert!(status.success(), "child failed: {stderr}");
    let responses: Vec<Value> = stdout
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    let calls: Vec<&Value> = responses
        .iter()
        .filter(|response| matches!(response.get("id").and_then(Value::as_i64), Some(2..=5)))
        .collect();
    assert_eq!(calls.len(), 4, "stdout={stdout}");
    let successes = calls
        .iter()
        .filter(|response| response.pointer("/result/isError") == Some(&Value::Bool(false)))
        .count();
    assert_eq!(successes, 1, "stdout={stdout}");
    let markers: Vec<_> = std::fs::read_dir(&marker_root)
        .unwrap()
        .collect::<Result<_, _>>()
        .unwrap();
    assert_eq!(markers.len(), 1);
    let marker: Value = serde_json::from_slice(&std::fs::read(markers[0].path()).unwrap()).unwrap();
    assert_eq!(marker["token_commitment"], hex(&[3; 32]));
    assert_eq!(marker["production_authority"], false);
}

fn reader<R: Read + Send + 'static>(mut input: R) -> thread::JoinHandle<String> {
    thread::spawn(move || {
        let mut output = String::new();
        input.read_to_string(&mut output).unwrap();
        output
    })
}

fn wait_timeout(child: &mut std::process::Child, timeout: Duration) -> std::process::ExitStatus {
    let deadline = std::time::Instant::now() + timeout;
    loop {
        if let Some(status) = child.try_wait().unwrap() {
            return status;
        }
        if std::time::Instant::now() >= deadline {
            let _ = child.kill();
            return child.wait().unwrap();
        }
        thread::sleep(Duration::from_millis(20));
    }
}

fn decode_hex_32(value: &str) -> [u8; 32] {
    let mut output = [0; 32];
    for (index, pair) in value.as_bytes().chunks_exact(2).enumerate() {
        output[index] = u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap();
    }
    output
}

fn hex(value: &[u8]) -> String {
    value.iter().map(|byte| format!("{byte:02x}")).collect()
}
