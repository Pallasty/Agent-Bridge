function sameVector(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((item, index) => Math.abs(item - b[index]) < 0.001);
}

function entityPosition(entity) {
  return entity?.transform?.position ?? null;
}

function projectionFor(snapshot, entityId) {
  return snapshot.projected_entities.find((entity) => entity.entity_id === entityId) ?? null;
}

function targetEntityId(action) {
  if (action.action_type === "add_entity") {
    return action.payload.entity.entity_id;
  }
  return action.payload.entity_id;
}

function baseVerification(action, targetId) {
  return {
    schema: "agent_bridge.lswr.verification.v0",
    action_id: action.action_id,
    verdict: "verified",
    reason: null,
    method: "web_scene_projection_check",
    verified_to: targetId ? `entity:${targetId}` : null,
    evidence: {
      adapter_kind: "threejs_web",
      entity_id: targetId,
      projected: false,
      bounds_nonzero: false,
      hit_testable: false,
      inside_bounds: false
    }
  };
}

export function blockedVerification(action, reason, evidence = {}) {
  return {
    schema: "agent_bridge.lswr.verification.v0",
    action_id: action.action_id,
    verdict: "blocked",
    reason,
    method: "web_scene_policy_check",
    verified_to: null,
    evidence: {
      adapter_kind: "threejs_web",
      policy_checked: true,
      ...evidence
    }
  };
}

export function verifyAction(action, state, projectionSnapshot) {
  const targetId = targetEntityId(action);
  const entity = state.entities.find((item) => item.entity_id === targetId);
  const verification = baseVerification(action, targetId);

  if (!entity) {
    verification.verdict = "not_verified";
    verification.reason = "expected_effect_absent";
    return verification;
  }

  const projected = projectionFor(projectionSnapshot, targetId);
  verification.evidence.inside_bounds = isPositionInsideBounds(state.world.bounds, entityPosition(entity));

  if (!projected) {
    verification.verdict = "not_verified";
    verification.reason = "projection_object_absent";
    return verification;
  }

  verification.evidence.projected = true;
  verification.evidence.bounds_nonzero = projected.bounds_nonzero;
  verification.evidence.hit_testable = projected.hit_testable;
  verification.evidence.position = projected.position;
  verification.evidence.material_opacity = projected.material_opacity;

  if (!projected.bounds_nonzero) {
    verification.verdict = "not_verified";
    verification.reason = "bounds_zero";
    return verification;
  }

  if (projected.material_opacity <= 0) {
    verification.verdict = "not_verified";
    verification.reason = "material_opacity_zero";
    return verification;
  }

  if (action.expected_effect?.hit_testable && !projected.hit_testable) {
    verification.verdict = "not_verified";
    verification.reason = "hit_test_failed";
    return verification;
  }

  if (action.expected_effect?.position && !sameVector(action.expected_effect.position, entityPosition(entity))) {
    verification.verdict = "not_verified";
    verification.reason = "position_mismatch";
    verification.evidence.expected_position = action.expected_effect.position;
    return verification;
  }

  if (!verification.evidence.inside_bounds) {
    verification.verdict = "not_verified";
    verification.reason = "position_out_of_bounds";
  }

  return verification;
}

export function verifyRollback(action, state, record, projectionSnapshot) {
  const restored = JSON.stringify(record.before.entities.map((entity) => [entity.entity_id, entity.transform]));
  const current = JSON.stringify(state.entities.map((entity) => [entity.entity_id, entity.transform]));
  const projectedSelectable = state.entities
    .filter((entity) => entity.state?.selectable)
    .every((entity) => projectionSnapshot.projected_entities.some((projected) => projected.entity_id === entity.entity_id));

  return {
    schema: "agent_bridge.lswr.verification.v0",
    action_id: action.action_id,
    verdict: restored === current && projectedSelectable ? "verified" : "not_verified",
    reason: restored === current && projectedSelectable ? null : "rollback_projection_mismatch",
    method: "web_scene_rollback_check",
    verified_to: `rollback:${record.rollback_group}`,
    evidence: {
      adapter_kind: "threejs_web",
      rollback_group: record.rollback_group,
      semantic_state_restored: restored === current,
      projected_selectable_entities: projectedSelectable
    }
  };
}

export function isPositionInsideBounds(bounds, position) {
  if (!bounds || !position) {
    return false;
  }
  return (
    position[0] >= bounds.x[0] &&
    position[0] <= bounds.x[1] &&
    position[1] >= bounds.y[0] &&
    position[1] <= bounds.y[1] &&
    position[2] >= bounds.z[0] &&
    position[2] <= bounds.z[1]
  );
}
