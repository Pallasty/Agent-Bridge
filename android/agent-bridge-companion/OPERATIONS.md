# Operator boundary

These commands are examples, not automated setup. Replace placeholders locally;
never commit the token or challenge.

```sh
adb install -r build/agent-bridge-companion-debug.apk
adb shell pm enable dev.agentbridge.companion/.CompanionService
adb shell am startservice \
  -n dev.agentbridge.companion/.CompanionService \
  --es health_token '<64-lower-hex-token>'

adb shell am startservice \
  -n dev.agentbridge.companion/.CompanionService \
  --es imu_request_id 'manual-1' \
  --es imu_challenge '<64-lower-hex-challenge>' \
  --el imu_duration_ms 500 \
  --el imu_sample_rate_hz 20

adb shell dumpsys activity service dev.agentbridge.companion/.CompanionService
```

Stopping or uninstalling the package releases its wake/Wi-Fi locks:

```sh
adb shell am stopservice -n dev.agentbridge.companion/.CompanionService
adb shell pm disable dev.agentbridge.companion/.CompanionService
adb uninstall dev.agentbridge.companion
```

The service is disabled by default, is not started at boot, and returns
`START_NOT_STICKY`. Always disable it after an explicit test. Projection does
not require enabling it.

## Recovery signer profile boundary

The recovery signer adapter requires an explicit fixed profile in addition to
the independently pinned public key:

```sh
export AB_APP_CONTROL_RECOVERY_AUTH_ALGORITHM='ES256'
export AB_APP_CONTROL_RECOVERY_AUTH_PROFILE='biometric_strong' # or device_credential
export AB_APP_CONTROL_RECOVERY_AUTH_PUBLIC_KEY_B64='<independently-pinned-profile-key>'
```

The Activity never changes profiles in response to device capability. Changing
the profile requires updating the profile setting and independently repinning
that profile's key. A missing or permanently invalidated biometric key is not
regenerated silently. Stop and disable the service, explicitly clear app data
or reinstall the companion, repeat provisioning, and repin the new key. An app
data reset also removes the health token and all other companion-local state.
Never automate reset or repinning.

The LAN health endpoint is read-only. Its request line is
`ABH1 <unix-seconds> <32-lower-hex-nonce> <HMAC-SHA256>`. Use the Agent-Bridge
host verifier rather than hand-assembling production requests.

## Temporary projection

Generate a fresh 32-byte token and retain it only in the shell environment.
Start the host on a private LAN address; its lifetime cannot exceed 600 seconds:

```sh
export AGENT_BRIDGE_MOBILE_PROJECTION_TOKEN='<64-lower-hex-token>'
cargo run -p ab-bridge --bin mobile-projection-host -- \
  --bind '<host-private-ip>' --session 'manual-1' --ttl-seconds 300 \
  --title 'Agent-Bridge' --body 'Projection is ready.'
```

Use the printed expiry in the explicit activity intent:

```sh
adb shell am start \
  -n dev.agentbridge.companion/.ProjectionActivity \
  --es projection_host '<host-private-ip>' \
  --ei projection_port 17322 \
  --es projection_token '<same-64-lower-hex-token>' \
  --es projection_session_id 'manual-1' \
  --el projection_expires_at_unix_seconds '<printed-expiry>'
```

The person holding the phone must press **Allow and connect**. Pressing
**Disconnect**, Back, or closing the activity stops all pulls. The token is an
ephemeral bearer secret passed through an operator-controlled local ADB session;
do not reuse the health/IMU token. Payloads are authenticated but not encrypted,
so do not display secrets even on a trusted LAN.
