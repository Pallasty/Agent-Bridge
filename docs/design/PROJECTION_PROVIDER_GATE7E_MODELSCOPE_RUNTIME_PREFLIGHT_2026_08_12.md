# Projection Provider Gate 7E: ModelScope Runtime Preflight

Date: 2026-08-12

## Result

The default-off ModelScope adapter now has a read-only runtime preflight. It
validates the Gate 7D admission packet, a candidate `AuthorityDecision`, an
unconsumed scoped nonce digest, current provider readiness, active-session
count, and the explicit runtime opt-in.

Authority and nonce checks in this gate are structural only. The preflight
explicitly reports `authority_authenticity_verified=false` and
`nonce_store_checked=false`; Gate 7F owns both authenticity and atomic
single-use state.

The preflight never consumes authority or nonce state, starts Studio, creates a
session, registers MCP, or authorizes execution. A passing result means only
that Gate 7F may evaluate an atomic single-use consumption contract.

## Interface

```text
python3 scripts/modelscope_abot_provider.py \
  --runtime-preflight \
  --authority-candidate <candidate.json> \
  --admission-packet \
    docs/design/evidence/modelscope_abot_gate7d_runtime_admission_2026_08_12.json \
  --active-sessions 0 \
  --now-unix-ms <current-time>
```

The CLI reads the public readiness endpoint before evaluating the candidate.
It does not call the start or stop endpoints. Opt-in requires
`AB_MODELSCOPE_ABOT_RUNTIME_ENABLE=1`, but opt-in alone is never authority.

## Live default-off evidence

The checked-in candidate is explicitly synthetic and cannot pass preflight,
even if opt-in is later enabled. On the current host the live read-only probe
reported:

```text
provider_ready=true
provider_idle=false
session_state_authoritative=false
synthetic_candidate_not_executable
session_state_not_authoritative
runtime_opt_in_missing
preflight_passed=false
authority_consumed=false
nonce_consumed=false
studio_start_called=false
execution_authorized=false
runtime_admitted=false
```

Receipt:

```text
docs/design/evidence/modelscope_abot_gate7e_live_preflight_2026_08_12.json
```

## Fail-closed coverage

Tests reject malformed authority envelopes, wrong provider or boundary,
missing owner confirmation, consumed or expired nonce, malformed nonce digest,
provider unavailability, concurrent sessions, missing opt-in, and checked-in
synthetic candidates. The candidate file is byte-identical before and after
preflight.

The current CLI has no admitted runtime session registry, so its caller-supplied
active-session count is advisory and the live preflight fails closed with
`session_state_not_authoritative`. Gate 7F must define owned atomic reservation
state before a real preflight can claim the provider is idle.

## Verdict

`GATE7E_MODELSCOPE_READ_ONLY_PREFLIGHT_VERIFIED_DEFAULT_OFF_NO_AUTHORITY_CONSUMED`

The next gate is Gate 7F: design an atomic, single-use authority/nonce
consumption contract with crash recovery. It remains separate from Studio
execution and does not imply MCP registration.
