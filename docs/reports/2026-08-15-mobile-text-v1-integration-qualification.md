# Mobile text V1 integration qualification

Date: 2026-08-15

## Scope and authority boundary

This gate qualifies the previously device-accepted mobile text-input V1 work
against the current default branch. It does not merge or push `master`, and it
does not install, replace, launch, or otherwise operate the phone package.

## Integration evidence

- target baseline: `8055f64c9e40842c1f9d429c126f5f5bb6aa0dab`;
- both `origin/master` and `github/master` resolved to that baseline before the
  integration;
- integration commit: `469c609c`;
- candidate cleanup commit: `aeeda035`;
- `origin/master` is an ancestor of the candidate;
- candidate divergence after integration: 0 behind, 13 ahead before this
  report commit;
- the integration used the `ort` merge strategy and reported no conflicts;
- the three baseline-only ModelScope commits changed no mobile V1 files;
- `git diff --check origin/master...HEAD`: PASS after normalizing six legacy
  report EOFs introduced on this branch.

## Regression evidence

- `cargo test -p ab-bridge mobile_projection --lib`: 26 passed, 0 failed;
- `sh android/agent-bridge-companion/test-protocol.sh`: PASS;
- compiler warnings were pre-existing/non-fatal and did not change either test
  verdict.

## Reproducible signed build

Two consecutive clean-output executions of `android/agent-bridge-companion/build.sh`
used:

- Android SDK root: `/opt/homebrew/share/android-commandlinetools`;
- recovered test keystore SHA-256:
  `c4a09af5fcb93b8d621de59fef6c23096650587e1125dcdadd661f009173e21c`;
- alias: `androiddebugkey`;
- keystore entry: `PrivateKeyEntry`.

Both builds were byte-identical:

- unsigned APK SHA-256, build 1 and build 2:
  `3bd909b629d9ca1a4cf096485de917b4d050ac0a4fea988177e14888211eea6f`;
- signed APK SHA-256, build 1 and build 2:
  `974034f188d08c196f06dbc736bc58e5c58cb910bbdd9bf18b8e3922de2d96f6`.

The signed digest is also the exact artifact previously installed and accepted
on the device. `zipalign -c 4` passed. `apksigner` verified v1, v2, and v3;
v3.1 and v4 were not present.

Signer continuity remained exact:

- certificate subject: `CN=Android Debug, O=Android, C=US`;
- certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- public-key SHA-256:
  `dc6efd11ec8ae8bab4308d55fac27f539e55d9ed44c23b464091cbb717ca0795`.

## Device boundary

No ADB package, process, activity, service, or projection command was issued in
this gate. The existing installed APK was left unchanged and stopped according
to the preceding live-device cleanup evidence.

## Verdict

`PASS_INTEGRATION_QUALIFICATION`

The mobile text-input V1 candidate incorporates the current default branch,
passes its scoped regressions, reproduces the exact signed APK and signer, and
is qualified to proceed to a separately authorized default-branch merge and
dual-remote push gate.
