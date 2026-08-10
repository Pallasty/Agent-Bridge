# S638 Story render artifact identity and Python package

## Decision

Accept the source implementation and isolated package tests. S638 provides a
fixed-allowlist, owner-custodied, hash-manifested control-plane package and a
descriptor-stable launch of the packaged CPython and S637 Worker. The real
Worker continues to return only `custody_rejected`; runtime adoption remains
closed.

This unit did not read the installed authority key, load a model, resolve or
download dependencies, create render output, register MCP, change runtime
configuration, deploy, or play audio.

## Identity and custody

`story_render_artifact_package.py` packages the four Guardian custody sources,
the Worker and its transitive Python sources, the trusted runner, and the fixed
S602/S603/S604/S608/S611/S620 JSON evidence. It also copies the resolved
`/usr/bin/python3` executable and its complete 30 MiB standard-library tree.
Source symlinks are materialized as regular files. Every packaged file is
present in a canonical manifest with SHA-256, size, and mode.

Construction requires a new path below a private owner-controlled parent.
Verification requires owner UID, package/directory mode `0500`, regular-file
mode `0400` or executable mode `0500`, link count one, no symbolic links, no
unmanifested files, and exact content hashes. Reads use `O_NOFOLLOW`; identity
is compared before and after the bounded read using device, inode, size, and
nanosecond mtime.

The isolated launcher reopens the packaged Python and Worker with
`O_NOFOLLOW`, verifies both descriptors, marks only those descriptors
inheritable, and executes `/proc/self/fd/<python>` with the Worker descriptor.
The script descriptor resolves back into the read-only package, so its pinned
relative dependencies remain inside the verified package tree.

## Offline Python boundary

The present control path is a copied and manifest-bound CPython-standard-library
closure. It runs with `-I -S`, package-local `PYTHONHOME`, an otherwise empty
application environment, and bytecode writes disabled. It is therefore
deterministic and offline for the only currently permitted behavior:
pre-authority contract rejection.

The inference dependency closure is deliberately not claimed. The fixed
interpreter has no discoverable `numpy`, `onnxruntime`, `soundfile`, `torch`, or
`transformers` under isolated `-S` operation, and there is no reviewed offline
wheelhouse. S638 performs no download or package resolution. A real render must
remain blocked until a separately reviewed, hash-bound offline inference
wheelhouse closes that gap.

## Verification

The focused suite proves package construction and round-trip verification,
private modes and zero authority, tamper and symlink rejection, pre-existing
destination and writable-parent rejection, and a real descriptor-launched
Worker subprocess returning a redacted `custody_rejected` response.

## Remaining ladder

S639 may add only a minimal Guardian product entrypoint with synthetic process
tests and runtime default-off. S640 still owns contract/output convergence and
the owner broker. S641 owns default-off MCP registration, S642 deployment
review, and S643 the separately authorized single fixture pilot. The offline
inference wheelhouse is an additional hard blocker before any real render.

## Rollback

Rollback is deletion of the source builder, tests, and S638 evidence files.
Isolated test packages live only in temporary directories and are removed by
the tests. No live installation or runtime state points at this package.
