# G2H local toolchain integrity decision

Forum #4793 records this static decision after G2G's fail-closed toolchain
sync attempts.  It freezes local filesystem observations only; it does not
execute, trust, repair, install, select, or otherwise exercise Rust tooling.

The repository selector requests `stable`.  The observed local directories
are `1.92.0-aarch64-apple-darwin`, `1.96.0-aarch64-apple-darwin`, and
`stable-aarch64-apple-darwin`.  The `1.96.0` directory contains `cargo` but
does not contain `rustc`; the G2F-bound `1.94` directory is absent.  Directory
names and executable presence are not identity, completeness, or usability
evidence.

The verdict is `FAIL_CLOSED_LOCAL_TOOLCHAIN_NOT_PROVEN`.  G2H authorizes no
Cargo or rustup invocation, network, install/update/remove, compile/build,
run, dependency/source/component/runtime/deploy/G1.4 action.  A later,
separate recovery authorization must name an exact preinstalled toolchain,
run outside repository selector effects, record pre/post binary identities,
and receive independent review.  It is not an automatic successor.
