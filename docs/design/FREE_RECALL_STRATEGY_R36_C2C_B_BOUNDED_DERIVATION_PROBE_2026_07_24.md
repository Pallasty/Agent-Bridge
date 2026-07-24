# R36 — Bounded C2C-B Derivation Probe

Status: **PREREGISTERED / ONE DISPOSABLE RUN ONLY**

R35 bounds observation-side Keychain derivation to 250 ms. After its completed
source tests and feature build, execute the existing live-lab command exactly
once with fresh disposable custody. Accept only a normal `session_curate`
response with core `saved_count > 0`; the observation receipt may be incomplete
because its sidecar is intentionally fail-closed. Record one result, do not
retry, merge, deploy, enumerate Keychain, or access existing items.
