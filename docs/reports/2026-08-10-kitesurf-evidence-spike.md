# Cloudflare Kitesurf Evidence Spike

Status: source and offline validation implemented; live qualification pending credentials.

## Boundary

- Read-only, stateless capture of public HTTP(S) URLs.
- Runtime default-off via `AGENT_BRIDGE_KITESURF=1`.
- Per-call consent via `per_call_opt_in=true`.
- No cookies, credentials, custom headers, scripts, local addresses, or private-network targets.
- Kitesurf remains a remote evidence provider; it does not replace the local stateful Chromium backend.

## Qualification Matrix

| Lane | Target | Expected evidence | Boundary under test |
| --- | --- | --- | --- |
| Static HTML | `https://example.com` | PNG digest, title/status, Markdown, accessibility tree | Basic public capture |
| JavaScript SPA | `https://todomvc.com/examples/react/dist/` | Rendered tasks UI represented in image and accessibility output | Client-side rendering |
| WebGL boundary | `https://get.webgl.org/` | Explicit failure or degraded evidence, recorded without retry escalation | Documented engine limitation |

For each live run, record HTTP status, title, screenshot byte count and SHA-256, Markdown and accessibility-tree character counts, `X-Browser-Ms-Used`, and a comparison with the local Chromium result. Do not store API tokens or authenticated page content in the receipt.

## Admission Rule

The source implementation may merge while remaining default-off. Runtime admission requires a least-privilege Cloudflare Browser Rendering token, account ID, successful static and SPA captures, an explicit WebGL limitation receipt, and confirmation that the deployed MCP process exposes the tool only when opted in.
