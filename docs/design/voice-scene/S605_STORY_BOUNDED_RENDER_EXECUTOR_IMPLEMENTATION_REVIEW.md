# S605 Story bounded-render executor implementation review

S605 selects one isolated Python source module as the smallest future executor
surface. It may call the existing hash-bound runner directly, but may not use a
shell or subprocess, register an MCP tool, or modify the Rust registry. The
source patch is limited to the future executor and its focused test file.

Before any output directory exists, a future implementation must validate an
expiring, single-use render grant bound to the S604 contract, preflight hash,
and exact output directory. Output must use a new dedicated directory,
executor-scoped temporary files, no overwrites, atomic finalization, and cleanup
limited to files created by that executor invocation.

The review records sixteen fail-closed cases spanning authorization, output
custody, source and model admission, request validation, rendering, machine
audio verification, and playback separation. Playback remains outside the
executor and requires its own later grant. Recording and memory writes remain
unsupported.

This review implements no executor and performs no runtime action. The next
gate requires explicit owner authorization for the two-file isolated source
implementation; runtime execution would remain closed after that source lands.
