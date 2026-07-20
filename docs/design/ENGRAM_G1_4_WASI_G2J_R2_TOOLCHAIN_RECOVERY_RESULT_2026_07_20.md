# G2J/R2 local toolchain recovery result

R2 is a clean retry after the G2J control-order failure recorded at forum #4891.
It is not a repair or reinterpretation of that failed batch.

Owner authorization was recorded at #4893.  Independent pre-execution review
passed at #4896 before any R2 toolchain command.  The only R2 execution used a
new empty disposable directory and direct absolute paths, never a repository
selector, rustup shim, dependency resolver, or build command:

1. capture SHA-256 and `stat` of the installed 1.92.0 pair;
2. run `<absolute rustc> --version` and `<absolute cargo> --version` with an
   empty environment and a disposable working directory;
3. capture SHA-256 and `stat` again; and
4. remove the empty disposable directory and confirm it no longer exists.

The pair was unchanged before and after:

| Binary | SHA-256 | Version |
| --- | --- | --- |
| `/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/rustc` | `12cab30aa9890d54445e29149a1e82d18fbe457de12801bd11bbe7e5e7fe33a0` | `rustc 1.92.0 (ded5c06cf 2025-12-08)` |
| `/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/cargo` | `03e381389f5b7b8e695a744362f3866478f99034b2cf2df6afd4d42cfdab6f67` | `cargo 1.92.0 (344c4567c 2025-10-21)` |

Both regular arm64 executables retained their mode, owner, size, and mtime.
There was no rustup or network indication, and no toolchain mutation.

This is `RECOVERY_PROBE_PASS_EVIDENCE_READY_NO_G2G_RETRY_AUTHORITY`: it proves
only that this exact local pair can be directly version-probed.  It grants no
authority to retry G2G, resolve dependencies, compile, test, run, invoke
components/linker, deploy, or advance G1.4.
