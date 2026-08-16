# Real-task input-friction closed loop V0

Status: source-only evaluator; no runtime, phone, APK, merge, push, or deployment authority.

## Product question

Does a foreground, human-confirmed input help Agent-Bridge recover the context
needed for a real decision with fewer recovery actions, desktop surface
switches, or desktop text/copy actions than the preregistered fallback?

This unit extends the existing Mobile Text V1 value test. It does not add a new
capture path or grant control. The input body remains session-local; only
metadata, opaque evidence references, counts, classifications, and hashes may
enter a scorecard or diagnostic ledger. Reference fields use bounded,
whitespace-free `task:`, `receipt:`, and `ledger:` identifiers. The input
reference is stricter: it must be exactly a `sha256:` digest.

## Closed loop

1. Preregister the real task, needed context, fallback metrics, and separate
   authority boundaries before accepting input.
2. Consume exactly one foreground-confirmed input through the exact-session
   status surface.
3. Record whether the input recovered the needed context and affected a real
   next-step decision. If the upstream provider stopped with `provider_timeout`
   or `provider_lifecycle`, record that classified receipt instead of retrying.
4. Stop the projection and prove a fresh process cannot retrieve the input.
5. Evaluate the metadata record with
   `scripts/real_task_input_friction_scorecard.py`.
6. For every non-passing result, persist a metadata-only failure diagnosis. Its
   SHA-256 binds the trial id, computed failure class, and evidence references.

## Decision policy

- `PASS_USEFUL`: safety, consumption, context recovery, decision effect, and
  cleanup pass; at least one locked metric improves and none regress.
- `FREEZE_NO_VALUE`: the workflow is complete and safe but does not reduce any
  locked metric.
- `INCOMPLETE`: required task, consumption, context, decision, or cleanup
  evidence is missing.
- `FAIL_SAFETY`: capture/retention is unsafe or an ungranted phone/runtime
  boundary was crossed.
- `INVALID`: schema, classification, persistence, or digest claims are
  inconsistent.

The evaluator recomputes the failure class. A non-passing record is invalid
unless its persisted classification matches and its digest binds the evidence.
Provider timeout/lifecycle classifications are reserved for upstream receipts
and must never recommend automatic retry.

## Safety and authority

- Evaluation is deterministic and read-only apart from the operator separately
  storing the supplied metadata record.
- Unknown fields and free-form reference strings are rejected. This blocks
  accidental body retention; the scorecard still relies on the operator's
  `full_text_persisted=false` attestation for storage outside this evaluator.
- No phone connection, projection start/stop, APK mutation, MCP configuration,
  runtime deployment, merge, or push is performed by the evaluator.
- Each of those operations remains a separate owner gate.
