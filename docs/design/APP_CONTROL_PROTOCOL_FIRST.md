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
excluded from the request digest. Before calling
`playerctl next`, it atomically persists `phase=dispatch_started` and consumes
the operation's one-dispatch budget. A second process with the same operation
and request therefore either replays a completed receipt or performs a
read-only observation. It never dispatches `next` again.

If the first process disappears after dispatch but before its terminal receipt:

- a different strict track ID proves that the requested outcome is currently
  satisfied, so recovery may return `verified` while keeping
  `causal_attribution=unknown_after_restart`;
- the same, missing, or unreadable track identity is indeterminate and returns
  `replan` without another dispatch;
- a changed request digest, expired operation, unavailable journal, or busy
  per-operation lock fails closed before mutation.

The journal lives at an absolute path under the user's state directory with a private directory,
hashed filenames, per-operation `flock`, 0600 records, and atomic
write/fsync/rename. Caller-selected `cwd` and `script_path` backends are
rejected for durable operations at the MCP boundary so an operation cannot be
silently rebound to another implementation.

The mobile projection remains a reconstructible presentation tail. After a
verified media operation, callers may create or reuse a consent-gated mobile
projection, call `mobile_projection_sync_media` with the exact `player` from
the durable receipt, then pass `projection_update.revision` as
`mobile_projection_wait.target_revision`. Updating the in-memory frame alone is
not proof that the device displayed it, and a projection session is not part of
the durable media-operation identity.

The first live Rhythmbox acceptance receipt is stored at
`docs/design/evidence/app_control_rhythmbox_acceptance_2026_08_12.json`.
The first durable action/replay plus authenticated mobile-delivery episode is
stored at
`docs/design/evidence/app_control_embodied_media_episode_acceptance_2026_08_19.json`.

## Extension rule

Add a new domain only as a typed adapter with:

- an allowlisted intent set;
- deterministic capability discovery;
- argument-array execution without shell interpolation;
- an independent, domain-native postcondition;
- explicit failure semantics before any lower-layer fallback is enabled.
