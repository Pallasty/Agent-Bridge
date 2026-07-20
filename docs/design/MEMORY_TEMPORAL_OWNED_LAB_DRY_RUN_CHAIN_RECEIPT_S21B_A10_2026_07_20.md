# S21B-A10 non-live transcript-chain receipt

S21B-A10 derives one canonical receipt from the four A9 role transcripts. It
accepts only a directory containing the exact controller, observer, runner,
and validator outputs produced for the one A9 canonical plan. It rechecks the
plan binding, role order, operations, states, terminal denial, canonical JSON,
and all non-live assertions before emitting a receipt to standard output.

The receipt is deterministic: the plan digest and the SHA-256 digest of each
terminal-LF transcript are committed in role order, then the entire receipt
body is domain-separated and hashed. The self digest excludes only the self
field. No input is accepted as real experiment data; all invalid or altered
transcripts fail closed with exit code 65 and no receipt.

The builder reads only the supplied transcript files and repository contracts.
It does not write a receipt file, use the network, access a device, request an
owner signature, issue an execution capability, or unlock side effects.
`scripts/check-memory-temporal-owned-lab-dry-run-chain-receipt-s21b-a10.sh`
generates the A9 synthetic transcript set, validates the A10 receipt, and
checks plan-digest, role, ordering, and trailing-byte tampering.
