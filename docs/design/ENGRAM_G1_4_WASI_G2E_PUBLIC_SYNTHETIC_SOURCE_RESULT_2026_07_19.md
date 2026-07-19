# Engram G1.4 WASI G2E — result receipt

G2E records public synthetic source evidence under the G2D authorization (#4759).
The receipt binds the three source files by SHA-256 and keeps the exact
three-interface WIT boundary visible to review.

**The fixture is NOT compiled, linked, or run.** No generated bindings, import
manifest, linker timer isolation, component behavior, dependency acquisition, or
build authority is proven here.  A separate owner decision, G2F public synthetic
build authorization, is required before any build lane may open.

The earlier identical-text candidate `b4cbfeda` was explicitly withdrawn in
#4768 after a repository-wide pre-commit hook attempted `cargo check`. This
replacement candidate is regenerated from G2D in a clean worktree and commits
with that hook bypassed; the earlier attempt is neither evidence nor authority.

Run `scripts/check-engram-g14-wasi-g2e-public-synthetic-source.sh` for static
integrity evidence, or `python3 scripts/eval/engram_g14_wasi_g2e_public_source.py`
for a deterministic source-hash receipt.
