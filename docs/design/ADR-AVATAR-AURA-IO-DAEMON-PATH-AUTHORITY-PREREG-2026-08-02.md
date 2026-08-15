# ADR: Avatar Aura I/O daemon path-authority preregistration

- Status: Accepted for preregistration; Rust implementation remains separate
- Date: 2026-08-02
- Decision scope: file-backed `aura_io` intake on the Avatar Linux renderer
  daemon endpoints
- Audited base: `e71533e4b0f50c770756b83e07c213a9b9efc09b`
- Coordination: Agent-Bridge forum thread #322
- Predecessor: S7 Avatar inventory and authority-safety stop
- Current-unit posture: documentation only; no Rust production or test change,
  deployment, daemon restart, runtime enablement, or client reconnect

The source audit began at predecessor
`a5744e82b12301abc589353123a1887c01558bab`. During review, GitLab and GitHub
`master` advanced together to the audited base through S619 and S620. Those two
direct descendants add only twelve Voice Scene documentation, Python, fixture,
and test files; they do not change `main.rs`, `daemon_http.rs`,
`avatar_renderer.rs`, Avatar tests, or this ADR path. The isolated worktree was
fast-forwarded before final verification. The canonical checkout contained
unrelated user work and was not edited.

## Context

The S7 Avatar inventory identified a daemon query field that is typed as
`Option<PathBuf>` and reaches an Aura sidecar validator without a visible path
allowlist or equivalent authority contract. S7 deliberately stopped at that
finding and required an independent threat model and authorization decision
before repair.

The file path is optional, and requests without `aura_io` do not enter the Aura
file reader. When the field is present, however, the operation is not
authority-free merely because its payload calls itself read-only. It exercises
the daemon process's filesystem read authority and performs synchronous,
unbounded reads inside an asynchronous HTTP handler.

This ADR governs only the daemon file-backed Aura path. It does not classify
all Avatar endpoints as authenticated or secure, and it does not turn a
network ACL, a renderer hash, or an `AppState` value into general filesystem
authority.

## Audited call graph

The only current production caller of the Aura path reader is daemon HTTP:

```text
GET /avatar-surface/linux-renderer[-state]?aura_io=<PathBuf>
  daemon_http.rs:162-165,612-633
    -> avatar_linux_renderer[_state]                 :1299-1317
    -> avatar_linux_renderer_payload                 :1256-1296
       -> presence Store read                        :1260
       -> pet-state read                             :1263
       -> renderer_payload_from_sources_with_aura_io_path
                                                       :1275-1280
          -> validate_aura_io_sidecar_path           avatar_renderer.rs:454-462
             -> fs::read(sidecar)                    :245-247
             -> parse and validate manifest          :248-250,140-182
             -> resolve uniform and digest paths     :115-123,187-188
             -> fs::read(uniform)                    :189-190
             -> check 1,024 bytes after full read    :191-196
             -> fs::read(digest)                     :198-199
             -> compare caller-supplied hashes       :200-207
```

The HTML renderer carries the original `aura_io` value into its state URL at
`daemon_http.rs:1331-1347` and fetches that URL once per second at
`5761-5769`. One opened page can therefore repeat all three reads indefinitely.

Other Avatar surface handlers deserialize the shared query type but do not
consume `aura_io`. The current Avatar MCP renderer schema has no Aura path
field, and the CLI has no Aura sidecar argument. Public library calls and
integration tests are not additional network entry points.

## Current authority and resource state

| Property | Sidecar | Uniform | Digest |
| --- | --- | --- | --- |
| First explicit filesystem operation | unbounded `fs::read` | unbounded `fs::read` | unbounded `fs::read` |
| Metadata before content read | none | none | none |
| Regular-file check | none | none | none |
| Symlink policy | follows | follows | follows |
| Canonical containment | none | none | none |
| Byte ceiling | none | exact 1,024 checked only after read | none |
| Accepted path form | arbitrary `PathBuf` | absolute, or relative to sidecar parent including `..` | same |

`resolve_manifest_path` joins a relative string to the sidecar parent. It does
not normalize, canonicalize, or establish authority. An absolute reference
bypasses the parent, while `..` can escape it.

