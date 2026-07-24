#!/usr/bin/env python3
"""Fail-closed static source gate for R25 C2C-B startup wiring."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
STORE_CARGO = ROOT / "crates/store/Cargo.toml"
STORE_LIB = ROOT / "crates/store/src/lib.rs"
STORE_RUNTIME = ROOT / "crates/store/src/episode_observation_c2_keychain_macos_runtime.rs"
STORE_SLICE = ROOT / "crates/store/src/sqlite/episode_observation_slice_b.rs"
BRIDGE_CARGO = ROOT / "crates/bridge/Cargo.toml"
BRIDGE_LIB = ROOT / "crates/bridge/src/lib.rs"
BRIDGE_RUNTIME = ROOT / "crates/bridge/src/episode_observation_c2c_keychain_macos_runtime.rs"
MAIN = ROOT / "crates/bridge/src/main.rs"
HUB = ROOT / "crates/bridge/src/hub.rs"

FEATURE = "episode-observation-c2c-keychain-macos-runtime"


def checks(
    store_cargo: str,
    store_lib: str,
    store_runtime: str,
    store_slice: str,
    bridge_cargo: str,
    bridge_lib: str,
    bridge_runtime: str,
    main: str,
    hub: str,
) -> list[tuple[str, bool]]:
    store_feature = (
        'episode-observation-c2c-keychain-macos-runtime = [\n'
        '    "episode-observation-slice-b",\n'
        '    "episode-observation-c2-keychain-macos",\n'
        ']'
    )
    bridge_feature = (
        'episode-observation-c2c-keychain-macos-runtime = [\n'
        '    "episode-observation-slice-c1",\n'
        '    "ab-store/episode-observation-c2c-keychain-macos-runtime",\n'
        ']'
    )
    mac_gate = (
        '#[cfg(all(\n'
        '    feature = "episode-observation-c2c-keychain-macos-runtime",\n'
        '    target_os = "macos"\n'
        '))]'
    )
    main_gate = 'cfg(all(feature = "episode-observation-c2c-keychain-macos-runtime", target_os = "macos"))'
    runtime_body = store_runtime.split("#[cfg(test)]", 1)[0]
    bridge_body = bridge_runtime.split("#[cfg(test)]", 1)[0]
    compact_main = "".join(main.split())
    compact_main_gate = "".join(main_gate.split())
    return [
        ("store feature has only the approved prerequisites", store_feature in store_cargo),
        ("bridge feature forwards only C1 and store runtime", bridge_feature in bridge_cargo),
        ("features are absent from defaults", FEATURE not in store_cargo.split("default =", 1)[1].split("]", 1)[0] and FEATURE not in bridge_cargo.split("default =", 1)[1].split("]", 1)[0]),
        ("store runtime declaration is macOS and feature gated", mac_gate + "\npub mod episode_observation_c2_keychain_macos_runtime;" in store_lib),
        ("bridge runtime declaration is macOS and feature gated", mac_gate + "\npub mod episode_observation_c2c_keychain_macos_runtime;" in bridge_lib),
        ("store performs bounded readiness before a handle exists", 'const READINESS_MEMORY_KEY: &str = "c2c-keychain-readiness-v1";' in runtime_body and "Self::from_deriver(store, Arc::new(MacOsDeriver))" in runtime_body and "map_err(|_| CurationBatchObservationError::Unavailable)?" in runtime_body),
        ("store derives an item reference immediately", "let item_ref = self.deriver.derive(memory_key)" in runtime_body),
        ("store exposes only coarse custody failure", "CurationBatchObservationError::Unavailable" in runtime_body and "derive_active_item_ref_from_keychain(key).map_err(|_| ())" in runtime_body),
        ("store runtime has no custody writes or enumeration", not any(token in runtime_body for token in ("set_generic_password", "delete_generic_password", "find_generic_passwords", "std::env", "println!"))),
        ("store append path is private and feature gated", '#[cfg(feature = "episode-observation-c2c-keychain-macos-runtime")]\n    pub(crate) async fn append_c2_keychain_macos_runtime_event' in store_slice),
        ("bridge maps unavailable to no injection", "Err(_) => builder," in bridge_body and "fn attach_observer(" in bridge_body),
        ("bridge owns no custody implementation", not any(token in bridge_body for token in ("security_framework", "derive_active_item_ref_from_keychain", "std::env", "set_generic_password", "delete_generic_password"))),
        ("bridge test proves unavailable injection is absent", "unavailable_store_handle_injects_no_observer" in bridge_runtime and "curation_batch_observer.is_none()" in bridge_runtime),
        ("CLI mode is typed and exact", "enum EpisodeObservationMode {\n    KeychainMacosV1," in main and "episode_observation: Some(EpisodeObservationMode::KeychainMacosV1)" in main),
        ("implicit daemon mode remains disabled", compact_main.count("unwrap_or(Cmd::Daemon{episode_observation:None,") == 2),
        ("startup attachment requires the macOS feature gate", compact_main_gate in compact_main and "attach_explicit_keychain_macos_observer(builder,store_impl)" in compact_main),
        ("no episode-observation environment switch exists", "EPISODE_OBSERVATION" not in main and "episode_observation" not in main.split("enum Cmd", 1)[0]),
        ("Hub seam is not widened", FEATURE not in hub and "pub fn curation_batch_observer" not in hub),
    ]


def mutations_fail(*values: str) -> bool:
    store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub = values
    variants = [
        (store_cargo.replace('episode-observation-c2c-keychain-macos-runtime = [\n    "episode-observation-slice-b",', 'episode-observation-c2c-keychain-macos-runtime = [\n    "other",', 1), store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo.replace('default = [', f'default = ["{FEATURE}", ', 1), store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib.replace('feature = "episode-observation-c2c-keychain-macos-runtime",\n    target_os = "macos"', 'feature = "episode-observation-c2c-keychain-macos-runtime",\n    target_os = "linux"', 1), store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime.replace("READINESS_MEMORY_KEY", "READINESS_REMOVED", 1), store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime.replace("let item_ref = self.deriver.derive(memory_key)", "let item_ref = String::new()", 1), store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime.replace("derive_active_item_ref_from_keychain(key).map_err(|_| ())", "Ok(key.to_owned())", 1), store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime.replace("#[cfg(test)]", "set_generic_password();\n#[cfg(test)]", 1), store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime, store_slice.replace("pub(crate) async fn append_c2_keychain_macos_runtime_event", "pub async fn append_c2_keychain_macos_runtime_event", 1), bridge_cargo, bridge_lib, bridge_runtime, main, hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime.replace("Err(_) => builder,", "Err(_) => builder.curation_batch_observer(todo!()),", 1), main, hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime.replace("#[cfg(test)]", "use security_framework::passwords::delete_generic_password;\n#[cfg(test)]", 1), main, hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime.replace("unavailable_store_handle_injects_no_observer", "missing", 1), main, hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main.replace("KeychainMacosV1", "Anything", 1), hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main.replace("episode_observation: None", "episode_observation: Some(EpisodeObservationMode::KeychainMacosV1)", 2), hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main.replace('feature = "episode-observation-c2c-keychain-macos-runtime",\n        target_os = "macos"', 'target_os = "macos"', 1), hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main + '\nconst EPISODE_OBSERVATION: &str = "bad";\n', hub),
        (store_cargo, store_lib, store_runtime, store_slice, bridge_cargo, bridge_lib, bridge_runtime, main, hub + f"\n// {FEATURE}\n"),
    ]
    failed = [index + 1 for index, variant in enumerate(variants) if all(ok for _, ok in checks(*variant))]
    if failed:
        print(f"diagnostic: mutations escaped checks: {failed}")
    return not failed


def main() -> int:
    paths = (STORE_CARGO, STORE_LIB, STORE_RUNTIME, STORE_SLICE, BRIDGE_CARGO, BRIDGE_LIB, BRIDGE_RUNTIME, MAIN, HUB)
    values = tuple(path.read_text() for path in paths)
    result = checks(*values)
    for label, ok in result:
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
    mutation_ok = mutations_fail(*values)
    print(f"{'PASS' if mutation_ok else 'FAIL'}: 16 directed mutation checks")
    return 0 if all(ok for _, ok in result) and mutation_ok else 1


if __name__ == "__main__":
    sys.exit(main())
