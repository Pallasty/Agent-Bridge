# Quick Design Spec: Mobile Voice and Text Input Addition

**Type**: Addition
**System**: Android Companion Projection Interaction
**GDD Reference**: No system GDD or systems index exists. Current contracts are documented in `docs/DESIGN-mobile-device-bridge-2026-05-23.md` and `docs/reports/2026-08-13-mobile-text-perception.md`.
**Date**: 2026-08-15

## Change Summary

Keep the existing foreground, user-submit-only text observation path as the
only device-to-host input protocol. Add a visible **Dictate draft** action that
opens Android's system speech-recognition UI and places the selected transcript
in the existing editable text field. Dictation never submits automatically.

This first voice slice is voice-assisted text composition, not raw-audio
capture and not a new voice-observation protocol.

## Motivation

The current companion already gives the phone holder a trustworthy text path,
but typing on a phone is unnecessarily slow for short observations. The useful
product improvement is faster composition while preserving the boundary that
the holder can inspect, edit, cancel, and explicitly submit the final text.

## Current State

- `ProjectionActivity` shows the text editor only inside a foreground,
  consented, expiring projection session.
- **Submit text** produces an authenticated
  `agent_bridge.mobile_text_observation.v0` envelope.
- The host validates session binding, freshness, HMAC, digest, size, nonce,
  foreground submit evidence, ephemeral retention, and zero authority.
- Accepted text remains in the current MCP process only. It is not memory,
  attention, instruction, or action authority.
- The installed companion on the observed OPPO PKW110 is version `0.2.0`,
  target SDK 35, stopped, with no running service and no microphone permission.
- No active projection session was present during this design audit.

## Design Delta

Current mobile text perception requires typed text followed by an explicit
submit. This addition allows the holder to compose that same draft through a
system-owned speech-recognition Activity.

The resulting rule is:

1. **Dictate draft** is available only after the holder has approved the
   foreground projection session.
2. Selecting it opens an Android system speech-recognition UI. The companion
   does not create an `AudioRecord`, `MediaRecorder`, foreground service, or
   background microphone path.
3. A successful recognition result populates the existing `EditText`. It does
   not send a network request and does not clear an existing draft without a
   visible holder action.
4. The holder may edit or discard the transcript. Only the existing
   **Submit text** action creates an authenticated observation.
5. Cancellation, missing recognizer support, empty results, or recognizer
   errors leave the current draft intact and show a local status message.
6. The companion requests no `android.permission.RECORD_AUDIO` permission.
   Audio handling, retention, and any recognizer network use remain under the
   selected Android recognizer's visible system surface and policy. The UI must
   describe this boundary before launch.
7. There is no automatic retry, continuous listening, wake word, interruption
   authority, durable transcript, memory promotion, or actuation path.

## New Rules and Values

| Rule | Value |
|---|---|
| Entry point | Foreground button labelled **Dictate draft** |
| Recognition surface | Android system Activity via `RecognizerIntent.ACTION_RECOGNIZE_SPEECH` |
| Language | Device locale, explicitly passed as the recognizer language hint |
| Result count | Request one best result; ignore additional alternatives in v0 |
| Transcript destination | Existing `EditText` only |
| Submission | Existing **Submit text** action only |
| Text bound | Existing 1–1000 character rule; over-limit recognition stays local and is not submittable until edited |
| Raw audio | Never read, stored, hashed, logged, or transmitted by the companion |
| Companion microphone permission | Must remain absent |
| Retention | Existing `ephemeral_session_only` text observation after explicit submit |
| Authority | Attention, memory, and actuation remain `false` |
| Fallback | Fail closed with local guidance when no system recognizer is available |

## Affected Systems

| System | Impact | Action Required |
|---|---|---|
| Android `ProjectionActivity` | Adds visible dictation launcher and result handling | Source change in a dedicated branch |
| Android Manifest | Must remain free of `RECORD_AUDIO` | Add negative manifest test/gate; no permission change |
| Text observation protocol | Reused without schema changes | Preserve protocol tests and host validation |
| MCP projection runtime | No new tool or authority | Existing status remains the only host observation surface |
| Build/deploy workflow | APK source and runtime admission remain separate | Require explicit owner authority at every gate |

## Implementation Slices

### Slice V0 — Source-only voice draft

- Add **Dictate draft** beside the existing text editor.
- Launch the system recognizer with an explicit user gesture.
- Populate but never submit the returned transcript.
- Preserve the current draft on cancel/error.
- Keep the Manifest permission set unchanged.
- Add source/protocol checks; produce no installed APK claim.

### Slice V1 — Build qualification

