# Engram G1.4 public-synthetic business component implementation result

Date: 2026-07-21  
Verdict: `PASS_PUBLIC_SYNTHETIC_IMPLEMENTATION_NO_AUTHORITY`

## 1. Delivered

- standard-library-only in-memory contract harness;
- default-off CLI with explicit `--enable-public-synthetic` opt-in;
- duplicate-key, UTF-8, integer-only, exact-schema, bounds, and canonical-byte
  validation;
- deterministic pure world-state transformation;
- two-attempt replay receipt with distinct invocation IDs and byte-equality;
- independent adversarial checker and pinned shell entrypoint; and
- runtime-crate leak check.

The harness uses the frozen WIT bytes only as a transparent artifact surrogate.
It does not claim that a WASI component was built or executed.

## 2. Evidence

`bash scripts/check-engram-g14-public-synthetic-business-component-harness.sh`
passed:

- 22 independent checks;
- default-off boundary;
- deterministic contract validation and receipt output;
- happy-path occupancy fixture (`750` per mille);
- missing/extra/duplicate/float/out-of-bounds input falsifiers;
- exact zero-import policy;
- all admission flags false; and
- no symbol leakage into `crates/`.

Pinned artifacts:

| Artifact | SHA-256 |
| --- | --- |
| implementation | `fe04dc3cfd674d918c44ffa6719f9db5c15429000d4279e6babf27ee89f139fd` |
| independent checker | `80eef297e51468e94245ca77c7e8fbaa517ba68e46a0e97b29612efe098353b2` |
| shell entrypoint | `6c3ffbc6cd09bffbde39f1ff0577b1a81b609a1ae817947dbe532006f18056ef` |
| WIT fixture | `67a4317d8b2664dcdd18223908dc003a03baef6513e13e37d8fa49d4868b9bd5` |
| contract JSON | `a666088da2603b7caf7fc4ce3a2950d08fc5ce2c4c1665d9ee4985ffe505c374` |

## 3. Authority boundary

This result grants no authority for WIT binding, Cargo/component/linker
selection, actual component build, runtime registration, MCP exposure, release,
deployment, production writes, candidate/private data, or native sandbox and
clock-isolation claims.

The only admissible next review is a separately scoped component-construction
or host-integration gate. It must consume this result as synthetic contract
evidence and preserve the default-off boundary.
