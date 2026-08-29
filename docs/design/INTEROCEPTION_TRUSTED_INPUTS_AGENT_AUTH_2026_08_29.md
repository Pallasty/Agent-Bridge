# AB interoception: trusted inputs and exact agent authentication

Date: 2026-08-29

Status: **R9-M6 private inputs remain verified; the first R9-M2 production
root was rejected before consumer use, source-mode correction
`0e445333da0d4d2c3159d49aaed861b163146082` is `SOURCE_READY`, and a fresh
publication/seed/root retry is pending; production remains `HOLD`**.

Scope: close the last truthful input-custody gap before R9-M2 can plan the
birth of `/Data/agent-bridge-r9`, without generating or exporting another
private key.

## Decision

The node already has an enrolled GitLab identity in an owned, mode-`0600`
current-boot agent socket. R9-M5 proved that this identity can publish and
acquire an independent seed. Requiring a newly generated private-key file for
R9-M2 would add a second credential and an enrollment ceremony without adding
identity evidence.

R9-M6 therefore extends, rather than weakens, the R9-M2 contract:

- legacy fixed-private-key manifests remain accepted unchanged;
- agent manifests bind the exact socket path and inode facts, a mode-`0600`
  public-key selector and its SHA-256 fingerprint, and live agent membership;
- the private key remains inside the agent and is never copied into the
  deployment root;
- the provisioned root stores only the public selector plus a canonical
  `authentication.json` descriptor;
- offline provisioning-receipt verification checks the durable public
  identity and descriptor without pretending the current-boot agent is
  permanently live; and
- every production Git operation revalidates the physical socket, public
  fingerprint, and exact loaded identity immediately before use.

This is current-boot authenticated operation, not an unattended credential
claim. If the agent is unavailable, the publisher fails before fetch. The
optional R9-M4 persistent-key ceremony remains available if a future owner
chooses unattended publication.

## Current-node input inventory

The prior default credential notebooks are absent. The active daemon,
daemon-http, and Palace service environments contain no secret-like keys, so
the trusted credentials input contains only the expected section header and
an explicit statement that no persistent external-provider credential was
admitted.

The old HOME `machine.env` was not copied. It is below a root-owned mode-`0777`
FUSE boundary and also contains a HOME model path. R9-M6 retained only the
four settings supported by current runtime evidence:

```text
AB_SUBSTRATE_PROJECTION=bucket_pool
AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=organic
AGENT_BRIDGE_EMBED_REMOTE_URL=http://127.0.0.1:7878/embed
AGENT_BRIDGE_ONNX_MODEL_DIR=/Data/agent-bridge-r9/toolchain/machine-assets/onnx-models
```

