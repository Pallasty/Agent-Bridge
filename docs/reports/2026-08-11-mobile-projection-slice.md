# Consent-visible mobile projection slice

Date: 2026-08-11

## Product outcome

Agent-Bridge can host a short-lived read-only title/text frame on a private LAN.
An Android companion shows the endpoint, session, expiry, and authority boundary
before it connects. The person holding the device must explicitly allow the
session and can disconnect at any time.

## Enforced boundary

- maximum session lifetime: 600 seconds;
- private or link-local endpoints only;
- fresh bearer token supplied out of band and read by the host from an
  environment variable, never a command-line argument;
- authenticated pull request and response bound to session, timestamp, and
  random nonce;
- bounded 160-character title, 8,000-character body, and 16 KiB wire frame;
- attention, memory, and actuation authority fixed to `false`;
- no IMU service start, sensor access, discovery, input forwarding, or remote
  action surface;
- activity close, Back, or Disconnect stops mobile polling immediately;
- expiry is checked independently by host and mobile.

The protocol authenticates but does not encrypt payloads. It is suitable for a
trusted LAN status surface, not secrets.

## Verification scope

Pure-Java tests cover request generation, response authentication, tamper
rejection, and lifetime bounds. Rust tests cover zero-authority frame creation,
HMAC behavior, and a complete authenticated TCP pull with a decoded frame.

## Live-device addendum

The earlier tooling limitation was closed on 2026-08-11 with a minimal Debian
Android toolchain and an attached OPPO PKW110 (`arm64-v8a`, Android 16/API 36).

Verified on the device:

- Java sources compiled against Android API 23 and produced a real DEX/APK;
- the APK contained root `classes.dex` and passed APK signature v1/v2/v3
  verification with an ephemeral 30-day local test certificate;
- package version `0.1.0` installed cleanly with no prior package replacement;
- the consent screen showed the exact private host, session, expiry, and
  zero-authority statement before any projection pull;
- after user consent, the phone at `192.168.1.7` repeatedly authenticated to the
  host at `192.168.1.16:17322` and displayed the expected Chinese title/body;
- Activity Manager showed no `CompanionService`; SensorService showed no
  companion sensor registration;
- after the user pressed Disconnect, the UI reported `Disconnected by you`, the
  button was disabled, and a subsequent observation window produced no pulls;
- the host listener was then stopped early and the device-side temporary APK
  copy was removed. The installed test application remains available for the
  next compatibility check.

Android 16 displayed an operating-system warning because the recovered manifest
targets API 27. Raising target SDK safely requires a separate compatibility
slice covering notification channels, foreground-service types/restrictions,
and boot behavior; this live result does not claim those changes are complete.