The hashes in the manifest prove only that bytes read by the daemon equal
hashes supplied in that same manifest. They do not establish trusted
provenance or permission to open the named files.

The daemon router has no route-local authentication middleware. `AppState`
contains only a Store and embedding backend; it has no Hub security object or
path capability. The CLI default listen value is `0.0.0.0:7878`. A real
deployment may be narrowed by explicit listen configuration, host firewall,
or Tailscale ACL, but none of those conditions is proven by this source audit.

## Threat model

### Protected assets

- daemon request-path availability and bounded memory, CPU, and filesystem I/O;
- files readable by the daemon OS user but not named by the operator's one
  configured Aura entry;
- host paths and the shape of the ambient filesystem outside that entry;
- bounded parsing and byte-for-byte self-consistency of the cached Aura report;
- the distinction between a file-read capability and review, write, queue,
  audio, notification, or desktop-control authority.

The configured selector name `default` is public and not a secret. The Aura
manifest's hashes are self-consistency checks, not authenticity, authorship, or
trusted-provenance evidence.

### Actors and trust boundaries

- The operator may delegate exactly one sidecar under one dedicated Aura root.
- The root and its writer are trusted operator custody. Enabling Aura on a
  directory writable by socket callers, another untrusted principal, group, or
  world is outside this contract and must fail closed.
- A socket-reachable requester is not an operator. It may select only the
  public identifier `default`; it cannot submit a filesystem path, choose a
  root, or widen the configured entry.
- Manifest values remain untrusted parser input even when their writer is
  operator-controlled and the connection passed an external network ACL.
- Process cwd, projected presence cwd, request `project`, sidecar parent, and
  manifest content are not authority sources.
- P2 still binds admission to retained descriptors so a root-path or symlink
  substitution cannot redirect a checked open. It does not claim to defend a
  deliberately malicious operator or a hostile writer already holding write
  authority inside the accepted root.

### Source-backed threats

1. **Unbounded or blocking reads.** On Unix, `/dev/zero` can cause an
   indefinitely growing allocation, while a FIFO, device, or slow file can
   block a Tokio worker. A large regular sidecar or digest is fully allocated
   before any limit.
2. **Polling amplification.** The renderer's one-second state refresh repeats
   the work and lets multiple pages multiply I/O and hashing cost.
3. **Path-authority escape.** Absolute paths, `..`, and symlinks can select
   files outside any implied sidecar directory.
4. **Filesystem oracle and error disclosure.** The HTTP 400 body currently
   includes validation context. Paths, read stage, actual schema values,
   shadow-key names, and the actual uniform length can be exposed. Successful
   responses also echo the sidecar and manifest path strings.
5. **Time-of-check/time-of-use substitution.** `canonicalize` followed by a
   separate path-based open rejects a static escape but does not bind the file
   that was checked to the file that is read.

The current code does not return arbitrary file bytes. It can provide
existence/read-stage, length, and caller-selected hash-equality oracles, but
this ADR does not label it a demonstrated full local-file-content disclosure.
Nor does this source finding prove that a particular deployed daemon was
reachable, exploited, or exhausted.

Aura data feeds only the renderer JSON and CSS hue layer. The audited call
chain does not write files, grant review authority, enqueue actions, emit
audio or notifications, or control the desktop. Those non-effects remain
important boundaries; they do not reduce the filesystem and availability
risk.

## Options considered

| Option | Security result | Compatibility and cost | Decision |
| --- | --- | --- | --- |
| Preserve the current unrestricted reader | No authority boundary; unbounded blocking and memory risk remain | No compatibility change | Rejected |
| Treat the caller-selected sidecar parent as the root | Caller still chooses the root; absolute and sibling references remain ambiguous | Small code change but no real delegation | Rejected |
| Derive a root from query `project`, presence `cwd`, process cwd, or repository cwd | These values are not operator capabilities and may expose a broad checkout | Appears convenient but conflates identity/scope with file authority | Rejected |
| Rely only on Tailscale ACL or future route authentication | Narrows callers but still delegates all daemon-readable paths and permits resource abuse | Useful defense in depth, insufficient path authority | Rejected as the file gate |
| Immediately hard-disable daemon Aura file reads | Closes the network file-read and unbounded-read path | Temporarily removes optional file-backed Aura behavior | Accepted as the first Rust safety gate |
| Per-request root-relative paths plus bounded opens | Narrows ambient authority but still exposes a namespace oracle and lets one-second polling sustain file I/O | Preserves dynamic updates but leaves an avoidable request-time resource surface | Rejected for initial reopening |
| Operator-configured entry preloaded once into an immutable sanitized snapshot | Removes filesystem paths and file I/O from HTTP while retaining one bounded Aura choice | Aura changes require a restart or a separately designed reload | Accepted for staged reopening |
| Canonicalize then reopen by ambient path | Rejects static root escape but retains a substitution race | Portable and simple | Rejected for final HTTP reopening |

