#!/usr/bin/env python3
"""Static, no-Keychain source gate for R33 item-subphase instrumentation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "crates/bridge/src/episode_observation_c2c_live_lab_diagnostics.rs"
DRIVER = ROOT / "crates/bridge/src/bin/episode_observation_c2c_live_lab.rs"
RUNTIME = ROOT / "crates/store/src/episode_observation_c2_keychain_macos_runtime.rs"
LABELS = (
    "item_derivation_enter",
    "item_derivation_done",
    "item_append_enter",
    "item_append_done",
)


def checks(bridge: str, driver: str, runtime: str):
    labels_in_bridge = all(f'| "{label}"' in bridge for label in LABELS)
    labels_in_driver = all(f'    "{label}",' in driver for label in LABELS)
    return [
        ("bridge and driver whitelist every item subphase", labels_in_bridge and labels_in_driver),
        ("store marker is live-lab feature gated and fixed-label only", '#[cfg(feature = "episode-observation-c2c-keychain-macos-live-lab")]\nfn mark_live_lab_phase' in runtime and all(f'"{label}"' in runtime for label in LABELS)),
        ("derivation checkpoints bound only item-reference derivation", 'mark_live_lab_phase("item_derivation_enter");\n        let item_ref = match self.deriver.derive(memory_key)' in runtime and 'mark_live_lab_phase("item_derivation_done");' in runtime),
        ("append checkpoints bound only the episode-item append", 'mark_live_lab_phase("item_append_enter");\n        match self\n            .store\n            .append_c2_keychain_macos_runtime_event' in runtime and 'mark_live_lab_phase("item_append_done");' in runtime),
        ("marker neither creates paths nor exposes key material", '.create(true)' not in runtime and 'find_generic_passwords' not in runtime and 'security ' not in runtime),
    ]


def main() -> int:
    values = tuple(path.read_text() for path in (BRIDGE, DRIVER, RUNTIME))
    result = checks(*values)
    for label, ok in result:
        print(f"{'PASS' if ok else 'FAIL'}: {label}")
    variants = [
        (values[0].replace('| "item_derivation_done"', '', 1), values[1], values[2]),
        (values[0], values[1].replace('    "item_append_done",', '', 1), values[2]),
        (values[0], values[1], values[2].replace('mark_live_lab_phase("item_derivation_done");', '// removed', 1)),
        (values[0], values[1], values[2].replace('mark_live_lab_phase("item_append_enter");', '// removed', 1)),
        (values[0], values[1], values[2].replace('OpenOptions::new().append(true).open(path)', 'OpenOptions::new().append(true).create(true).open(path)', 1)),
    ]
    escaped = [i + 1 for i, variant in enumerate(variants) if all(ok for _, ok in checks(*variant))]
    if escaped:
        print(f"diagnostic: mutations escaped checks: {escaped}")
    print(f"{'PASS' if not escaped else 'FAIL'}: 5 directed mutation checks")
    return 0 if all(ok for _, ok in result) and not escaped else 1


if __name__ == "__main__":
    sys.exit(main())
