# Mobile Projection In-Session Update — 2026-08-11

## Outcome

`mobile_projection_update` turns the consented Android projection from a
one-shot static card into a bounded live status surface. It updates title and
body within the original session and cannot change endpoint, token, expiry, or
the protocol's fixed zero-authority flags.

The runtime retains a revisioned frame. Update returns
`updated_awaiting_authenticated_pull`; it does not claim that changing host
memory means the phone rendered the change. `mobile_projection_status` reports
the current and last authenticated served revisions, plus an explicit
`current_revision_observed_by_device` boolean.

## Physical-device acceptance

Device serial `3K661F0178H00000` manually consented to session
`mcp-1786463113-ad0e3ad062a5` at `192.168.1.16:40021`. Revision 1 was served,
then the same session was updated to revision 2 without reopening the Activity
or extending its 600-second TTL.

The update initially returned `last_served_revision=1`. A subsequent status
read reported:

- `current_revision=2`
- `last_served_revision=2`
- `current_revision_observed_by_device=true`
- `phase=connected_recently`
- `pull_count=18`

The session was then stopped explicitly. ADB force-stop returned exit code 0,
`pidof` was empty, and Activity Manager reported no companion services.

An earlier 240-second attempt expired before the holder pressed Allow. The
phone correctly displayed `Cannot connect: invalid or expired session`, while
host status retained zero pulls and `consent_observed=false`. This is retained
as useful fail-closed evidence rather than treated as a transport failure.

## Validation

- `cargo check -p ab-bridge --lib`
- `cargo test -p ab-bridge 'mobile_' --lib`
- `cargo test -p ab-bridge 'projection_' --lib`
- `cargo build -p ab-bridge --bin agent-bridge`
- `git diff --check`
- source-built MCP registry increased from 103 to 104 tools
- physical start → consent → update → authenticated revision confirmation →
  stop sequence — passed
