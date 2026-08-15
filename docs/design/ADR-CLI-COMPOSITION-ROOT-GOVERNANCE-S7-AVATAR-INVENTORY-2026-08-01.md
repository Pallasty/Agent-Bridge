# ADR: CLI composition-root governance S7 Avatar inventory and safety stop

## Status

Accepted on 2026-08-01.

- Decision scope: `crates/bridge/src/main.rs` Avatar schema, dispatch, executors,
  and their transitive authority boundary
- Audited base: `ac0665740dd06e29a9b0af02100f1d707cb0e481`
- Avatar source comparison base: `56bbd314152ac8a2dc5762853404eb313bb27e64`
- Landing predecessor: `8521abba3dd315d9afe0fb794e49588a22f25937`
- Coordination: Agent-Bridge forum thread #297, intent post #5787
- Predecessor: S5-V BioCortex effectful-executor audit
- Implementation posture: inventory and freeze only; no Rust production or test
  movement, deployment, runtime enablement, or client reconnect

The commits between the comparison base, audited base, and landing predecessor
change only isolated voice-scene documentation, Python, tests, and the
unregistered story adapter. They do not change `main.rs`, any `avatar_*.rs`
source, or the Avatar integration tests, so the source locations and counts
below apply through the landing predecessor.

## Context

S0 classified Avatar as a high-cohesion but broad-dependency command family
with process, UI, and platform effects. S5-V therefore closed the BioCortex
phase and selected a separately preregistered Avatar inventory instead of
assuming that Avatar could follow the presentation-only extraction pattern.

That caution is necessary. At the audited base, two root comments still call
Avatar read-only:

- `main.rs:236` says "Read-only avatar/presence surfaces";
- `main.rs:4748` says "short-lived read-only terminal surface over presence
  rows".

The current command family has outgrown both descriptions. Its 43 variants can
write presence, JSONL ledgers, queue records, and cooldown state; create
snapshot-parent directories and delete existing snapshot files while attempting
a currently disabled append; install and remove launchd jobs; start browsers,
Wayland surfaces, notification and audio processes; and execute a binary
obtained from a plist. Those comments are recorded as stale contract evidence.
S7 does not change them because even a comment correction in `main.rs` would
enter the active composition-root merge surface during an audit-only unit.

## Physical inventory

`main.rs` contains 19,274 lines at the audited base.

| Region | Audited location | Physical span | Exact symbols |
| --- | --- | ---: | ---: |
| `AvatarOp` enum | `844-2063` | 1,220 lines | 43 variants |
| Avatar early dispatch | `4748-5687` | 940 lines | 43 unique variant arms |
| Avatar executor/helper area | `8400-11485` | 3,086 lines | 43 Avatar/Xiao Shu executor definitions and 15 `avatar_*` helpers |

The three physical spans total 5,246 lines, about 27.2% of `main.rs`. This is
not an owned-line count: the executor/helper span contains at least one adjacent
non-Avatar helper (`memory_record_from_instinct_plan`). Size is evidence of
review surface, not by itself a reason to move code.

The eight `avatar_*.rs` library modules total 14,057 lines:

| Module | Lines |
| --- | ---: |
| `avatar_alert.rs` | 338 |
| `avatar_cortex.rs` | 10,662 |
| `avatar_floater.rs` | 389 |
| `avatar_health.rs` | 439 |
| `avatar_native.rs` | 1,230 |
| `avatar_renderer.rs` | 511 |
| `avatar_seed.rs` | 288 |
| `avatar_surface.rs` | 200 |

All eight modules are public from `lib.rs`. Several effectful operations are
therefore library APIs rather than private CLI mechanics. Creating a private
`cli::avatar` module would not by itself establish an authority boundary.

## Command-level ownership map

Each row records `schema / dispatch / executor` line spans at the audited base.
The map is deliberately complete so a later extraction cannot silently omit a
variant or confuse an adjacent helper with Avatar ownership.

