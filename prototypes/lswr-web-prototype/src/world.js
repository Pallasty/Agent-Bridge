import { createEventFactory, SOURCES } from "./events.js";
import { cloneJson, makeRollbackRecord, restoreRollbackEntities } from "./rollback.js";
import { blockedVerification, isPositionInsideBounds, verifyAction, verifyRollback } from "./verification.js";

function initialScene() {
  return {
    schema: "agent_bridge.lswr.web_scene.v0",
    world: {
      world_id: "lswr_web_proto_01",
      branch_id: "main",
      tick: 0,
      bounds: { x: [-6, 6], y: [0, 4], z: [-6, 6] },
      authority_mode: "coedit"
    },
    entities: [
      {
        entity_id: "platform",
        kind: "surface",
        label: "Platform",
        transform: { position: [0, 0, 0], rotation: [0, 0, 0], scale: [8, 0.2, 8] },
        geometry: { type: "box" },
        material: { color: "#6f7d8c", opacity: 1.0 },
        state: { selectable: false, locked: true, verification: "verified" },
        tags: ["ground"]
      },
      {
        entity_id: "cube_01",
        kind: "object",
        label: "Cube 01",
        transform: { position: [0, 1, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
        geometry: { type: "box" },
        material: { color: "#2f80ed", opacity: 1.0 },
        state: { selectable: true, selected: false, verification: "verified" },
        tags: ["demo", "movable"]
      }
    ],
    events: [],
    verification: [],
    rollback: {
      next_group_id: "rb_001",
      available_groups: []
    }
  };
}

function nextId(prefix, value) {
  return `${prefix}_${String(value).padStart(3, "0")}`;
}

function normalizeAction(action) {
  return {
    schema: "agent_bridge.lswr.action.v0",
    source: SOURCES.ai,
    rollback_group: action.rollback_group ?? null,
    expected_effect: {},
    ...action
  };
}

function latestActionEvent(events) {
  return [...events].reverse().find((event) => event.event_type === "runtime.action_result") ?? null;
}

export class SemanticWorld {
  constructor() {
    this.state = initialScene();
    this.makeEvent = createEventFactory();
    this.nextAction = 1;
    this.nextCube = 2;
    this.nextRollback = 1;
  }

  world_get() {
    return cloneJson(this.state);
  }

  world_events_query(filter = {}) {
    return cloneJson(
      this.state.events.filter((event) => {
        if (filter.event_type && event.event_type !== filter.event_type) {
          return false;
        }
        if (filter.entity_id && !event.refs?.entities?.includes(filter.entity_id)) {
          return false;
        }
        return true;
      })
    );
  }

  world_evidence_query(refs = {}) {
    return cloneJson(
      this.state.verification.filter((verification) => {
        if (refs.action_id && verification.action_id !== refs.action_id) {
          return false;
        }
        if (refs.entity_id && verification.evidence?.entity_id !== refs.entity_id) {
          return false;
        }
        return true;
      })
    );
  }

  world_export(projectionSnapshot = { projected_entities: [], unprojected_entities: [] }) {
    return cloneJson({
      world: this.state.world,
      entities: this.state.entities,
      events: this.state.events,
      verification: this.state.verification,
      rollback: this.state.rollback,
      projection: {
        adapter: "threejs_web",
        projected_entities: projectionSnapshot.projected_entities,
        unprojected_entities: projectionSnapshot.unprojected_entities
      }
    });
  }

  makeAgentAction(action_type, payload, expected_effect = {}) {
    const action_id = nextId(`act_${action_type}`, this.nextAction);
    this.nextAction += 1;
    const rollback_group = nextId("rb", this.nextRollback);
    this.nextRollback += 1;
    this.state.rollback.next_group_id = nextId("rb", this.nextRollback);
    return normalizeAction({ action_id, action_type, payload, expected_effect, rollback_group });
  }

  nextEntityTemplate({ projectionMiss = false } = {}) {
    const entity_id = nextId("cube", this.nextCube);
    this.nextCube += 1;
    return {
      entity_id,
      kind: "object",
      label: entity_id.replace("_", " ").replace(/\b\w/g, (value) => value.toUpperCase()),
      transform: { position: [2, 1, this.nextCube % 2 === 0 ? -1 : 1], rotation: [0, 0, 0], scale: [1, 1, 1] },
      geometry: { type: "box" },
      material: { color: projectionMiss ? "#f2c94c" : "#f2994a", opacity: 1.0 },
      state: { selectable: true, selected: false, projection_disabled: projectionMiss, verification: "pending" },
      tags: ["demo", "movable"]
    };
  }

  applyHumanSelect(entity_id, screen_position) {
    this.state.entities.forEach((entity) => {
      entity.state.selected = entity.entity_id === entity_id;
    });
    this.state.events.push(
      this.makeEvent({
        event_type: "human.select",
        source: SOURCES.human,
        refs: { entities: [entity_id], viewport: "main_canvas" },
        payload: { selection_state: "selected", screen_position }
      })
    );
    this.tick();
  }

  applyHumanMove(entity_id, from, to, projectionAdapter) {
    const action = normalizeAction({
      action_id: nextId("act_human_move", this.nextAction),
      action_type: "move_entity",
      source: SOURCES.human,
      rollback_group: nextId("rb", this.nextRollback),
      payload: { entity_id, position: to },
      expected_effect: { entity_present: entity_id, position: to, human_visible: true }
    });
    this.nextAction += 1;
    this.nextRollback += 1;
    this.state.events.push(
      this.makeEvent({
        event_type: "human.drag_move",
        source: SOURCES.human,
        refs: { entities: [entity_id], viewport: "main_canvas" },
        payload: { from, to, input: "mouse" }
      })
    );
    return this.world_apply(action, projectionAdapter);
  }

  applyDecision(decision, reason_hint = "human_surface_decision") {
    const latest = latestActionEvent(this.state.events);
    const event_type = decision === "accept" ? "human.accept" : "human.reject";
    this.state.events.push(
      this.makeEvent({
        event_type,
        source: SOURCES.human,
        refs: {
          actions: latest ? [latest.refs.actions[0]] : [],
          entities: latest?.refs.entities ?? []
        },
        payload: {
          decision,
          reason_hint,
          does_not_change_verification: true
        }
      })
    );
    this.tick();
  }

  world_apply(rawAction, projectionAdapter) {
    const action = normalizeAction(rawAction);
    this.state.events.push(
      this.makeEvent({
        event_type: "runtime.action_attempted",
        source: SOURCES.runtime,
        refs: { actions: [action.action_id], entities: actionRefs(action) },
        payload: { action }
      })
    );

    const blocked = this.validate(action);
    if (blocked) {
      const verification = blockedVerification(action, blocked.reason, blocked.evidence);
      this.recordActionResult(action, verification);
      this.tick();
      return { action, verification };
    }

    const before = cloneJson(this.state);
    this.mutate(action);
    projectionAdapter.project(this.state);
    const verification = verifyAction(action, this.state, projectionAdapter.getSnapshot());
    this.applyVerificationToEntity(action, verification);
    projectionAdapter.project(this.state);
    const verificationWithFinalEvidence = verification.verdict === "verified" ? verifyAction(action, this.state, projectionAdapter.getSnapshot()) : verification;
    this.state.verification.push(verificationWithFinalEvidence);
    const verificationEvent = this.recordActionResult(action, verificationWithFinalEvidence);

    const after = cloneJson(this.state);
    this.state.rollback.available_groups.push(
      makeRollbackRecord({
        rollback_group: action.rollback_group,
        before,
        after,
        action_id: action.action_id,
        verification_event_id: verificationEvent.event_id
      })
    );
    this.tick();
    return { action, verification: verificationWithFinalEvidence };
  }

  world_rollback(rollback_group, projectionAdapter) {
    const record = this.state.rollback.available_groups.find((item) => item.rollback_group === rollback_group);
    const action = normalizeAction({
      action_id: nextId("act_rollback", this.nextAction),
      action_type: "rollback",
      source: SOURCES.ai,
      payload: { rollback_group },
      expected_effect: { rollback_group }
    });
    this.nextAction += 1;

    if (!record) {
      const verification = blockedVerification(action, "rollback_group_not_found", { rollback_group });
      this.recordRollback(action, verification);
      this.tick();
      return { action, verification };
    }

    restoreRollbackEntities(this.state, record);
    projectionAdapter.project(this.state);
    const verification = verifyRollback(action, this.state, record, projectionAdapter.getSnapshot());
    this.state.verification.push(verification);
    this.recordRollback(action, verification);
    this.tick();
    return { action, verification };
  }

  latestRollbackGroup() {
    return this.state.rollback.available_groups.at(-1)?.rollback_group ?? null;
  }

  latestVerification() {
    return this.state.verification.at(-1) ?? null;
  }

  selectedEntity() {
    return this.state.entities.find((entity) => entity.state?.selected) ?? null;
  }

  validate(action) {
    if (this.state.world.authority_mode === "locked") {
      return { reason: "authority_mode_locked", evidence: { authority_mode: "locked" } };
    }

    if (action.action_type === "add_entity") {
      const entity = action.payload.entity;
      if (this.state.entities.some((item) => item.entity_id === entity.entity_id)) {
        return { reason: "duplicate_entity_id", evidence: { entity_id: entity.entity_id } };
      }
      if (entity.geometry?.type !== "box") {
        return { reason: "invalid_geometry", evidence: { geometry: entity.geometry } };
      }
      if (!isPositionInsideBounds(this.state.world.bounds, entity.transform?.position)) {
        return { reason: "position_out_of_bounds", evidence: { entity_id: entity.entity_id } };
      }
      return null;
    }

    if (action.action_type === "move_entity" || action.action_type === "set_material") {
      const entity = this.state.entities.find((item) => item.entity_id === action.payload.entity_id);
      if (!entity) {
        return { reason: "entity_not_found", evidence: { entity_id: action.payload.entity_id } };
      }
      if (entity.state?.locked) {
        return { reason: "locked_entity", evidence: { entity_id: entity.entity_id } };
      }
      if (action.action_type === "move_entity" && !isPositionInsideBounds(this.state.world.bounds, action.payload.position)) {
        return { reason: "position_out_of_bounds", evidence: { entity_id: entity.entity_id, position: action.payload.position } };
      }
    }

    return null;
  }

  mutate(action) {
    if (action.action_type === "add_entity") {
      this.state.entities.push(cloneJson(action.payload.entity));
    }
    if (action.action_type === "move_entity") {
      const entity = this.state.entities.find((item) => item.entity_id === action.payload.entity_id);
      entity.transform.position = cloneJson(action.payload.position);
    }
    if (action.action_type === "set_material") {
      const entity = this.state.entities.find((item) => item.entity_id === action.payload.entity_id);
      entity.material = { ...entity.material, ...cloneJson(action.payload.material) };
    }
  }

  applyVerificationToEntity(action, verification) {
    const entityId = actionRefs(action)[0];
    const entity = this.state.entities.find((item) => item.entity_id === entityId);
    if (!entity) {
      return;
    }
    entity.state.verification = verification.verdict;
    entity.state.verification_reason = verification.reason;
  }

  recordActionResult(action, verification) {
    if (verification.verdict === "blocked") {
      this.state.verification.push(verification);
    }
    const event = this.makeEvent({
      event_type: "runtime.action_result",
      source: SOURCES.runtime,
      refs: { actions: [action.action_id], entities: actionRefs(action) },
      payload: { action_type: action.action_type },
      verification
    });
    this.state.events.push(event);
    return event;
  }

  recordRollback(action, verification) {
    const event = this.makeEvent({
      event_type: "runtime.rollback_applied",
      source: SOURCES.runtime,
      refs: { actions: [action.action_id], rollback_groups: [action.payload.rollback_group] },
      payload: { rollback_group: action.payload.rollback_group },
      verification
    });
    this.state.events.push(event);
    return event;
  }

  tick() {
    this.state.world.tick += 1;
  }
}

function actionRefs(action) {
  if (action.action_type === "add_entity") {
    return [action.payload.entity.entity_id];
  }
  if (action.payload?.entity_id) {
    return [action.payload.entity_id];
  }
  return [];
}
