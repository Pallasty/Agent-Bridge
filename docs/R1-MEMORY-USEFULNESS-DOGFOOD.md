# R1 Memory Usefulness Dogfood

R1 asks one product question: across 20 real development tasks, did remembered context help, go unused, fail to appear, or actively mislead?

## Decision state

The code-locked 20-task gate closed on 2026-08-11. The product decision is to retain the current memory and continuity architecture without widening retrieval, adding another ranking layer, or reopening research-heavy lanes from this aggregate alone. See `docs/reports/goal-c-u/2026-08-11-r1-memory-usefulness-final-decision.md`.

The decision is based on the 20-task gate snapshot, not on an ever-growing positive counter. After closure, do not append routine `used` or `no_recall` rows merely to increase the sample size. Record a new row only when an ordinary product task produces meaningful `missing`, `stale`, or `harmful` recall evidence worth investigating. A ledger count above 20 does not reopen R1 or strengthen the causal claim.

Record one aggregate row after a real task:

```bash
python3 scripts/agent-bridge-memory-usefulness.py record \
  --task-kind repo_truth --attest-real-task \
  --recall-outcome used --repeated-explanations 0
```

Read the current scorecard:

```bash
python3 scripts/agent-bridge-memory-usefulness.py report
```

The local JSONL file is mode `0600` in Agent-Bridge's state directory. This command only appends to it; the file is not tamper-evident or OS-immutable. Rows contain only a generated UUID, closed task-kind label, outcome label, explicit operator attestation that the task was real, repeated-explanation count, timestamp, and optional numeric recovery/payload measurements. The closed schema has no free-text field for prompts, messages, transcripts, paths, memory keys/content, notes, or secrets. Real-task provenance is operator-attested, not technically proven; do not encode sensitive meaning in identifiers.

Use outcomes consistently: `used` means recalled context materially informed the task; `no_recall` means no recall was attempted or needed; `missing` means useful prior context was expected but not returned; `stale` means returned context was outdated but caught; `harmful` means returned context caused avoidable wrong work or recovery.

The report remains `COLLECTING_REAL_TASKS` before 20 unique tasks and becomes `READY_FOR_PRODUCT_DECISION` at the gate. It does not infer that memory caused an outcome and does not change retrieval, ranking, memory, or runtime behavior. Before closure, tasks accrue naturally during product work; synthetic tasks must not be added to reach the target faster. After closure, use the recorder only for the meaningful negative regression evidence described above. This utility currently targets Unix-like hosts because it relies on `flock` and `O_NOFOLLOW`.
