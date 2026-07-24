# R37 — C2C-B Final Receipt Probe

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

Run the corrected R36 driver exactly once with fresh disposable Keychain
custody and temporary SQLite. Acceptance requires a core `session_curate`
response with `saved_count > 0` and a finalized contiguous CurationBatch
receipt. Cleanup must complete; no retry, merge, deployment, enumeration, or
existing-item access is permitted.
