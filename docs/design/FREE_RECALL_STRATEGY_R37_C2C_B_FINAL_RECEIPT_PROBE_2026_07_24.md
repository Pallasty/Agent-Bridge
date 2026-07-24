# R37 — C2C-B Final Receipt Probe

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

Run the corrected R36 driver exactly once with fresh disposable Keychain
custody and temporary SQLite. Acceptance requires a core `session_curate`
response with `saved_count > 0` and a finalized contiguous CurationBatch
receipt. Cleanup must complete; no retry, merge, deployment, enumeration, or
existing-item access is permitted.

## Attempt-1 receipt

The run returned the pre-R36 behavior:

```text
after_curate_response_before_exit; last_checkpoint=curate_response_ready
```

The live binary had been built before the driver fix `1d2348ea`, so this is
not evidence against the fix and is not a final receipt. R37 is closed without
retry; a fresh R38 must rebuild the live binary before its one run.
