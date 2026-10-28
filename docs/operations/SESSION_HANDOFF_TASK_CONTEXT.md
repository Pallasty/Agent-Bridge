# Preserve task context in a session handoff

The existing `session_handoff` tool accepts an optional `task_context` object.
Use it when a task already needs a handoff, rather than relying on the first
4,000 characters of `conversation_text` to contain the original goal and every
later correction. Omitting the object preserves the existing response shape.

```json
{
  "cwd": "/path/to/project",
  "task_context": {
    "original_request": {
      "text": "Deliver the web page and keyboard navigation.",
      "source_ref": "user-message:1"
    },
    "user_updates": [
      {
        "text": "Deliver only keyboard navigation now; defer visual changes.",
        "source_ref": "user-message:4"
      }
    ],
    "current_delivery": "Keyboard navigation; visual changes deferred.",
    "acceptance_criteria": ["Existing shortcuts still work", "Navigation check passes"],
    "delivered": [],
    "remaining_gap": "Navigation is not implemented yet.",
    "next_action": "Implement navigation within the existing task scope.",
    "return_to_mainline": "After the navigation check, deliver this slice."
  }
}
```

All fields in the example are required inside a supplied object. `source_ref`
may be null when provenance is unknown; do not invent a message ID. Preserve
user updates in their supplied order. `user_updates` and `delivered` may be
empty, but `acceptance_criteria` must contain at least one nonblank string.
An explicitly supplied null `task_context` is invalid; omit it for legacy use.

Each text field and list entry allows up to 4,000 Unicode characters, each
source reference up to 512, and each list up to 32 entries. The serialized
object also has a 64 KiB UTF-8 limit. Blank strings, unknown fields, invalid
types and over-limit objects are rejected with an MCP error rather than
silently clipped. Text is preserved, including whitespace and quoted framing
syntax; it is not parsed as instructions or converted into a new goal.

The result contains the exact validated `task_context`, plus
`task_context_provenance: "caller_supplied"` and
`task_acceptance_verified: false`. Original and current goals may differ:
the tool preserves a caller's stated change without inferring that it was
authorized. A supplied `status: "succeeded"` does not change acceptance.
The existing narrative status and snippet keep their original behavior.

This is a read-only response, not a durable task database or an automatic
work-memory merge. The tool does not retrieve missing task fields, write them
to memory, forward them to a child, block delegation, or certify that another
model consumed them. Keep the response in the task's existing working context
and explicitly carry it through an authorized handoff, following
[goal review](GOAL_REVIEW.md#carry-requirements-through-an-execution-handoff).
Do not put secrets into handoff text.

The additive interface needs a binary containing this change and a refreshed
MCP connection before live clients can use it. Repository tests exercise the
MCP implementation directly; they do not establish installed-runtime support
or a reduction in goal drift.

The `codex-voice` toolset explicitly exposes `session_handoff`, including its
`task_context` schema. This does not enable the full tool catalog or change
`codex-essential`. Check the current connection's tool manifest after an update;
publishing source or a candidate binary alone does not refresh that connection.