## Decision

This documentation unit freezes the following sequence. Each numbered phase is
a separate landing and authority gate.

### P0: preregistration only

Land this ADR without changing Rust behavior or tests. The documentation unit
does not open any supplied path and does not deploy or restart the daemon.

### P1: default-disabled daemon safety stop

The first Rust unit must unconditionally reject every successfully
deserialized daemon request whose `aura_io` field is present. P1 introduces no
capability type, bypass, enable/configuration path, or alternate reader.

The guard must run at the start of `avatar_linux_renderer_payload`, before its
presence Store read, pet-state read, path admission, metadata call, open, or
content read. It returns HTTP 403 with the exact stable body
`aura_io_file_access_disabled`; no caller path or OS error is included.
Requests without `aura_io` retain their current behavior and output.

Axum may reject malformed percent encoding, duplicate/invalid typed fields, or
another invalid query field before entering the handler. P1 does not promise
403 for such requests. It promises that no successfully parsed
`Some(aura_io)` reaches payload acquisition or filesystem code; extractor
rejection also cannot reach the Aura reader.

P1 does not remove the pure href serializer and does not add Aura path input to
CLI or MCP. The existing unrestricted local validator may remain available to
explicit library callers, but daemon HTTP must no longer reach it.

### P2: opaque capability and one-shot snapshot loader

A later Rust unit may introduce an opaque, field-private capability in
`avatar_renderer.rs`, without connecting it to the daemon. A representative
shape is:

```rust,ignore
pub struct AuraIoReadCapability {
    root: OpaqueDirectoryHandle,
    limits: AuraIoLimits,
}

impl AuraIoReadCapability {
    pub fn parse_entry(&self, raw: &Path) -> Result<RelativeAuraPath, AuraIoReadError>;

    pub fn load_snapshot(
        &self,
        logical_sidecar: &RelativeAuraPath,
    ) -> Result<SanitizedAuraIoReport, AuraIoReadError>;
}
```

The concrete handle type is platform-specific and the names are illustrative;
the opacity and behavior below are normative. Construction must retain an
opened directory handle, and `load_snapshot` must perform every open relative
to that handle. There is no `capability exists -> call legacy ambient-path
validator` seam. P2 covers handle acquisition, close-on-exec, bounded reads,
the sanitized result, and root-path/symlink substitution tests. It does not
read environment variables or connect to daemon HTTP.

### P3: explicit startup preload and memory-only HTTP selection

Only after P2 passes its complete negative matrix may daemon startup accept an
explicit operator configuration. P3 uses the P2 capability once before binding
listeners, loads exactly one sidecar, and installs only an immutable sanitized
report under the public selector `default` in `AppState`. The handler never
retains the directory capability or opens a file.

The initial configuration contract is:

- `AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE` unset, empty, or `0`: disabled;
- `AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE=1`: requires a non-empty
  `AGENT_BRIDGE_AVATAR_AURA_IO_ROOT` and non-empty root-relative
  `AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY`;
- any other activation value, root/entry present without activation, missing or
  invalid enabled configuration, preload failure, or an unsupported safe-open
  platform while enabled: daemon startup fails before binding listeners;
- a disabled daemon starts normally on an unsupported safe-open platform;
- config is parsed once from a pure values map, not consulted per request;
- the root must be an existing absolute directory, not a symlink, filesystem
  root, or the user's home directory itself, and must satisfy the trusted-writer
  checks below;
- the initial ceilings are fixed; P3 exposes no environment or query option to
  lower or raise them;
