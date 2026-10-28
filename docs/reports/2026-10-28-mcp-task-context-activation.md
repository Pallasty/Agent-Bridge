# Structured handoff activation repair

Current delivery: make structured task handoff usable through the installed
`codex-voice` MCP entry. This is the next step after the 2026-10-27 release
closeout, not another memory framework or collection campaign.

## Baseline and discriminating observation

Source/candidate: `7f382efc592e14b812328fdbd4c33d68432cacba`.
Current MCP on 2026-10-28 still reports `e32700c1e92f`, 107 tools,
`codex-voice`, with no `session_handoff`. The earlier formal admission and
same-source diagnostic both timed out at 45 seconds; neither activated the
candidate.

One additional diagnostic preserved the candidate SHA-256, default embedding
backend, messages, 45-second deadline, output limits and process-group cleanup.
Only observation was added: timestamped reads, captured streams and thread
wait channels at the deadline. All three JSON-RPC responses completed without
errors by 0.493 seconds (101 tools). The server logged stdin-closed shutdown.
At 45 seconds the parent still waited in `futex_do_wait`; its sole remaining
worker was `fastembed-init` in `wait_woken`. Together with the shutdown join
and unconditional MCP warmup source, this locates the observed exit blocker
in background embedding initialization after protocol completion. It does not
identify the exact blocked network operation or establish general cancellation.

Private evidence: `/home/pallasting/agent-bridge-closeout-20261028/stage-probe/`
(`stages.jsonl`, `stdout.raw`, `stderr.raw`); instrumentation in `stage_probe.py`
at the parent directory. These are diagnostics, not an admission receipt.

## Bounded repair and acceptance

Skip speculative MCP model warmup only when the store has no active embedding
profiles. Preserve populated-store warmup, lookup-error behavior, dimension
guards, lazy embedding on actual use and the native initialization shutdown
join. No backend override or admission timeout change. This does not promise
instant shutdown after actual semantic work initiates a model load.

Expose readonly `session_handoff` by exact name in `codex-voice`; keep
`codex-essential` and unrelated Niche tools unchanged. Caller-supplied task
context remains unverified and is not automatically persisted or forwarded.

Validation so far: the new registry test failed on the missing tool before
the change, then all 11 handoff tests passed after the change. The existing
bounded voice policy test also passed. Logs are retained at the private
evidence directory above (`policy-red.log`, `handoff-green.log`,
`voice-policy.log`). The default-feature build passed. The unchanged exact probe then passed
with the default backend, isolated empty state, all three response validations,
101 codex-essential tools, and a clean exit in 4.20 seconds including interpreter
startup and binary hashing. Its deadline remained 45 seconds. The probe source
SHA-256 is `387203c8749b0ae9b470a3d86d558058153470fd70aef538a561e5d74f46fccc`.
See `default-probe/result.json` and `default-probe/stdout` in the private
evidence directory. This local development build binds source digests and
reports the pre-commit HEAD; it is not a governed published candidate.

Implementation commit: `9e48e7a75906e885671a76f1216369c7b0e3c5be`.
Its normal commit gate passed: 405 exact S18–S21 cases, 143 fresh isolated
CLI comparisons, and default-feature `cargo check -p ab-bridge --all-targets`.
Fresh CLI evidence: `governance-live/run-5h_9v91g` under the native validation
root `/home/pallasting/.agent-bridge-secure/research/copilotkit-four-20261027/cargo-validation`.
Release remains pending at this source-validation checkpoint. Publication, admission,
activation, service health, current-client visibility and a real handoff are
separate acceptance steps. Long-term drift reduction is not claimed.
