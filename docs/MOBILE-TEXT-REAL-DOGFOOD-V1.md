# Mobile text real-task dogfood V1

Status: preregistered; source-only; no phone session started.

## Product question

Can one foreground, human-confirmed mobile text observation remove at least one
desktop context switch or manual copy action from a real Agent-Bridge task,
without granting attention, memory, actuation, package, or deployment authority?

This is a use-value test of the existing mobile text path. It is not a new
projection protocol, a voice expansion, or an embodiment/research gate.

## One bounded workflow

The trial is a **device-readiness handoff** during an actual Agent-Bridge mobile
acceptance task:

1. Codex starts one short-lived projection only after the owner separately
   authorizes connecting the named phone.
2. The projected frame asks for the current device-readiness fact needed by the
   active task, such as whether the phone is idle and ready for the already
   described acceptance step.
3. The owner types or dictates a draft on the phone, reviews it, and taps
   `SUBMIT TEXT` in the foreground.
4. Codex reads the exact session with `mobile_projection_status(session_id=...)`
   and uses the observation to choose the next step or to stop.
5. The observation is information only. It does not authorize ADB, APK changes,
   app launch, deployment, merge, push, or any other action. Those remain
   separate owner gates.
6. Codex stops the projection. After evidence is reduced to metadata, the MCP
   process is reconnected so the session-local full text is no longer
   retrievable.

The trial must use a fact that the ongoing task genuinely needs. A canned
phrase submitted only to make the test pass is invalid.

## Locked baseline and success rule

The comparison is the ordinary fallback for the same handoff: the owner returns
to the desktop Codex surface and types or pastes the readiness fact there.
That fallback costs one desktop surface switch and one desktop text-entry
action. It is recorded before the mobile observation is submitted.

`PASS_USEFUL` requires all of the following:

- exactly one unique accepted observation;
- Codex reads it through the exact-session MCP status call;
- the observation changes or confirms a real next-step decision;
- at least one fewer desktop surface switch or manual copy/text-entry action
  than the preregistered fallback, without increasing either metric;
- foreground user confirmation, no background capture, no implicit control;
- no full observation text copied into the scorecard, reports, logs, memory, or
  commit; only identifiers, hashes, counts, timestamps, and short evidence
  references may persist;
- phone connection, APK mutation, runtime deployment, merge, and push boundaries
  are recorded independently and no ungranted boundary is crossed;
- the projection is stopped and a fresh MCP process can no longer retrieve the
  exact session.

If safety and consumption pass but no interaction cost is saved, the result is
`FREEZE_NO_VALUE`. Missing authoritative evidence is `INCOMPLETE`; any crossed
authority or retention boundary is `FAIL_SAFETY`.

## Evidence record

Use `scripts/mobile_text_dogfood_scorecard.py` with a JSON record conforming to
`agent_bridge.mobile_text_real_dogfood_scorecard.v1`. The record deliberately
has no observation-text field. The validator rejects unknown keys so text
cannot be smuggled into an otherwise valid scorecard.

The committed repository contains the preregistration and validator only. The
real trial record is created after the device gate and may be committed only
after confirming it contains metadata and evidence references, not the mobile
observation body.

## Authority state at preregistration

- source/design work: authorized by the active goal;
- phone connection: not yet authorized for this trial;
- APK install, replacement, launch, or uninstall: not authorized;
- runtime deployment or MCP restart: not authorized;
- merge or remote push: not authorized.
