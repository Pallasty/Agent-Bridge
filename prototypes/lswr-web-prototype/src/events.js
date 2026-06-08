export function createEventFactory() {
  let nextEvent = 1;

  return function makeEvent({ event_type, source, refs = {}, payload = {}, verification = null }) {
    const event = {
      schema: "agent_bridge.lswr.event.v0",
      event_id: `evt_${String(nextEvent).padStart(4, "0")}`,
      event_type,
      source,
      refs,
      payload,
      at: new Date().toISOString()
    };

    nextEvent += 1;
    if (verification) {
      event.verification = verification;
    }
    return event;
  };
}

export const SOURCES = {
  ai: { participant_id: "ai:codex", authority_mode: "coedit" },
  human: { participant_id: "human:owner", surface: "web_scene" },
  runtime: { participant_id: "runtime:lswr-web-prototype", surface: "web_scene" }
};
