# R1 Memory Usefulness Dogfood

R1 asks one product question: across 20 real development tasks, did remembered context help, go unused, fail to appear, or actively mislead?

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

The report remains `COLLECTING_REAL_TASKS` before 20 unique tasks. It does not infer that memory caused an outcome and does not change retrieval, ranking, memory, or runtime behavior. Tasks should accrue naturally during product work; synthetic tasks must not be added to reach the target faster. This utility currently targets Unix-like hosts because it relies on `flock` and `O_NOFOLLOW`.
