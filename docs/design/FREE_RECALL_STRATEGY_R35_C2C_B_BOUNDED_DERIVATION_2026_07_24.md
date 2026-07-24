# Free Recall Strategy R35 — Bounded C2C-B Keychain Derivation

Status: **SOURCE-ONLY**

R34 localized the stall to synchronous Keychain derivation. R35 moves that
single derivation to `spawn_blocking` and bounds the MCP-facing wait to 250 ms.
Timeout, join failure, or derivation failure marks only the observation attempt
compromised; the core curate save remains successful and the sidecar closes
fail-closed. The default-off feature and Keychain access surface are unchanged.
