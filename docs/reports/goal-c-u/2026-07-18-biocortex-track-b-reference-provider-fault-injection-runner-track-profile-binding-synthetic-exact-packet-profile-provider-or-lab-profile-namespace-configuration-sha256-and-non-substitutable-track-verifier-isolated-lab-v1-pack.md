# BioCortex Track B T07 exact track/profile binding isolated-lab pack

Date: 2026-07-18

## Outcome

This pack implements the one authorized T07 candidate-surface component: a
pure, public-only, synthetic KAT verifier that binds the frozen T06 receipt
identity to one exact track/profile tuple.  It remains default-off and has no
production, provider, runtime, evidence-admission, output, fault-injection, or
deployment authority.

The public reviewer accepts exactly eight syntactic inputs.  It rejects a
production, unknown, or non-exact-string mode before observing any of the
other seven inputs.  In synthetic mode it calls the frozen T06 public reviewer
exactly once, validates a separately injected two-profile closed-world policy,
observes the detached four-field binding request last, and requires one exact
six-dimensional ASCII-byte match.

## Frozen binding contract

The policy contains exactly two ordered profiles: managed first and
self-hosted second.  A match covers all of:

1. the T06 receipt `content_sha256`;
2. the T06 receipt `track_id`;
3. `packet_profile_id`;
4. `provider_or_lab_profile_id`;
5. `namespace_id`; and
6. `configuration_sha256`.

The detached T07 request contains only the final four fields.  It cannot
supply a predecessor receipt or track identity.  Zero matches, multiple
matches, policy drift, request drift, wildcard, prefix, hierarchy, inheritance,
or cross-track substitution all reject.

The review order is frozen as:

1. mode pre-observation guard;
2. T06 signer role/scope reviewer exactly once;
3. separate T07 policy review;
4. detached T07 request review last;
5. exact single-profile match;
6. T06 receipt track/content binding; and
7. closed receipt construction.

## What success means

A successful receipt means only that a fixed public KAT tuple was matched
exactly against the exact track and content identity returned by the T06 KAT.
The successful component state is
`BOUND_SYNTHETIC_KAT_TRACK_PROFILE_LABELS_FOR_EXACT_FROZEN_COMPONENT_ONLY`.

It does not authenticate or prove the identity, truth, availability, or
currentness of a provider/lab profile, packet profile, namespace, or
configuration.  It does not inspect or bind subject, prerequisite, source,
build, session, channel, schedule, or row-set identity.  It does not establish
content custody, quarantine, durable replay protection, or CAS.

Accordingly this pack exercises local T07 only.  T08 end-to-end subject binding
and T09 content identity/quarantine/custody remain false.  The target production
control is documented as `TRACK_SUBJECT_BINDING`, with target failure code
`E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED`; neither is implemented here.

## Resource and side-effect boundary

The implementation uses only the Python standard library and committed public
KAT material.  It has no network endpoint, credential path, ambient trust,
private seed, signing, clock, persistence, daemon, provider call, or real
evidence input.  Bounds are frozen at 1 MiB for the frame; 64 KiB for each
authentication/trust/signer-policy/T07-policy input; 16 KiB for each detached
authorization/T07 request; 256 UTF-8 bytes per profile string; two profiles;
JSON depth 32, 4096 nodes, 256 object members and 64 array items; one
predecessor call; one worker; and a 64 MiB private scratch checkpoint cap.
External paid spend is zero.

## Independent verification

The independent checker owns its policy, request, receipt, JSON, fixture,
schema, and source-AST oracles.  It covers both positive tracks and directed
negative cases for pre-observation mode rejection, exactly-once call/order,
bounded duplicate-safe canonical JSON, policy and request closed worlds,
ordered frozen profiles, request-field exclusions, default rejection,
cross-track substitution, predecessor receipt identity, receipt nonclaims,
the exact eight-argument API, and forbidden imports/capabilities.

The source-bound shell gate requires an exact eight-path all-add source delta
from baseline `084eb71dd9c95fbc6285041b1503327705f9a6a1`.  It protects an
import-complete archive of 62 unique paths: eight owned artifacts and 54 frozen
direct dependencies.  It calls the current T07 authority gate exactly once and
serially (`fast` to `fast`, `full-replay` to `full-replay`); it does not invoke
T06 or T05 separately.  Only an ordinary two-parent integration plus a passing
integrated full replay consumes the single-use T07 implementation authority.
Fast validation and failed full validation do not consume it.

## Release boundary

Before an integrated full gate passes, this pack is only a frozen implementation
candidate.  After that exact gate passes it may record five isolated-lab
candidate-surface components and local threats T01 through T07 as exercised.
It still records zero production ingestion controls, zero runtime prerequisites,
zero production threat specifications exercised, zero real evidence items, and
`side_effects_unlocked=NONE`.  The gate does not prove globally unique authority
consumption and grants no authority for a T08 successor.

## Artifact binding

The source-bound candidate freezes these non-cyclic artifact identities:

| Artifact | Raw SHA-256 |
| --- | --- |
| JSON Schema | `7cdbb084c193e5936cd66237504f40cd3d050a3b5f814c0e8e92992a68ac9634` |
| Verifier source | `777bfaa0c18569e68af1cf7c6e5957f1712079bfcfe4e2085e607dba5c9fcb23` |
| Independent checker | `27c25f6c75504925859d693d09c391a6f60ec2c34aab84dda26bd610d4b94e91` |
| Synthetic fixture | `97a45faa1a2e4d1198c5ea5222ada4d31e46093c8956ecb319a2912e46b5b4e4` |
| Expected checker TSV | `bb1bb0f215cf8e272335dbec1d6c7ac2958dd52985a090a9e9fbf2abaf72585a` |
| Pack manifest | `75bcb6f0a47395b0aa5969f8071701a5ef8d777e902c255299d069413278b7e5` |

The report and executable gate are bound by the exact eight-path Git delta and
ordinary integration topology; the gate excludes its own raw digest to avoid a
self-hash cycle.
