#!/usr/bin/env python3
"""Reject authority expansion in the C2B macOS Keychain source lane."""

from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
paths = {
    "store_cargo": root / "crates/store/Cargo.toml",
    "store_lib": root / "crates/store/src/lib.rs",
    "store_c2b": root / "crates/store/src/episode_observation_c2_keychain_macos.rs",
    "bridge_cargo": root / "crates/bridge/Cargo.toml",
    "bridge_lib": root / "crates/bridge/src/lib.rs",
    "main": root / "crates/bridge/src/main.rs",
    "hub": root / "crates/bridge/src/hub.rs",
    "lock": root / "Cargo.lock",
}
canonical_text = {name: path.read_text() for name, path in paths.items()}


def evaluate(text: dict[str, str]) -> dict[str, bool]:
    source = text["store_c2b"]
    test_marker = "#[cfg(test)]\nmod tests"
    if test_marker not in source:
        return {"test_partition_present": False}
    production_source, test_source = source.rsplit(test_marker, 1)
    feature_block = re.search(
        r"episode-observation-c2-keychain-macos\s*=\s*\[(.*?)\]",
        text["store_cargo"],
        re.S,
    )
    feature_text = feature_block.group(1) if feature_block else ""
    default_block = re.search(
        r"^default\s*=\s*\[(.*?)\]", text["store_cargo"], re.M
    )
    default_text = default_block.group(1) if default_block else ""
    return {
        "feature_default_off": "episode-observation-c2-keychain-macos"
        not in default_text,
        "feature_exact_dependencies": all(
            item in feature_text
            for item in [
                '"episode-observation-slice-b"',
                '"dep:security-framework"',
                '"dep:zeroize"',
            ]
        ),
        "locked_versions_unchanged": 'name = "security-framework"\nversion = "3.7.0"'
        in text["lock"]
        and 'name = "zeroize"\nversion = "1.8.2"' in text["lock"],
        "private_macos_module": 'feature = "episode-observation-c2-keychain-macos"'
        in text["store_lib"]
        and 'target_os = "macos"' in text["store_lib"]
        and "pub mod episode_observation_c2_keychain_macos"
        not in text["store_lib"],
        "fixed_namespace": '"com.agent-bridge.episode-ref.v1"'
        in production_source
        and '"active-epoch"' in production_source
        and '"key:"' in production_source,
        "read_only_keychain": "generic_password" in production_source
        and "PasswordOptions::new_generic_password" in production_source
        and not any(
            forbidden in production_source
            for forbidden in [
                "set_generic_password",
                "delete_generic_password",
                "SecItemAdd",
                "SecItemUpdate",
                "SecItemDelete",
            ]
        ),
        "no_ambient_configuration": not any(
            forbidden in production_source
            for forbidden in [
                "std::env",
                "env::var",
                "clap::",
                "mcp_tools",
                "SqliteStore",
            ]
        ),
        "no_secret_observability": not any(
            forbidden in production_source
            for forbidden in [
                "tracing::",
                "println!",
                "eprintln!",
                "serde::",
                "Serialize",
                "Deserialize",
            ]
        ),
        "secret_buffer_not_clone_or_debug": "struct SecretBytes"
        in production_source
        and not re.search(
            r"#\[derive\([^\]]*(?:Clone|Debug)[^\]]*\)\]\s*struct SecretBytes",
            production_source,
        ),
        "exact_key_length_and_zeroize": "const KEY_BYTES: usize = 32"
        in production_source
        and "!= KEY_BYTES" in production_source
        and ".zeroize()" in production_source
        and "impl Drop for SecretBytes" in production_source,
        "coarse_payload_free_errors": bool(
            re.search(
                r"enum KeychainCustodyError\s*\{\s*Unavailable,\s*InvalidEpoch,\s*InvalidKeyLength,\s*DerivationFailed,\s*\}",
                production_source,
                re.S,
            )
        )
        and "ReaderFailure;" in production_source,
        "no_synthetic_fallback": "SyntheticProvider" not in production_source
        and "synthetic_test_only" not in production_source,
        "no_global_cache_or_persistence": not any(
            forbidden in production_source
            for forbidden in ["OnceLock", "static mut", "Mutex<", "write_all(", "File::create"]
        ),
        "public_surface_stays_crate_private": not re.search(
            r"(?m)^pub (?:struct|enum|trait|fn) ", production_source
        ),
        "bridge_has_no_c2b_surface": "episode-observation-c2-keychain-macos"
        not in text["bridge_cargo"] + text["bridge_lib"],
        "no_startup_injection": "derive_active_item_ref_from_keychain"
        not in text["main"] + text["hub"],
        "tests_use_fake_only": "struct FakeReader" in test_source
        and "MacOsKeychainReader" not in test_source,
        "required_negative_tests": all(
            marker in test_source
            for marker in [
                "malformed_or_missing_custody_inputs_fail_closed",
                "epoch_rotation_reads_the_new_account_without_rewriting_old_refs",
                "backend_detail_and_secret_sentinel_never_cross_the_error_boundary",
                "default_fake_construction_performs_zero_reads",
            ]
        ),
    }


