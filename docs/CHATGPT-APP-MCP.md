# ChatGPT App MCP setup

## Host distinction

The unified ChatGPT desktop application contains two different execution paths:

- Codex tasks can spawn local stdio MCP servers from `~/.codex/config.toml`.
- Ordinary ChatGPT chats discover Apps/Plugins and do not inherit local Codex MCP config.

Use the existing Codex setup for the first path. Use a Developer Mode App plus
OpenAI Secure MCP Tunnel for the second path.

## Read-only contract

Set `AGENT_BRIDGE_TOOLSET=chatgpt-read`. This profile exposes exactly:

- `search`: company-knowledge-compatible memory search.
- `fetch`: side-effect-free exact memory read via `memory_peek`.
- `capabilities`: compact local capability diagnostic.
- `context_governor_snapshot`: read-only context lifecycle diagnostic.

`search` and `fetch` have the exact single-field input schemas expected by
ChatGPT company knowledge, declare `outputSchema`, and return the same JSON in
both `structuredContent` and the text compatibility block. They return an empty
`url` because local Agent-Bridge memories do not have a user-openable canonical
HTTP URL; ChatGPT should treat them as ordinary tool results rather than false
citations.

The generic `search` and `fetch` names are registered only for `chatgpt-read`.
Existing Codex, Claude, Gemini, hook, standard, and development profiles retain
their existing tool membership.

## Local verification

Build the current source and inspect the stdio descriptor surface before
creating a tunnel:

```bash
cargo build --release -p ab-bridge

printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"chatgpt-contract-probe","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | env \
      AGENT_BRIDGE_CLIENT=chatgpt \
      AGENT_BRIDGE_TOOLSET=chatgpt-read \
      AGENT_BRIDGE_TOOL_PROFILE=essential \
      ./target/release/agent-bridge mcp
```

The `tools/list` response should contain exactly four tools. Every descriptor
must have a non-empty `title` and explicit `readOnlyHint=true`,
`destructiveHint=false`, and `openWorldHint=false`. `search` and `fetch` must
also have `outputSchema`.

## Secure MCP Tunnel

Prerequisites:

- A tunnel ID created in OpenAI Platform tunnel settings.
- A runtime API key with Tunnels Read + Use.
- ChatGPT Developer Mode access for the target workspace.
- The current Agent-Bridge binary installed at a stable absolute path.

Keep credentials in the environment, not in shell history or MCP arguments:

```bash
export CONTROL_PLANE_API_KEY="sk-..."

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile agent-bridge-chatgpt-read \
  --tunnel-id tunnel_0123456789abcdef0123456789abcdef \
  --mcp-command "env AGENT_BRIDGE_CLIENT=chatgpt AGENT_BRIDGE_TOOLSET=chatgpt-read AGENT_BRIDGE_TOOL_PROFILE=essential /Users/you/.local/bin/agent-bridge mcp"

tunnel-client doctor --profile agent-bridge-chatgpt-read --explain
tunnel-client run --profile agent-bridge-chatgpt-read
```

While the tunnel client is running, open ChatGPT Settings -> Plugins, create a
Developer Mode App, select **Tunnel** as the connection type, and select the
associated tunnel.

## Security boundary

Secure MCP Tunnel avoids a public inbound listener, but fetched memory content
still travels to the connected OpenAI product and workspace. Before enabling the
App, confirm that the selected Agent-Bridge memory database is appropriate for
that workspace. The v0 profile is intentionally read-only and has no memory,
forum, shell, browser, device, or deployment mutation tools.

Do not replace `chatgpt-read` with `all-dev`, `claude-standard`,
`codex-essential`, or `codex-lean` in the tunnel profile.

Official references:

- <https://developers.openai.com/apps-sdk/build/mcp-server>
- <https://developers.openai.com/api/docs/mcp>
- <https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>
