#!/usr/bin/env python3
"""Reject authority expansion in the C2A synthetic adapter source."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
files = {
    "store_cargo": root / "crates/store/Cargo.toml",
    "bridge_cargo": root / "crates/bridge/Cargo.toml",
    "store_lib": root / "crates/store/src/lib.rs",
    "store_c2": root / "crates/store/src/episode_observation_c2_synthetic.rs",
    "slice_b": root / "crates/store/src/sqlite/episode_observation_slice_b.rs",
    "bridge_c2": root / "crates/bridge/src/episode_observation_curation_batch_c2_synthetic.rs",
    "main": root / "crates/bridge/src/main.rs",
    "hub": root / "crates/bridge/src/hub.rs",
    "state": root / "crates/store/src/lib.rs",
}
text = {name: path.read_text() for name, path in files.items()}
checks = {
    "store_feature_default_off": 'default = ["onnx-embed", "episode-observation-slice-c2-synthetic"]' not in text["store_cargo"],
    "bridge_feature_default_off": 'default = ["onnx-embed", "episode-observation-slice-c2-synthetic"]' not in text["bridge_cargo"],
    "bridge_forwards_store_feature": 'ab-store/episode-observation-slice-c2-synthetic' in text["bridge_cargo"],
    "store_contract_is_opaque": 'pub struct CurationBatchObservationHandle' in text["store_c2"] and 'pub struct EpisodeObservationEvent' not in text["store_lib"],
    "no_public_projection": 'pub fn read_finalized' not in text["store_c2"] and 'pub async fn read_finalized' not in text["slice_b"],
    "no_statestore_expansion": 'curation_batch_observation' not in text["state"],
    "bridge_no_sqlite_import": 'SqliteStore' not in text["bridge_c2"] and 'tokio_rusqlite' not in text["bridge_c2"],
    "bridge_no_raw_event": 'EpisodeObservationEvent' not in text["bridge_c2"],
    "no_environment_key": 'std::env' not in text["store_c2"] and 'var(' not in text["store_c2"],
    "no_startup_injection": 'synthetic_store_observer' not in text["main"] and 'synthetic_store_observer' not in text["hub"],
    "synthetic_feature_named": 'episode-observation-slice-c2-synthetic' in text["store_cargo"],
    "store_owns_derivation": 'derive_active_item_ref' in text["store_c2"] and 'derive_active_item_ref' not in text["bridge_c2"],
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
if failed:
    sys.exit(f"C2A source authority check failed: {', '.join(failed)}")
