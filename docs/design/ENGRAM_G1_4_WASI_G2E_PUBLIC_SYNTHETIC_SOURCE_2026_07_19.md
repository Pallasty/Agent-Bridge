# Engram G1.4 WASI G2E — public synthetic source

## Authority and boundary

G2D's owner authorization (#4759; landed at `32c9edcd`) permits exactly this
source-only successor.  G2E adds a public, synthetic WIT world and source-level
models for a component and direct host.  It does **not** add Cargo metadata,
lockfiles, dependencies, installs, compilation, linking, execution, private or
capability access, runtime behavior, deployment, canary, G1.4 activation, or a
native/QEMU fallback.

The public static boundary is deliberate: source text can make the requested
architecture reviewable without claiming that generated bindings or a linker
actually exist.  The only permitted next decision is G2F public synthetic build
authorization; G2E itself grants no build authority.

## Exact source surface

`world.wit` imports exactly three Preview2 interfaces, in order: wall-clock,
monotonic-clock, and io/poll.  The component model reports the fixed wall epoch
(`946684800` seconds), a logical monotonic value, and one-millisecond quantum.
The host model owns all clock and poll semantics directly: each `now` returns
the current logical time and then advances one checked quantum; subscriptions do
not advance time; poll returns ready caller indices or advances only the logical
clock to the nearest deadline.  It exposes no broad WASI context or ambient
timer path.

These are static source claims, not compiled or built evidence.

## Acceptance

`scripts/check-engram-g14-wasi-g2e-public-synthetic-source.sh` validates the
exact three-source hash manifest, WIT import set/order, direct logical clock and
poll markers, forbidden-family scan, scope and authority flags, documents, and
directed semantic mutations.  It uses only Python's standard library and Git
metadata; it does not invoke Cargo or execute the source fixture.
