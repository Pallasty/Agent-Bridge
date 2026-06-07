import "./styles.css";
import { ProjectionAdapter } from "./projection.js";
import { SemanticWorld } from "./world.js";

const world = new SemanticWorld();
const projection = new ProjectionAdapter(document.querySelector("#scene"));
let dragStart = null;
let pendingDragEntity = null;

const nodes = {
  worldId: document.querySelector("#world-id"),
  worldTick: document.querySelector("#world-tick"),
  selectedId: document.querySelector("#selected-id"),
  latestVerdict: document.querySelector("#latest-verdict"),
  latestAction: document.querySelector("#latest-action"),
  latestReason: document.querySelector("#latest-reason"),
  latestRollback: document.querySelector("#latest-rollback"),
  eventList: document.querySelector("#event-list"),
  readbackJson: document.querySelector("#readback-json")
};

function sync() {
  projection.project(world.state);
  const exportPacket = world.world_export(projection.getSnapshot());
  const latestVerification = world.latestVerification();
  const selected = world.selectedEntity();
  const latestRollback = world.latestRollbackGroup();

  nodes.worldId.textContent = exportPacket.world.world_id;
  nodes.worldTick.textContent = String(exportPacket.world.tick);
  nodes.selectedId.textContent = selected?.entity_id ?? "none";
  nodes.latestVerdict.textContent = latestVerification?.verdict ?? "verified";
  nodes.latestVerdict.className = `verdict ${latestVerification?.verdict ?? "verified"}`;
  nodes.latestAction.textContent = latestVerification?.action_id ?? "none";
  nodes.latestReason.textContent = latestVerification?.reason ?? "none";
  nodes.latestRollback.textContent = latestRollback ?? "none";
  nodes.readbackJson.textContent = JSON.stringify(exportPacket, null, 2);

  renderEvents(exportPacket.events);
}

function renderEvents(events) {
  nodes.eventList.replaceChildren();
  const recent = events.slice(-8).reverse();
  for (const event of recent) {
    const item = document.createElement("li");
    const verdict = event.verification?.verdict ?? "event";
    item.className = `event-row ${verdict}`;
    item.innerHTML = `
      <span>${event.event_id}</span>
      <strong>${event.event_type}</strong>
      <em>${event.verification?.reason ?? event.verification?.verdict ?? "recorded"}</em>
    `;
    nodes.eventList.appendChild(item);
  }
}

function applyAction(action) {
  world.world_apply(action, projection);
  sync();
}

function selectedOrDefault() {
  return world.selectedEntity()?.entity_id ?? "cube_01";
}

document.querySelector("#add-cube").addEventListener("click", () => {
  const entity = world.nextEntityTemplate();
  applyAction(
    world.makeAgentAction(
      "add_entity",
      { entity },
      { entity_present: entity.entity_id, human_visible: true, hit_testable: true }
    )
  );
});

document.querySelector("#move-cube").addEventListener("click", () => {
  const entity_id = selectedOrDefault();
  const entity = world.state.entities.find((item) => item.entity_id === entity_id);
  const current = entity.transform.position;
  const nextPosition = current[0] < 0 ? [1.8, 1, -1.4] : [-2.1, 1, 1.2];
  applyAction(
    world.makeAgentAction(
      "move_entity",
      { entity_id, position: nextPosition },
      { entity_present: entity_id, position: nextPosition, human_visible: true }
    )
  );
});

document.querySelector("#set-material").addEventListener("click", () => {
  const entity_id = selectedOrDefault();
  applyAction(
    world.makeAgentAction(
      "set_material",
      { entity_id, material: { color: "#27ae60", opacity: 1.0 } },
      { entity_present: entity_id, material_color: "#27ae60", human_visible: true }
    )
  );
});

document.querySelector("#force-miss").addEventListener("click", () => {
  const entity = world.nextEntityTemplate({ projectionMiss: true });
  applyAction(
    world.makeAgentAction(
      "add_entity",
      { entity },
      { entity_present: entity.entity_id, human_visible: true, hit_testable: true }
    )
  );
});

document.querySelector("#blocked-action").addEventListener("click", () => {
  applyAction(
    world.makeAgentAction(
      "move_entity",
      { entity_id: "platform", position: [0, 1, 0] },
      { entity_present: "platform", position: [0, 1, 0], human_visible: true }
    )
  );
});

document.querySelector("#rollback").addEventListener("click", () => {
  const group = world.latestRollbackGroup();
  if (group) {
    world.world_rollback(group, projection);
    sync();
  }
});

document.querySelector("#accept-action").addEventListener("click", () => {
  world.applyDecision("accept", "human_accepts_latest_action");
  sync();
});

document.querySelector("#reject-action").addEventListener("click", () => {
  world.applyDecision("reject", "human_rejects_latest_action");
  sync();
});

projection.renderer.domElement.addEventListener("pointerdown", (event) => {
  const entity_id = projection.selectAt(event.clientX, event.clientY);
  if (!entity_id) {
    return;
  }
  const point = projection.groundPointAt(event.clientX, event.clientY);
  const entity = world.state.entities.find((item) => item.entity_id === entity_id);
  world.applyHumanSelect(entity_id, [Math.round(event.offsetX), Math.round(event.offsetY)]);
  pendingDragEntity = entity_id;
  dragStart = point ?? [...entity.transform.position];
  sync();
});

projection.renderer.domElement.addEventListener("pointerup", (event) => {
  if (!pendingDragEntity || !dragStart) {
    return;
  }
  const end = projection.groundPointAt(event.clientX, event.clientY);
  if (end) {
    world.applyHumanMove(pendingDragEntity, dragStart, end, projection);
  }
  pendingDragEntity = null;
  dragStart = null;
  sync();
});

window.lswr = {
  world_get: () => world.world_get(),
  world_apply: (action) => {
    const result = world.world_apply(action, projection);
    sync();
    return result;
  },
  world_events_query: (filter) => world.world_events_query(filter),
  world_evidence_query: (refs) => world.world_evidence_query(refs),
  world_rollback: (rollback_group) => {
    const result = world.world_rollback(rollback_group, projection);
    sync();
    return result;
  },
  world_export: () => world.world_export(projection.getSnapshot())
};

window.lswr_debug = {
  screen_for_entity: (entity_id) => projection.screenPointForEntity(entity_id)
};

sync();
