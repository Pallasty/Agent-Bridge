# Source snapshot notes

`evidence_manifest_source_snapshot.json` is the current L=8/R=100 evidence snapshot.
It records known source-leading or derived steady-state subtotals while leaving all
unmeasured fields null. It is intentionally different from the empty template:

- native derived schedule: `448` steady count/step, `8` steady depth/step, first-step
  bookkeeping correction `64` count and `1` depth, giving the known logical subtotal
  `44,864` and depth `801` under the common group-order target;
- dynamic-JW source leading: `2,688` count/step and `32` depth/step;
- dynamic-JW candidate fit: `2,496` count/step and `62` depth/step;
- standard FSN candidate fit: `8,080` count/step and `128` depth/step;
- ladder FSN candidate fit: `3,984` count/step and `64` depth/step.
- surface place-route: a contract-shaped placeholder only; it has no patches,
  layouts, intervals, operation windows, or compiler/measured provenance.

The snapshot does **not** close any complete route. Native timing is missing its
occurrence table; qubit routes lack first-step corrections and route timing; all routes
lack individual-term exports and common-R measurement data; and the surface schedule is
empty. Running the unified validator therefore remains `UNRESOLVED`. Candidate-fit rows
are confined to the Fig. 5 domain and retain their non-source provenance.
