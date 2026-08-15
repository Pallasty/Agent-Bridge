# Mobile voice-draft signer recovery

Date: 2026-08-15

## Scope

Read-only recovery of the historical Android test-signing identity. No private
key was copied, no APK was signed, and no device state was changed.

## Matched identity

- candidate keystore:
  `/Users/pallasting/Projects/nexus-civilization-battle-truthful-command-20260717/client/godot/android/debug.keystore`;
- alias: `androiddebugkey`;
- entry type: `PrivateKeyEntry`;
- certificate subject: `CN=Android Debug, O=Android, C=US`;
- certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- device-installed certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- keystore file SHA-256:
  `c4a09af5fcb93b8d621de59fef6c23096650587e1125dcdadd661f009173e21c`;
- certificate validity observed: 2026-07-06 through 2056-06-28.

## Verdict

`SIGNER_IDENTITY_RECOVERED_READ_ONLY`.

The candidate keystore's certificate exactly matches the signer on the
installed Companion APK, so it is suitable for a future signed-build
qualification. The keystore remains in its existing project; it was not copied
into Agent-Bridge. Its current file mode is `0644`, which should be reviewed
before any production or shared-host use. A future signing gate must explicitly
bind this path, alias/password policy, signed APK digest, and `apksigner`
certificate output before any install/replace decision.

