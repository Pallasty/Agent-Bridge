# Mobile companion recovery and integration

Date: 2026-08-11

## Outcome

The `aio2` checkout contained an untracked Android companion directory with APK,
DEX, and Java class artifacts, but no recoverable source tree or build scripts.
The bounded protocol has been reconstructed in this repository and paired with
a read-only Agent-Bridge host verifier.

This is a recovery-equivalent implementation, not a claim that the missing
source was reproduced byte for byte.

## Recovered boundary

- LAN health: authenticated TCP request on port 17321, 60-second clock window,
  nonce replay protection, and per-minute rate limiting.
- IMU: explicit Android service intent, 100–1000 ms duration, 1–50 Hz sampling,
  accelerometer required and gyroscope optional.
- Evidence: summary/hash plus HMAC-bound consent and result receipts.
- Authority: attention, memory, and actuation are always `false`.
- Excluded: camera, microphone, autonomous discovery, remote provisioning,
  launcher UI, screen projection, and remote actuation.

The original IMU result does not echo its challenge in the JSON summary. The
host verifier therefore accepts only the exact challenge retained by the
request issuer and verifies both receipts against it; it never derives trust
from response-controlled challenge data.

## Integration

`ab_bridge::mobile_companion` provides:

- construction of authenticated health requests;
- a bounded read-only TCP health query;
- verification of IMU summary, consent receipt, and result attestation.

It deliberately provides no device discovery, APK installation, service start,
token provisioning, sensor capture trigger, or actuation API. Operator-only
commands remain in the Android companion operations document.

## Verification performed

- Reconstructed pure-Java protocol tests pass with a JDK.
- Rust known-answer and RFC 4231 HMAC tests pass.
- Rust negative tests reject malformed secrets/nonces and reject IMU evidence
  with missing challenge binding or any asserted authority.
- Repository diff whitespace validation passes.
- No Android device was attached to `aio2`, so no live sensor capture or service
  mutation was performed.

An APK rebuild additionally requires an Android SDK platform and build-tools.
Those tools were not present on `aio2` during recovery; the checked-in build
script fails closed when they are absent. The recovered binary remains evidence,
not a reproducible build result.

## Next product slice

Do not expand sensor collection until a real AB consumer needs it. The next
useful mobile-node increment is a consent-visible projection surface with an
ephemeral session and explicit disconnect control. Keep projection independent
from IMU evidence and preserve the same zero-authority default. This is a
product utility milestone, not an external reproducibility or research goal.