- Run the pure Java protocol suite.
- Build an unsigned, aligned target-SDK-35 APK in the isolated worktree.
- Verify the APK manifest contains no camera, microphone, location, activity,
  body-sensor, boot receiver, or newly enabled service authority.
- Record APK SHA-256 and signer state. Building does not authorize installation.

### Slice V2 — Explicit install qualification

- Requires fresh owner authority naming the exact APK digest and device serial.
- Verify the currently installed package/version/signer before replacement.
- Install or replace only the named companion package.
- Confirm package version, target SDK, permission set, and disabled service.
- Installation does not authorize launching dictation or capturing a voice
  result.

### Slice V3 — Real-device acceptance

- Requires the holder to approve a fresh projection session on the device.
- Requires a separate visible tap on **Dictate draft** and system recognizer
  consent/UI.
- Demonstrate cancel/error preservation and successful transcript-to-draft.
- Demonstrate that no host text observation exists before **Submit text**.
- After explicit submit, verify one authenticated observation with zero
  authority and ephemeral retention.
- Disconnect, then verify no companion process/service, projection listener,
  or further observation remains.

## Permission and Data Boundary

- Source, APK build, APK install, projection consent, recognizer launch, and
  text submit are six separate authority events.
- The companion never receives raw audio bytes in V0–V3.
- The system recognizer may use device or network services according to the
  user's Android configuration. The companion must not claim offline ASR.
- The transcript is local draft state until the holder explicitly submits it.
- Submitted text inherits the existing authenticated, nonce-bound,
  `ephemeral_session_only`, zero-authority contract.
- Logs and status responses must not include raw audio and must not include an
  unsubmitted transcript.

## Acceptance Criteria

- [ ] The connected projection UI shows **Dictate draft** with clear local-only
      draft wording.
- [ ] Dictation can start only from an explicit foreground tap.
- [ ] The companion Manifest contains no `android.permission.RECORD_AUDIO`.
- [ ] No `AudioRecord`, `MediaRecorder`, microphone foreground-service type,
      continuous listening, or wake-word code is introduced.
- [ ] A recognition result populates the existing editor and performs no host
      request until **Submit text** is tapped.
- [ ] Cancellation, unavailable recognizer, empty result, and recognizer error
      preserve the existing draft and report a local status.
- [ ] The existing 1–1000 character validation remains authoritative.
- [ ] Existing Java protocol tests and Rust mobile projection tests pass.
- [ ] APK build evidence includes target SDK, permission audit, artifact hash,
      and signer state; it does not claim installation.
- [ ] Installation occurs only with fresh authority for an exact digest and
      exact device serial.
- [ ] Real-device acceptance proves consent, editable draft, explicit submit,
      authenticated receipt, zero authority, disconnect, and process/service
      teardown.
- [ ] No regression: typed text submission behaves exactly as before.

## Non-goals

- Raw-audio upload or storage.
- Host-side ASR, voice identity, emotion inference, or speaker recognition.
- Continuous/background listening, wake words, automatic submit, or hands-free
  actuation.
- Durable memory writes or treating transcript content as an instruction.
- APK installation, package replacement, or runtime admission in this design
  slice.

## GDD Update Required?

No system GDD exists. The quick spec is sufficient for this bounded addition.
After implementation and device acceptance, add a short evidence-backed
addendum to `docs/DESIGN-mobile-device-bridge-2026-05-23.md`; do not update that
document from design intent alone.

## V0 Source-only Implementation Evidence

Implemented on branch `codex/mobile-voice-draft-v0-20260815` without running
the APK build or changing the installed phone package:

- `VoiceDraftPolicy` selects the first non-empty system transcript and appends
  it to an existing draft without silent replacement.
- `ProjectionActivity` opens `RecognizerIntent.ACTION_RECOGNIZE_SPEECH` only
  after a foreground button tap and updates only the local `EditText`.
- Cancelled, unavailable, or empty recognition preserves the current draft.
- The existing **Submit text** listener remains the only call site for
  `submitTextObservation`; dictation has no network or submit call.
- The protocol test gate rejects `RECORD_AUDIO`, `AudioRecord`, and
  `MediaRecorder`, and tests draft selection/merge behavior.
- Pure Java protocol tests pass, and all Android companion Java sources compile
  against Android 35 `android.jar` into a temporary directory.
- APK build, APK installation, projection launch, dictation launch, and phone
  submission remain unperformed and unclaimed.

## Systems Index

No systems index was found. This addition remains below the systems-index
tracking threshold because it reuses the existing text observation protocol
and introduces no new host service or authority surface.
