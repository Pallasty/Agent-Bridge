#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out="$root/build/protocol-test"
rm -rf "$out"
mkdir -p "$out"
grep -q 'android:targetSdkVersion="35"' "$root/AndroidManifest.xml"
python3 - "$root/AndroidManifest.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

android = "{http://schemas.android.com/apk/res/android}"
root = ET.parse(sys.argv[1]).getroot()
services = [node for node in root.findall("./application/service")
            if node.get(android + "name") == ".CompanionService"]
assert len(services) == 1
assert services[0].get(android + "enabled") == "false"
PY
grep -q 'android.permission.USE_BIOMETRIC' "$root/AndroidManifest.xml"
grep -q 'android:foregroundServiceType="connectedDevice"' "$root/AndroidManifest.xml"
if grep -q 'BOOT_COMPLETED\|RECEIVE_BOOT_COMPLETED' "$root/AndroidManifest.xml"; then
  echo "boot-start authority must remain absent" >&2
  exit 1
fi
if grep -q 'RECORD_AUDIO' "$root/AndroidManifest.xml"; then
  echo "companion microphone permission must remain absent" >&2
  exit 1
fi
if grep -R -q 'AudioRecord\|MediaRecorder' "$root/src"; then
  echo "companion raw-audio capture must remain absent" >&2
  exit 1
fi
grep -q 'AndroidKeyStore' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'setUserAuthenticationRequired(true)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'BiometricPrompt.CryptoObject' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'loadOrProvisionKey(BIOMETRIC_ALIAS, authenticationProfile, 0, KeyProperties.AUTH_BIOMETRIC_STRONG)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'setAllowedAuthenticators(BiometricManager.Authenticators.DEVICE_CREDENTIAL)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'canAuthenticate(BiometricManager.Authenticators.DEVICE_CREDENTIAL)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'loadOrProvisionKey(CREDENTIAL_ALIAS,authenticationProfile,15,KeyProperties.AUTH_DEVICE_CREDENTIAL)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'signer key disappeared; reset and repin required' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'putString(AUTH_PROFILE_KEY,authenticationProfile)' "$root/src/dev/agentbridge/companion/RecoveryAuthorizationActivity.java"
grep -q 'put("authentication_profile",authenticationProfile)' "$root/src/dev/agentbridge/companion/CompanionService.java"
if grep -R -q 'getPrivate().getEncoded\|private_key.*putString' "$root/src/dev/agentbridge/companion"; then
  echo "recovery signing private key must never be exported" >&2; exit 1
fi
test "$(grep -c 'submitTextObservation()' "$root/src/dev/agentbridge/companion/ProjectionActivity.java")" -eq 2
javac -source 8 -target 8 -d "$out" \
  "$root/src/dev/agentbridge/companion/Hex.java" \
  "$root/src/dev/agentbridge/companion/LanHealthProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuCaptureContract.java" \
  "$root/src/dev/agentbridge/companion/ImuSampleSummary.java" \
  "$root/src/dev/agentbridge/companion/ConsentReceiptProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuResultAttestationProtocol.java" \
  "$root/src/dev/agentbridge/companion/ProjectionProtocol.java" \
  "$root/src/dev/agentbridge/companion/TextObservationProtocol.java" \
  "$root/src/dev/agentbridge/companion/VoiceDraftPolicy.java" \
  "$root/src/dev/agentbridge/companion/RecoveryAuthorizationProtocol.java" \
  "$root/test/dev/agentbridge/companion/ProtocolTest.java"
java -cp "$out" dev.agentbridge.companion.ProtocolTest
