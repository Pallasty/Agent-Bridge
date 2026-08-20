# Protocol-first application control

`app_control` is the first application-capability router in Agent-Bridge. It
turns a high-level media intent into one bounded, auditable transaction:

1. discover MPRIS players through `playerctl`;
2. select an exact or unique-substring player;
3. read playback state and track identity;
4. dispatch one allowlisted MPRIS action;
5. read MPRIS again until the requested effect is verified or the deadline
   expires.

The routing order is explicit:

1. application protocol/API;
2. AT-SPI UI semantics;
3. screen vision;
4. coordinate input.

The current implementation selects only layer 1. Lower layers are returned as
`not_executed` candidates and are never used silently. This matters because an
API failure must not unexpectedly become a desktop click.

## Supported media contract

- Domain: `media`
- Read-only operation: `discover`
- Read-only observations: `state_get`, `volume_get`, `position_get`, `playlist_list`, `playlist_current`
- Mutating operations: `next`, `previous`, `play`, `pause`, `play_pause`,
  `stop`, `playlist_activate`
- Backend: MPRIS through the argument-safe `playerctl` client
- Verification:
  - `next`/`previous`: MPRIS track identity changed;
  - `play`/`pause`/`stop`: requested playback status observed;
  - `play_pause`: playback status changed;
  - `volume_get`: normalized player volume observed;
  - `volume_up`/`volume_down`: volume changed in the requested direction;
  - `volume_set`: normalized volume reached the requested value within 0.01.
  - `state_get`: playback state, track identity, metadata, and volume observed.
  - `position_get`: current position and track duration observed in seconds.
  - `playlist_list`: MPRIS playlist object paths and names observed.
  - `playlist_current`: MPRIS `ActivePlaylist` object path/name and independent current-track summary observed.
    If no playlist is active, it returns `active=false` and an empty track summary as a verified observation; if the MPRIS property read fails, it returns structured `observation_failed` and never infers a playlist from player metadata.
  - `playlist_activate`: exact object path activated and a track observed afterward;
    duplicate names are never resolved implicitly.

The media adapter also exposes `volume` capability discovery with the MPRIS
range `0.0..=1.0` and a default step of `0.05`. This is player-local volume;
system output volume remains a separate `system_control` concern.

The MCP schema exposes no arbitrary bus name, object path, DBus method, shell
command, or coordinates. `dry_run=true` performs discovery and reads the
selected player's state without dispatching.

Before discovery, the adapter validates inherited `unix:path=` session-bus
addresses against a socket owned by the current UID. A stale path is replaced
with the current trusted runtime bus; non-path transports are preserved rather
than guessed. This keeps long-lived MCP sessions from losing protocol control
after the desktop session bus is replaced.

## Evidence boundary

A successful command exit is dispatch evidence only. The transaction reports
`verdict=verified` only after the post-action observation satisfies the effect
predicate. A timeout or unchanged state returns `unmet` with a recovery hint;
it is not promoted to success.

## Durable `next` operation slice

`operation_id` opts the relative `next` action into a narrow, local
at-most-once journal. This is the first embodied task-continuity slice; it is
not a general workflow runtime and it does not change calls that omit the
field.

The backend binds the identifier to the canonical mutation request
(`action`, exact caller-supplied player selector, and TTL), an exact resolved player, a
non-empty baseline MPRIS track ID, and a short TTL. The verification timeout is
an execution-policy budget rather than mutation identity, so it is deliberately
excluded from the request digest. Before calling `playerctl next`, it atomically
persists `phase=dispatch_started` and consumes the operation's one-dispatch
budget. A changed track is not immediately terminal: the backend requires
three exact observations of the same non-baseline track ID spanning at least
500 ms before it writes a verified terminal receipt. This bounded settlement
evidence shows that the selected MPRIS identity stopped changing during that
window; it does not prove long-lived stability or exclude another MPRIS
controller as a cause. A second process with the same operation and request
therefore either replays a completed receipt or performs a read-only
observation. It never dispatches `next` again.

If the first process disappears after dispatch but before its terminal receipt:

- three matching non-baseline observations spanning at least 500 ms prove the
  bounded postcondition, so recovery may return `verified` while keeping
  `causal_attribution=unknown_after_restart`;
- an unchanged, missing, unreadable, or still-changing identity remains
  `phase=dispatch_started`, returns a structured pending/retry disposition, and
  requires the exact same operation ID for another read-only observation;
- a changed request digest, expired operation, unavailable journal, or busy
  per-operation lock fails closed before mutation.

An unexpired `dispatch_started` record is therefore a recoverable pending
receipt, not a failed operation and never a reason to spend a second dispatch.
Legacy terminal receipts that predate settlement evidence fail closed for the
settled-track contract; they are neither upgraded from current state nor
silently rewritten. A fresh in-process settled result may report temporal
`verified_fresh_dispatch_track_change` attribution, but that label still does
not prove exclusive causation in the presence of external MPRIS actors.

The journal lives at an absolute path under the user's state directory with a private directory,
hashed filenames, per-operation `flock`, 0600 records, and atomic
write/fsync/rename. Caller-selected `cwd` and `script_path` backends are
rejected for durable operations at the MCP boundary so an operation cannot be
silently rebound to another implementation.

