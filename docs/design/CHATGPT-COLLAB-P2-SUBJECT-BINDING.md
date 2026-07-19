# ChatGPT collaboration P2 authenticated subject binding

**Status:** P2A implemented; P2B blocked on authenticated HTTP/OAuth transport
**Date:** 2026-07-19
**Production tunnel:** unchanged on `chatgpt-read`
**Execution plane:** absent

## Decision

Authenticated ChatGPT collaboration is feasible, but not through the current
stdio tunnel profile. P2 must use a separate loopback Streamable HTTP MCP
resource server that verifies OAuth 2.1 bearer tokens before it constructs an
authenticated tool context.

P2A establishes the internal trust boundary and negative regression test. It
does not add an HTTP listener, OAuth verifier, local-subject policy, executor,
or production write capability.

## Verified current state

The production tunnel is healthy and ready, but its `main` channel launches:

```text
AGENT_BRIDGE_TOOLSET=chatgpt-read agent-bridge.real mcp
```

The installed `tunnel-client` resolves that channel as `transport=stdio`, skips
the MCP HTTP probe, and reports an empty OAuth discovery URL list. Its own
`sample_mcp_stdio_local` contract states that stdio skips HTTP OAuth discovery
because there is no protected-resource metadata endpoint to fetch.

This proves transport reachability and the configured OpenAI tunnel/workspace
association. It does not give Agent-Bridge a cryptographically verified end-user
subject on each tool call.

Official OpenAI guidance requires authenticated Apps SDK MCP servers to:

1. implement an OAuth 2.1 resource server;
2. advertise protected-resource metadata;
3. receive `Authorization: Bearer <token>` on subsequent MCP requests; and
4. verify issuer, audience, expiration, and scopes before executing a tool.

It also explicitly warns that client `_meta` hints such as user agent, locale,
and location are not authorization evidence.

References:

- <https://developers.openai.com/apps-sdk/build/auth>
- <https://developers.openai.com/apps-sdk/build/mcp-server>
- <https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>

## Trust boundary

```text
ChatGPT user
  -> OAuth authorization code + PKCE
Authorization server
  -> signed or introspectable access token
ChatGPT MCP client
  -> Authorization: Bearer <token>
OpenAI Secure MCP Tunnel
  -> HTTP request forwarding
loopback Agent-Bridge MCP resource server
  -> verify token and bind exact local policy subject
ToolContext.verified_oauth_subject
  -> collaboration policy evaluation
P1 request queue
  -> local fresh human gate
future narrow executor (not implemented)
```

The following remain hints or transport configuration, not authenticated human
identity:

- MCP `session_id` or thread ID;
- JSON-RPC `_meta`, including any claimed `sub`, `issuer`, or authorization
  value;
- MCP client name such as `openai-mcp` or `ChatGPT`;
- `AGENT_BRIDGE_CHATGPT_COLLAB_CHANNEL`;
- the tunnel ID, workspace association, or tunnel runtime API key;
- caller-supplied task-contract parent evidence.

## P2A internal contract

`ab-mcp::ToolContext` now distinguishes:

- `transport_kind`, which the server sets rather than inferring from request
  content;
- `session_id` and `extras`, which remain untrusted hints; and
- `verified_oauth_subject`, which only code inside the MCP transport crate can
  construct after cryptographic verification.

The stdio server always sets `transport_kind=stdio` and
`verified_oauth_subject=None`. A negative known-answer test submits forged OAuth
claims and a fake bearer token through `_meta` and proves that none are promoted
to authenticated identity.

This is a type and regression boundary, not proof that OAuth is implemented.

## Required P2B subject contract

The future HTTP transport may populate a verified subject only after all checks
pass:

