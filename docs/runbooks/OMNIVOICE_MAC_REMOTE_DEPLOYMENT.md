# OmniVoice Mac remote deployment checklist

This checklist configures the optional Mac execution path for the existing
default-off OmniVoice canary. It does not authorize changing the production
default, increasing the canary percentage, or removing Qwen3 fallback.

## Preconditions

- The deployment is built from a reviewed commit merged into `master`.
- The Mac model composition has been verified with the pinned SHA-256 and byte
  sizes in a node-local manifest.
- The remote Python environment imports `numpy`, `onnxruntime`, `soundfile`,
  `scipy`, and `tokenizers`.
- Non-interactive SSH host-key and key authentication succeeds from the Agent
  Bridge runtime identity. No password prompt is permitted.
- The remote adapter path belongs to the same reviewed Agent Bridge revision.
- The Qwen3 control backend has independently produced a WAV in the deployment
  environment before enabling the candidate.

## Required settings

| Setting | Purpose | Safe deployment rule |
| --- | --- | --- |
| `AB_OMNIVOICE_TTS_ENABLED` | Existing candidate gate | Keep unset until all preflight checks pass |
| `AB_OMNIVOICE_MAC_REMOTE_ENABLED` | Separate remote execution gate | Keep unset by default; enable only in the bounded pilot |
| `AB_OMNIVOICE_MAC_REMOTE_HOST` | SSH destination | Operator-owned hostname or tailnet name; never commit a node address |
| `AB_OMNIVOICE_MAC_REMOTE_PYTHON` | Remote isolated Python | Absolute path managed on the Mac |
| `AB_OMNIVOICE_MAC_REMOTE_ADAPTER` | Remote reviewed adapter | Absolute path to `omnivoice_mac_remote_synth.py` |
| `AB_OMNIVOICE_MAC_REMOTE_DISPATCH_PYTHON` | Local dispatcher Python | Existing Python 3.9 or newer runtime |
| `AB_OMNIVOICE_MAC_REMOTE_TIMEOUT_SECS` | Inner SSH/inference timeout | Start at 300; allowed range is clamped to 30–840 seconds |
| `AB_OMNIVOICE_MAC_REMOTE_LOCK` | Local single-flight lock | Writable runtime-only path; default is under `/tmp` |
| `AB_OMNIVOICE_MAC_REMOTE_JOB_DIR` | Remote UUID job root | Optional runtime-only directory; default is under `/tmp` |
| `--omnivoice-manifest` | Remote pinned composition | Absolute Mac path; keep the manifest node-local |

The existing `AB_TTS_CANARY_ENABLED` switch, checked-in 10% policy, subject
allowlist, review binding, and request bucket remain authoritative.

## Preflight

1. Verify the branch test and review evidence cited by the merge request.
2. Verify SSH in batch mode and confirm the presented host key out of band.
3. Run one direct remote adapter synthesis with both candidate switches enabled.
4. Confirm the receipt reports `hashes_verified=true`, 32 decode steps, 24 kHz,
   `execution_transport=ssh`, and a successful WAV copy.
5. Confirm the UUID job directory is removed after success.
6. Route an allowlisted request in the existing 10% bucket and confirm assigned
   and executed backends are both `omnivoice`.
7. Inject a request-scoped invalid manifest and confirm assigned backend remains
   `omnivoice`, executed backend becomes `qwen3`, fallback is true, and Qwen3
   produces a valid WAV.
8. Confirm non-allowlisted, named-speaker, instruction, clone, and out-of-bucket
   requests still select Qwen3 without contacting the Mac worker.

## Rollback

Unset `AB_OMNIVOICE_MAC_REMOTE_ENABLED` to disable only remote execution, or
unset `AB_OMNIVOICE_TTS_ENABLED`/`AB_TTS_CANARY_ENABLED` to disable candidate
routing. No model deletion, service binary rollback, policy edit, or canary
percentage change is required. Verify a Qwen3 control request after the switch
change and retain the last candidate-error receipt for diagnosis.
