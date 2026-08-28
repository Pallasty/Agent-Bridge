# R8 macOS read-only profile live closure

Date: 2026-08-27 (America/Los_Angeles)

Status: PASS for the bounded `codex-ag-ui-readonly` profile extension. This is
not macOS action admission and does not authorize an AG-UI transport.

## Source and publication

The extension landed at
`daca14b9aea11831c11a11bdcc42317893bcb832`. It adds exactly
`macos_ax_probe`, `macos_ax_verify`, and `macos_ax_watch` to the existing
explicit `codex-ag-ui-readonly` toolset. The action-side
`macos_ax_action_admission`, `embodiment_lease`, and
`macos_ax_focus_transaction` tools remain outside that toolset.

The extension is present in both remote `master` histories through the later
shared head `843fe1b4e08dbca54dd946cf52dad2119bf8b633`.

## Installed and fresh-MCP evidence

The current Codex MCP reported:

- installed build `db7203f2c048` (`agent-bridge 0.14.0`);
- frontend `codex`, host `desktop`;
- toolset `codex-ag-ui-readonly`;
- profile `essential`;
- profile extras `ag_ui_readonly_project`, `macos_ax_probe`,
  `macos_ax_verify`, and `macos_ax_watch`;
- 59 exposed tools in total.

This proves that the profile extension is not merely present in source: the
fresh installed MCP selected and disclosed it.

## Natural read-only acceptance

A live `macos_ax_probe` against the frontmost Codex application returned:

- schema `macos_ax_probe/v0` and status `ready`;
- `read_only=true` and existing AX trust without prompting;
- adapter `native_ax`;
- `uses_apple_events=false` and `uses_system_events=false`;
- complete, untruncated coverage of two frontmost-app windows;
- no stable `AXIdentifier`, therefore zero action-eligible windows;
- pinned runtime with no caller runtime override;
- exit code zero and no stderr.

The result preserved the original authority boundary: complete semantic
observation does not imply stable identity or action eligibility.

## Verdict and next action

The source, publication, installed-build, fresh-MCP, and natural read-only
acceptance gates are closed for this bounded profile extension. Retain the
surface and record only real regressions. Do not widen action authority, add a
new observation framework, or reopen this lane without a new user-cost signal.
