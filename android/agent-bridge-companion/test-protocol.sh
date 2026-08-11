#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out="$root/build/protocol-test"
rm -rf "$out"
mkdir -p "$out"
javac -source 8 -target 8 -d "$out" \
  "$root/src/dev/agentbridge/companion/Hex.java" \
  "$root/src/dev/agentbridge/companion/LanHealthProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuCaptureContract.java" \
  "$root/src/dev/agentbridge/companion/ImuSampleSummary.java" \
  "$root/src/dev/agentbridge/companion/ConsentReceiptProtocol.java" \
  "$root/src/dev/agentbridge/companion/ImuResultAttestationProtocol.java" \
  "$root/test/dev/agentbridge/companion/ProtocolTest.java"
java -cp "$out" dev.agentbridge.companion.ProtocolTest
