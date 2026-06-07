export function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

export function makeRollbackRecord({ rollback_group, before, after, action_id, verification_event_id }) {
  return {
    rollback_group,
    before: { entities: cloneJson(before.entities) },
    after: { entities: cloneJson(after.entities) },
    actions: [action_id],
    verification_event_id
  };
}

export function restoreRollbackEntities(state, record) {
  state.entities = cloneJson(record.before.entities);
}