- after successful preload, the directory handle is closed and only the
  sanitized in-memory report remains in daemon state.

P3 changes the daemon query field from a path-bearing type to an opaque string
selector. Only the exact seven-byte value in `aura_io=default` selects the
cached report. An omitted parameter means no Aura; an explicitly empty value,
any other value, and any duplicate/invalid selector reject with the typed or
framework behavior below rather than being treated as absent. The one-second
renderer state URL may preserve only `default`, so polling performs Store/pet
and memory reads but no Aura filesystem operation or hashing.

This capability is server-side file authority, not caller authentication.
External network policy remains a separate control and must not be described
as supplied by the capability.

### P4: runtime adoption

Deployment, daemon restart, environment installation, endpoint probing, and
client reconnect are separately authorized operations. A source merge through
P3 does not prove any deployed process has adopted the capability.

## Normative preload contract for P2/P3

### Logical paths and containment

- The operator-configured sidecar entry is a non-empty root-relative logical
  path composed only of normal components. Absolute/root/prefix, `.` and `..`
  components reject.
- The uniform and digest references are non-empty logical paths relative to
  the admitted sidecar's directory. The same component rules apply.
- Both referenced files must remain in that sidecar-directory subtree and the
  same retained Aura root capability.
- All symlinks, including in intermediate components, reject. All three
  objects must be regular files, have link count one, and reside on the same
  device/filesystem as the retained root.
- Admission and open must be descriptor-relative and bind checks to the opened
  object, set close-on-exec, and forbid symlink and mount traversal, using an
  audited `openat2` beneath/no-symlink/no-xdev policy, `cap-std` equivalent, or
  another primitive with the same demonstrated semantics. A
  `canonicalize`/`starts_with` check followed by `fs::read` is insufficient.
- The root, every traversed directory, and the sidecar, uniform, and digest
  files must be owned by the daemon effective user and reject group/world write
  permission on Unix. Other platforms need an equivalent reviewed
  trusted-writer check across the full chain; absence of one keeps enabled
  preload fail-closed.
- Unknown, network, and FUSE filesystems reject for initial P3. The exact
  platform classifier and allowlist must be reviewable in P2.
- If the safe-open, same-filesystem, link-count, or writer-custody checks cannot
  be demonstrated on a platform, enabled Aura preload remains unavailable.

These checks reduce confused-deputy and replacement risk. Because the operator
and root writer are trusted, this contract does not claim authenticity against
a hostile writer inside the accepted root. The manifest hashes remain only
structural self-consistency evidence.

### Resource bounds and loading

- sidecar: at most 65,536 bytes;
- uniform: exactly 1,024 bytes;
- digest: at most 1,048,576 bytes;
- logical path text: at most 4,096 UTF-8 bytes per field.

The limits are fixed compile-time ceilings. Any committed or operator fixture
that needs a higher limit stops the implementation and returns to design with
measured evidence.

File type and size are checked on the opened descriptor. Readers consume at
most ceiling plus one byte and require EOF, so a file that grows after metadata
cannot force an unbounded allocation. Uniform validation checks the same opened
descriptor and never reads more than 1,025 bytes.

The preload runs before listener bind on one dedicated bounded worker and is
not repeated by requests. P3 therefore claims bounded bytes and removal of
request-triggered Aura I/O, not that a kernel or failing device syscall can be
force-cancelled. Rejecting network/FUSE/unknown filesystems and requiring
trusted operator custody are prerequisites for enabling the one-shot preload.

### Error and response contract

HTTP has no file-existence, size, schema, or hash error path after P3 because
all filesystem validation happens before the listener binds:

| Condition | HTTP status | Body |
| --- | ---: | --- |
| successfully parsed Aura selector while P1/P3 is disabled | 403 | `aura_io_file_access_disabled` |
| empty selector or selector other than exact `default` | 403 | `aura_io_not_authorized` |
| malformed query rejected by Axum before the handler | 400 | framework-controlled, no Aura file read |

Responses must not contain the submitted host path, canonical path, OS error,
actual schema value, actual file length, or rejected manifest key. Internal
P2 errors are typed by role and reason for operator diagnostics, but never
contain file bytes. Startup maps every unhandled I/O condition, including
permission, I/O, stale-handle, and safe-open failure, to a redacted daemon-start
error and does not bind a listener.

