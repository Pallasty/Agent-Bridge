# License Compliance Notes for Warp Integration

> Status: Working guidance for engineering execution.
>
> This document is **not legal advice**. It is an engineering checklist to
> reduce licensing risk and preserve traceability while integrating with Warp.

## 1) Current Licensing Snapshot (from Warp repo)

- Warp repository states:
  - `warpui_core` + `warpui` are under MIT.
  - Most remaining code is under AGPL-3.0.
- AGPL is not "no commercial use", but it is strong copyleft with network-use
  obligations.

## 2) Architecture Boundary Decision

To reduce compliance risk, we keep a strict boundary:

- `agent-bridge` remains a standalone project/repo.
- Warp-side adaptation lives in Warp repo under:
  - `crates/agent_bridge/` (adapter/protocol)
  - optional: `crates/agent_bridge_ipc/` (protocol-only crate)
- Integration mode: local IPC (Unix socket / named pipe), not source-copy merge.

Why:
- Keeps code ownership and obligations easier to reason about.
- Avoids accidental code mixing that can force broader AGPL obligations.
- Preserves replaceability (Warp backend can be swapped without changing core).

## 3) Hard Rules for Contributors

1. Do not copy AGPL code from Warp into `agent-bridge` source files.
2. Keep integration through process boundary + protocol contracts.
3. Preserve all upstream copyright/license notices where required.
4. Track every Warp-derived file/path in this document (append in section 8).
5. If unsure whether a change creates a derivative coupling, escalate before merge.

## 4) What AGPL Usually Means in Practice (engineering view)

For AGPL-covered components, when you modify and distribute or make them
available over a network, you may need to provide corresponding source under
AGPL terms. This is the key operational difference vs MIT/Apache style
permissive licenses.

## 5) Release Tracks and Required Checks

### A. Open-source track (recommended for fastest compliance)

- [ ] Keep integrated AGPL parts open and publish corresponding source.
- [ ] Include AGPL and MIT license texts in distribution artifacts.
- [ ] Keep attribution notices intact.
- [ ] Include change log entries for AGPL-touched components.
- [ ] Verify dependency license report before release.

### B. Commercial/closed distribution track (high-risk without legal review)

- [ ] Confirm no AGPL-covered code is copied into closed-source modules.
- [ ] Confirm integration is protocol/process boundary only.
- [ ] Perform formal legal review before release sign-off.
- [ ] Verify trademark/branding usage permissions separately.
- [ ] Produce a compliance memo per release (artifact + reviewer + decision).

## 6) Engineering Guardrails

### Code review checklist additions

- [ ] Any file imported from Warp AGPL area?
- [ ] Any direct source reuse vs protocol reimplementation?
- [ ] Any new dependency with copyleft license?
- [ ] Any missing notice/attribution text?

### CI suggestions

- Add a lightweight check that fails if forbidden path patterns are copied
  into `agent-bridge` (example: `warp/app/src/**` snippets pasted verbatim).
- Add dependency license scan to release workflow.

## 7) Decision Log (concise)

- D-LIC-1: Prefer IPC adapter architecture over source merge.
- D-LIC-2: Keep Warp migration in `warp/crates/agent_bridge` only.
- D-LIC-3: Treat AGPL network obligations as potentially triggered for modified
  Warp-side components.
- D-LIC-4: Require legal review for any closed-source commercial release that
  touches AGPL-covered integration.

## 8) Traceability Appendix (update continuously)

### Warp-side migration artifacts

- `warp/crates/agent_bridge/Cargo.toml`
- `warp/crates/agent_bridge/src/lib.rs`
- `warp/crates/agent_bridge/src/protocol.rs`

### Agent-bridge-side docs

- `docs/DESIGN-warp-first-agent-shell.md`
- `docs/LICENSE-COMPLIANCE.md` (this file)

