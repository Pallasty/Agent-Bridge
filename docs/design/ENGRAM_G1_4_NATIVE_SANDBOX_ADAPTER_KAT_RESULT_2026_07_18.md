# Engram G1.4 native sandbox adapter KAT result

Date: 2026-07-18

Verdict: **REJECTED FAIL-CLOSED — wall clock remains unconfined; no
authority**.

## Observed Darwin evidence

The fixed public probe was compiled with the closed preregistered compiler argv
and run on Darwin:

- control observation: `clock_mask=15`;
- Seatbelt direct-syscall denial observation: `clock_mask=7`;
- symbolic full-clock profile: profile compilation rejected with exit 65
  because `system-clock` is not a bound Seatbelt operation.

The direct syscall bit was removed, but all three libc/commpage clock bits
remained. Therefore `wall_clock_read = deny` is not proved, platform support is
false, and the state machine terminated without policy compile/apply/active or
the full 14-canary run.

## Gate evidence

The independent checker verified:

- exact contract, fixture, probe, implementation, predecessor, and
  `nono = 0.53.0` checksum bindings;
- default-off behavior and rejection of arbitrary probe/path CLI arguments;
- a real fixed-probe native run with the expected negative support matrix;
- 11 ordered, distinct, embedded-payload hash-chain receipts;
- a durable prelaunch expected-chain anchor written before probe launch;
- one-shot replay denial;
- no raw path, run ID, clock output, or Seatbelt diagnostic in the public
  result;
- cleanup success leaves no obligation, lesson, or scratch residue;
- injected cleanup failure writes and reopens a durable minimal lesson before
  unblocking;
- injected lesson-write failure remains absorbing and blocks a new claim;
- receipt reorder, payload mutation, fixture mutation, and fully rehashed
  forgery checks.

The public receipt states:

- `native_adapter_implemented = false`;
- `native_enforcement_verified = false`;
- `full_fourteen_canary_run_executed = false`;
- `production_admissible = false`;
- `g1_4_execution_open = false`;
- `prelaunch_anchor_authenticated = false`.

## Decision

Do not promote the current nono/Seatbelt or nono/Landlock plus syscall-filter
plan as the G1.4 native adapter. Keep nono as a useful filesystem/network
primitive behind a larger proof boundary. Any stronger clock-isolation design
is a separate security-review unit; this result opens no candidate, private,
execution, deployment, or runtime authority.
