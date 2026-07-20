# S21B-A13 static non-upgrading reachability audit

S21B-A13 audits the exact repository bytes of the A9 canonical plan and the
A9–A12 contracts. Its scope is intentionally finite: it proves that these
specified, version-frozen artifacts expose no structured edge to execution
capability, live-execution authority, owner authority, or real experiment
input admission.

The audit is not a proof about runtime behavior, undeclared code, future
versions, credentials, or external systems. Its output explicitly records that
limitation. Each audited artifact is raw-byte hashed; the auditor checks all
required negative fields and computes an A13 domain-separated self digest.

Any byte change, unexpected nonclaim value, or invalid audit output fails
closed. The result remains audit-only: it cannot issue a permit, become owner
authority, admit real input, or unlock side effects.
