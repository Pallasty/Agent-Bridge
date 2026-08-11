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

The current Codex environment has neither `adb` nor an Android SDK, even though
a device is physically attached to the host. Consequently this slice does not
claim APK compilation or on-device UI validation. Those are the remaining
integration checks once the existing host-side Android tools are exposed to the
workspace; no additional protocol design is required.
