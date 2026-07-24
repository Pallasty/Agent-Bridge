#!/usr/bin/env python3
"""Fail-closed static source gate for the default-off R27 C2C live lab.

It validates source boundaries only.  It never invokes Keychain, creates a
database, starts MCP, or runs the fixture binary.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
STORE_CARGO = ROOT / "crates/store/Cargo.toml"
STORE_LIB = ROOT / "crates/store/src/lib.rs"
STORE_LAB = ROOT / "crates/store/src/episode_observation_c2c_keychain_macos_c2c_live_lab.rs"
BRIDGE_CARGO = ROOT / "crates/bridge/Cargo.toml"
DRIVER = ROOT / "crates/bridge/src/bin/episode_observation_c2c_live_lab.rs"

FEATURE = "episode-observation-c2c-keychain-macos-live-lab"


def checks(store_cargo: str, store_lib: str, store_lab: str, bridge_cargo: str, driver: str):
    return [
        ("store lab feature is default-off and depends only on C2 Keychain", 'episode-observation-c2c-keychain-macos-live-lab = [\n    "episode-observation-c2-keychain-macos",\n]' in store_cargo and FEATURE not in store_cargo.split("default =", 1)[1].split("]", 1)[0]),
        ("store lab declaration is feature and macOS gated", '#[cfg(all(\n    feature = "episode-observation-c2c-keychain-macos-live-lab",\n    target_os = "macos"\n))]\npub mod episode_observation_c2c_keychain_macos_c2c_live_lab;' in store_lib),
        ("bridge lab feature forwards accepted R25, store lab, and its optional tempdir", 'episode-observation-c2c-keychain-macos-live-lab = [\n    "episode-observation-c2c-keychain-macos-runtime",\n    "ab-store/episode-observation-c2c-keychain-macos-live-lab",\n    "dep:tempfile",\n]' in bridge_cargo and 'tempfile = { version = "3", optional = true }' in bridge_cargo),
        ("fixture binary has required feature", 'name = "episode-observation-c2c-live-lab"' in bridge_cargo and 'required-features = ["episode-observation-c2c-keychain-macos-live-lab"]' in bridge_cargo),
        ("custody uses exact service and two exact account shapes", 'const SERVICE: &str = "com.agent-bridge.episode-ref.v1";' in store_lab and 'const ACTIVE_EPOCH_ACCOUNT: &str = "active-epoch";' in store_lab and 'format!("key:c2c-live-{epoch}")' in store_lab),
        ("both metadata-only preflights occur before writes", 'io.account_exists_without_data(ACTIVE_EPOCH_ACCOUNT)?\n        || io.account_exists_without_data(&key_account)?' in store_lab and 'io.create_only(&state.key_account, key)?;' in store_lab),
        ("key is fixed 32 random bytes and zeroized", 'let mut key = [0_u8; 32];' in store_lab and 'key.zeroize();' in store_lab),
        ("cleanup deletes pointer before key and postchecks both", 'io.delete_exact(ACTIVE_EPOCH_ACCOUNT)?;' in store_lab and 'io.delete_exact(&state.key_account)?;' in store_lab and '|| io.account_exists_without_data(&state.key_account)?' in store_lab),
        ("lab source has no Keychain enumeration or shell password command", not any(token in store_lab for token in ('find_generic_passwords', 'security ', 'Command::new', 'set_generic_password'))),
        ("driver defaults to refusal before run", 'if source_only_refusal(&args)' in driver and 'std::process::exit(64);' in driver),
        ("driver starts only the explicit MCP opt-in and carries only DB env", '.arg("mcp")' in driver and '.arg("--episode-observation")' in driver and '.arg("keychain-macos-v1")' in driver and '.env_clear()' in driver and '.env("AGENT_BRIDGE_DB", db_path)' in driver),
        ("driver issues exactly one session_curate fixture request", '"name": "session_curate"' in driver and 'fixture_contains_one_session_curate_request' in driver),
        ("fixture rejects an empty core save", '.filter(|count| *count > 0)' in driver and 'zero_saved_count_is_not_accepted' in driver),
        ("driver bounds the MCP process and captures a finalized SQLite receipt", 'const MCP_TIMEOUT: Duration = Duration::from_secs(30);' in driver and 'wait_for_child(&mut child)?;' in driver and 'FROM episode_observation_events' in driver and 'receipt_requires_one_finalized_contiguous_curation_batch' in driver),
        ("cleanup failure carries only the public recovery account", 'Keychain cleanup unconfirmed; recover only {} and active-epoch' in driver and 'custody.key_account()' in driver),
    ]


def mutations_fail(*values: str) -> bool:
    store_cargo, store_lib, store_lab, bridge_cargo, driver = values
    variants = [
        (store_cargo.replace('default = [', f'default = ["{FEATURE}", ', 1), store_lib, store_lab, bridge_cargo, driver),
        (store_cargo, store_lib.replace('feature = "episode-observation-c2c-keychain-macos-live-lab",\n    target_os = "macos"', 'feature = "episode-observation-c2c-keychain-macos-live-lab",\n    target_os = "linux"', 1), store_lab, bridge_cargo, driver),
        (store_cargo, store_lib, store_lab.replace('key.zeroize();', '// removed', 1), bridge_cargo, driver),
        (store_cargo, store_lib, store_lab.replace('io.delete_exact(ACTIVE_EPOCH_ACCOUNT)?;', '// removed', 1), bridge_cargo, driver),
        (store_cargo, store_lib, store_lab + '\nfind_generic_passwords();\n', bridge_cargo, driver),
        (store_cargo, store_lib, store_lab, bridge_cargo, driver.replace('if source_only_refusal(&args)', 'if false', 1)),
        (store_cargo, store_lib, store_lab, bridge_cargo, driver.replace('.env_clear()', '// removed', 1)),
        (store_cargo, store_lib, store_lab, bridge_cargo, driver.replace('.filter(|count| *count > 0)', '.filter(|count| *count >= 0)', 1)),
        (store_cargo, store_lib, store_lab, bridge_cargo, driver.replace('wait_for_child(&mut child)?;', '// removed', 1)),
        (store_cargo, store_lib, store_lab, bridge_cargo, driver.replace('FROM episode_observation_events', 'FROM memories', 1)),
    ]
    escaped = [i + 1 for i, variant in enumerate(variants) if all(ok for _, ok in checks(*variant))]
    if escaped:
        print(f"diagnostic: mutations escaped checks: {escaped}")
    return not escaped


def main() -> int:
    values = tuple(path.read_text() for path in (STORE_CARGO, STORE_LIB, STORE_LAB, BRIDGE_CARGO, DRIVER))
    result = checks(*values)
    for label, ok in result:
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
    mutation_ok = mutations_fail(*values)
    print(f"{'PASS' if mutation_ok else 'FAIL'}: 10 directed mutation checks")
    return 0 if all(ok for _, ok in result) and mutation_ok else 1


if __name__ == "__main__":
    sys.exit(main())
