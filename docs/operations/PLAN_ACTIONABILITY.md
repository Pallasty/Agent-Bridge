# Dependency-ready plan suggestions

The tb14 source fix `aa385dfc0` is integrated against the maintenance baseline
`26c6a5291`. A suggested step must have status `pending`, `in_progress`,
`not_yet`, or be an incomplete `done` repair candidate. Waiting and unknown
status strings remain stored but are never suggested as executable work.
Dependencies and original list order still apply.

The current plan's completion mode remains authoritative: `agent_reported`
uses reported completion for progress/dependencies; `evidence_gated` requires
verified anchors and retains unverified-done repair priority. A reported
completion is never relabeled as verified. No store migration is introduced.

Focused regression filters are `plan_actionability` and
`plan_enrichment_never_promotes_legacy_done_or_skips_dependencies` in
`cargo test -p ab-bridge --lib`. Both completion modes are covered. The separate
old-installed-source backport `c3a2214b4` is not imported.

Source integration does not refresh installed binaries or current MCP clients.
