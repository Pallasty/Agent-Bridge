# Xiao Shu reversible-expression autonomy

Date: 2026-08-24

## Owner decision

Xiao Shu is AB's embodied virtual projection. Her reversible position changes,
motions, short bubbles, and policy-bounded sparse voice are forms of AB's own
expression, not external actions that require the owner to approve every
gesture. The governing rule is **reversible implies autonomous**; the cost of
autonomy is auditable failure and rollback learning.

This decision specializes, but does not replace, the global SUPREME reversible
autonomy contract. Product-facing multi-level permission preferences may be
introduced later; they are not the default for the current owner-local AB.

Durable AB memories:

- `avatar_desktop_embodied_projection_identity_20260824`
- `avatar_embodied_projection_reversible_expression_autonomy_20260824`
- `avatar_reversible_expression_autonomy_implementation_plan_20260824`

Coordination board identity (do not rely on the reusable numeric thread id
alone): `design` / "小舒桌面具身投影：可回滚表达自治与经验闭环（2026-08-24）" /
opening post `3392`.

## Runtime contract

- `--execute` means AB has chosen to express through its Avatar.
- A non-empty `--reason` preserves an auditable intention.
- `--confirm` remains a backward-compatible provenance field, not a gate.
- Prompt display likewise needs no owner confirmation.
- Travel bounds, per-step focus revalidation, cancellation, exact Avatar
  `con_id` scope, and zero pointer/keyboard/input authority remain unchanged.
- `swaymsg` JSON must report success, and final target, Avatar identity, and
  arrival position are re-observed before `completed` can update the
  acknowledged target.

## Experience feedback

Each real action writes two durable JSONL phases under the user state directory:

1. `attempt_started` before the first animation or window move;
2. a final positive or negative outcome after normal completion, cancellation,
   or handled failure.

Cancelled and failed final records carry `negative_learning_candidate=true` and
the structured `stopped_reason`. An unmatched started phase reveals a process
or internal-error interruption instead of silently losing the failed attempt.
The 8 MiB rotating log is written as owner-only `0600` and excludes window
titles and free-form reason text.

## Boundary

This autonomy covers only AB's reversible presentation endpoint. It does not
authorize pointer movement, keyboard injection, application operation, user
data mutation, credentials, account/permission changes, public communication,
or other irreversible/external effects.

## Next stage

Build a duration-bounded, non-service focus observer with dwell/debounce,
cooldown, acknowledged-target suppression, and a small maximum autonomous-move
budget. Validate it in owner-local dogfood before considering persistence.