On success, the daemon projection omits `sidecar_path`, `uniform_path`,
`digest_path`, and every configured host path. The renderer may
retain hashes and validated schema fields it already consumes. A polling URL
may carry only `aura_io=default`; every poll selects the immutable in-memory
report and performs no Aura filesystem admission, open, read, or hash.

The unrestricted local validator's report compatibility is outside the daemon
projection. P2 must not silently claim that retaining this explicit local API
makes it safe for untrusted paths.

## TDD preregistration

No Rust test is added in P0. P1 through P3 must follow separate, observed
RED-GREEN cycles; a batch of already-green tests is not evidence of the first
missing behavior.

### P1 first RED

Add only:

`avatar_linux_renderer_rejects_successfully_parsed_aura_io_before_payload_acquisition`

The test supplies an `aura_io` path to deliberately invalid JSON and an
ordinary isolated test Store whose fixture uses a unique pet id with no ambient
pet-state file. At the audited base it reaches later acquisition and returns a
path/parse-oriented 400, so the exact 403/body assertion must be observed RED.
P1 is green when it returns exact
403/`aura_io_file_access_disabled` and invalid file bytes cannot affect the
result.

`StateStore` has no narrow spy and approximately 135 trait methods, so P1 does
not claim a dynamic zero-Store-read proof. A source-order ownership oracle must
also prove the unconditional Aura branch lexically precedes
`avatar_surface_entries` and `read_pet_state`. After the first GREEN, add the
positive control
`avatar_linux_renderer_without_aura_io_preserves_existing_payload` in the same
landing and compare the existing status and payload shape. Then add the
source-boundary RED
`avatar_linux_renderer_aura_guard_precedes_payload_acquisition`; its exact
filter uses the same P1 command shape with that qualified test name.

The exact RED command is:

```text
CARGO_TARGET_DIR=/tmp/ab-aura-p1-target cargo test --locked --offline \
  -p ab-bridge --lib \
  daemon_http::tests::avatar_linux_renderer_rejects_successfully_parsed_aura_io_before_payload_acquisition \
  -- --exact --nocapture
```

Do not run `/dev/zero` or FIFO directly against the old implementation. Any
liveness regression probe must use an injected reader or an isolated child
process with a hard timeout and cleanup.

### P2 first RED and gradient

The first capability-reader RED is:

`aura_io_capability_rejects_absolute_sidecar_before_parse`

Create sibling `trusted/` and `outside/` directories and put invalid JSON in
`outside/bad.json`. Pass that absolute path to the wished-for `parse_entry`
constructor. It must return the typed `aura_io_sidecar_not_relative` variant,
not a parse/read error. On the audited base this is a compile RED because the
opaque capability, relative-path constructor, and loader do not exist.

After that one behavior is green, add one RED at a time:

- `aura_io_capability_accepts_regular_relative_files_inside_trusted_root`;
- `aura_io_capability_rejects_parent_sidecar_before_parse`;
- empty, `.`, parent, absolute, and over-4,096-byte logical paths for the
  sidecar, uniform, and digest roles;
- symlink, intermediate-symlink, non-regular, hard-link, cross-device,
  wrong-owner, and group/world-writable cases for the sidecar, uniform, and
  digest roles and every traversed directory;
- `aura_io_capability_rejects_oversize_sidecar_before_parse`;
- `aura_io_capability_rejects_wrong_uniform_size_before_content_read`;
- `aura_io_capability_rejects_oversize_digest_before_hash`;
- metadata-then-growth tests proving a ceiling-plus-one read rejects;
- root-path replacement and authorize/open symlink-swap harnesses proving the
  retained descriptor never escapes;
- close-on-exec, trusted-writer permission, unknown/network/FUSE filesystem,
  and safe-open unsupported-platform cases;
- typed-error tests for permission, I/O, and stale-handle failures;
- a sanitized-report test proving no host path or file byte enters the result.

