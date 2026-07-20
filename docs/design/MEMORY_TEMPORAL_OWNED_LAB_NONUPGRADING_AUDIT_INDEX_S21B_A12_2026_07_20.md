# S21B-A12 non-upgrading audit index

S21B-A12 maps one exact A11 static-replay statement into a canonical audit
index. It is deliberately not an admission or authorization layer. The only
input is a self-digested A11 statement bound to the frozen A11 contract; the
only output is an indexed evidence statement with another domain-separated
self digest.

The index is structurally non-upgrading. It contains no allow, permit, token,
credential, owner-decision, or action field. Instead it always emits explicit
negative fields for owner authority, execution capability, real experiment
input, and side effects. Its validity boundary states that it is audit-only.

The builder rejects altered, noncanonical, extra-field, wrong-contract, and
wrong-boundary A11 statements with exit code 65 and no index. The independent
checker validates the index self digest and every negative field. No file is
written by the builder; it only writes the synthetic index to standard output.
