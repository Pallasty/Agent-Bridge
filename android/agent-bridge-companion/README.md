# Agent-Bridge Android Companion

Recovered source for the bounded Android IMU/LAN prototype found on `aio2` on
2026-08-11. The authoritative recovery inputs were `classes.jar`, `classes.dex`,
and the debug APK dated 2026-07-31. This directory replaces the untracked,
binary-only copy; it does not claim source-level identity with files that no
longer exist.

The service has deliberately narrow authority:

- authenticated, rate-limited health reads on the phone Wi-Fi address, TCP
  port 17321;
- explicit 100–1000 ms accelerometer/gyroscope captures requested through an
  Android service intent;
- summary/hash output through `dumpsys`, never a continuous raw sensor stream;
- HMAC-bound consent and result receipts with attention, memory, and actuation
  authority fixed to `false`.

On Android target SDK 35 builds the service component is disabled after install,
does not receive boot broadcasts, and is non-sticky. An operator must explicitly
enable it before a bounded service test and disable it again afterward. The
projection Activity does not enable or start the service.

There is no camera, microphone, autonomous discovery, or remote actuation. The
projection activity is a separate, user-visible slice: it connects only after
the person holding the phone confirms a named endpoint and a session that
expires within ten minutes. It displays authenticated title/text frames and
offers an always-visible disconnect action. It does not start the IMU service.
Starting the service or installing an APK is an operator action and is not
performed by repository tests.

## Build

Set `ANDROID_SDK_ROOT` to an Android SDK containing API 35 and build-tools,
then run:

```sh
./build.sh
```

The script writes only beneath `build/`, uses a repository-local debug keystore
only when explicitly requested with `AB_COMPANION_DEBUG_KEYSTORE`, and otherwise
produces an unsigned APK. Pure protocol tests require only a JDK:

```sh
./test-protocol.sh
```

The preferred DEX compiler is SDK `d8`. Debian installations that package the
legacy Android compiler as `dalvik-exchange` can instead set
`AB_COMPANION_DX_JAR` to `com.android.dx.jar`. Debug signing defaults to JKS;
set `AB_COMPANION_KEYSTORE_TYPE` explicitly for another keystore format.

## Provision and inspect

The app has no launcher activity. A 32-byte random token is provisioned as a
64-character lowercase hexadecimal service extra. IMU capture also requires an
explicit request id, 32-byte challenge, bounded duration, and bounded rate.
Exact commands are intentionally kept in `OPERATIONS.md` so normal builds do
not accidentally start a persistent service.

## Projection boundary

The host binds only a private/link-local address. The phone pulls rather than
accepting inbound control, and both request and response are HMAC-bound to the
session, timestamp, and nonce. Projection payloads are not encrypted; use only
on a trusted LAN and do not project secrets. Closing the activity immediately
stops pulls, while both sides independently enforce the expiry time.
