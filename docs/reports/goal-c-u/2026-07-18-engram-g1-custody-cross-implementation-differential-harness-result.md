# Engram G1 custody differential harness result

Status: local verification passed; no push, deployment, runtime registration, or forum post.

The receipt is intentionally redacted: it contains only registered probe IDs,
execution coverage, static error labels, classifications, and false authority
fields. It never records temporary paths, bytes, inodes, ledger contents, keys,
or subprocess output.

Observed verdict: `PASS_SYNTHETIC_DIFFERENTIAL_OBSERVATIONS_NO_AUTHORITY` with
18 preregistered probes: seven individually named Rust dynamic tests, eight
Python dynamic observations, and four shared-gap classifications. No equivalence
claim was emitted; ACL and APFS copy-alias remain explicit unresolved gaps.

Frozen local artifact digests:

- contract: `15ab49b5b4da4935e1ff0cb96f1ce52ae307affcbe98d2d63127ec36931b7acc`;
- harness: `3349006d73a3fb1d3edce62bdd4fba48eaed2725a13b727f75b6fb796a51525b`;
- checker: `8e1349160a0d56b2a553f72fbba51c81cf2bbc767c95071e0b848776e5c7461d`.

Verification reran the frozen predecessor reconciliation checker, the 13-test
Rust custody suite, exact Rust dynamic test selectors, dual deterministic Python
receipts, semantic contract mutations, and exception-safe per-fixture cleanup
assertions for both the private tree and the external SQLite ledger. The
independent read-only review initially found checker pinning, aggregate
Rust-evidence, and ledger cleanup-assertion gaps; all were corrected before
this final rerun.
