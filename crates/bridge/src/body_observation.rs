//! Pure, read-only afferent adapter from local body telemetry into world-core.
//! It grants no authority, performs no action, and persists no raw sample.

use ab_world_core::{
    aggregate_observed_world, shadow_attention, AttentionDecision, BodyDescriptor, BodyId,
    ObservationEnvelope, ObservedWorld, ShadowAttentionPolicy, OBSERVATION_SCHEMA_V0,
};
use serde_json::Value;

pub const BODY_OBSERVATION_SOURCE: &str = "body_status";

pub fn body_observation_envelope(
    body_status: &Value,
    world_revision: u64,
) -> Result<(BodyDescriptor, ObservationEnvelope), String> {
    if body_status.get("enabled").and_then(Value::as_bool) != Some(true) {
        return Err("body telemetry is disabled".into());
    }
    let status = body_status
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    if !matches!(status, "ok" | "partial") {
        return Err(format!("body telemetry status is {status}"));
    }
    if body_status
        .pointer("/freshness/status")
        .and_then(Value::as_str)
        != Some("fresh")
    {
        return Err("body telemetry is not fresh".into());
    }
    let body_id_raw = body_status
        .pointer("/identity/body_id")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "body identity is missing".to_string())?;
    let instance_id = body_status
        .pointer("/identity/body_instance_id")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "body instance identity is missing".to_string())?;
    let observed_at_unix_ms = body_status
        .pointer("/sample/observed_at_unix_ms")
        .and_then(Value::as_i64)
        .and_then(|value| u64::try_from(value).ok())
        .ok_or_else(|| "body observation timestamp is missing".to_string())?;
    let confidence = body_status
        .pointer("/coverage/required_ratio")
        .and_then(Value::as_f64)
        .filter(|value| value.is_finite() && (0.0..=1.0).contains(value))
        .ok_or_else(|| "body coverage is missing or invalid".to_string())?
        as f32;
    if confidence == 0.0 || (status == "ok" && confidence < 1.0) {
        return Err("body coverage does not support the declared status".into());
    }

    let body_id = BodyId::from_raw(body_id_raw);
    let descriptor = BodyDescriptor {
        body_id: body_id.clone(),
        kind: std::env::consts::OS.to_string(),
        label: "current local body".into(),
        capabilities: vec!["interoception".into()],
        authority_scope: "local_read_only".into(),
        online: true,
        last_observed_unix_ms: Some(observed_at_unix_ms),
    };
    let envelope = ObservationEnvelope {
        schema: OBSERVATION_SCHEMA_V0.into(),
        body_id,
        source: BODY_OBSERVATION_SOURCE.into(),
        observed_at_unix_ms,
        freshness_ms: body_status
            .pointer("/freshness/age_ms")
            .and_then(Value::as_u64)
            .unwrap_or(0),
        confidence,
        world_revision,
        payload: serde_json::json!({
            "body_instance_id": instance_id,
            "organ_id": body_status.get("organ_id"),
            "collector": body_status.get("collector"),
            "coverage": body_status.get("coverage"),
            "pressure": body_status.get("pressure"),
            "sample": body_status.get("sample"),
        }),
    };
    Ok((descriptor, envelope))
}

pub fn assemble_body_world(
    body_status: &Value,
    world_revision: u64,
    now_unix_ms: u64,
    max_age_ms: u64,
) -> Result<ObservedWorld, String> {
    let (body, observation) = body_observation_envelope(body_status, world_revision)?;
    aggregate_observed_world(vec![body], vec![observation], now_unix_ms, max_age_ms)
        .map_err(|violations| format!("body world rejected: {violations:?}"))
}

pub fn attend_body(world: &ObservedWorld, body_id: &BodyId) -> Result<AttentionDecision, String> {
    shadow_attention(
        world,
        body_id,
        &ShadowAttentionPolicy {
            max_observations: 1,
            required_sources: vec![BODY_OBSERVATION_SOURCE.into()],
        },
    )
    .map_err(|violations| format!("body attention rejected: {violations:?}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn status(status: &str, ratio: f64, freshness: &str) -> Value {
        json!({
            "enabled": true,
            "status": status,
            "identity": {"body_id":"body-linux-test", "body_instance_id":"boot-test"},
            "organ_id": "interoception",
            "collector": {"adapter_id":"test"},
            "freshness": {"status": freshness, "age_ms": 5},
            "coverage": {"required_ratio": ratio},
            "pressure": "nominal",
            "sample": {"observed_at_unix_ms": 1_000}
        })
    }

    #[test]
    fn partial_observation_preserves_uncertainty_and_reaches_shadow_attention() {
        let world = assemble_body_world(&status("partial", 0.75, "fresh"), 7, 1_010, 100).unwrap();
        assert_eq!(world.observations[0].confidence, 0.75);
        let decision = attend_body(&world, &world.bodies[0].body_id).unwrap();
        assert!(decision.is_shadow());
        assert!(decision.is_non_authoritative());
        assert_eq!(decision.selected_observations.len(), 1);
    }

    #[test]
    fn unavailable_zero_coverage_and_stale_samples_fail_closed() {
        assert!(body_observation_envelope(&status("unavailable", 0.0, "fresh"), 1).is_err());
        assert!(body_observation_envelope(&status("partial", 0.0, "fresh"), 1).is_err());
        assert!(body_observation_envelope(&status("ok", 1.0, "stale"), 1).is_err());
    }

    #[test]
    fn aggregation_enforces_absolute_age() {
        assert!(assemble_body_world(&status("ok", 1.0, "fresh"), 1, 2_000, 100).is_err());
    }
}