The positive fixture must use relative manifest references. Existing
`avatar_renderer` integration fixtures write absolute uniform and digest paths;
they are baseline compatibility evidence for the explicit local validator, not
valid capability-reader fixtures. Platform-sensitive device/filesystem cases
must use an injected metadata/open adapter or another unprivileged deterministic
harness; tests must not require a privileged mount.

The exact first RED command is:

```text
CARGO_TARGET_DIR=/tmp/ab-aura-p2-target cargo test --locked --offline \
  -p ab-bridge --test avatar_renderer \
  aura_io_capability_rejects_absolute_sidecar_before_parse \
  -- --exact --nocapture
```

### P3 integration matrix

- config values: disabled forms, invalid activation, root/entry without
  activation, activation without root/entry, invalid/symlink/root/home root,
  safe valid root, and unsupported-platform disabled/enabled behavior;
- every enabled preload error prevents listener binding;
- a valid config preloads one sanitized report as `default`, closes its file
  capability, and stores no host path in `AppState`;
- after preload, renaming/removing the fixture and root does not change HTTP
  success for `aura_io=default`, proving the handler performs no file reopen;
- disabled mode returns the P1 code, while an unknown selector returns the one
  redacted authorization code without filesystem access;
- successful daemon JSON and HTML contain no host path;
- the state URL carries at most `aura_io=default`, and repeated state calls use
  only the cached report;
- requests without `aura_io` preserve status, JSON shape, and renderer HTML;
- CLI and MCP help/schema tests prove no new caller-selected Aura file path was
  added there.

The config parser and preload composition must be testable without binding a
socket. The exact first integration RED command is:

```text
CARGO_TARGET_DIR=/tmp/ab-aura-p3-target cargo test --locked --offline \
  -p ab-bridge --lib \
  daemon_http::tests::avatar_aura_enabled_config_preloads_default_snapshot_before_router \
  -- --exact --nocapture
```

The exact focused baseline command is:

```text
CARGO_TARGET_DIR=/tmp/agent-bridge-aura-prereg-target-20260802 \
  cargo test --locked --offline -p ab-bridge --test avatar_renderer -- --nocapture
```

Each Rust landing additionally requires touched-file rustfmt, staged
`git diff --cached --check`, focused daemon tests, and:

```text
CARGO_TARGET_DIR=/tmp/ab-aura-phase-target \
  cargo check --locked --offline -p ab-bridge --all-targets
```

## Current-unit acceptance

P0 is accepted only if:

- the worktree creation base was the then-current dual-remote `a5744e82`, and
  the worktree was fast-forwarded to landing base `e71533e4` after both remotes
  advanced together through the non-overlapping S619 and S620 commits;
- forum thread #322 owns the documentation lane;
- only this ADR changes;
- a source oracle reconfirms the route, query field, unbounded reads,
  post-read uniform check, detailed HTTP error mapping, repeated state URL, and
  lack of an Aura capability in `AppState`;
- the existing nine-test `avatar_renderer` integration target passes;
- after staging the new ADR, `git diff --cached --check` passes;
- two independent reviewers confirm the threat model, docs-only stop, and TDD
  split.

## Verification evidence

Fresh P0 verification completed on 2026-08-02:

- GitLab and GitHub `master` both resolved to
  `e71533e4b0f50c770756b83e07c213a9b9efc09b`. Ancestry checks proved the
  creation base `a5744e82` and intermediate S619 base `62a082ad` are ancestors;
  their S619/S620 delta does not touch any audited Avatar source or test.
- Forum thread #322 had the only Aura path-authority claim. No competing
  worktree changed this ADR, `daemon_http.rs`, or `avatar_renderer.rs`.
- A fail-fast source oracle reconfirmed the optional `PathBuf` query field,
  three `fs::read` calls, post-read uniform-size check, detailed error mapping,
  one-second poll, and Store/embed-only `AppState`; it exited zero.
- The exact isolated baseline command above completed with 9 passed, 0 failed,
  and 0 ignored. It emitted only pre-existing repository warnings.
- The worktree contained one staged file, this ADR, and
  `git diff --cached --check` exited zero.
- Independent security and TDD reviews initially required contract changes.
  After P1 became unconditional, P2 became a retained-handle one-shot loader,
  and P3 became memory-only HTTP selection, both reviewers returned no blocker
  and accepted the docs-only P0 boundary.

