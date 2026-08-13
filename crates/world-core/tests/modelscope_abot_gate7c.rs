use ab_world_core::projection_provider::{ProjectionRequestEnvelope, SimulatedWorldRollout};
use serde_json::Value;

const RECEIPT: &str = include_str!(
    "../../../docs/design/evidence/modelscope_abot_gate7c_artifact_receipt_2026_08_12.json"
);

#[test]
fn gate7c_request_and_rollout_satisfy_provider_neutral_contracts() {
    let receipt: Value = serde_json::from_str(RECEIPT).expect("valid Gate 7C receipt JSON");
    let request: ProjectionRequestEnvelope =
        serde_json::from_value(receipt["request"].clone()).expect("projection request shape");
    let rollout: SimulatedWorldRollout =
        serde_json::from_value(receipt["rollout"].clone()).expect("rollout shape");

    assert!(request.validate().is_ok());
    assert!(rollout.validate().is_ok());
    assert_eq!(request.request_id, rollout.request_id);
    assert_eq!(request.provider_id, rollout.provider.id);
    assert!(!rollout.truth_boundary.external_world_effect_claimed);
    assert!(rollout.truth_boundary.verified_to.is_none());
}
