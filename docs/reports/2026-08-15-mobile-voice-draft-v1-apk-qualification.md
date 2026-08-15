# Mobile voice draft V1 APK qualification

Date: 2026-08-15
Source commit: `af8862d65020d8b2517cef253efd076fd2ff89e0`
Branch: `codex/mobile-voice-draft-v0-20260815`

## Verdict

PASS for APK build qualification only. The source produced an unsigned,
ZIP-aligned Android APK whose packaged manifest and DEX preserve the V0
review-first voice-draft boundary. No APK installation, package replacement,
Activity launch, projection session, dictation launch, or phone submission was
performed.

## Build

- Command: `ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools sh build.sh`
- Artifact: `android/agent-bridge-companion/build/agent-bridge-companion-aligned.apk`
- SHA-256: `c8f422097cea7aa0d3ca1d71f3f158a4618c32d0fbdcaaba5b1e1f4a808c1f9e`
- Size: 25,306 bytes
- Package: `dev.agentbridge.companion`
- Version: `0.2.0` / version code 2
- Minimum SDK: 21
- Target SDK: 35
- Compile SDK: 36
- ZIP alignment: PASS (`zipalign -c 4`)
- Signature state: intentionally unsigned; `apksigner verify` returned
  `DOES NOT VERIFY` with no signer metadata.
- APK entries include root `AndroidManifest.xml` and `classes.dex`.

## Packaged permission and component audit

The binary manifest contains only:

- `android.permission.INTERNET`
- `android.permission.ACCESS_WIFI_STATE`
- `android.permission.CHANGE_WIFI_STATE`
- `android.permission.WAKE_LOCK`
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE`
- `android.permission.POST_NOTIFICATIONS`

The packaged APK contains no `RECORD_AUDIO`, camera, location, body-sensor,
activity-recognition, or boot-receiver permission. `CompanionService` remains
disabled and retains only the existing connected-device service type.

## Packaged feature evidence

`classes.dex` contains the V0 feature markers:

- `Dictate draft`
- `android.speech.action.RECOGNIZE_SPEECH`
- `VoiceDraftPolicy`
- `Draft updated locally; review it, then tap Submit text`
- `System dictation is unavailable; type your draft instead`

The pure Java protocol gate passed and statically rejects `RECORD_AUDIO`,
`AudioRecord`, `MediaRecorder`, and any new `submitTextObservation()` call site.

## Device non-admission boundary

Before this build, the connected OPPO PKW110 at `192.168.1.3:46035` reported:

- installed companion `0.2.0`, version code 2, target SDK 35;
- `lastUpdateTime=2026-08-14 20:29:13`;
- package stopped, no PID, no companion service;
- no active Agent-Bridge projection session.

V1 does not authorize signing, installing, launching, dictating, submitting,
or accepting the feature on a real device. Those remain later, separately
authorized gates bound to this exact artifact digest or to a newly rebuilt and
requalified digest.