def replace_once(
    text: dict[str, str], file_key: str, old: str, new: str
) -> None:
    if text[file_key].count(old) != 1:
        raise AssertionError(f"mutation anchor mismatch: {file_key}: {old}")
    text[file_key] = text[file_key].replace(old, new, 1)


mutations = [
    (
        "default_on",
        "feature_default_off",
        "store_cargo",
        'default = ["onnx-embed"]',
        'default = ["onnx-embed", "episode-observation-c2-keychain-macos"]',
    ),
    (
        "drop_zeroize_dependency",
        "feature_exact_dependencies",
        "store_cargo",
        '    "dep:zeroize",\n',
        "",
    ),
    (
        "drift_locked_version",
        "locked_versions_unchanged",
        "lock",
        'name = "zeroize"\nversion = "1.8.2"',
        'name = "zeroize"\nversion = "9.9.9"',
    ),
    (
        "public_module",
        "private_macos_module",
        "store_lib",
        "mod episode_observation_c2_keychain_macos;",
        "pub mod episode_observation_c2_keychain_macos;",
    ),
    (
        "override_namespace",
        "fixed_namespace",
        "store_c2b",
        '"com.agent-bridge.episode-ref.v1"',
        '"operator-selected-service"',
    ),
    (
        "keychain_write",
        "read_only_keychain",
        "store_c2b",
        "generic_password(PasswordOptions::new_generic_password(SERVICE, account))",
        "set_generic_password(SERVICE, account, b\"mutation\")",
    ),
    (
        "ambient_environment",
        "no_ambient_configuration",
        "store_c2b",
        "use zeroize::Zeroize;",
        "use zeroize::Zeroize;\nuse std::env;",
    ),
    (
        "secret_tracing",
        "no_secret_observability",
        "store_c2b",
        "impl KeychainSecretReader for MacOsKeychainReader {\n"
        "    fn read(&self, account: &str) -> Result<Vec<u8>, ReaderFailure> {",
        "impl KeychainSecretReader for MacOsKeychainReader {\n"
        '    fn read(&self, account: &str) -> Result<Vec<u8>, ReaderFailure> {\n'
        '        tracing::debug!("custody");',
    ),
    (
        "clone_secret_buffer",
        "secret_buffer_not_clone_or_debug",
        "store_c2b",
        "struct SecretBytes {",
        "#[derive(Clone)]\nstruct SecretBytes {",
    ),
    (
        "wrong_key_length",
        "exact_key_length_and_zeroize",
        "store_c2b",
        "const KEY_BYTES: usize = 32;",
        "const KEY_BYTES: usize = 31;",
    ),
    (
        "payload_error",
        "coarse_payload_free_errors",
        "store_c2b",
        "    Unavailable,\n",
        "    Unavailable(String),\n",
    ),
    (
        "synthetic_fallback",
        "no_synthetic_fallback",
        "store_c2b",
        "struct MacOsKeychainReader;",
        "struct MacOsKeychainReader;\nstruct SyntheticProvider;",
    ),
    (
        "global_cache",
        "no_global_cache_or_persistence",
        "store_c2b",
        "const MAX_EPOCH_BYTES: usize = 32;",
        "const MAX_EPOCH_BYTES: usize = 32;\nstatic KEY_CACHE: OnceLock<Vec<u8>> = OnceLock::new();",
    ),
    (
        "public_constructor",
        "public_surface_stays_crate_private",
        "store_c2b",
        "pub(crate) fn derive_active_item_ref_from_keychain(",
        "pub fn derive_active_item_ref_from_keychain(",
    ),
    (
        "bridge_feature",
        "bridge_has_no_c2b_surface",
        "bridge_cargo",
        "episode-observation-slice-c1 = []",
        'episode-observation-slice-c1 = []\nepisode-observation-c2-keychain-macos = ["ab-store/episode-observation-c2-keychain-macos"]',
    ),
    (
        "startup_injection",
        "no_startup_injection",
        "hub",
        "use crate::security::SecurityPolicy;",
        "use crate::security::SecurityPolicy;\n// derive_active_item_ref_from_keychain",
    ),
    (
        "real_reader_in_test",
        "tests_use_fake_only",
        "store_c2b",
        "mod tests {\n",
        "mod tests {\n    const REAL_READER_FORBIDDEN: &str = \"MacOsKeychainReader\";\n",
    ),
    (
        "remove_negative_test",
        "required_negative_tests",
        "store_c2b",
        "malformed_or_missing_custody_inputs_fail_closed",
        "mutation_removed_negative_test",
    ),
]

checks = evaluate(canonical_text)
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

mutation_failures = []
for mutation_name, expected_check, file_key, old, new in mutations:
    mutated = dict(canonical_text)
    replace_once(mutated, file_key, old, new)
    rejected = not evaluate(mutated).get(expected_check, False)
    if not rejected:
        mutation_failures.append(mutation_name)

print(
    "directed_mutations: "
    f"{'PASS' if not mutation_failures else 'FAIL'} "
    f"({len(mutations) - len(mutation_failures)}/{len(mutations)})"
)
if failed or mutation_failures:
    details = failed + [f"mutation:{name}" for name in mutation_failures]
    sys.exit(f"C2B source authority check failed: {', '.join(details)}")