| Command | Schema | Dispatch | Executor |
| --- | ---: | ---: | ---: |
| `Surface` | `846-871` | `4751-4772` | `8400-8457` |
| `BackendProbe` | `875-879` | `4773` | `8543-8590` |
| `LinuxFloater` | `881-921` | `4774-4805` | `8593-8719` |
| `LinuxNativeTransparent` | `923-1000` | `4806-4861` | `8741-8852` |
| `SyncPresence` | `1002-1075` | `4862-4915` | `8864-8981` |
| `InstallHeartbeat` | `1077-1135` | `4916-4959` | `9183-9294` |
| `RemoveHeartbeat` | `1137-1144` | `4960-4962` | `9296-9311` |
| `HeartbeatStatus` | `1146-1153` | `4963-4965` | `9313-9335` |
| `HeartbeatHealth` | `1155-1168` | `4966-4974` | `11353-11429` |
| `HeartbeatAlert` | `1170-1204` | `4975-5002` | `11432-11485` |
| `InstallHeartbeatAlert` | `1206-1243` | `5003-5032` | `9338-9435` |
| `RemoveHeartbeatAlert` | `1245-1252` | `5033-5035` | `9437-9455` |
| `HeartbeatAlertStatus` | `1254-1261` | `5036-5038` | `9457-9482` |
| `SeedEvents` | `1263-1288` | `5039-5060` | `9505-9578` |
| `CortexReplay` | `1290-1321` | `5061-5086` | `9581-9649` |
| `InstallCortexRunner` | `1323-1363` | `5087-5118` | `9652-9752` |
| `RemoveCortexRunner` | `1365-1372` | `5119-5121` | `9754-9772` |
| `CortexStatus` | `1374-1390` | `5122-5137` | `9774-9820` |
| `CortexPreview` | `1392-1408` | `5138-5153` | `9822-9867` |
| `CortexLanguage` | `1410-1426` | `5154-5169` | `9869-9919` |
| `CortexMotion` | `1428-1444` | `5170-5185` | `9921-9965` |
| `CortexRenderer` | `1446-1462` | `5186-5201` | `9967-10018` |
| `CortexRendererRegistry` | `1464-1480` | `5202-5217` | `10020-10064` |
| `CortexBindingPlan` | `1482-1498` | `5218-5233` | `10066-10105` |
| `CortexBindingFixture` | `1500-1516` | `5234-5249` | `10107-10149` |
| `CortexVisualAdapter` | `1518-1534` | `5250-5265` | `10151-10193` |
| `CortexRendererView` | `1536-1552` | `5266-5281` | `10195-10236` |
| `CortexReviewGate` | `1554-1570` | `5282-5297` | `10238-10297` |
| `CortexReviewPacket` | `1572-1588` | `5298-5313` | `10299-10355` |
| `CortexReviewReport` | `1590-1606` | `5314-5329` | `10357-10430` |
| `CortexReviewDecisions` | `1608-1636` | `5330-5353` | `10433-10506` |
| `CortexReviewDecision` | `1638-1675` | `5354-5383` | `10509-10574` |
| `CortexReviewRecord` | `1677-1714` | `5384-5413` | `10576-10635` |
| `CortexVoicePolicy` | `1716-1732` | `5414-5429` | `10637-10691` |
| `CortexVoiceRequest` | `1734-1756` | `5430-5449` | `10693-10747` |
| `CortexVoiceConfirm` | `1758-1783` | `5450-5471` | `10749-10798` |
| `CortexVoiceAction` | `1785-1825` | `5472-5503` | `10801-10865` |
| `CortexVoiceActionPreview` | `1827-1864` | `5504-5533` | `10868-10929` |
| `XiaoShuActionRequest` | `1866-1918` | `5534-5573` | `10932-11046` |
| `XiaoShuActionRequests` | `1920-1942` | `5574-5593` | `11048-11112` |
| `XiaoShuActionRequestAction` | `1944-1987` | `5594-5627` | `11115-11190` |
| `CortexVoiceGate` | `1989-2020` | `5628-5653` | `11192-11256` |
| `CortexVoiceEmit` | `2022-2062` | `5654-5685` | `11259-11331` |

