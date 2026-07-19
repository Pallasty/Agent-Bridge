# ChatGPT collaboration P2B provider candidate

**Status:** source and provider KAT implemented; external identity and tunnel acceptance pending
**Date:** 2026-07-19
**Production profile:** unchanged `chatgpt-read` stdio tunnel
**Candidate authority:** one read-only authentication diagnostic; no Agent-Bridge backends

## Decision

The first live-provider candidate uses a separate loopback Streamable HTTP
resource server, an established OAuth/OIDC provider, and a separate OpenAI
Secure MCP Tunnel. Auth0 Free is the initial no-cost provider candidate because
it advertises MCP authorization support, PKCE, CIMD, and rotating RS256 keys.
The Agent-Bridge config remains provider-neutral and can use CIMD, DCR, or a
predefined client when the selected provider advertises the required metadata.

This is not production promotion. The command is default off, exposes only
`oauth_subject_diagnostic`, and always returns `execution_allowed=false`.
Credentials, Seed, SQLite, memory, forum, browser, terminal, agents, P1 request
tools, and all executors are deliberately not initialized.

## Command and configuration

Start the candidate only with an explicit config:

```bash
agent-bridge mcp-http-auth-candidate \
  --config /absolute/path/to/provider-config.json
```

Start a second tunnel-client process with a separate profile after the local
candidate is ready:

```bash
tunnel-client start --profile agent-bridge-chatgpt-p2b-provider
```

Use these checked-in secret-free templates:

- [`CHATGPT-COLLAB-P2B-PROVIDER-CONFIG.template.json`](CHATGPT-COLLAB-P2B-PROVIDER-CONFIG.template.json)
- [`CHATGPT-COLLAB-P2B-TUNNEL-PROFILE.template.yaml`](CHATGPT-COLLAB-P2B-TUNNEL-PROFILE.template.yaml)

The provider config must not contain an access token, authorization code,
private key, client secret, tunnel runtime key, cookie, or refresh token. The
tunnel profile contains only `env:CONTROL_PLANE_API_KEY`; the key stays in the
existing runtime secret path.

## Provider contract

Startup fails closed unless all of these hold:

- the listener is a numeric loopback socket;
- the external resource and every accepted audience are HTTPS, except
  loopback HTTP in tests;
- accepted audiences include the exact external MCP resource URL;
- `authorization_servers[0]` and provider discovery `issuer` exactly equal the
  configured issuer;
- discovery advertises PKCE `S256` and the selected CIMD or DCR capability;
- authorization, token, registration, and JWKS endpoints use HTTPS, except
  loopback HTTP in tests;
- discovery and JWKS requests do not follow redirects, have short timeouts,
  and enforce bounded response bodies;
- JWKS contains at least one usable, unique RSA/RS256 signing key;
- required scopes and exact external-to-local subject policies are non-empty.

Every MCP request verifies RS256 signature, exact issuer, one configured exact
audience, token times, token lifetime, required scopes, subject mapping, and
the optional exact client ID. JSON-RPC `_meta`, MCP session IDs, tunnel IDs,
channel labels, and control-plane credentials never supply identity.

The JWKS cache is bounded and expires after 30 to 3,600 seconds. A missing
`kid` triggers one serialized refresh, followed by a short global refresh
cooldown so random key IDs cannot amplify provider traffic. Provider failure
while refreshing returns `503 jwks_unavailable`; an expired cached key is not
used. A successful refresh atomically replaces the cache, so removed keys do
not remain trusted.

## Secure MCP Tunnel routing

The local server publishes both RFC 9728 routes expected by tunnel-client:

```text
/.well-known/oauth-protected-resource
/.well-known/oauth-protected-resource/mcp
```

For a public resource such as:

```text
https://api.openai.com/v1/mcp/tunnel_<id>
```

the OAuth challenge points to the path-specific public metadata URL:

```text
https://api.openai.com/.well-known/oauth-protected-resource/v1/mcp/tunnel_<id>
```

Tunnel-client forwards `Authorization` headers and OAuth discovery requests,
and rewrites protected-resource metadata for the tunnel's public endpoint. The
authorization server is not tunneled. Its discovery, authorization, token, and
JWKS endpoints must remain publicly reachable by ChatGPT and the user's
browser.

## Auth0 Free setup boundary

External setup is intentionally not automated in source tests. The operator
must create or select a free Auth0 tenant and configure:

1. the exact public tunnel resource URL as the API/resource identifier;
2. RS256 access tokens and the `agent-bridge:subject.read` permission;
3. PKCE `S256` and CIMD, or switch the config to a verified DCR/predefined
   client flow;
4. an allowed login identity;
5. the exact token `sub` and exact ChatGPT OAuth client ID in the local policy.

Do not weaken `subjects`, `expected_audiences`, or `allowed_client_ids` merely
to make the first login pass. Capture only claim names and fingerprints in
evidence; never paste a token or authorization code into git, the forum, test
logs, support bundles, or memory.

## Known-answer tests

The provider KAT uses a real loopback fake IdP over TCP. It proves:

- discovery and initial JWKS loading complete before the MCP listener starts;
- provider keys may carry ordinary ignored fields such as `x5c`;
- a valid provider token binds the exact local subject and cannot be replaced
  by forged `_meta`;
- the public resource and path-specific metadata challenge remain distinct
  from the private listener;
- an unknown rotated `kid` refreshes JWKS once and the new key succeeds;
- repeated random `kid` values inside the refresh cooldown do not hit the IdP;
- unknown keys and expired cache entries fail with 503 during provider outage;
- unsafe listeners, mismatched resource audiences, unknown config fields, and
  issuer mismatch fail before trust is established.

## Live acceptance and rollback

Live acceptance requires a new tunnel ID and a separate provider tenant or
application. It must not modify the existing
`agent-bridge-chatgpt-read` profile or its launchd job.

Acceptance evidence must show:

1. unauthenticated public MCP calls receive the correct OAuth challenge;
2. ChatGPT completes authorization code plus PKCE and invokes the diagnostic;
3. diagnostic output contains the expected external and local subject, exact
   resource audience, required scope, and `execution_allowed=false`;
4. bad issuer/audience/scope/subject/client and provider outage fail closed;
5. candidate and tunnel logs contain no bearer token or authorization code;
6. the original production read tunnel remains healthy and unchanged.

Rollback is to stop the candidate process and its separate tunnel-client
process, then remove or disable only the candidate ChatGPT connector. The
existing stdio read profile requires no edit or restart.

P1 request tools may be considered only after independent threat review and
live acceptance. An executor remains a separate phase with a fresh local human
gate and is not authorized by this candidate.
