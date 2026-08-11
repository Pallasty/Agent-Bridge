#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${ANDROID_SDK_ROOT:?set ANDROID_SDK_ROOT to an Android SDK}"
platform=$(find "$ANDROID_SDK_ROOT/platforms" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)
tools=$(find "$ANDROID_SDK_ROOT/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)
test -f "$platform/android.jar"
for tool in aapt d8 zipalign; do test -x "$tools/$tool"; done

out="$root/build"
rm -rf "$out"
mkdir -p "$out/classes" "$out/dex" "$out/gen"
"$tools/aapt" package -f -m -J "$out/gen" -M "$root/AndroidManifest.xml" -I "$platform/android.jar"
javac -source 8 -target 8 -classpath "$platform/android.jar" -d "$out/classes" \
  $(find "$root/src" "$out/gen" -type f -name '*.java' | sort)
jar cf "$out/classes.jar" -C "$out/classes" .
"$tools/d8" --min-api 21 --output "$out/dex" "$out/classes.jar"
"$tools/aapt" package -f -M "$root/AndroidManifest.xml" -I "$platform/android.jar" \
  -F "$out/agent-bridge-companion-unsigned.apk"
"$tools/aapt" add "$out/agent-bridge-companion-unsigned.apk" "$out/dex/classes.dex"
"$tools/zipalign" -f 4 "$out/agent-bridge-companion-unsigned.apk" "$out/agent-bridge-companion-aligned.apk"

if [ -n "${AB_COMPANION_DEBUG_KEYSTORE:-}" ]; then
  test -x "$tools/apksigner"
  "$tools/apksigner" sign --ks "$AB_COMPANION_DEBUG_KEYSTORE" \
    --ks-pass "pass:${AB_COMPANION_DEBUG_KEYSTORE_PASSWORD:-android}" \
    --out "$out/agent-bridge-companion-debug.apk" "$out/agent-bridge-companion-aligned.apk"
fi
sha256sum "$out"/*.apk