## Effect and authority matrix

The 43 commands divide into five authority families. "Read" below still means
an effect when it opens SQLite, reads caller-selected paths, probes launchd, or
starts another process.

| Family | Commands | Direct or transitive authority | Governance disposition |
| --- | ---: | --- | --- |
| Surface/body backend | 4 | SQLite open/query; environment inspection; browser and `setsid` spawn; repeated `swaymsg`; Wayland/layer-shell event loop; sidecar and HTTP polling | Keep acquisition, spawn, window, device, network, and retry sequencing at the composition/effect root; pure projection and completed-result rendering are conditional seams |
| Presence/heartbeat/runner lifecycle | 13 | Presence reads and writes; pet sidecar and caller-selected seed input/output files; launchd plist/log reads and writes; plist-selected binary execution; `launchctl`; JSONL event/state writes; notification/TTS; snapshot-parent creation, existing-destination deletion, and disabled append attempt; scheduled replay | Effect acquisition and invocation permanently stay at the root; completed-result rendering remains conditional |
| Cortex projection/review evidence | 13 | Attempted snapshot reads through the disabled shim and snapshot-path existence probes; event JSONL and caller-selected path reads; launchd process probe; completed JSON/text output | Lower `*_from_status` projections are mostly pure, but root executors transitively own file/process input; only completed-result renderers are conditional seams |
| Review ledger | 3 | Disabled-shim snapshot attempts, event JSONL and caller-selected snapshot-path reads; launchd process probe; ledger reads; confirmed append-only review decision/record writes | Preserve status acquisition, validation, confirmation, append order, and distinct approval/audit semantics at the effect root |
| Voice/action queue | 10 | Disabled-shim snapshot attempts, event JSONL and caller-selected snapshot-path reads; launchd process probe; queue reads/appends; cooldown and event writes; environment evaluation; Python audio adapter or macOS `say`; transition writes | Preserve status acquisition, confirm/emit/reason/cooldown gates, file order, subprocess, audio, and queue custody at the effect root |

The presence/heartbeat/runner family comprises `SyncPresence`, the three
heartbeat lifecycle commands, `HeartbeatHealth`, `HeartbeatAlert`, the three
heartbeat-alert lifecycle commands, `SeedEvents`, `CortexReplay`, and the two
cortex-runner lifecycle commands. The read/projection family runs from
`CortexStatus` through `CortexReviewReport`. The ledger and voice/action groups
are the final 3 and 10 commands in the command-level ownership map above.

### Representative ordering contracts

- `Surface` opens `SqliteStore` and obtains presence rows before constructing
  and rendering the report. Store construction can initialize a database and
  is not a pure read adapter.
- `LinuxFloater` selects a browser before its dry-run return. Live execution
  starts a process and may perform up to 20 window-management retries.
- launchd install commands compute a plan before dry-run, but live paths create
  directories, write a plist, optionally stop an old job, bootstrap, and
  kickstart. `--no-load` still writes the plist.
- `HeartbeatAlert --preview` suppresses notification/TTS only. It still appends
  an event and overwrites alert state in `avatar_alert.rs:264-275`.
- Cortex projection wrappers generally call `avatar_cortex_status` first. That
  status function attempts a snapshot read through the disabled shim, probes
  snapshot-path existence, reads event JSONL, and probes launchd, even when the
  wrapper's later `Value -> JSON/text` tail is pure.
- review-decision and review-record operations have different durable
  semantics. Their validation, confirmation, and append sequence must not be
  collapsed into a generic presentation helper.
