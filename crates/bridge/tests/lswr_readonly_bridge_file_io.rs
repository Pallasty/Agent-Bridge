use ab_bridge::lswr_snapshot_bridge::{
    build_readonly_bridge_snapshot, ReadOnlyBridgeSnapshot, ReadOnlyBridgeSnapshotOptions,
};
use ab_world_core::{WorldLedger, WorldLedgerSnapshot, SCHEMA_LEDGER_SNAPSHOT};

const LEDGER_SNAPSHOT_JSON: &str = include_str!("fixtures/lswr_ledger_snapshot_v0.json");
const PROJECTION_JSON: &str = include_str!("fixtures/lswr_readonly_bridge_projection_v0.json");

#[test]
fn ledger_snapshot_fixture_imports_and_projects_to_existing_readonly_fixture() {
    let snapshot: WorldLedgerSnapshot =
        serde_json::from_str(LEDGER_SNAPSHOT_JSON).expect("ledger snapshot fixture json");
    assert_eq!(snapshot.schema, SCHEMA_LEDGER_SNAPSHOT);

    let projection = build_readonly_bridge_snapshot(
        snapshot,
        ReadOnlyBridgeSnapshotOptions {
            include_snapshot: false,
        },
    )
    .expect("readonly bridge projection");
    let expected: ReadOnlyBridgeSnapshot =
        serde_json::from_str(PROJECTION_JSON).expect("projection fixture json");

    assert_eq!(projection, expected);
}

#[test]
fn ledger_snapshot_fixture_round_trips_through_core_import_export() {
    let snapshot: WorldLedgerSnapshot =
        serde_json::from_str(LEDGER_SNAPSHOT_JSON).expect("ledger snapshot fixture json");
    let ledger = WorldLedger::from_snapshot(snapshot.clone()).expect("ledger import");

    assert_eq!(ledger.to_snapshot(), snapshot);
}

#[test]
fn ledger_snapshot_file_projection_can_include_raw_snapshot_when_requested() {
    let snapshot: WorldLedgerSnapshot =
        serde_json::from_str(LEDGER_SNAPSHOT_JSON).expect("ledger snapshot fixture json");
    let projection = build_readonly_bridge_snapshot(
        snapshot.clone(),
        ReadOnlyBridgeSnapshotOptions {
            include_snapshot: true,
        },
    )
    .expect("readonly bridge projection");

    assert_eq!(projection.snapshot, Some(snapshot));
}