P0 did not start or call a daemon, open an Aura fixture, probe a special file,
change environment configuration, deploy a binary, restart a process, or
reconnect a client.

## Stop conditions

Stop and return to design if an implementation:

- needs to infer authority from request or renderer identity data;
- lets any P1 request bypass the unconditional disabled guard;
- uses capability presence only as a Boolean before calling the legacy
  ambient-path validator;
- needs to keep enabled startup or listener binding alive when capability
  construction or preload fails;
- retains a path or file capability in request-handling state, reopens Aura
  files per request, or cannot prevent symlink/root-path substitution during
  preload;
- needs an untrusted, group-writable, world-writable, network, FUSE, unknown,
  hard-linked, or cross-device Aura source;
- needs higher resource ceilings without measured fixtures;
- changes no-Aura renderer output, Aura schema/hash semantics, or the explicit
  local validator merely to make the route gate compile;
- introduces Aura path input into HTTP, CLI, or MCP instead of the one opaque
  HTTP selector;
- requires Hub, review, queue, voice, notification, desktop, Store schema,
  memory, or runtime-admission authority;
- collides with another owner of `daemon_http.rs` or `avatar_renderer.rs`;
- finds either remote no longer contains the implementation base.

## Non-goals

This P0 unit does not authorize:

- Rust implementation or a static Python gate;
- opening any live Aura path or probing `/dev/zero`, FIFO, devices, or host
  secrets;
- daemon deployment, restart, environment changes, endpoint calls, or client
  reconnect;
- a claim that current external ACLs authenticate every requester;
- a claim that canonical path-prefix checking alone is race-free;
- removal of the explicit local validator or changes to its public report;
- review approval, action queue, audio, notification, desktop-control, Store,
  Hub, MCP registration, CLI composition-root, or `main.rs` governance work.

## Consequences and trade-offs

P1 intentionally prefers a temporary loss of optional HTTP file-backed Aura
over retaining ambient filesystem authority. Separating P1 from P2 means the
urgent safety stop can be reviewed without simultaneously accepting a new
cross-platform directory-capability implementation.

P2 before P3 makes the filesystem contract testable without network or daemon
configuration effects. It also leaves a short interval in source history where
the bounded loader exists but is unreachable; that is preferable to exposing
it before its negative matrix is complete.

Rejecting absolute paths and all symlinks breaks the existing `/tmp/...`
example and absolute-path integration fixture for the daemon preload path. The
explicit local validator can retain that compatibility. Operator-approved
daemon fixtures must move under a dedicated root and use relative references;
HTTP callers use only `default`.

Descriptor-relative, no-symlink opening is more complex than canonical string
containment, especially across Linux and macOS. The alternative would make a
race-free claim the implementation cannot support. Unsupported platforms
therefore stay disabled until an equivalent primitive and tests exist.

Preloading an immutable report removes request-time file I/O and the current
one-second amplification, but Aura file changes are not observed until daemon
restart. A future live-reload mechanism requires a new authority and resource
ADR; it cannot be smuggled into P3 as a watcher, timer, signal handler, or
request-triggered refresh.

The selected byte ceilings may reject a future legitimate Aura artifact. They
are deliberately small because the current renderer uses a 1,024-byte uniform
and hashes rather than rendering digest bytes. Raising a ceiling is a measured
compatibility decision, not a query or environment option.

The root writer is deliberately trusted. P2/P3 protect the daemon from ambient
path delegation, static and raced name substitution, hard links, mount
crossing, and unbounded bytes; they do not authenticate content authored by a
malicious operator. Calling the manifest hashes signatures or provenance would
be a contract violation.

## Revisit triggers and rollback

Revisit this decision if Aura artifacts are supplied directly as bounded,
authenticated values rather than files, if route-level authenticated
capabilities are introduced, or if operators require live reload and can
preregister a cancellable, rate-bounded mechanism that never delegates an
ambient path to a requester.

This documentation-only unit is independently revertible but may remain as a
security audit artifact if implementation is abandoned. P1, P2, and P3 must be
separate commits. Rolling back P2 or P3 must leave P1's default-disabled guard
in place; restoring unrestricted daemon reads is not an acceptable rollback.
