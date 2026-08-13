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
- Mutating operations: `next`, `previous`, `play`, `pause`, `play_pause`,
  `stop`
- Backend: MPRIS through the argument-safe `playerctl` client
- Verification:
  - `next`/`previous`: MPRIS track identity changed;
  - `play`/`pause`/`stop`: requested playback status observed;
  - `play_pause`: playback status changed.

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
