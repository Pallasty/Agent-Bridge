# External Browser-Lite Spike: h4ckf0r0day/obscura

Date: 2026-06-03
Status: validated as optional external-backend candidate; not approved as Chrome replacement
Scope: Agent-Bridge browser backend strategy, Codex tool-profile gaps, and external open-source Skill intake

## Question

Can Agent-Bridge borrow value from `h4ckf0r0day/obscura`, and should it be
treated as an implementation candidate for a lighter browser automation path?

## Upstream Shape

Obscura is an Apache-2.0 Rust workspace that implements a lightweight
headless browser with:

- CLI fetch/scrape commands.
- A Chrome DevTools Protocol server.
- An MCP server exposing browser tools.
- An optional `stealth` feature.
- A repository-local `skills/obscura/SKILL.md`.

Relevant upstream repository:

- `https://github.com/h4ckf0r0day/obscura`

Validated source snapshots:

- `main`: `990f2a63c82feeb8e231132a2cb8499cda790924`
- release tag `v0.1.6`: `c9f32aa2f0a0ae574adef4e47a7684a4d54e2532`

Important provenance finding: `main` and `v0.1.6` differ materially in MCP
tool surface. Agent-Bridge must not index README claims or `main` source as
release-binary facts without recording the exact ref and tool snapshot.

## Validation

Release artifact tested:

- `obscura-aarch64-macos.tar.gz`
- size from GitHub release metadata: `43908637` bytes
- SHA-256 local artifact hash:
  `9bd1ad1adcf7046c973ed6522f3bca7b3e35daf1b6d9fbecf7097f10a64f2158`
- archive contents: `obscura`, `obscura-worker`

Smoke checks:

- `/tmp/obscura-bin-eval/obscura --help` succeeded.
- `/tmp/obscura-bin-eval/obscura fetch https://example.com --dump text --quiet --timeout 15`
  returned the expected visible text.
- `/tmp/obscura-bin-eval/obscura fetch https://example.com --eval 'document.title' --quiet --timeout 15`
  returned `Example Domain`.
- Default private-network protection worked:
  `http://127.0.0.1:7878/...` failed with
  `Access to private/internal IP address 127.0.0.1 is not allowed`.
- `obscura serve --port 19322 --host 127.0.0.1` exposed CDP endpoints:
  `/json/version`, `/json`, and `/json/protocol`.
- `obscura mcp` on the `v0.1.6` release binary returned 12 browser tools.

Source build check:

- Command:
  `CARGO_TARGET_DIR=/tmp/obscura-target-ab-eval cargo build -p obscura-cli --bin obscura --no-default-features`
- Checkout: `main` at `990f2a63c82feeb8e231132a2cb8499cda790924`
- Result: success in about 1m 26s on this Mac.
- The built `main` binary successfully ran `fetch ... --eval 'document.title'`.
- The built `main` MCP server returned a larger browser tool surface including
  element refs, markdown extraction, links, interactive elements, history,
  cookies, form detection/fill, scroll, structured extraction, tabs, search,
  and storage-state import/export.

## Borrowable Ideas

### Optional Browser-Lite Backend

Obscura is a credible optional backend for low-resource page reads:

- static or lightly dynamic page text extraction;
- JavaScript expression evaluation;
- link/markdown/structured extraction;
- CDP-compatible probes;
- simple form interaction.

This is useful for Codex-facing tool profiles because it could supply cheap
browser reads without launching or owning a full Chrome profile.

The correct product shape is:

- discover an installed `obscura` binary;
- run it as an external process;
- keep it disabled by default unless explicitly configured;
- route only browser-lite tasks to it;
- fall back to current Chrome/desktop/mobile paths for visual, authenticated,
  or high-fidelity tasks.

### Tool UX

The `main` MCP surface has useful agent-facing patterns:

- stable element refs instead of forcing agents to synthesize CSS selectors;
- capped text extraction;
- token-denser markdown extraction;
- multi-tab state;
- structured extraction via schema;
- storage-state export/import;
- form detection before form filling.

These ideas are useful even if Agent-Bridge never launches Obscura directly.

### Runtime Hazard Classification

Obscura's CDP code contains concrete handling for V8 runtime hazards,
including process-wide V8 serialization and control-plane isolation. The
lesson for Agent-Bridge is to classify external-runtime tools by blocking and
crash risk, then keep daemon health/control routes independent from heavy or
runtime-mutating work.

### Security Defaults

Obscura's default private-network block is the right baseline. Any
Agent-Bridge external browser-lite backend should preserve:

- no private network by default;
- no localhost by default;
- file access off by default;
- explicit allow flags/env only for local development or operator-approved
  flows;
- clear error text when a request is blocked.

### External Skill Intake Fixture

`skills/obscura/SKILL.md` is a useful real-world fixture for open-source Skill
indexing. It also demonstrates why external Skill intake must separate:

- upstream claims;
- indexed metadata;
- local lint/risk tags;
- runnable binary evidence;
- exact git provenance.

## Non-Goals

Do not treat Obscura as:

- a full Chrome replacement;
- a visual QA backend;
- a screenshot backend;
- a default authenticated-browser backend;
- a default stealth or anti-detection subsystem.

The current Agent-Bridge Chrome/desktop/mobile paths remain required for
pixel-level verification, real browser profiles, login-heavy flows, screenshots,
and mobile/desktop UX checks.

## Recommended Agent-Bridge Path

### Phase 0: Index and Observe

Add Obscura to the external open-source Skill/source watchlist, not as an
installed default.

Desired source record:

- repo: `https://github.com/h4ckf0r0day/obscura`
- preferred ref for runnable evidence: `v0.1.6`
- main source snapshot observed: `990f2a63c82feeb8e231132a2cb8499cda790924`
- release tool count: 12
- main-built tool count: larger ref/tab/storage-state surface
- safety tags: `risk:network_fetch`, `risk:server_start`,
  `risk:external_binary`, `risk:stealth_optional`

### Phase 1: Browser-Lite Design

Draft a small `BrowserLiteBackend` boundary instead of overloading the existing
Chrome-backed `BrowserBackend`.

Candidate capabilities:

- `fetch_text(url, policy)`
- `fetch_markdown(url, policy)`
- `eval(url, expression, policy)`
- `extract(url, schema, policy)`
- `list_links(url, policy)`
- `mcp_tool_snapshot()`

Explicitly excluded from `BrowserLiteBackend`:

- screenshots;
- file uploads;
- pixel/layout assertions;
- authenticated profile ownership;
- CAPTCHA or human-resume flows.

### Phase 2: External Process Probe

Implement a read-only probe before any routed execution:

- `agent-bridge browser-lite probe obscura --json`
- detects binary path and version;
- runs `--help`;
- optionally runs `mcp tools/list`;
- returns tool count and safety flags;
- never starts persistent service unless explicitly requested.

### Phase 3: Optional Routing

Only after the probe exists, route narrowly:

- Codex low-risk page read tasks can prefer browser-lite.
- Chrome remains the default for existing `browser_*` MCP tools.
- Stealth mode is never enabled implicitly.
- Private-network/file access requires explicit operator policy.

## Decision

Obscura is worth borrowing from and tracking, but the immediate Agent-Bridge
task is design/probe work, not integration into the default MCP tool surface.

The highest-value near-term implementation is a provenance-aware external
browser-lite probe plus a compact design boundary. This aligns with the current
Codex tool-profile direction: expose fewer default tools, but keep specialized
external capabilities discoverable and verifiable when the task calls for them.
