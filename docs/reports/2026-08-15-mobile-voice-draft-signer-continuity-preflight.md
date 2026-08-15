# Mobile voice-draft signer-continuity preflight

Date: 2026-08-15

## Scope

Read-only continuity check for the V1 companion APK. This gate does not sign,
install, replace, launch, or project the APK.

## Evidence

- source/report worktree: `c44cee80251190722bebdbf3a98a67a28ceceb0e`;
- V1 aligned APK:
  `android/agent-bridge-companion/build/agent-bridge-companion-aligned.apk`;
- V1 aligned APK SHA-256:
  `c8f422097cea7aa0d3ca1d71f3f158a4618c32d0fbdcaaba5b1e1f4a808c1f9e`;
- V1 signature check: `DOES NOT VERIFY` (`META-INF/MANIFEST.MF` missing);
- connected device: `192.168.1.3:46035`, OPPO PKW110, Android 16;
- installed package: `dev.agentbridge.companion`, version `0.2.0` / versionCode
  `2`, installed and stopped, `lastUpdateTime=2026-08-14 20:29:13`;
- installed APK SHA-256 (pulled read-only from the device):
  `d6f7295a14625097681a488a4b5f2441c67f93758b6dff56b276b59786ab4da0`;
- installed APK verification: v1, v2, and v3 pass;
- installed signer certificate: `CN=Android Debug, O=Android, C=US`;
- installed signer certificate SHA-256:
  `ebcd0970f09f2d5818f84ab738971827f5af8ba9482d5087ae2fcd821cb8b655`;
- installed signer public-key SHA-256:
  `dc6efd11ec8ae8bab4308d55fac27f539e55d9ed44c23b464091cbb717ca0795`;
- local keystore inventory under the isolated worktree, companion Android
  project, and Agent-Bridge cache: no `.jks`, `.keystore`, `.p12`, or
  `.pkcs12` files found;
- `AB_COMPANION_DEBUG_KEYSTORE`: absent;
- runtime after the check: no companion PID, no companion service, and zero
  projection sessions.

## Verdict

`SIGNER_CONTINUITY_NOT_ESTABLISHED`.

The device holds a historical ephemeral Android Debug-signed package, while the
current V1 artifact is intentionally unsigned and has a different APK digest.
No local signing identity was available to prove that the next install would
retain the installed package's signer. The install/replace gate therefore
remains closed. A future install gate requires the exact debug/test keystore
or an explicitly authorized replacement-key decision, followed by a fresh
signed APK digest and certificate comparison before any device write.
