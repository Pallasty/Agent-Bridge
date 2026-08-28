# R8 native macOS semantic observation live acceptance

Date: 2026-08-26

Status: PASS

## Bound source and runtime

- Source, GitHub master, and GitLab master: `8c913594d0bff02b341f526db089803e542c2093`.
- Installed binary SHA-256: `e7e8e1dfe99037dbf6e5266cb2e7aef0541da683673420f94dc6406f586dbe0e`.
- Installed binary inode: `56598302`.
- daemon, daemon-http, and Palace mapped the installed inode; daemon-http and
  Palace health endpoints returned `ok`.
- The independent fresh-MCP admission receipt recorded `fresh_mcp=verified`,
  `probe_build_git_sha=8c913594d0bf`, and
  `probe_method=independent_stdio_private_exact_binary_copy`.
- After MCP reconnection, the current Codex consumer reported
  `capabilities.build.git_sha=8c913594d0bf`.

## Natural read-only acceptance

The repository-bound `scripts/macos_accept/run_readonly_accept.sh` completed
with `status=passed`. Its private receipt was generated at
`2026-08-27T05:32:54.330044+00:00` with SHA-256
`017387abbec5c8802ba33205d55b664637bb940498de9b2d1bf416bd66beb8e2`.
The receipt itself remains outside the repository because it contains local
process and window evidence.

Observed result:

- AX trust was present through `AXIsProcessTrusted`; no permission prompt was
  requested.
- The frontmost `com.openai.codex` application and one `AXWindow` were observed
  through the native AX path with complete, non-truncated coverage.
- The window had no `AXIdentifier`. It was declared sample-local,
  `stable_identity_available=false`, and `action_eligible=false`.
- App identity and window presence both verified from the complete sample.
- Screenshot, OCR, Apple Events, coordinate input, and desktop mutation
  channels were not used.

## Product decision

R8 met its bounded benefit measure: one natural frontmost-app task produced a
usable semantic observation without screenshot fallback, Apple Events state,
or owner restatement, while preserving fail-closed action eligibility. Retain
the native sampler as the current observation path. This result grants no new
action authority and does not justify another observation framework; only real
regressions should reopen the lane.
