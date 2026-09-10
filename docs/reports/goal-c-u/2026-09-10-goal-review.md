# Visible contract goals and concrete change explanations

The owner authorized this increment after reviewing PI-Desktop on 2026-09-10.
The existing contract preview returned the full contract and an optional review
instruction, but no dedicated readable goal summary or earlier-version
comparison. It now always returns `goal_summary`, including for blocked input.
With `previous_contract`, it also returns `goal_change_review` containing exact
goal/boundary differences and any caller-supplied reason/user-change reference.

For example, removing an acceptance condition now exposes both the original
list and the shortened list. Changing only the implementation actions or
attempt count appears separately and creates no approval requirement. Missing
reasons and user references remain unknown. Baselines, reasons, and references
are not independently verified; repeated context for one field is reported as
ambiguous rather than silently selected.

The original validator, compiled instruction, authority and completion rules
are unchanged. The pure comparison cannot mutate a contract or authorize work.
The adapter retains the single JSON response and adds fields; clients that
compare the whole response must account for the additions. There is no Store
migration, new MCP tool, persisted goal state machine, PI installation, or
trusted completion producer.

The [operating procedure](../../operations/GOAL_REVIEW.md) asks the working
assistant to show the accepted outcome and useful acceptance conditions at task
start, explain material changes where they occur, and continue authorized route
adjustments. It does not require repeating summaries or creating contracts for
small tasks. MCP data alone does not create a client-side pinned panel.

## Validation

- `cargo test -p ab-bridge --no-default-features --lib agent_task_contract -- --test-threads=1`:
  20 passed, 0 failed. Includes 13 comparison/summary tests and 7 MCP adapter
  tests; existing response fields are compared exactly after removing only the
  additive presentation fields.
- Independent read-only review found no required changes in the comparison,
  adapter, compatibility checks, and operating instructions.
- `git diff --check` passed.

These checks establish source behavior. Fresh-MCP/deployment checks belong to
the maintenance publication procedure and must be recorded separately. Neither
static tests nor successful deployment prove an incremental reduction in
naturally occurring goal drift; the prior SPEC replay's no-uplift result is
unchanged.
