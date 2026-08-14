#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out="$root/build/protocol-test"
rm -rf "$out"
mkdir -p "$out"
grep -q 'android:targetSdkVersion="35"' "$root/AndroidManifest.xml"
grep -q 'android:enabled="false"' "$root/AndroidManifest.xml"
grep -q 'android:foregroundServiceType="connectedDevice"' "$root/AndroidManifest.xml"
if grep -q 'BOOT_COMPLETED\|RECEIVE_BOOT_COMPLETED' "$root/AndroidManifest.xml"; then
  echo "boot-start authority must remain absent" >&2
  exit 1
fi
javac -source 8 -target 8 -d "$out" \
  "$root/src/dev/agentbridge/companion/Hex.java" \
  "$root/src/dev/agentbridge/companion/LanHealthProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuCaptureContract.java" \
  "$root/src/dev/agentbridge/companion/ImuSampleSummary.java" \
  "$root/src/dev/agentbridge/companion/ConsentReceiptProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuResultAttestationProtocol.java" \
  "$root/src/dev/agentbridge/companion/ProjectionProtocol.java" \
  "$root/src/dev/agentbridge/companion/TextObservationProtocol.java" \
  "$root/test/dev/agentbridge/companion/ProtocolTest.java"
java -cp "$out" dev.agentbridge.companion.ProtocolTest
