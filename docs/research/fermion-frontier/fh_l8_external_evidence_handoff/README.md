# FH-L8 external-evidence handoff

This directory is the sender/receiver handoff for the five raw compiler or
hardware exports required by `FH-L8-EXTERNAL-EVIDENCE-INTAKE-V1`.

## Sender workflow

1. Open the `REQUEST.md` under the requested route.
2. Produce the complete ordered individual-term JSON export for the fixed
   `FH_L8_UoverT8_tT1_half_filling`, `linear_size=8`, `trotter_steps=100`
   workload. Do not reconstruct it from a paper figure or prose.
3. Copy `registration.template.json` to a separate intake registry and fill all
   blank custody fields. Keep the raw export outside this Git repository.
4. Supply immutable HTTPS provenance, release or commit identity, compiler
   identity/version, configuration SHA-256 and environment-lock SHA-256.

## Receiver workflow

From the repository root, first verify this handoff package:

```bash
python3 docs/research/fermion-frontier/fh_l8_external_evidence_handoff_checker.py
```

Place received exports beneath a dedicated intake root and create a draft
registry only for unambiguous files:

```bash
python3 docs/research/fermion-frontier/fh_l8_external_evidence_intake_bootstrap.py \
  --intake-root /ABSOLUTE/INTAKE/ROOT \
  --select-unique-candidates \
  --emit-registry /ABSOLUTE/INTAKE/ROOT/draft-registry.json
```

After reviewing and completing every custody field, run:

```bash
python3 docs/research/fermion-frontier/fh_l8_external_evidence_intake_runner.py \
  --registry /ABSOLUTE/INTAKE/ROOT/completed-registry.json \
  --intake-root /ABSOLUTE/INTAKE/ROOT
```

An incomplete or rejected route is not evidence. The package itself supplies no
real export, compiler result, performance result, cross-route comparison,
physical reference, full-53 authority, or `READY_FOR_BENCHMARK` status.

