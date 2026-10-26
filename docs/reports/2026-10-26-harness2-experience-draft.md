# Harness²-inspired experience draft export — 2026-10-26

The existing execution contrast command now accepts an optional `--lesson`
JSON file and packages a caller-proposed lesson into AB's experience v0 shape.
This closes the manual copy step between contrast review and experience review.
It extends the existing tool without adding a runner, service or model call.

Only freshly verified `helped` or `hurt` contrasts produce a draft. The draft
retains evidence references, execution review, costs, applicability cue,
counterexample and explicit unknowns. Other valid outcomes produce `NO_ENTRY`.
Old success and promotion claims are excluded by constructing a new object from
selected fields. Task acceptance and causal proof remain false; promotion and
runtime influence remain disabled. Output is JSON on stdout, not a memory write.

Validation covers draft replay, noninheritance of authority, missing evidence,
single-pair confounds, negative observations, required lesson context, input
immutability and opt-in CLI compatibility. The original contrast, candidate
helper and artifact comparison suites are also run because they share helpers.
All examples are synthetic mechanism checks, not measured task improvements.

The command cannot certify lesson semantics, independent task acceptance,
complete attempt coverage or transfer. Original relative artifact references
require the original evidence root when replaying an exported draft. A canonical
review digest is a byte binding, not an acceptance signature. No production
memory, retrieval behavior or deployment changes are included.

See [usage and output contract](../operations/WORKFLOW_EXPERIENCE_CONTRAST.md).
This increment continues the independently implemented experience-review idea
from the [initial report](2026-10-26-harness2-experience-contrast.md); no upstream
code or dependencies were copied.