- direct `CortexVoiceEmit` writes cooldown/state only after successful
  emission, but appends its event JSONL whether its lower gate blocks, audio
  fails, or emission succeeds. `CortexVoiceAction` has outer
  confirm/ready/emit/reason/line gates that can return without invoking the
  adapter or writing a voice event; once it invokes the adapter, the event is
  appended regardless of adapter success. After any voice-side effects, a Xiao
  Shu queue action appends a distinct transition record to the same
  request-queue JSONL. Physical extraction must preserve these partial-effect
  boundaries.

## Critical safety findings

These findings block Avatar production movement. They are source-level
findings at the audited base, not claims about a deployed binary, reachable
network, loaded launchd job, audible playback, or current client adoption.

### Cortex replay deletes the previous output before a deterministic disabled append

`avatar_cortex_replay` reads seed events, resolves the output, creates its
parent, and deletes any prior output at `avatar_cortex.rs:5625-5630`. It then
constructs a row and calls `snapshot::append_row` at `5660-5668`.

The runtime no longer links the legacy Seed substrate:

- `seed_substrate.rs:1-5` defines the compatibility surface as disabled;
- `SeedBackend::build_row` always returns `Some` at `114-127`;
- `snapshot::read_all` and `append_row` always return
  `SnapshotError::Disabled` at `214-219`;
- `pub use disabled::*` is unconditional at line 233;
- Cargo feature `seed-substrate = []` is only a reserved marker at
  `crates/bridge/Cargo.toml:42-45`.

With otherwise valid seed input, successful path and embedding setup, and
execution reaching `append_row`, the current command removes an existing
snapshot and then fails deterministically. Enabling the marker feature does not
restore the implementation. The ignored test and comment at
`avatar_cortex.rs:7876-7885` incorrectly assume that a feature-on run exercises
a working append implementation. The CLI can also install this command as a
periodic launchd runner at `main.rs:9652-9735`.

The required repair gate, in a separately preregistered unit, is:

1. determine replay capability before creating, deleting, or writing the
   destination or its parent;
2. preserve a sentinel destination byte-for-byte on every default-build and
   marker-feature error, and leave both destination and parent absent when they
   were initially absent;
3. build a replacement at a sibling temporary path and atomically replace the
   destination only after the complete write/readback succeeds;
4. refuse to install or schedule a replay implementation known to be disabled,
   without writing a plist or invoking `launchctl`;
5. add fault injection around future temporary write, readback, and rename
   stages before a real backend is restored;
6. replace the stale ignored/feature assumption with negative and preservation
   tests.

S7 records this requirement but does not implement or schedule it.

### Heartbeat health can execute a plist-selected binary

An explicit heartbeat label is trimmed but otherwise unsanitized at
`avatar_health.rs:55-66`, then used to form a plist path at `68-73`. Health
parses the first `ProgramArguments` value from that plist and runs the selected
binary with `avatar --help` at `191-239`.

The health operation first runs `id -u` and `launchctl print`. On a target
macOS environment where those probes return, it then parses and may execute the
plist-selected binary. A normal Linux host without `launchctl` fails before
that spawn. The HTTP daemon passes the query `label` into this path at
`daemon_http.rs:1091-1103`. Its router lists the route without a route-local
authentication layer at `117-235`, and the CLI's default listen value is
`0.0.0.0:7878` at `main.rs:8243`. External network controls such as Tailscale
ACL may narrow real reachability, but they are outside this source audit.

This is a source-backed `request label -> plist path -> parsed executable ->
process spawn` authority chain, not proof of exploitability. Before health code
or its renderer moves, a separate security review must define trusted label and
binary provenance, path confinement, local opt-in, and daemon behavior that
does not execute a plist-selected binary by default.

### Other cross-surface authority blockers

