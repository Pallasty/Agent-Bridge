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
- Read-only observations: `state_get`, `volume_get`, `position_get`, `playlist_list`
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
  - `playlist_activate`: exact object path activated and a track observed afterward;
    duplicate names are never resolved implicitly.

The media adapter also exposes `volume` capability discovery with the MPRIS
range `0.0..=1.0` and a default step of `0.05`. This is player-local volume;
system output volume remains a separate `system_control` concern.

The MCP schema exposes no arbitrary bus name, object path, DBus method, shell
command, or coordinates. `dry_run=true` performs discovery and reads the
selected player's state without dispatching.

## Evidence boundary

A successful command exit is dispatch evidence only. The transaction reports
`verdict=verified` only after the post-action observation satisfies the effect
predicate. A timeout or unchanged state returns `unmet` with a recovery hint;
it is not promoted to success.

The first live Rhythmbox acceptance receipt is stored at
`docs/design/evidence/app_control_rhythmbox_acceptance_2026_08_12.json`.

## Extension rule

Add a new domain only as a typed adapter with:

- an allowlisted intent set;
- deterministic capability discovery;
- argument-array execution without shell interpolation;
- an independent, domain-native postcondition;
- explicit failure semantics before any lower-layer fallback is enabled.
