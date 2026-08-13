# Projection Provider Gate 7J: ModelScope External Adapter Boundary

Gate 7J prepares a bounded adapter plan from a consumed Gate 7I receipt. It is
plan-only: no network, subprocess, Studio request, prompt transport, artifact,
MCP registration, or runtime admission is performed.

The plan fixes the provider, action, endpoint, capability digest, 30-second
timeout ceiling, and explicit `network_allowed=false` / `subprocess_allowed=false`.
Any open execution boundary, mismatched capability, unsupported operation, or
out-of-range timeout fails closed.

Verdict: `GATE7J_MODELSCOPE_EXTERNAL_ADAPTER_PLAN_VERIFIED_NON_ACTUATING`.
The next gate is Gate 7K: separately admit an external execution attempt.