| Field | Required check |
|---|---|
| token signature or introspection | Valid response from the configured authorization authority |
| `iss` | Exact configured issuer match; redirects do not change issuer |
| `aud` | Contains the canonical Agent-Bridge MCP resource URI |
| `exp` / `nbf` / `iat` | Valid under a bounded clock-skew policy |
| `sub` | Non-empty and mapped by an explicit local policy entry |
| scope | Exact capability-specific scope set, not a generic write scope |
| OAuth client | Expected ChatGPT client registration where policy requires it |
| token fingerprint | SHA-256 fingerprint for audit only; never store the token |

Mapping must use an operator-owned policy file with exact issuer, subject,
audience, and scope matches. Unknown subjects, duplicate matches, missing claims,
stale keys, network verification failures, and policy parse errors fail closed.
The external `sub` value is not itself a local owner ID.

## Threat model

| Threat | Required control | P2A state |
|---|---|---|
| Forged identity in JSON-RPC `_meta` | Transport-owned authenticated subject slot and negative KAT | Implemented |
| Stolen or replayed access token | Short expiry, audience binding, optional `jti` replay cache, TLS, no token logging | P2B required |
| Confused deputy across projects | Exact subject + capability + target policy | P2B required |
| Prompt injection requests a mutation | Fresh local human gate independent of model intent | Required before executor |
| Tunnel credential mistaken for user identity | Keep control-plane authentication separate from app OAuth | Documented |
| Same-user local process edits queue files | Signed/MACed records or protected broker plus atomic consume | Required before executor |
| Approval replay or double execution | One-time digest consumption under an atomic lock | Required before executor |
| Partial mutation or failed rollback | Pre-recorded rollback handle and outcome receipt | Required before executor |
| Authorization service outage | Fail closed; read-only production profile remains available | P2B required |

## Phased implementation

### P2A: trust-boundary prerequisite

- Add transport-owned subject context.
- Prove stdio cannot authenticate from caller metadata.
- Record the HTTP/OAuth requirement and threat model.
- Keep `chatgpt-read` production unchanged.

### P2B: authenticated request control plane

1. Add a separate loopback-only Streamable HTTP MCP command or process.
2. Serve MCP protected-resource metadata through the tunnel path.
3. Integrate one OAuth 2.1 authorization server without committing secrets.
4. Verify tokens on every request and map claims through an exact local policy.
5. Expose only a read-only authentication diagnostic and the existing
   non-executing P1 request tools.
6. Run synthetic invalid-token tests before any live ChatGPT test.

The authorization server must be reachable by the user's browser and ChatGPT.
The Secure MCP Tunnel can forward resource-server discovery, but does not make a
private authorization server public automatically. Provider or self-hosting
selection is therefore an explicit infrastructure prerequisite; no paid service
is selected by this decision.

### P2C: one narrow executor

P2C may start only after P2B passes independent threat review and live tunnel
acceptance. Its first candidate should be lower risk than project, external, or
runtime writes. `work_memory_write` is the leading candidate, constrained to an
exact project/scope/lane, with one-use local approval, atomic digest consumption,
an append-only receipt, rate limits, and a tested rollback.

Direct ChatGPT project/shell/browser/deployment tools remain a P3 question.

## Acceptance gates

P2B is not complete until all of these are independently evidenced:

1. unauthenticated HTTP MCP calls return an OAuth challenge;
2. bad signature, wrong issuer, wrong audience, missing scope, expired token,
   and unknown subject all fail closed;
3. spoofed `_meta` cannot affect the verified subject;
4. valid OAuth produces the expected exact local subject binding;
5. only the explicit `chatgpt-collab` profile sees collaboration tools;
6. production `chatgpt-read` remains the four/six-tool read-only surface;
7. source tests, built artifact, tunnel reconnect, and real ChatGPT calls agree;
8. logs and support exports contain no bearer tokens or authorization codes;
9. stopping the new HTTP process or restoring the stdio profile is a tested
   rollback.

Until then, `authenticated_subject_binding=false` and `execution_allowed=false`
remain the only accurate production claims.
