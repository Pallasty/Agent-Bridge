# Xiao Shu focus-follow stage 5: production contract

Date: 2026-08-23

## Outcome

The five missing dedicated motions now have a machine-readable, fail-closed
production contract exposed by `avatar sprite-asset-contract`. It defines exact
filenames, frame sequences, grid geometry, deployed viewport, and action-specific
baseline limits, then audits any files already present in the selected asset root.

Current readiness is expected to be `0/5 accepted, 5 missing, 0 rejected`.
Existing runtime fallback bindings remain unchanged.

The user confirmed the CLI/API fallback path, but `OPENAI_API_KEY` was absent
from the current process environment. No network generation was attempted and no
credential was requested or persisted. The checked-in contract and prompt
invariants allow generation to resume without redesign once the key is configured
locally.

## Verification

- contract completeness and fail-closed missing-asset test;
- previous alpha, geometry, populated-frame, projection, and baseline tests;
- normal `ab-bridge` binary check;
- live CLI report against the project asset directory.