The previous Rust 1.96.0 installation was also below the unsafe HOME/FUSE
boundary. R9-M6 instead downloaded the official standalone 1.96.1 archive,
verified SHA-256
`d29ccb1559a177c4e72291f6e5f629de7fe8885e7521ca47802627544b121e95`,
and installed only rustc, the host standard library, Cargo, rustfmt, and
Clippy. Rust 1.96.1 is the upstream point/security release for the repository's
already-pinned 1.96 line; the repository pin now names 1.96.1. See the
[official Rust 1.96.1 release](https://blog.rust-lang.org/2026/06/30/Rust-1.96.1/).

The GTE asset is pinned to repository `onnx-community/gte-multilingual-base`
at immutable revision `2edbf5e672aab465f9ed4c154a8b61791c082c69`. The large
model and tokenizer were admitted only after source-before, source-after,
destination, and exact-revision remote hashes agreed. The three small config
files were fetched directly from that exact HTTPS revision. A private manifest
inside the model directory records all five SHA-256 values.

## Prepared private bundle

The input bundle is
`/Data/agent-bridge-r9-bootstrap/trusted-inputs-r9-m6`, owned by the current
operator at exact mode `0700`. It contains:

```text
credentials                         0600
gitlab-agent-key.pub                0600
known_hosts                         0600
machine.env                         0600
toolchain/                          0700
  bin/{cargo,rustc,...}             0700
  machine-assets/onnx-models/...    private physical files
  share/agent-bridge-r9/input-origin.json
```

The complete bundle has 177 regular files and 1,916,000,745 logical bytes.
All directories are `0700`; all regular files are `0600` or owner-executable
`0700`; every inode is operator-owned and singly linked; and there are no
symlinks, sockets, devices, FIFOs, or stale staging-prefix references. After
atomic no-replace activation, `rustc --print sysroot` resolves exactly to the
final toolchain directory.

Top-level input digests are:

| Input | SHA-256 |
|---|---|
| GitLab public selector | `4621063c05d7611b57f4c8649547c16a805dcfe851b397f5b92436deb908f0a5` |
| GitLab known-hosts | `0a05b156080b28acbb84e38be631f1cfe49c8fa9379cac1a1395346eb82328a8` |
| `machine.env` | `181009490d149dcbdc03f0d11d54ab64abf959b55c7b48a3de81e9905a7cb553` |
| credentials | `72d8bcbe6cc355707d87d31f6e57667f7ed87d38ee18447a2823e24a6867bfe3` |

The public selector fingerprint is
`SHA256:cM+VGWPRZ4DH6siwj2HvR8DFkCH6mb2uzyX/ysUVJDE`. No private key is present
in the bundle.

## Provisioner and publisher hardening

The R9-M2 provisioner now treats authentication as an exact tagged union:
either the original `gitlab_deploy_key` input or one
`gitlab_authentication` object. Mixing the forms, unknown keys, descriptor
drift, unsafe socket ancestry or mode, a missing live identity, or a public
fingerprint mismatch fails before target creation. The plan digest binds the
socket device/inode/mode/owner facts and public identity bytes.

The final deployment-root activation now uses Linux
`renameat2(RENAME_NOREPLACE)`. A target appearing between the last check and
activation is preserved, and provisioning fails closed. The trusted Cargo and
rustc modes are consistently `0700` in both provisioner output and publisher
admission. The critical source inventory also now names the actual
`scripts/wrapper/creds.example` file.

The GTE model is 1,255,502,649 bytes, larger than the old generic 1 GiB
single-file input cap. Tree members now hash against the manifest's explicit
tree-byte limit, itself bounded by the fixed 16 GiB hard ceiling. Standalone
configuration and credential inputs retain their separate bounded-file path;
the large-model exception does not broaden their admission.

## Verification evidence

- R9-M2 provisioning and agent authentication: `15/15 PASS` with warnings as
  errors;
- R9-M3/M5 publication and seed: `6/6 PASS`;
- R9-M4 optional credential ceremony: `4/4 PASS`;
- R9-M1 migration: `15/15 PASS`;
- publisher lease/recovery/admission, including a real isolated ssh-agent:
  `publisher-lease-v0-ok`;
- wrapper, systemd transaction, post-build remote race, pinned assets,
  audio/runtime parity, and GTE readiness: `PASS`;
- the standalone 1.96.1 toolchain built and tested `ab-core` offline with the
  lockfile unchanged.

A full workspace test first reached the expected offline ONNX Runtime link
boundary. A normal-network rerun downloaded the pinned ORT artifact and
continued through the large workspace, but the final `ab-bridge` debug link
exhausted `/Data`; no test assertion failed. Its 3.4+ GiB target and local ORT
cache were removed, and no generated file remains in the source worktree.
CI was explicitly skipped.

## Handoff boundary

The R9-M6 preparation increment did not create `/Data/agent-bridge-r9`, install
a wrapper or binary, stop or restart a service, migrate SQLite/body state,
write a unit, or claim installed admission. Its later first R9-M2 provision
was rejected as described below, before any consumer action.

The corrected retry sequence is:

```text
publish the source-mode correction and this failure record with ci.skip
  -> acquire and verify a new independent seed at that exact candidate
  -> archive the rejected receipt and retire only its deterministic copied root
  -> update the external mode-0600 R9-M2 manifest from the verified bundle
  -> run the read-only R9-M2 plan and inspect its exact confirmation
  -> provision once with that exact confirmation
  -> run immediate fixed-path verification before any consumer
```

Only after an exact candidate-matching plan is green may R9-M2 create the
trusted root. Until then production remains `HOLD`.

The first provision at reporting candidate `5faac795...` subsequently proved
the fixed-path verifier's fail-closed value: it rejected a sole Git mode drift
on the migration orchestrator before any consumer ran. Correction
`0e445333da0d4d2c3159d49aaed861b163146082` aligns the candidate executable
bit with private production custody and adds a pre-activation clean-tree gate.
The failed receipt is evidence, not admission; the copied root will be retired
rather than repaired before a fresh candidate-bound retry.