Before an embodied episode opens mobile UI, the installed backend also offers
a private `--operation-preflight` mode. This is a bounded, journal-only
admission snapshot, not a public `app_control` action. It does not create the
journal directory or lock, write or normalize a record, inspect MPRIS, recover
`dispatch_started`, reserve an ID, or authorize dispatch. Existing lock and
record files are opened without following symlinks and checked for owner-only
regular-file shape before the exact request, phase, dispatch count, TTL, and
terminal receipt are classified.

`fresh`, retryable count-zero, verified terminal replay, and structurally valid
recovery states are only reported as candidates. Expired, conflicting,
terminal-failure, busy, corrupt, or unavailable states fail before ADB is
invoked. For existing candidates, the composition also requires enough TTL for
the two bounded ADB windows inside projection start, the bounded connection
wait, and the durable action's bounded pre-dispatch observation window, with a
scheduling margin. The preflight lock is released before it returns, so its
receipt explicitly says that it neither
reserves the ID nor keeps state unchanged. The later mutating call still takes
the exclusive per-ID lock and repeats the complete validation; this is the only
authority boundary and remains safe if state changes after preflight.

The mobile projection remains a reconstructible presentation tail. Updating
the in-memory frame or flushing it to the TCP connection proves neither that
the Android Activity accepted it nor that the UI drew it. The projection
protocol therefore reports three distinct stages: queued by the host, served
to an authenticated client, and an exact `(session, revision, frame_sha256)`
draw report sent by the companion after the Activity's main-thread draw pass.
`mobile_projection_wait` v1 verifies only the final exact report; a later
revision never proves that an earlier revision was drawn. This is app-originated
device evidence, not proof that a human saw the display and not independent
pixel verification.

## `advance_track_then_project` episode

`advance_track_then_project` is a deliberately narrow composition of the
durable `next` operation and the consent-gated mobile presentation tail. It is
available only in the explicit `codex-essential-mobile-projection` profile. It
is not exposed by either `codex-essential` or `codex-mobile-projection` alone,
because neither component profile should silently acquire the other's
authority.

The tool accepts a caller-supplied `operation_id`; it never creates or replaces
that identity. After validating every argument, it follows one fixed sequence:

1. run the private journal-only preflight and reject deterministic blockers
   without opening mobile UI;
2. create a short-lived, one-shot projection session;
3. obtain either explicit holder connection consent, or a clearly labelled
   test-only authenticated auto-connection;
4. call durable `app_control(next)` with the same operation ID and revalidate
   under its exclusive lock;
5. sync media through the exact resolved player in the durable receipt;
6. require the projected track ID to equal the verified post-action track ID;
7. wait for the companion's exact revision-and-digest draw report; and
8. stop its owned projection session.

The action journal is the only durable mutation authority. The projection
session and composite execution are process-local and may be reconstructed.
If execution stops after the media dispatch while the record is still valid, a
retry must reuse the same `operation_id`: app-control replays or
read-only-recovers the action and never dispatches `next` twice, while the
presentation tail may run again. A structured pending receipt with
`phase=dispatch_started` and `dispatch_count=1` has the same continuity rule:
retry the exact same ID for settlement observation, never generically replan
it as a fresh actuation. Expired and terminal-failure records are not same-ID
retry loops; they require a fresh current-state replan, and a new ID can only
represent an explicit new intent rather than an automatic replacement.
Losing the operation ID is not recoverable automatically. A connection, media-sync, draw,
binding, or cleanup failure returns non-proceed evidence rather than inventing
success. The episode does perform the one explicitly requested,
journal-bounded media actuation; the projection grants no additional
actuation, attention, memory, sensor, arbitrary mobile input, or
background-service authority.

The first live Rhythmbox acceptance receipt is stored at
`docs/design/evidence/app_control_rhythmbox_acceptance_2026_08_12.json`.
The first durable action/replay plus authenticated mobile-delivery episode is
stored at
`docs/design/evidence/app_control_embodied_media_episode_acceptance_2026_08_19.json`.
That v0 artifact predates ABR1 and its field named
`revision_observed_by_device` proves only the legacy authenticated host serve;
it is preserved as historical evidence and must not be cited as an Activity
draw report. The first exact draw-reported composite acceptance is stored
separately at
`docs/design/evidence/advance_track_then_project_acceptance_2026_08_19.json`.

Repeated product value is evaluated separately from protocol correctness. The
metadata-only, code-locked three-pair dogfood gate is documented in
`docs/design/EMBODIED_MEDIA_EPISODE_DOGFOOD_2026_08_20.md`. It measures observed
owner restatements and manual interventions without retaining prompts, track
metadata, device identifiers, or operation IDs, and it never authorizes runtime
influence.

## Extension rule

Add a new domain only as a typed adapter with:

- an allowlisted intent set;
- deterministic capability discovery;
- argument-array execution without shell interpolation;
- an independent, domain-native postcondition;
- explicit failure semantics before any lower-layer fallback is enabled.
