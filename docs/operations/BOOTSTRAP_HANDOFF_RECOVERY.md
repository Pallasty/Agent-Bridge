# Current project handoffs in bootstrap

An actionable exact-project session_handoff should appear in task-targeted
bootstrap even when the user only says “continue”. The existing eligibility
rules still exclude automatic curation, unverified identifiers, stale,
background/archive, and non-project records from unconditional priority.
Ordinary semantic ranking remains available for other memories.

Bootstrap and its state digest share one bounded candidate read: at most 256
newest visible handoffs, then exact-project eligibility, then the output cap
(eight for semantic bootstrap, one for the digest). This avoids allowing
recent accesses to global or ancestor handoffs to consume the old five/eight
row windows before the current project could be considered.

The candidate read is bounded. If it fills, bootstrap reports that older
candidates may be omitted, including when no eligible row survived. It provides
a session_handoff follow-up; that tool reports its own candidate limit. Use
memory_get with a known key when necessary. An empty capped result does not
establish that no current handoff exists. A failed candidate read retains the
existing best-effort behavior; this change does not establish complete storage
error diagnostics.

The focused regression is
`cargo test -p ab-bridge --lib bootstrap_handoff_priority_tests`.
The real MCP regression uses isolated synthetic state and requires a built
binary:

```bash
python3 scripts/check-bootstrap-handoff-mcp.py \
  --binary /absolute/path/to/agent-bridge \
  --output /absolute/path/to/new-evidence-directory
```

Add `--baseline-binary /absolute/path/to/old-binary` to reproduce the old
generic-query omission before exercising the candidate. The test verifies
generic and targeted queries, limit=1, trailing slashes, existing eligibility
guards, project isolation, and a full candidate window with a working
follow-up. Its database and transcript are synthetic; passing it is not
evidence of natural-task recovery, model use, or owner time saved.

For production diagnostics, start with session_handoff for the actual project,
then query session_bootstrap and expand the returned key with memory_get.
Preserve a failed call when another query happens to succeed. Source identity,
installed binary identity, and a connected client's identity must be checked
separately during release. No Hook or database migration is required.
