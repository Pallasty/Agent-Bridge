# R38 — C2C-B Final Receipt Probe

Status: **ATTEMPT-1 INCOMPLETE / NO RETRY**

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

R38 therefore does not claim a finalized observation receipt. The bounded
sidecar path no longer blocks the core response, but its fail-closed timeout
does not currently leave a receipt that satisfies the finalized CurationBatch
gate. R38 is closed without retry. The next source-only decision is whether to
emit an explicit incomplete/aborted sidecar terminal event or to make the
experiment's acceptance contract explicitly distinguish core success from
sidecar incompleteness.
