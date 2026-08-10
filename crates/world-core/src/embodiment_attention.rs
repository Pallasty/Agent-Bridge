//! P2 shadow-attention over an already aggregated ObservedWorld.
//!
//! The selector is deterministic and non-authoritative.  It does not call a
//! model, write memory, request authority, or create a projection plan.

use serde::{Deserialize, Serialize};

use crate::{
    BodyId, DecisionAuthority, ObservationEnvelope, ObservedWorld, OBSERVED_WORLD_SCHEMA_V0,
};

pub const ATTENTION_DECISION_SCHEMA_V0: &str = "agent_bridge.attention_decision.v0";
pub const SHADOW_ATTENTION_MODE: &str = "shadow";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShadowAttentionPolicy {
    pub max_observations: usize,
    #[serde(default)]
    pub required_sources: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AttentionObservationRef {
    pub body_id: BodyId,
    pub source: String,
    pub observed_at_unix_ms: u64,
    pub world_revision: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AttentionDecision {
    pub schema: String,
    pub mode: String,
    pub decision_id: String,
    pub body_id: BodyId,
    pub input_schema: String,
    pub input_world_revision: u64,
    pub selected_observations: Vec<AttentionObservationRef>,
    pub omitted_observations: usize,
    pub authority: DecisionAuthority,
}

impl AttentionDecision {
    pub fn is_shadow(&self) -> bool {
        self.mode == SHADOW_ATTENTION_MODE
    }

    pub fn is_non_authoritative(&self) -> bool {
        self.authority == DecisionAuthority::NonAuthoritative
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ShadowAttentionViolation {
    InvalidPolicy,
    BodyNotFound(String),
    NoObservations(String),
    RequiredSourceMissing(String),
    UnsupportedWorldSchema(String),
}

/// Select a bounded, deterministic attention surface from `ObservedWorld`.
///
/// Required sources are ranked first in declaration order.  Remaining
/// observations are ranked by confidence, then freshness timestamp, then
/// source name.  Only references leave this function; raw payloads are not
/// copied into the decision.
pub fn shadow_attention(
    world: &ObservedWorld,
    body_id: &BodyId,
    policy: &ShadowAttentionPolicy,
) -> Result<AttentionDecision, Vec<ShadowAttentionViolation>> {
    let mut violations = Vec::new();
    if policy.max_observations == 0 {
        violations.push(ShadowAttentionViolation::InvalidPolicy);
    }
    if world.schema != OBSERVED_WORLD_SCHEMA_V0 {
        violations.push(ShadowAttentionViolation::UnsupportedWorldSchema(
            world.schema.clone(),
        ));
    }
    if !world.bodies.iter().any(|body| &body.body_id == body_id) {
        violations.push(ShadowAttentionViolation::BodyNotFound(body_id.to_string()));
    }

    let body_observations: Vec<&ObservationEnvelope> = world
        .observations
        .iter()
        .filter(|observation| &observation.body_id == body_id)
        .collect();
    if body_observations.is_empty() {
        violations.push(ShadowAttentionViolation::NoObservations(
            body_id.to_string(),
        ));
    }

    for source in &policy.required_sources {
        if !body_observations
            .iter()
            .any(|observation| &observation.source == source)
        {
            violations.push(ShadowAttentionViolation::RequiredSourceMissing(
                source.clone(),
            ));
        }
    }
    if !violations.is_empty() {
        return Err(violations);
    }

    let required_rank = |source: &str| {
        policy
            .required_sources
            .iter()
            .position(|required| required == source)
            .unwrap_or(usize::MAX)
    };
    let mut ranked = body_observations;
    ranked.sort_by(|left, right| {
        required_rank(left.source.as_str())
            .cmp(&required_rank(right.source.as_str()))
            .then_with(|| right.confidence.total_cmp(&left.confidence))
            .then_with(|| right.observed_at_unix_ms.cmp(&left.observed_at_unix_ms))
            .then_with(|| left.source.cmp(&right.source))
    });

    let omitted_observations = ranked.len().saturating_sub(policy.max_observations);
    let selected_observations = ranked
        .into_iter()
        .take(policy.max_observations)
        .map(|observation| AttentionObservationRef {
            body_id: observation.body_id.clone(),
            source: observation.source.clone(),
            observed_at_unix_ms: observation.observed_at_unix_ms,
            world_revision: observation.world_revision,
        })
        .collect();

    Ok(AttentionDecision {
        schema: ATTENTION_DECISION_SCHEMA_V0.into(),
        mode: SHADOW_ATTENTION_MODE.into(),
        decision_id: format!("shadow-attention-{}-{}", body_id, world.world_revision),
        body_id: body_id.clone(),
        input_schema: world.schema.clone(),
        input_world_revision: world.world_revision,
        selected_observations,
        omitted_observations,
        authority: DecisionAuthority::NonAuthoritative,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        aggregate_observed_world, BodyDescriptor, ObservationEnvelope, OBSERVATION_SCHEMA_V0,
    };
    use serde_json::json;

    fn body(id: &str) -> BodyDescriptor {
        BodyDescriptor {
            body_id: BodyId::from_raw(id),
            kind: "host".into(),
            label: id.into(),
            capabilities: vec!["body_status".into()],
            authority_scope: "local".into(),
            online: true,
            last_observed_unix_ms: Some(100),
        }
    }

    fn observation(body_id: &str, source: &str, confidence: f32) -> ObservationEnvelope {
        ObservationEnvelope {
            schema: OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw(body_id),
            source: source.into(),
            observed_at_unix_ms: 100,
            freshness_ms: 20,
            confidence,
            world_revision: 4,
            payload: json!({"raw": "omitted"}),
        }
    }

    fn world() -> ObservedWorld {
        aggregate_observed_world(
            vec![body("body-a")],
            vec![
                observation("body-a", "memory", 0.8),
                observation("body-a", "cpu", 0.9),
                observation("body-a", "network", 0.7),
            ],
            110,
            30,
        )
        .unwrap()
    }

    #[test]
    fn shadow_attention_is_bounded_deterministic_and_non_authoritative() {
        let decision = shadow_attention(
            &world(),
            &BodyId::from_raw("body-a"),
            &ShadowAttentionPolicy {
                max_observations: 2,
                required_sources: vec!["memory".into()],
            },
        )
        .unwrap();
        assert!(decision.is_shadow());
        assert!(decision.is_non_authoritative());
        assert_eq!(decision.input_world_revision, 4);
        assert_eq!(decision.selected_observations.len(), 2);
        assert_eq!(decision.selected_observations[0].source, "memory");
        assert_eq!(decision.selected_observations[1].source, "cpu");
        assert_eq!(decision.omitted_observations, 1);
    }

    #[test]
    fn shadow_attention_rejects_missing_required_source() {
        let errors = shadow_attention(
            &world(),
            &BodyId::from_raw("body-a"),
            &ShadowAttentionPolicy {
                max_observations: 2,
                required_sources: vec!["gpu".into()],
            },
        )
        .unwrap_err();
        assert!(
            errors.contains(&ShadowAttentionViolation::RequiredSourceMissing(
                "gpu".into()
            ))
        );
    }

    #[test]
    fn shadow_attention_rejects_invalid_target_and_policy() {
        let errors = shadow_attention(
            &world(),
            &BodyId::from_raw("body-b"),
            &ShadowAttentionPolicy {
                max_observations: 0,
                required_sources: Vec::new(),
            },
        )
        .unwrap_err();
        assert!(errors.contains(&ShadowAttentionViolation::InvalidPolicy));
        assert!(errors.contains(&ShadowAttentionViolation::BodyNotFound("body-b".into())));
        assert!(errors.contains(&ShadowAttentionViolation::NoObservations("body-b".into())));
    }
}
