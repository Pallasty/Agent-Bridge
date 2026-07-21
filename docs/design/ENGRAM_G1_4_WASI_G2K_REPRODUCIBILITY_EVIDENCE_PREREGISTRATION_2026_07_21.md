# G2K reproducibility evidence preregistration

G2K repairs the evidence model exposed by the old G2G attempt: a raw Rust
`.rlib` SHA-256 is an observation of one target directory, not a portable
cross-worktree reproducibility invariant. G2K is static only. It neither
invokes Cargo nor authorizes a G2G retry.

## Frozen inputs

Any future G2G retry must bind both independent receipts to this exact input
tuple:

| Input | Required binding |
| --- | --- |
| G2E host source | SHA-256 `52f5f2adeed96e4d70b3ddb03d7793bac6f142b7eb8e125eb591eec4f1207343` |
| Isolated fixture | pre-registered zero-dependency `[workspace]` manifest and lockfile, each SHA-256 frozen below and recorded in both receipts |
| Toolchain | direct 1.92.0 absolute `rustc`/`cargo` paths, their R2 SHA-256 values, and `--version` output |
| Build semantics | `--offline --locked`, explicit fixture manifest, fresh target directory, no output execution |
| Independence | two distinct clean worktrees and distinct fresh target directories, each with a separate receipt |

The receipts must show a successful compilation and cleanup. They must fail
closed on rustup-selector re-entry, network indication, lockfile mutation,
dependency appearance, source or toolchain binding drift, non-empty leftovers,
or any attempt to run the output.

The pre-registered fixture is
`scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0`. Its only permitted
compile template is:

```sh
CARGO_NET_OFFLINE=true /Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo \
  build --offline --locked \
  --manifest-path scripts/eval/fixtures/engram_g14_wasi_g2g_host_build_v0/Cargo.toml \
  --target-dir <fresh-target-directory>
```

The target placeholder is the only variable. Each receipt must bind its
manifest and lockfile to the G2K fixture bytes, then record a distinct clean
worktree identifier and target path.

## Future receipt contract

Each of the two future receipts must contain: an absolute clean-worktree path;
its Git `HEAD` and tree IDs; the absolute manifest and target paths; the fully
expanded command; exit code; compilation-success flag; manifest/lock/wrapper
and G2E-source pre- and post-SHA-256 as separate named values; `rustc` and `cargo` absolute path,
SHA-256, and version before and after; raw artifact SHA marked local-only;
cleanup result; a negative-evidence object for network, rustup-selector,
lockfile, dependency, and output-execution indicators; and a fail-closed reason
when unsuccessful. A receipt without every field is not admissible.

Pair acceptance requires two receipts with different worktree paths and target
paths; equal G2E/fixture/toolchain bindings; each exit code zero, compilation
success true, and cleanup true; and no network, selector, lock, dependency, or
execution indication in either receipt. The fully expanded command must name that receipt's own
absolute manifest and target path. Pair acceptance must ignore raw artifact SHA
equality and must not synthesize a normalized artifact digest. Equality between
receipts is insufficient: each receipt's pre- and post-G2E, fixture, and
toolchain identities must separately equal the G2K frozen input tuple.

## Artifact rule

Each receipt may record its raw `.rlib` SHA-256 for local forensic inspection.
It must state `raw_artifact_sha_scope = local_observation_only`. Cross-worktree
PASS must **not** compare those raw hashes. No canonical artifact normalizer
exists or is authorized by this gate, so `normalized_artifact_digest` is
explicitly `UNDEFINED_NOT_AUTHORIZED`, never a fabricated stable digest.

The G2G evidence claim is therefore bounded: both independently bound input
tuples compiled offline and locked under the same verified direct toolchain.
It is not byte-for-byte reproducibility, component construction, behavioral
proof, or execution proof.

## Authority boundary

G2K does not authorize a G2G build, dependency resolution, WIT generation,
components/linker, output execution, runtime/G1.4 activation, deployment, or
any use of a private/candidate/capability input. A separate owner authorization
and a pre-execution independent review remain mandatory for a future G2G retry.
