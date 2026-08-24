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

Each real action writes two durable JSONL v2 phases under the user state
directory, paired by one random `attempt_id`:

1. `attempt_started` before the first animation or window move;
2. a final positive or negative outcome after normal completion, cancellation,
   or handled failure.

Cancelled and failed final records carry `negative_learning_candidate=true` and
the structured `stopped_reason`. An unmatched started phase reveals a process,
post-movement persistence, or internal-error interruption instead of silently
losing the failed attempt. Historical v1 rows are retained as unpairable legacy
evidence.

The 8 MiB rotating log lives in the dedicated `avatar-focus-follow` subtree
under the common `AGENT_BRIDGE_STATE_DIR` when configured. Only this subtree is
restricted to `0700`; its regular single-link log and lock files are `0600`, and
window titles and free-form reason text are excluded. `O_NOFOLLOW` plus fd-based
mode and file-type re-observation reject symlinks, hardlinks, and filesystems
that only pretend to accept `chmod`. Failure to persist the initial started row
blocks movement. Storage can still fail after movement; in that case the paired
terminal is absent and the already durable started row remains the audit signal.

## Local falsification evidence

The candidate runtime was exercised against both local state filesystems:

- the NTFS/FUSE home-state fallback reported an observed `0777` after chmod,
  exited before movement, and left the Avatar rectangle unchanged;
- the F2FS common state root created the dedicated directory as `0700` and the
  lock/log as `0600`;
- an already-present cancel file produced a v2 `started` + `final` pair with one
  `attempt_id`, zero movement, and `cancel_file_present` as negative learning;
- removing `XDG_RUNTIME_DIR` after the started receipt produced a paired failed
  terminal with `unhandled_internal_error_or_unwind`, zero steps, and the
  `preparing` execution stage.

Unit falsifiers also cover state-root precedence, refusal of relative/missing
roots, unchanged common-root permissions, end-to-end symlink/hardlink refusal,
repair of an existing permissive regular file, start-only rotation, durable
paired appends with private modes, and preservation of observed execution
progress in the failure snapshot.

## Boundary

This autonomy covers only AB's reversible presentation endpoint. It does not
authorize pointer movement, keyboard injection, application operation, user
data mutation, credentials, account/permission changes, public communication,
or other irreversible/external effects.

## Next stage

Increment 2 has passed its automated and adversarial implementation gates but
remains a **live candidate**, not an accepted runtime baseline. It is one
owner-started, foreground, at-most-30-minute,
non-service focus observer. The first focus establishes a no-move baseline;
later focus changes must pass dwell/debounce, cooldown, acknowledged-target,
fullscreen, structured `ab-sensitive` mark, structured-identity,
built-in/owner exact-denylist, pause, action-lock, minimum/maximum travel,
exponential failure-backoff, and three-attempt-budget gates. Duration and
attempt-budget normalization cannot exceed 30 minutes or three attempts.
Observer presentation is silent: no prompt, audio, pointer motion, focus change,
or input injection.

The exact target/workspace geometry is frozen at dispatch and rechecked under
the lock, before every step, and at arrival. Target movement/resize, workspace
change, or an owner drag of Xiao Shu cancels the old path. Action, observation,
and proven-prestart runtime failures remain separate closed learning signals.

The observer's runtime receipt starts as a privacy-minimal `running` aggregate
before movement can occur and is atomically replaced by the final aggregate;
the final aggregate is also projected to stdout. Both exclude window titles,
app ids, the raw Sway tree, and free-form reason text. Each real move continues
to use the existing durable Focus-follow outcome v2 started/final pair as
action truth. This increment adds no observer-run journal, service, autostart,
or background persistence.

The candidate contract and deliberately unfilled live-verification matrix are
in `docs/reports/avatar/2026-08-24-focus-follow-bounded-observer.md`. Owner-local
dogfood must establish zero focus/input interference, policy suppressions,
complete receipts, and practical use value before this candidate can be called
accepted or considered for persistence.