- daemon renderer queries accept an `aura_io: PathBuf` and pass it to a
  sidecar/manifest validator that reads the manifest plus referenced uniform
  and digest files (`daemon_http.rs:612-633,1251-1289` and
  `avatar_renderer.rs:140-258`). A path allowlist or equivalent authority
  contract is not visible in this call chain.
- the daemon exposes a confirmed review-decision POST whose lower operation can
  append a sidecar ledger only when `confirm=true`, the track and decision are
  valid, and the referenced source item exists. This is not an entirely
  read-only Stage 1 surface. A review record may report
  `writes_approval=true` without promoting a binding; a review decision remains
  audit-only with `writes_approval=false`.
- the Niche MCP `xiao_shu_action_request` description says it never writes
  request records, while its `enqueue=true` schema and implementation append a
  pending-action record (`mcp_tools.rs:20751-20759,20810-20814,20945-20955`).
  The tool constructor discards `Hub`; profile registration is not per-call
  write authorization. This MCP path can append a pending request, but cannot
  consume the queue or emit audio. The daemon exposes only Xiao Shu
  preview/read handlers, not enqueue or voice-emit handlers.
- an audio adapter receipt with status `played_unverified` is counted as
  emitted at `avatar_cortex.rs:594-598`. That status must not be promoted to a
  claim of human audibility, sink-monitor delivery, or acoustic-loop closure.

These cross-surface findings expand the safety backlog, not S7 implementation
scope. They require independent threat models and authorization before repair.

### Authority routing boundary

The Avatar CLI dispatch returns before `build_hub` at `main.rs:7809`, so its
direct Store, file, process, notifier, and audio operations do not pass through
`Hub.security`, Hub notifier, or Hub Store custody. The daemon's `AppState`
contains only Store and an embedding backend; this router relies on its network
access boundary rather than a route-local Hub/security layer.

Both `AvatarCortexRendererSnapshotTool::new(_hub)` and
`XiaoShuActionRequestTool::new(_hub)` discard the supplied Hub at
`mcp_tools.rs:9849-9853,20723-20727`. Niche/profile registration controls tool
exposure, but is not per-call path, process, or write authorization. Any future
governance must keep this bypass visible rather than implying that physical
movement into a module acquires Hub policy automatically.

Likewise, payload fields such as `read_only=true` describe the intended payload
contract, not the complete executor authority: live floater paths spawn browser
and window-management processes, while live native paths create a Wayland layer
surface. Daemon handlers also invoke synchronous file/process work inside async
request paths; resource and blocking behavior needs separate review without
being mislabeled as a demonstrated vulnerability.

## Existing pure seams

The inventory found useful seams, but none override the safety stop:

- `BackendProbe` detects compositor environment, applies a pure recommendation,
  and renders JSON/text without files, Store, or subprocesses. Its completed
  presentation tail is the narrowest future candidate by dependency and
  authority width. Moving the whole executor would also move environment
  custody and is not authorized here.
- pure helper candidates include label normalization/builders, XML escaping,
  plist text construction, argument assembly, payload record projection, and
  completed-value display.
- Cortex already exposes multiple `pub(crate) *_from_status` projection seams.
  The corresponding CLI executors still acquire status through the disabled
  snapshot attempt/path probe, event JSONL reads, and launchd probes before
  their pure rendering tails.
- the `CortexMotion` executor's `main.rs:9936-9964` tail is a bounded
  `Value -> stdout` candidate, but the renderer itself has low historical
  churn and lacks CLI parity evidence. It is not worth crossing the current
  safety and ownership gaps solely to reduce line count.

The common `avatar_health_display` helper has hundreds of root call sites.
Moving or copying it for one renderer would broaden dependencies rather than
establish a coherent command boundary.

## Test evidence and gaps

Within the eight `avatar_*.rs` modules and the three named Avatar integration
files, the bounded scan finds 103 test attributes at the audited base:

- 64 source-module tests;
- 39 integration tests in `avatar_floater.rs`, `avatar_native.rs`, and
  `avatar_renderer.rs` under `crates/bridge/tests`.

