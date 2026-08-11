# Operator boundary

These commands are examples, not automated setup. Replace placeholders locally;
never commit the token or challenge.

```sh
adb install -r build/agent-bridge-companion-debug.apk
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
adb uninstall dev.agentbridge.companion
```

The LAN health endpoint is read-only. Its request line is
`ABH1 <unix-seconds> <32-lower-hex-nonce> <HMAC-SHA256>`. Use the Agent-Bridge
host verifier rather than hand-assembling production requests.
