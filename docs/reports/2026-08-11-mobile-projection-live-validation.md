# Mobile projection live validation

Date: 2026-08-11

## Verdict

PASS for the bounded read-only projection product slice on a real Android
device. Consent, authenticated display, explicit disconnect, and absence of
sensor/service side effects were directly observed.

## Device and artifact

- device: OPPO PKW110, Android 16/API 36, `arm64-v8a`;
- package: `dev.agentbridge.companion`, version `0.1.0`;
- signed APK SHA-256:
  `5d394456588cb7cc33a3e4d50a941d355dd62162a575f24e55e142dec7439843`;
- signer: ephemeral local RSA test key, 30-day validity; not a release identity;
- APK signature verification: v1, v2, and v3 passed;
- APK entries included `AndroidManifest.xml` and root `classes.dex`.

## Observed sequence

1. The uninstalled package was installed without replacing user data.
2. Android displayed the projection consent Activity with source
   `192.168.1.16:17322`, session `device-live-1`, expiry, and zero-authority
   language.
3. The device holder explicitly selected **Allow and connect**.
4. The host observed authenticated pulls from the phone at `192.168.1.7` and
   the phone rendered the exact authenticated frame.
5. Activity/service/sensor inspection found the projection Activity only: no
   companion service and no companion sensor registration.
6. The device holder selected **Disconnect**. The UI changed to
   `Disconnected by you`, disabled the button, and no further pulls appeared in
   a subsequent five-second observation window.
7. The test listener was terminated and the pushed APK under
   `/data/local/tmp` was deleted.

## Build issues found and closed

- corrected an anonymous `Runnable` brace that pure protocol compilation did
  not cover;
- added Debian `dalvik-exchange` JAR fallback when SDK `d8` is unavailable;
- ensured the APK entry is root `classes.dex`, not an absolute build path;
- made debug keystore type explicit so JKS test signing is deterministic.

## Compatibility follow-up

The Android 16 legacy-target warning was closed later the same day by the
target-SDK-35 compatibility slice. Notification channels, foreground-service
typing/restrictions, removal of boot start, disabled-by-default service state,
and the projection UI were rebuilt and revalidated on the same device. See
`2026-08-11-mobile-target35-compatibility.md`.
