# Mobile text idempotency v1 live-device acceptance

Date: 2026-08-15

## Bound artifacts

- Source commit: `f5171aa0b5663ad95a4133d9feaea5af3a82d279`
- Behavior commit: `2c20c83229849894c4ca01f0ad6253bf6cca26a2`
- APK SHA-256: `974034f188d08c196f06dbc736bc58e5c58cb910bbdd9bf18b8e3922de2d96f6`
- Package: `dev.agentbridge.companion` (`0.2.0`, version code `2`)
- Device: OPPO PKW110, Android 16, wireless ADB `192.168.1.3:46035`
- Host session: `idempotency-v1-live-r2`, bound to the same isolated source worktree

## Live acceptance

1. The exact APK was installed and its device-pulled hash matched the artifact hash above.
2. The user explicitly allowed the foreground projection connection.
3. The Companion rendered `Agent-Bridge Idempotency V1`, revision 1, as a read-only and disconnectable projection.
4. The user entered a two-character draft and rapidly double-tapped Submit.
5. The host emitted exactly one accepted text observation during the observation window:
   - submission id: `b1f9270ae17540032d9f13403e47a894`
   - digest: `6aa8f49cc992dfd75a114269ed26de0ad6d4e7d7a70d9c8afb3d7a57a88a73ed`
   - character count: `2`
6. The UI cleared the draft and displayed `Accepted by this temporary Agent-Bridge session`.
7. No second accepted observation appeared. No live deduplication event appeared because the in-flight UI guard prevented the second tap from issuing another request.

## Claim boundary

This is real-device evidence for first submission and rapid-double-tap duplicate prevention. It is not evidence that a response-loss network retry occurred on the device. Reuse of one submission id across a retry, same-id/same-digest deduplication, and same-id/different-digest rejection remain covered by the 26/26 Rust protocol test pass for this source version.

## Cleanup

- The temporary host session was interrupted.
- The Android package was force-stopped and verified as `stopped=true` with no remaining package PID.
- The APK remains installed; no background service was introduced or admitted.

## Verdict

`PASS_REAL_DEVICE_DOUBLE_TAP_IDEMPOTENCY`

The live-device gate passes for the user-visible idempotency behavior. Network-retry deduplication remains a protocol-tested claim rather than a live induced-failure claim.
