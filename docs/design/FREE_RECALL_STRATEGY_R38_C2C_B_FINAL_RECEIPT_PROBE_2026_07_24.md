# R38 — C2C-B Final Receipt Probe

Status: **CORE-PATH ACCEPTED / SIDECAR RECEIPT INCOMPLETE**

The live-lab binaries are rebuilt from the current source immediately before
this probe. Execute once with fresh disposable Keychain custody and temporary
SQLite. Accept only a core `session_curate` response with `saved_count > 0`
and a finalized contiguous CurationBatch receipt. Cleanup must complete; no
retry, merge, deployment, enumeration, or existing-item access.

## Attempt-1 receipt

The rebuilt driver received the core curate response, but receipt validation
returned:

```text
episode receipt is empty
```

R38 therefore accepts the core curate path: the bounded sidecar no longer
blocks the response. It does not accept a finalized observation receipt; the
sidecar timeout currently leaves no receipt satisfying that gate. R38 is closed
without retry. Future reports must retain this two-level verdict rather than
promote core success into sidecar success.
