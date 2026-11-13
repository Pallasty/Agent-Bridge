# Hook environment and effect feedback

Direct IDE hook commands do not inherit the `agent-bridge` MCP wrapper's environment.
The four hook scripts now read the same trusted per-machine configuration:
`AGENT_BRIDGE_MACHINE_ENV`, or `~/.config/agent-bridge/machine.env`. Configuration
output is suppressed because that file may contain secrets. Environment precedence
is defined by the file, just as for the wrapper. The observer imports only its two
observer settings through a bounded subshell; configuration failure stops collection.

This keeps the memory database, hook log, pet state, and observer log on the same
paths as the configured MCP process. It does not merge databases or rotate observer
logs. The existing observer capacity limit remains in force.

## Install and recover

For an existing configured client, update the scripts without replacing the MCP
wrapper or rerunning setup:

```sh
python3 scripts/install-hook-scripts.py --check
python3 scripts/install-hook-scripts.py --install --backup-dir /private/new-backup-directory
python3 scripts/install-hook-scripts.py --rollback /private/new-backup-directory/manifest.json
```

The installer backs up all four scripts, records hashes, then atomically replaces
each script at its resolved target. The rollback refuses to overwrite subsequent
changes. Client hook commands and trust records remain unchanged. Existing database
files are outside this installer's write scope. Take SQLite online backups separately
when repairing a machine with divergent state directories; retain both databases.
Do not overwrite an active database using a filesystem copy.

A binary's `setup` command embeds the scripts at its build revision. A scripts-only
repair does not update those embedded templates. Running setup from an older binary
can restore older scripts; run `--check` and reinstall from this checkout afterward,
or use a binary built from the updated source. The MCP binary version and script
manifest are intentionally separate evidence.

If historical `setup-state.json` is relocated, preserve its original application
time and operations, retain the source, and record source hash and relocation
provenance. Relocation is not a new execution of setup. Keep historical hook logs
as separate archives rather than appending older entries after newer receipts.

## Memory effect receipts

`hook-runs.jsonl` retains its existing fields and adds `effect_feedback` and a
SHA-256 session identifier. No prompt, memory body, or plaintext session identifier
is added to this log.

| Outcome | Status | Code |
| --- | --- | --- |
| MCP bootstrap payload emitted | emitted | bootstrap_context_emitted |
| Requested bootstrap unavailable; static payload emitted | degraded | static_fallback_emitted |
| Explicit static mode emitted | emitted | static_requested_emitted |
| Cooldown or curator guard | skipped | cooldown / curator_guard |
| No database or no context | skipped | database_missing / no_context_emitted |
| Static query failed | failed | static_query_failed |

`requested`, `actual`, and `dropped` distinguish a successful process exit from the
requested retrieval effect. `verification_scope=hook_payload_only` is deliberate:
a receipt does not prove host ingestion, model use, retrieval quality, or task value.
MCP `capabilities` with `sections:["hooks"]` exposes `hooks.recent_runs`;
`hook_status` and `readiness_audit(include_local_install=true)` include the same
`last_effect_feedback`, `last_effect_feedback_state`, and `last_session_id_sha256`
fields per hook. `reported` preserves the producer's payload-only outcome;
`unreported` means a missing/legacy receipt, and `invalid` means an unsupported or
malformed effect object. Neither missing nor invalid feedback is inferred from an
exit code. Only known effect fields and vocabulary are forwarded; private extension
fields and malformed session hashes are not exposed.

These are the latest appended records per event across the machine, not necessarily
the caller's session. Compare the session hash before making a session-specific claim.
Readiness's overall `ready` remains an installation/source-coverage result, not an
assertion that memory was emitted or used. `include_local_install=false` continues
to omit local run evidence.

A binary rebuilt from this source embeds all four repaired Hook templates. The
real-MCP integration test executes `setup --frontend codex` twice in an isolated
HOME and compares the installed bytes with source, so a newly deployed binary's
setup must not regress this repair. Historical binaries retain their old templates.

Codex may deliver large additional context as a preview plus a reference to the
full output file. Validate the native hook notification and assembled model input;
for spilled output, compare the referenced file with the exact hook context. Do not
claim the model read that file merely because the reference was present.

## Bounded verification

```sh
python3 scripts/eval/hook_effect_feedback.py --output-dir /private/effect-test-output
python3 scripts/eval/hook_environment_paths.py --output-dir /private/path-test-output
python3 scripts/check-hook-effects-mcp.py --binary /path/to/candidate --output /private/mcp-test-output
```

These are synthetic process tests, not native Codex or model-quality evidence.
They cover ten memory outcomes plus path precedence, observer capacity/config
failure, and installer rollback. Fixtures are retained under the output directory.
Use an isolated Codex runtime for native checks; never alter the daily configuration
or its trust hashes to force a test through.
