# Mobile voice-draft V1 device install acceptance

Date: 2026-08-15

## Authorization and scope

The owner authorized installation/replacement and real-device acceptance for the
exact V1 signed APK. The flow below did not grant projection consent, start the
background service, or submit any text.

## Install proof

- device: `192.168.1.3:46035`, OPPO PKW110, Android 16;
- install command: `adb install -r` against the exact signed artifact;
- result: `Success`;
- installed package: `dev.agentbridge.companion`;
- version: `0.2.0`, versionCode `2`, target SDK `35`;
- installed `lastUpdateTime`: `2026-08-15 21:52:16`;
- pulled installed APK SHA-256:
  `8db585b68ce37012a2167ed305269f1454ff6568eccd77fffefd11df8ebab833`;
- installed APK signature: v1, v2, and v3 verified;
- installed signer certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`.

## Runtime acceptance

- `ProjectionActivity` launched successfully with `am start -W`;
- foreground UI visibly rendered “Allow temporary projection?” with the
  source/session/expiry fields, the no-authority explanation, and **ALLOW AND
  CONNECT** / **CANCEL** controls;
- the game surface initially obscured the Activity until the device was brought
  to the home surface; a second launch brought the Companion UI to focus;
- **CANCEL** was selected to close the Activity without granting projection;
- final projection status: zero sessions;
- `CompanionService`: no running service;
- no text submission, dictation, sensor capture, or other device authority was
  exercised.

## Verdict

`PASS_INSTALL_AND_UI_ACCEPTANCE; PROJECTION_NOT_ADMITTED`.

The exact signed V1 APK is installed and its on-device digest/certificate match
the qualified build and the historical package signer. The UI gate is real and
fail-closed; projection remains a separate explicit-consent gate.

