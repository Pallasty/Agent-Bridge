# G2I toolchain recovery preflight

G2H established that repository-selected Cargo may invoke rustup synchronization;
G2I is a static recovery-authorization preflight only. No toolchain command,
network, install, removal, build, or execution is performed here.

A future recovery lane must receive a new owner authorization and an independent
review before any action. It may proceed only with an exact already-installed
`rustc` and `cargo` absolute path, SHA-256 and version identity captured before
use; direct invocation that bypasses repository selector/rustup shims; an
isolated disposable environment; pre/post filesystem identity receipts; and a
one-command bounded action plan. Any missing binary, hash mismatch, selector
re-entry, network indication, or unexpected file change aborts before build.

Even a future recovery PASS grants only an evidence-ready local toolchain. It
does not retry G2G, compile, run, resolve dependencies, build components, or
change runtime/G1.4 without separate gates.
