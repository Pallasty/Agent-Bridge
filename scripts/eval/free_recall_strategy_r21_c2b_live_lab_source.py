#!/usr/bin/env python3
"""Fail-closed static gate for the R20 disposable macOS Keychain lab."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CARGO = ROOT / "crates/store/Cargo.toml"
LIB = ROOT / "crates/store/src/lib.rs"
READER = ROOT / "crates/store/src/episode_observation_c2_keychain_macos.rs"
LAB = ROOT / "crates/store/src/episode_observation_c2_keychain_macos_live_lab.rs"


def ordered(text: str, *needles: str) -> bool:
    cursor = -1
    for needle in needles:
        cursor = text.find(needle, cursor + 1)
        if cursor < 0:
            return False
    return True


def evaluate(cargo: str, lib: str, reader: str, lab: str) -> list[tuple[str, bool]]:
    feature = 'episode-observation-c2-keychain-macos-live-lab = [\n    "episode-observation-c2-keychain-macos",\n]'
    module_gate = (
        "#[cfg(all(\n"
        "    test,\n"
        '    feature = "episode-observation-c2-keychain-macos-live-lab",\n'
        '    target_os = "macos"\n'
        "))]\n"
        "mod episode_observation_c2_keychain_macos_live_lab;"
    )
    return [
        ("default-off feature depends only on accepted C2B", feature in cargo),
        ("module is test feature macOS gated", module_gate in lib),
        ("live test has exact name", "fn disposable_keychain_round_trip_cleans_up()" in lab),
        ("live test is ignored", '#[ignore = "requires explicit R20 disposable macOS Keychain authorization"]' in lab),
        ("service is fixed", 'const SERVICE: &str = "com.agent-bridge.episode-ref.v1";' in lab),
        ("epoch namespace is fixed", 'format!("c2b-live-{epoch}")' in lab),
        ("secure random generates epoch and key", lab.count("rng.fill(") == 2),
        ("key is exactly 32 bytes", "let mut key = [0_u8; 32];" in lab),
        ("local key is zeroized immediately after write", ordered(lab, "let key_write =", "key.zeroize();", "assert!(key_write.is_ok()")),
        ("metadata-only preflight avoids secret data", "ItemSearchOptions" in lab and ".load_attributes(true)" in lab and ".load_data(" not in lab),
        ("both accounts are preflighted", lab.count("account_exists_without_data(") >= 5),
        ("create-only API prevents overwrite", lab.count(".add_generic_password(") == 2 and "set_generic_password" not in lab),
        ("key is written before active pointer", ordered(lab, "let key_write =", "ACTIVE_EPOCH_ACCOUNT, epoch.as_bytes()")),
        ("active pointer is deleted before key", ordered(lab, "if self.active_written", "delete_generic_password(SERVICE, ACTIVE_EPOCH_ACCOUNT)", "if self.key_written", "delete_generic_password(SERVICE, &self.key_account)")),
        ("cleanup guard tracks write ownership", all(token in lab for token in ("key_written: bool", "active_written: bool", "impl Drop for CleanupGuard"))),
        ("accepted reader is called exactly once", lab.count("derive_active_item_ref_from_keychain(") == 1),
        ("production reader remains read-only", "set_generic_password" not in reader and "add_generic_password" not in reader and "delete_generic_password" not in reader),
        ("no secret transport or broad keychain authority", not any(token in lab for token in ("std::env", "std::fs", "println!", "eprintln!", "-A", "unlock", "search_list"))),
    ]


def mutation_checks(cargo: str, lib: str, reader: str, lab: str) -> bool:
    base = evaluate(cargo, lib, reader, lab)
    if not all(ok for _, ok in base):
        return False
    mutations = [
        (cargo.replace('"episode-observation-c2-keychain-macos"', '"episode-observation-slice-b"', 1), lib, reader, lab),
        (cargo, lib.replace("    test,\n", "", 1), reader, lab),
        (
            cargo,
            lib.replace(
                '    feature = "episode-observation-c2-keychain-macos-live-lab",\n'
                '    target_os = "macos"\n',
                '    feature = "episode-observation-c2-keychain-macos-live-lab"\n',
                1,
            ),
            reader,
            lab,
        ),
        (cargo, lib, reader, lab.replace("#[ignore =", "#[ignoreX =", 1)),
        (cargo, lib, reader, lab.replace("com.agent-bridge.episode-ref.v1", "other.service", 1)),
        (cargo, lib, reader, lab.replace('format!("c2b-live-{epoch}")', 'format!("other-{epoch}")', 1)),
        (cargo, lib, reader, lab.replace("rng.fill(", "rng.other(", 1)),
        (cargo, lib, reader, lab.replace("[0_u8; 32]", "[0_u8; 31]", 1)),
        (cargo, lib, reader, lab.replace("key.zeroize();", "", 1)),
        (cargo, lib, reader, lab.replace(".load_attributes(true)", ".load_data(true)", 1)),
        (cargo, lib, reader, lab.replace("account_exists_without_data(&key_account)", "false.into()", 1)),
        (cargo, lib, reader, lab.replace(".add_generic_password(", ".set_generic_password(", 1)),
        (cargo, lib, reader, lab.replace("let key_write =", "let active_write =", 1)),
        (cargo, lib, reader, lab.replace("if self.active_written", "if self.pointer_owned", 1)),
        (cargo, lib, reader, lab.replace("key_written: bool", "key_owned: bool", 1)),
        (cargo, lib, reader, lab.replace("derive_active_item_ref_from_keychain(MEMORY_KEY)", "String::new()", 1)),
        (cargo, lib, reader + "\nset_generic_password();", lab),
        (cargo, lib, reader, lab + "\nprintln!(\"secret\");\n"),
    ]
    return all(not all(ok for _, ok in evaluate(*mutation)) for mutation in mutations)


def main() -> int:
    cargo, lib, reader, lab = (path.read_text() for path in (CARGO, LIB, READER, LAB))
    checks = evaluate(cargo, lib, reader, lab)
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
    mutations_ok = mutation_checks(cargo, lib, reader, lab)
    print(f"{'PASS' if mutations_ok else 'FAIL'}: 18 directed mutation checks")
    return 0 if all(ok for _, ok in checks) and mutations_ok else 1


if __name__ == "__main__":
    sys.exit(main())
