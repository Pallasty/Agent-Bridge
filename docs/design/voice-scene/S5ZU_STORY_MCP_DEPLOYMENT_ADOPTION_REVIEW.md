# S5ZU Story MCP deployment-adoption review

## Outcome

Deployment adoption is deferred. The Story MCP source wiring exists at local
commit `26334149`, but that commit is not an ancestor of the currently recorded
`origin/master` (`9b198da9`). The guarded deployment script builds only from
`origin/master`, so using it now would produce a binary without the Story tool.

The installed `/home/pallasting/.local/bin/agent-bridge.real` identifies source
`5a02c8fd`, has SHA-256
`762c27bee788045dc23681881e1011be8722d9696b2205068a75b2a7c0c045ed`,
and does not contain the `story_command_preflight` marker. All seven observed
installed MCP processes point to that pre-Story binary.

Neither the installed wrapper nor the machine-local environment file contains
Story activation/configuration. No live client observation can therefore
establish tool adoption.

## Required adoption order

1. Land the Story source commit into the authoritative `origin/master` lineage.
2. Define a complete, hash-bound `AB_STORY_*` configuration in the per-machine
   environment rather than embedding host paths in the shared wrapper.
3. Run the guarded deployment dry-run against the adopted origin commit.
4. Separately authorize deployment, then verify the installed binary marker and
   direct stdio `tools/list` under the intended profile.
5. Refresh a chosen client and verify its new tool manifest separately.

S5ZU fetched no remote, built or deployed no binary, changed no configuration,
restarted no MCP process, refreshed no client, and called no Story or audio
path.
