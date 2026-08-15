# Android target SDK 35 compatibility

Date: 2026-08-11

## Verdict

PASS on an OPPO PKW110 running Android 16/API 36. The companion now targets
API 35 without the legacy-app warning, while temporary projection remains
explicitly consented, read-only, short-lived, and independent of the optional
background companion service.

## Compatibility changes

- raised compile/target SDK to 35 and application version to `0.2.0`/2;
- added notification-channel and immutable-`PendingIntent` handling;
- typed the optional foreground service as `connectedDevice` and declared its
  API-35 foreground-service permissions;
- made the service disabled by default and `START_NOT_STICKY`;
- removed `BOOT_COMPLETED` permission, receiver, and automatic boot start;
- adjusted the projection Activity for Android 16 edge-to-edge behavior and
  readable light status/navigation bars;
- built with API 35 `aapt`, `d8 --lib android.jar`, `zipalign`, and `apksigner`.

Projection does not require the service. Operators must explicitly enable the
service before a bounded health/IMU test and disable it afterwards.

## Real-device validation

1. Upgraded the installed package with the same ephemeral local test signer.
2. Confirmed package version `0.2.0`, version code 2, and target SDK 35.
3. Confirmed a direct service start fails while the component is disabled and
   that no service is running.
4. Opened projection session `api35-live-6` from `192.168.1.16:17322`; Android
   displayed the full source, session, expiry, zero-authority statement, and
   explicit **Allow and connect** control without a legacy-app warning.
5. After the device holder consented, the host served authenticated read-only
   frames to the phone at `192.168.1.7`; the exact title/body and revision were
   rendered.
6. During projection, `dumpsys activity services` remained empty for the
   package and the manifest held no camera, microphone, location, activity, or
   body-sensor permission.
7. The device holder disconnected; the Activity exited, the service remained
   absent, the short-lived listener expired, and the pushed APK under
   `/data/local/tmp` was deleted.

## Reproducible artifact and gates

- signed debug APK SHA-256:
  `c66b2234c93bf5d9a74a03282a3e1e8895d14c624eef25bb74f04bbdb7d97dfd`;
- APK verification: v1, v2, and v3 signatures pass;
- signer: ephemeral local RSA test key, not a release identity;
- `android/agent-bridge-companion/test-protocol.sh`: PASS;
- `cargo test -p ab-bridge 'mobile_' --lib`: 17 passed, 0 failed;
- `git diff --check`: PASS.

## Product boundary

This closes a practical device-compatibility gap; it does not expand the
project into autonomous sensing, remote control, publication, or external
certification. A release-signing and distribution workflow should be added
only when there is a concrete deployment need. The useful next mobile work
should be driven by an actual Agent-Bridge display/interaction need rather than
collecting more sensor evidence by default.
