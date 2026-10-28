# Existing installation layout compatibility

Delivery blocker after successful candidate admission: the installed legacy
entry has a relocated `HOME/.local`, and its frozen release belongs to a prior
private maintenance root. The previous helper both required the logical HOME
entry and refused its parent link; it also allowed only same-root upgrades.
Two plan failures are retained in the private release evidence. No service or
active alias had been changed.

The bounded repair resolves only the existing HOME/.local entry into physical
alias paths, retains the logical wrapper argument and wrapper hash, refuses
nested links, and rechecks the alias binding before activation moves. An
explicit `--previous-deploy-root` binds cross-root adoption. Both publisher locks
are held nonblocking; old aliases must form one generation with a valid frozen
receipt and intact assets. The old root is recorded for rollback. No private
root symlink allowance, manual copy path, HOME override, receipt fabrication or
new service was introduced.

Red: the two new positive scenarios failed on the original restrictions.
Green: 22 scenarios, 21 passed and one macOS-specific signing test skipped on
Linux. Coverage includes relocated plan/activation/rollback, cross-root rollback,
missing previous-root authorization, a redirected legacy entry, corrupted old
assets, an occupied old publisher lock, and existing admission/rollback checks.
The real host plan subsequently returned `ready` for 13 bound aliases.

Command: `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-activate-maintenance-release.py`.
Evidence: `/home/pallasting/agent-bridge-closeout-20261028/activation-tests-red.log`,
`activation-tests-final.log`, and `activation-plan-compatible.json`.

This changes the activation helper and its tests/documentation only. The admitted
Rust/runtime candidate remains `7cb079ea0ca229f16db8b23f36f17e097e3c2a6c`, SHA-256
`d6d66e725c6b346fe963bd5f22572c313e84b19a3cfa1b441c8f23b220fa218a`.
The helper consumes its existing independently bound admission receipt; it does
not relabel the binary as the later helper commit. No additional Rust build or
fresh admission is needed for this helper-only change. Live activation and
client refresh remain separate steps at this source-validation checkpoint.