This count deliberately excludes Avatar/Aura/Xiao Shu tests in daemon, MCP,
`pet_presence`, and other cross-surface files; it is not a repository-global
Avatar test total.

No integration test contains `Cmd::Avatar`, `AvatarOp::`, `run_avatar_`, or
`run_xiao_shu`. There is no Avatar clap/help snapshot, binary behavior fixture,
schema-dispatch-executor ownership assertion, or text/JSON parity fixture.
Existing lower tests therefore cannot prove that a `main.rs` move preserves:

- the 43-to-43-to-43 schema/dispatch/executor map;
- help text, defaults, invalid-argument errors, exit status, stdout, or stderr;
- cwd/project/default-path and environment evaluation order;
- Store/file/process/audio/launchd authority custody.

`avatar_cortex_replay_writes_isolated_snapshot` is ignored only when the marker
feature is off, but the feature-on implementation is still the disabled shim.
It is evidence of a stale test contract, not a working replay gate.

Before any future renderer move, add and observe a RED ownership test that
requires schema, dispatch, root invocation, parameters/defaults, authority
gates, and effect ordering to remain visible in their current explicit owners,
while forbidding clap, Store, file, process, launchd, audio, queue, and ledger
custody in the private presentation module. Then add deterministic
text/JSON/help/error parity artifacts before implementation.

## Verification evidence

Fresh verification completed on 2026-08-01 against the Rust/Avatar tree shared
by `896e63de` and landing predecessor `8521abba`; the intervening commits add
only voice-scene documentation, Python gates, and Python tests:

- a static inventory gate reproduced `19,274` main lines, `43` schema variants,
  `43` unique dispatch arms, `43` root executors, `15` helpers, `14,057`
  Avatar-module lines, the bounded `103` test attributes, and zero CLI ownership
  test files;
- `cargo test -q -p ab-bridge --lib avatar_ --locked --offline` completed with
  81 passed and the one default-ignored replay test;
- the `avatar_floater`, `avatar_native`, and `avatar_renderer` integration
  targets completed 7/7, 23/23, and 9/9;
- a feature-marker negative control ran the exact ignored replay test with
  `--features seed-substrate`; it failed as expected at `avatar_cortex.rs:7907`
  because `snapshot::append_row` still reports build-time-disabled support;
- the composite `ab-bridge --all-targets` gate exited zero, with 1,689 library
  tests passed and four ignored. Three story assertions whose expected receipts
  contain the canonical checkout path were skipped in the isolated worktree,
  then the just-built test binaries ran those exact assertions from canonical
  `crates/bridge`; all three passed 1/1;
- `git diff --check` passed.

The feature-marker failure is a successful negative control, not a passing
product test or a claim that replay is usable. S7 did not execute browser,
Wayland, HTTP-daemon, notification, audio, launchd installation, deployment, or
client-reconnect probes. Existing non-S7 compiler warnings were observed but no
new warning was introduced by this documentation-only unit.

## Churn and collision evidence

`avatar_cortex.rs` has 59 commits in its history. Since 2026-05-20, `main.rs`
and `avatar_cortex.rs` were touched together by 35 commits. This demonstrates
broad file-level collision exposure. It does not demonstrate that the proposed
`CortexMotion` renderer is a current hotspot: its schema, executor, domain
mapping, and common formatter are each long-lived and low-churn.

At the 2026-08-01 audit capture on landing predecessor `8521abba`, one S7
worktree/ref existed, `git ls-files -u` was empty, and no competing S7 forum
owner was found. Adjacent voice-scene work owned different files. This is a
point-in-time coordination finding, not a durable absence claim. Consequently,
neither total line count nor historical family churn justifies a sequence of
mechanical renderer extractions.

## Decision

1. Complete S7 as an audit-only inventory and safety-stop unit. The ADR is the
   narrow, reversible artifact; S7 moves no Rust production or test code.
