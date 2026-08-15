# Mobile voice-draft V1 signed-build qualification

Date: 2026-08-15

## Verdict

`PASS_BUILD_ONLY`.

The V1 source was rebuilt and signed with the recovered debug keystore whose
certificate matches the currently installed Companion package. This report
does not authorize or record an APK install, replace, launch, or projection.

## Reproducible inputs

- source/report worktree HEAD: `42b7415c4e6506c15f773f6d917ea0bbcfc5b87c`;
- protocol test: `sh test-protocol.sh` — PASS;
- build: `ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools`
  with the recovered `AB_COMPANION_DEBUG_KEYSTORE` and its configured local
  test password;
- package: `dev.agentbridge.companion`;
- version: `0.2.0`, versionCode `2`;
- target SDK: `35`, compile SDK: `36`, min SDK: `21`.

## Signed artifact

- path:
  `android/agent-bridge-companion/build/agent-bridge-companion-debug.apk`;
- size: `33111` bytes;
- SHA-256:
  `8db585b68ce37012a2167ed305269f1454ff6568eccd77fffefd11df8ebab833`;
- `zipalign -c 4`: PASS;
- `apksigner verify --verbose --print-certs`: PASS for v1, v2, and v3;
- signer certificate: `CN=Android Debug, O=Android, C=US`;
- signer certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- signer public-key SHA-256:
  `dc6efd11ec8ae8bab4308d55fac27f539e55d9ed44c23b464091cbb717ca0795`.

## Device boundary

The device package was not written. Before the build, the device had no
companion PID, service, or projection session. The final post-build wireless
ADB probe returned zero devices, so the prior package state could not be
re-read after the build; this is recorded as an unavailable observation, not
as live-device acceptance. The next gate is a separately authorized
install/replace and live acceptance using this exact signed artifact digest.
