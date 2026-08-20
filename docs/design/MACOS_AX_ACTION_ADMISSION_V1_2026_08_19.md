# macOS AX Action Admission v1

## Outcome

Agent-Bridge treats ordinary desktop navigation as part of the owner's standing
body authority. Rank-1 focus, move, resize, scroll, and selection do not require
a fresh user prompt for every motion. The relevant questions are instead:

1. is the semantic target exact;
2. is the observation complete and still fresh;
3. is the requested effect still within the admitted consequence class; and
4. does the caller hold the body's exclusive write lease and action slot for
   the complete transaction.

`macos_ax_action_admission` remains read-only. It previews this decision and
contains no executor.

## v1 hardening

The unmerged v0 candidate accepted caller-provided `surface_fresh` and
`observed_world_revision` values. v1 does not. It consumes an exact
`macos_ax_probe/v0` receipt and locally recomputes:

- receipt schema and complete-coverage state;
- returned/source/window counts recomputed from the actual window array;
- AX trust with `prompted=false`;
- frontmost `bundle_id + pid` scope;
- one unique matching window;
- observation age; and
- a SHA-256 digest of the evidence.

A stable target uses `bundle_id + pid + ax_identifier`. A sample-local index is
accepted only for preview when it is corroborated in the same receipt by exact
title and role. The first real executor does not accept a sample-local index.

## Consequence classes

| Rank | Class | Examples | Admission basis |
| --- | --- | --- | --- |
| 1 | `embodied_navigation` | focus, move, resize, scroll, select | standing authority plus exact fresh target |
| 2 | `reversible_content` | type, bounded control, move item to Trash | rank 1 plus task intent |
| 3 | `consequential_external` | submit, send, purchase, permanent delete | task-specific authority |
| 4 | `protected_boundary` | credential entry, permission change | user presence or OS-owned ceremony |

`requested_effect` may raise the floor and can never lower it.
Unknown authority scopes and requested-effect values fail closed in the
executor even if an upstream JSON-schema validator is bypassed.

## Lease versus permission

An embodiment lease is concurrency ownership, not a request for user
permission. A transaction-scoped mutex keeps the lease stable and serializes
lease-mediated body mutations through postflight and receipt persistence,
including two concurrent requests from the same owner session. Rank-1 actions
remain prompt-free after the owner has established standing body authority.

## Next executable gate

The first executor is `macos_ax_focus_transaction`. It is intentionally limited
to a unique AXIdentifier inside the already-frontmost application. Cross-app
activation, text input, coordinates, and arbitrary scripts remain outside v0.
