# Free Recall Strategy R25 — C2C-B Startup Wiring Result

Date: 2026-07-23

Status: **ACCEPTED / INDEPENDENT macOS REPLAY OWNER-WAIVED / LIVE C2C CLOSED**

Parents: R24 startup-wiring preregistration, source commit `d2b7527c`, and
the local source receipt.

## 1. Acceptance decision

The owner explicitly waived R24's independent-macOS replay requirement because
no second independent macOS executor is currently available. This is a bounded
source-acceptance waiver only. It does not transform local evidence into
independent evidence, and it grants no live C2C authority.

## 2. Accepted source boundary

R25 adds a default-off macOS C2C-B assembly path:

- `ab-store` owns opaque Keychain readiness plus immediate item-reference
  derivation;
- `ab-bridge` owns the narrow attachment adapter and maps unavailable custody
  to no Hub observer;
- only `daemon` and `mcp` accept the typed
  `--episode-observation keychain-macos-v1` authorization;
- attachment further requires the macOS target and the dedicated feature.

No schema/migration, Hub seam widening, MCP tool, retrieval, sync/export,
deployment, or C2B reader change is accepted by this result.

## 3. Evidence accepted

On the macOS implementation host, without invoking the explicit runtime CLI or
the real Keychain-backed C2C path:

```text
static source contract: 18/18 PASS
directed static mutations: 16/16 PASS
ab-store fake runtime tests: PASS
ab-bridge unavailable-injection test: PASS
ab-store feature check: PASS
ab-bridge feature check: PASS
```

The negative paths are material: omitted CLI authorization constructs no
observer; unavailable readiness injects nothing; bridge receives no custody
material; and the source checker rejects Keychain writes, deletion, unlocking,
ACL changes, enumeration, environment-based enablement, and Hub widening.

## 4. Limits and next gate

This result accepts source structure and local fake-custody behavior only. It
does not prove a normal-process observation episode, a real Keychain read from
that process, an MCP `session_curate` fixture, SQLite event persistence, or
cleanup of live disposable custody.

Those claims remain R26. R26 requires a separate itemized authorization after
its preregistration is reviewed.