2. Freeze the complete `AvatarOp` schema, 43-arm dispatch, 43 root executors,
   option assembly, environment/cwd/default-path decisions, Store custody,
   file and process operations, confirmation gates, and effect ordering in
   their current owners.
3. Do not create a monolithic `cli::avatar`, move the schema wholesale, or use
   line reduction as the success criterion.
4. Make an independently preregistered Avatar authority-safety phase the next
   prerequisite. Its first repair candidate is cortex replay capability and
   snapshot preservation because the failure is deterministic and locally
   testable. The heartbeat-health process chain and cross-surface HTTP/MCP path
   and write authorities require separate security review rather than being
   hidden in the replay patch.
5. Do not authorize a renderer extraction automatically after the repair.
   After safety review and RED CLI characterization, the conditional first
   presentation candidate is the completed `BackendProbe` result renderer;
   `CortexMotion` follows only if new conflict, typed-view, or consumer evidence
   justifies it.
6. Do not deploy, install a job, enable a runtime, restart a daemon, or request
   client reconnect as part of S7.

## Options considered

### Move the complete Avatar family to `cli::avatar`

Rejected. It would make a presentation-looking module own SQLite, launchd,
file replacement, review/queue ledgers, browser/Wayland control, subprocess,
notification, and audio authority. The physical boundary would conceal rather
than clarify effects.

### Add a RED ownership test and move the CortexMotion renderer now

Deferred. This is mechanically narrow, but no current CLI parity fixture exists,
the candidate tail has low churn, and the audit found higher-priority safety
defects. A production movement in the same commit would also weaken the clean
separation between inventory evidence and later implementation authorization.

### Move BackendProbe as a complete executor

Deferred. It is the narrowest whole executor and has no file, Store, or process
effect, but it reads current environment and lacks CLI behavior fixtures. Its
completed presentation tail remains a conditional candidate after the safety
gate; environment detection and backend recommendation should remain visibly
owned until a separate boundary decision says otherwise.

### Fix all discovered authority problems in S7

Rejected as a scope expansion. Replay preservation, HTTP process provenance,
path confinement, review authorization, and MCP enqueue policy have different
owners and threat models. Combining them would prevent focused verification
and a safe rollback.

## Reopen and stop conditions

Avatar presentation governance may reopen only after the safety prerequisites
are resolved and at least one of these evidence-backed triggers exists:

- the same candidate participates in two independent merge conflicts or at
  least three non-format behavior changes in 90 days;
- a typed completed-result view replaces untyped JSON-pointer rendering;
- a second binary-private consumer needs the same renderer;
- deterministic CLI help/text/JSON/error parity and a RED ownership test exist;
- effectful dependencies are first placed behind explicit capability
  interfaces whose invocation remains visible at the composition root.

Stop immediately if a proposed extraction moves or obscures:

- `SqliteStore::open`, presence reads/writes, DB selection, or Store migration;
- input path, default path, cwd/project, environment, or exact read/write
  error and precedence behavior;
- file replacement, JSONL/state/queue/cooldown/review writes, or partial-write
  order;
- subprocess, browser, window, Wayland, HTTP polling, launchd, notification, or
  audio custody;
- dry-run, no-load, confirm, emit, reason, cooldown, feature, runtime, operator,
  or capability gates;
- public CLI schema/help, MCP registration/policy, daemon exposure, default
  runtime behavior, deployment, or client adoption.

## Consequences

Avatar remains physically mixed by design. The composition root retains a
large family because its effects are broad and its current security boundary
is more important than reducing `main.rs`. The inventory provides an exact
ownership map, exposes stale read-only claims, and turns several latent
authorities into explicit prerequisites rather than hiding them behind a new
module.

No CLI spelling, help, output, error, Store/file/process/audio/window/launchd
behavior, MCP/HTTP policy, deployment, runtime state, or client session changes
as a consequence of S7.
