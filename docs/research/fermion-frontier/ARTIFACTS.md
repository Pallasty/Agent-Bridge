# Artifact manifest

All copied JSON files are research-only outputs. They contain no credentials.

## Claude source session

- Session:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2.jsonl`
- Round 1 workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_bc524afa-64c.json`
- Round 2 workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_d952301b-468.json`
- Round 3 partial workflow:
  `/home/pallasting/.claude/projects/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/workflows/wf_68398a04-e09.json`
- Temporary 70-claim ledger:
  `/tmp/claude-1000/-Data-CascadeProjects/7f73a250-8155-4f85-8d7e-f01582f0c0a2/scratchpad/gap345_claims.min.json`

## Preserved files

| File | Source transformation |
|---|---|
| `claude-round1-result.json` | Exact `.result` projection from round 1 workflow |
| `claude-round2-result.json` | Exact `.result` projection from round 2 workflow |
| `claude-round3-partial-result.json` | Exact `.result` projection from round 3 workflow |
| `gap345-claims.json` | Byte-for-byte copy of the temporary 70-claim ledger |

## Source hashes before preservation

- Gap 3/4/5 claim ledger:
  `ab11ba7a7648c6e2f5d37254d4500a8c405633280c443e4d83e9b2afd673fa81`
- Fixed Claude verification script (not copied; retained for provenance):
  `1f8d9fe0342c0ad111d7524a34d6207886cc13c5e3d06c37664e216eca28d108`

The copied workflow projections are independently hashed in
`SHA256SUMS` after creation.
