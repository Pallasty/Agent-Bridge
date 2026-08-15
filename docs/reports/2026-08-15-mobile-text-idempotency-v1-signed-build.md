# Mobile text idempotency V1 signed-build qualification

Date: 2026-08-15

## Verdict

`PASS_SIGNED_BUILD_ONLY`.

The text-submission idempotency source produced a signed Android APK with the
same certificate as the installed Companion. This gate did not install, launch,
or replace the device package.

## Inputs

- source commit: `2c20c83229849894c4ca01f0ad6253bf6cca26a2`;
- keystore SHA-256:
  `c4a09af5fcb93b8d621de59fef6c23096650587e1125dcdadd661f009173e21c`;
- Android protocol test: PASS;
- Rust mobile-projection tests: 26 passed, 0 failed.

## Artifact

- path:
  `android/agent-bridge-companion/build/agent-bridge-companion-debug.apk`;
- size: `33111` bytes;
- signed APK SHA-256:
  `974034f188d08c196f06dbc736bc58e5c58cb910bbdd9bf18b8e3922de2d96f6`;
- unsigned/aligned APK SHA-256:
  `3bd909b629d9ca1a4cf096485de917b4d050ac0a4fea988177e14888211eea6f`;
- `zipalign -c 4`: PASS;
- signature verification: v1, v2, and v3 PASS;
- signer certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- signer public-key SHA-256:
  `dc6efd11ec8ae8bab4308d55fac27f539e55d9ed44c23b464091cbb717ca0795`.

## Binary inspection

- package: `dev.agentbridge.companion`;
- version: `0.2.0`, versionCode `2`;
- min / target / compile SDK: `21` / `35` / `36`;
- DEX contains `agent_bridge.mobile_text_observation.v1`;
- DEX contains `submission_id` and the authenticated acceptance UI string;
- manifest still declares no microphone permission.

## Device boundary

The installed package retained `lastUpdateTime=2026-08-15 21:52:16`, remained
stopped, and had no Companion service or projection session. The next gate is a
separately authorized replacement install of this exact APK digest followed by
a real duplicate/retry acceptance run.

