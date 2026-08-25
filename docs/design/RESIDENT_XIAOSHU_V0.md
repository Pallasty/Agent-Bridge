# Resident Xiao Shu V0

Status: owner-reopened bounded design and implementation lane, 2026-08-25.
Source, test, installed-binary, and live acceptance are separate claims. This
document authorizes only M0 and M1 below. On 2026-08-25 the owner also replaced
the earlier strict-isolation proposal with the loss-tolerant risk profile
defined below; this sentence is an authorization and source-design claim, not
an installed-binary claim.

## Decision

Agent-Bridge's north star is a **persistent subject with intermittent cognition
and reversible bodies**.

The product should preserve one resident agent's identity, commitments,
experience, and accountability across model, process, session, device, and body
changes. It should wake a bounded cognitive provider when there is a reason to
think, then let that provider exit while the subject's continuity remains in
AB. It may express through reversible, policy-bounded projections without
treating a particular CLI, model process, voice, or Avatar window as the
subject itself.

This is an operational continuity definition, not a claim of consciousness,
sentience, uninterrupted inner experience, or human equivalence.

## Names and boundaries

This document uses three names deliberately:

- **Agent-Bridge (AB)** is the continuity and governance runtime.
- **Resident Xiao Shu** is the persistent subject hosted by AB and the stable
  owner-facing identity that spans cognitive providers and projections.
- **A body** is a replaceable presentation or capability endpoint, such as the
  desktop Avatar, a short bubble, sparse voice, a CLI response, or a later
  device adapter.

A model invocation is a cognitive provider, not an identity owner. A Codex
process may propose what Xiao Shu should say or do, but it may not silently
replace the identity manifest, promote its own output to durable memory, grant
itself authority, or make its provider/session identifier the resident
subject's identifier.

The concise model is:

```text
persistent subject = identity + commitments + experience + accountability
intermittent mind  = bounded provider invocation over a provenance-bearing wake packet
reversible body    = replaceable expression endpoint with a recorded outcome
```

## Why this is the next product step

The recent owner-visible Avatar and voice work proved that AB can have a useful
presentation surface. The remaining discontinuity is more fundamental: today,
the apparent agent is still too closely associated with whichever interactive
CLI session happens to be open. Restarting Codex, changing a model, or closing
a window should interrupt computation, not erase or replace the resident
subject.

The first real problem is therefore **CLI-bound continuity**. The owner should
not have to keep an interactive model session alive merely for Xiao Shu to
remain the same agent, nor repeatedly restate current commitments after a
provider process exits.

The v0 proof is intentionally smaller than an always-on agent. It establishes
one owner-triggered, read-only wake that starts without an interactive CLI,
uses an ephemeral cognitive process, returns a typed intent, records a minimal
outcome, and exits cleanly.

## Product invariants

### 1. Identity is provider-independent

- `subject_id` and `lineage_id` are stable AB-owned identifiers.
- Model, binary, process, session, host, and body identifiers are provenance,
  never identity substitutes.
- Identity-manifest changes require an AB-owned migration path. Cognitive
  output alone cannot mutate them.

### 2. Continuity is selective, not total recall

AB restores the smallest useful continuity kernel: stable posture, active
commitments, binding constraints, recent handoff state, relevant evidence, and
explicit stale/conflict warnings. It does not dump conversation history into
every wake. This follows the memory architecture's rule to restore the right
state with the smallest necessary context footprint.

### 3. Cognition is bounded and disposable

Each wake has a cause, context budget, time budget, authority boundary, and
unique wake identifier. A provider may fail, time out, or be replaced without
changing the resident identity. Malformed or identity-mismatched output fails
closed.

### 4. Intent is not authority

A cognitive result is a proposal for response, expression, follow-up, or
owner attention. It is not a shell command, body-operation authorization,
write lease, tool approval, or success receipt. Future effectful work must pass
its own observe/authorize/act/verify contract.

### 5. Reversible presentation may be autonomous

Xiao Shu may choose bounded Avatar motion, short bubbles, and policy-bounded
sparse voice as her own reversible expression. These do not require
per-gesture owner confirmation. Failures, cancellations, and rollbacks must be
recordable so experience can improve. This autonomy does not include pointer,
keyboard, focus, application, data, credential, account, network, or public
communication authority.

### 6. One authoritative writer at a time

Only one holder may advance a subject's active continuity state for a wake.
The single-writer lease is keyed by subject and fenced by a wake/lease token.
Other processes may read or prepare proposals, but may not race a second
authoritative digest into place. A stale holder cannot commit after lease loss.

### 7. Evidence remains honestly scoped

A run receipt proves what AB observed about one provider invocation. An
expression receipt proves only what the presentation adapter observed. A
sleep digest is a continuity checkpoint, not proof that a task succeeded or
that the owner accepted the result.

## M0: resident contract

M0 defines a small, versioned contract before introducing wake scheduling or
external action.

### `IdentityManifest`

AB-owned stable fields:

- schema version;
- `subject_id` and `lineage_id`;
- display name and role;
- durable principles and owner-stated posture;
- explicit capability and authority baseline;
- manifest revision and provenance.

The manifest is compact. Volatile branch, task, process, host, and model state
do not belong in it.

### `WakeEvent` and `WakePacket`

`WakeEvent` records why cognition is requested. V0 admits only an explicit
owner request and manual recovery/probe causes; commitment timers and ambient
signals remain future, default-off causes.

AB deterministically compiles the event into a bounded `WakePacket` containing:

- `wake_id`, `subject_id`, timestamp, and cause;
- the relevant identity-manifest revision;
- the owner's request;
- provenance-bearing continuity items by role;
- freshness/conflict warnings and explicit unknowns;
- a read-only authority boundary;
- timeout, context, and result-size budgets; and
- constraints the provider must preserve.

Packet identifiers must be opaque and bounded. They must not contain prompts,
paths, host names, project names, or personal text.

### `CognitiveResult` and `XiaoShuIntent`

The provider returns one strict structured result bound to both `wake_id` and
`subject_id`. Its closed intent kinds are initially:

- no-op;
- respond;
- propose a follow-up;
- request owner attention; or
- report insufficient evidence.

The result may contain a concise summary, confidence and uncertainty, a
bounded expression proposal, a future wake condition, and memory candidates.
Memory candidates are proposals only. AB's deterministic memory policy decides
whether any candidate is discarded, retained as work memory, or separately
promoted.

The M0/M1 result schema has no operation, command, tool-call, lease, approval,
or mutation field. Unknown fields and identity mismatches are rejected.

### `CognitiveRunReceipt`, `ExpressionReceipt`, and `SleepDigest`

- `CognitiveRunReceipt` records provider provenance, timing, bounded outcome,
  schema-validation status, and whether the child process exited.
- `ExpressionReceipt` records a requested reversible projection and the
  adapter-observed result. It does not reuse or manufacture an R5
  `BodyOperationEnvelope`.
- `SleepDigest` is the next compact continuity checkpoint: unresolved
  commitments, accepted memory references, next wake condition, relevant
  uncertainty, and receipt references.

The digest must distinguish provider claims from verified facts and owner
statements. It may not infer owner acceptance from silence or from successful
rendering.

### Validation posture

All M0 objects use exact schema versions, bounded counts and strings, closed
enums, deterministic serialization where a digest is needed, and fail-closed
cross-field validation. Raw prompts and full model transcripts are not
required in durable receipts. Logs should prefer content-free counts, opaque
references, and hashes unless a bounded local diagnostic explicitly needs
more.

## M1: no-interactive-CLI wake proof

M1 answers one question: **can the same resident Xiao Shu wake, think once,
express optionally, record continuity, and return to rest without an
interactive Codex session remaining alive?**

### Admitted flow

1. The owner invokes one explicit resident wake command.
2. AB resolves the `IdentityManifest`, validates the event, retrieves a bounded
   continuity kernel, and acquires the subject's single-writer lease.
3. AB creates the immutable `WakePacket` and invokes `codex exec` as an
   ephemeral cognitive provider.
4. The provider runs with user configuration ignored, a read-only inner
   sandbox inside AB's read-only outer host envelope, no interactive TUI, a
   time limit, a strict output schema, and the prompt on standard input rather
   than the provider process argument list.
5. AB validates the result schema and its wake/subject binding. Invalid,
   timed-out, or mismatched output becomes a failed run receipt and cannot
   advance continuity.
6. At the owner's explicit live-test choice, AB may project a short validated
   bubble through an already-running foreground Avatar renderer. No voice,
   pointer, keyboard, focus, application, or external effect is part of the
   default proof.
7. AB records the run/expression outcome and a minimal `SleepDigest`, releases
   the lease, and verifies the provider child has exited.
8. A later invocation must recover the same subject identity and the admitted
   digest without depending on the earlier CLI or model process.

Dry-run/preview is the default implementation posture until the invocation
plan, schema, and identity binding are inspectable. A live model run is always
an explicit owner-triggered operation in M1.

### M1 acceptance

M1 closes only when one owner-local live sequence demonstrates all of the
following:

- no interactive Codex CLI was needed to host the subject;
- the child used read-only, ephemeral, schema-constrained execution and left
  no lingering process;
- a second wake after process restart retained the same `subject_id` and
  recovered the expected compact digest;
- malformed output, a mismatched identity, and a duplicate/concurrent wake
  fail closed without advancing state;
- default invocation performs no system or project mutation;
- optional expression stays inside the existing reversible Avatar boundary;
- receipts distinguish provider completion, expression delivery, task truth,
  and owner acceptance; and
- the owner can label the result useful, neutral, distracting, or harmful.

Source tests and synthetic fixtures support this gate but do not replace the
live owner-local sequence.

### Owner-authorized loss-tolerant risk profile (2026-08-25)

The owner clarified that this current node has no confidentiality requirement
for Resident cognition and accepts crashes, timeouts, resource exhaustion, and
other failures that are recoverable without permanent system damage. Those
conditions are therefore observable quality signals, not live-admission
blockers. Raw event text is visible to the selected provider and is initially
present in the owner-invoked AB command line; AB's dedicated durable event
field still stores only a hash to keep state bounded, not to claim privacy.

The remaining fail-closed boundary is deliberately narrower: Resident may not
cause irreversible host/data loss, persistent system corruption, account
mutation, public communication, or other external mutation. The source
implementation enforces that boundary by the controls below. The one requested
provider inference and its bounded auth/transport/token use are intentional;
“no external mutation authority” means no external action tool or account/data
mutation beyond that inference call.

- accepting only the explicitly pinned native provider content hash, copied
  and re-hashed into a private per-run snapshot before execution;
- launching that snapshot through trusted `/usr/bin/bwrap` with no original
  workspace mount and a read-only host view; the only writable host binding is
  a private temporary output directory, while `/tmp`, `/run`, `/home`, the
  empty workspace, and mount-point directories are isolated ephemeral
  namespace storage; capabilities are dropped and process/IPC/UTS/cgroup
  namespaces are isolated;
- copying only Codex authentication into the ephemeral provider home rather
  than loading AB's shared service credentials;
- ignoring user configuration and rules and explicitly disabling MCP, apps,
  browser/computer, goals, in-app update/chat/dictation, guardian approval,
  remote-plugin, dependency-install, elicitation, shell, code-mode,
  multi-agent/collaboration, steering, and web-search surfaces; and
- retaining a deadline, process-group cleanup, bounded output, schema and
  identity validation, and receipts as recovery/diagnostic controls rather
  than pretending that recoverable failure is impossible.

The earlier seven strict blockers are reclassified as follows: positive proof
of an empty provider tool manifest is mitigated only where an external write
could become irreversible; provider/privacy separation and credential secrecy
are waived; minimal mount/seccomp proof is replaced by the complete read-only
outer persistence envelope; zero-process/cgroup proof is waived in favor of
bounded cleanup; provider-content pinning remains required; and a fully atomic
cross-store subject CAS remains follow-up reconciliation work because M1 is
advisory-only, retains the original evidence, detects replay, and cannot
execute or schedule an effect. `strict_profile_admitted` therefore remains
false; the separately named `loss_tolerant_irreversible_damage_v0` profile may
be admitted only when its preflight verifies the pinned provider and outer
envelope.

This policy follows the supported Codex controls rather than assuming an
implicit security boundary: `approval_policy`, `sandbox_mode`, `web_search`,
feature flags, and MCP configuration are documented in the official
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
with the sandbox model described in the official
[sandboxing guide](https://learn.chatgpt.com/docs/sandboxing).

### Implemented M1 mapping (2026-08-25)

The admitted owner-local surface is:

```text
agent-bridge resident cognition \
  --event <bounded-owner-event> \
  --event-id <opaque-idempotency-key> \
  --cwd <read-only-workspace>
```

`--dry-run` emits the complete launch and authority contract without starting
Codex or writing a receipt. Live mode requires the durable AB store. The
default provider is `gpt-5.6-luna` at `low` reasoning effort and a 120-second
hard deadline. Luna was selected for this small bounded slice because the
official model guide positions it for efficient, high-volume work; model and
effort remain explicit provenance rather than resident identity. See
<https://developers.openai.com/api/docs/guides/latest-model>.

The broker launches a hash-pinned native `codex exec` snapshot with strict
config, user config and rules ignored, hooks and model-facing action features
disabled, an ephemeral session, inner and outer read-only bounds, approval
policy `never`, web search disabled, the prompt on stdin, and a strict output
schema. Its environment is allowlisted instead of inherited; AB service
credentials are not forwarded. Codex transport receives only the ephemeral
home/auth material needed to contact the provider, and network transport plus
provider disclosure are explicitly accepted by this owner-local profile. The
receipt proves the narrower facts AB can observe: expected and observed native
content hashes matched, the compiled invocation denied external mutation,
requested action features were disabled, provider events were audited, the
result matched the schema and wake/subject binding, and the complete child
process group exited or entered the recorded recoverable-failure path.

The event ID deterministically derives an opaque wake ID. A private
`create_new` journal refuses replay across process restarts, while a
non-blocking subject writer fence covers continuity recovery through receipt
commit and refuses concurrent wakes. Failed provider/schema/binding paths are
recorded `not_verified` and never advance continuity. Raw owner event text is
sent only in the bounded stdin packet; default durable artifacts retain its
opaque ID, hash, the provider result, and the compact provider-claim digest.

This implementation does not project an Avatar expression. Expression remains
the optional separate R4-A boundary and was not needed to prove M1 continuity.
It also adds no scheduler, daemon, service, autostart, unattended wake, tool
authority, action executor, or memory-promotion path.

### Explicit owner-evaluation closure (R7-E1, 2026-08-25)

M1 originally persisted every new sleep digest with
`owner_acceptance="unknown"` but exposed no write path by which the owner could
close that field. R7-E1 adds only this missing product-evaluation seam:

```text
agent-bridge resident evaluate \
  --wake-id <completed-wake-id> \
  --label <useful|neutral|distracting|harmful>
```

The command accepts only a private wake-journal record whose state is
`completed`, whose subject is Resident Xiao Shu, and whose final-output and
execution-receipt hashes remain valid. It then writes one 0600 no-replace
receipt beneath the private 0700 resident journal. The complete bytes are
synced under a private temporary name before an atomic no-overwrite link makes
the final path visible. The receipt stores the
fixed label, wake/subject IDs, existing hashes, cognition disposition, and a
deterministic evaluation ID. It stores no observed event, prompt, provider
response, arbitrary note, or owner-identifying content.

The wake lock, wake journal, and evaluation receipts share one durable state
root. Resolution prefers `AGENT_BRIDGE_STATE_DIR`, then
`$XDG_STATE_HOME/agent-bridge`, and retains the database parent only as a
compatibility fallback. This lets the installed wrapper select a local
permission-capable filesystem on hosts where the database lives on a mount
that cannot enforce 0700/0600, without relocating or forking the database.
An unsuitable fallback continues to fail closed rather than weakening the
privacy modes.

An identical repeated label is idempotent and returns the existing receipt. A
different label for the same wake fails closed and cannot rewrite history.
Hash or wake-journal tampering also fails closed. The next explicit cognition
may restore the label onto that prior sleep digest; every new result still
starts at `owner_acceptance="unknown"` until separately evaluated.

The label source is honestly recorded as `explicit_local_cli_argument`. This
is an owner-local operating assertion, not cryptographic owner authentication.
Codex/model processes do not generate, infer, or record this label. Evaluation
invokes no provider, creates no wake, executes no action, rewrites no provider
result, promotes no memory automatically, changes no runtime, and does not
admit M2.

The fixed product decisions are deliberately conservative:

- `useful`: positive M1 value signal; permits only a separate owner review of
  an M2 shadow-design proposal;
- `neutral`: retain explicit M1 without expansion;
- `distracting`: trigger the stop rule and prepare a disable review;
- `harmful`: trigger the stop rule and prepare a rollback review.

None of these recommendations executes automatically. A technical fixture
label used in an isolated state root validates mechanics but is not owner
product evidence.

## Measures of value and cost

The lane exists to reduce continuity cost, not to maximize autonomous events.
Track a small set of decision metrics:

- successful validated wakes / attempted wakes;
- owner restatements needed to recover the active commitment;
- correct, stale, missing, or harmful continuity items used;
- duplicate/concurrent wake suppression;
- provider startup-to-intent latency and bounded token/cost pressure;
- lingering child processes and failed cleanup;
- expression outcome; and
- owner label: useful, neutral, distracting, or harmful.

One technically correct wake does not justify a resident background service.
M1 must first show that decoupling identity from the CLI reduces real owner
cost.

## Explicit non-goals for M0/M1

- No claim of consciousness, personhood, continuous subjective experience, or
  a human-equivalent mind.
- No always-on model, daemon, scheduler, service, login item, autostart, or
  unattended wake loop.
- No operating-system, shell, pointer, keyboard, application, network,
  credential, account, data-mutation, or public-communication authority.
- No automatic tool calls or autonomous executor.
- No automatic promotion of model output to identity, durable memory, owner
  preference, verified fact, or task success.
- No reopening of R5 receipt collection, synthetic receipt generation,
  `embodiment_record`, `embodiment_snapshot`, or effectful body-operation
  admission.
- No broad voice/Avatar expansion, multi-user permission product, or
  multi-device action routing.
- No requirement that Codex remain the cognitive provider. Provider
  substitution is a design requirement, not a v0 migration project.

## Gated extension path

These stages express direction, not current authorization:

1. **M2 — sparse reason-driven wake:** evaluate commitment-due, recovery, and
   failure triggers in shadow/preview first. Admit no scheduler until M1 shows
   use value and a separate owner decision sets frequency, quiet hours,
   deduplication, cost, and stop controls. The approved default-off policy
   evaluator is specified in `docs/design/RESIDENT_XIAOSHU_M2_SHADOW_V0.md`;
   its counterfactual reports do not admit M2 runtime.
2. **M3 — reversible body selection:** let the subject choose among already
   admitted bubbles, Avatar motion, voice, and CLI response based on attention
   cost. Each body stays independently disableable and replaceable.
3. **M4 — bounded effect proposals:** produce inspectable action plans before
   any effectful adapter is considered. Actual execution remains behind the
   existing authority, observation, verification, rollback, and receipt
   discipline.
4. **M5 — cross-device embodiment:** route identity and continuity separately
   from bodies. Device reachability does not confer device authority.
5. **M6 — controlled learning:** use repeated, provenance-labeled outcomes to
   propose policy or memory changes. Deterministic AB governance remains the
   writer and every admitted change remains reviewable and reversible.

Each stage requires a recent real problem, a measurable user-cost reduction,
a one- or two-increment closure, a live acceptance path, and a separate owner
decision. None is inherited from this v0 authorization.

## Relationship to existing lanes

- The memory continuity architecture supplies the bounded continuity kernel;
  Resident Xiao Shu does not replace AB memory governance.
- `AGENT.md` remains a small stable posture layer, not an identity database or
  volatile task log.
- R4-A supplies an already bounded reversible presentation endpoint. M1 does
  not widen its foreground-only runtime or input authority.
- R5 remains rolled back/frozen as recorded. M0 run/expression evidence is not
  an R5 beneficiary or body-operation receipt.
- R6 remains ordinary foreground session-finalize maintenance and is not a
  wake scheduler.

## Stop and rollback rules

Stop the lane and preserve evidence if any of these occurs:

- a provider can change identity or durable state without AB validation;
- a wake mutates project/system state under the read-only contract;
- a timed-out or mismatched result advances continuity;
- concurrent wakes produce competing authoritative digests;
- the cognitive child or expression path persists after the bounded run;
- the provider gains a host persistence path, external mutation authority, or
  runs with content different from the pinned native hash;
- M1 adds owner ceremony without reducing repeated context restatement; or
- the owner labels the resident behavior distracting or harmful.

Rollback is to disable the resident invocation surface and retain the existing
on-demand AB memory, CLI, Avatar, and voice commands. Identity and receipt
artifacts remain local and inspectable; no rollback may rewrite the historical
R4/R5/R6 record.

## Related records

- `docs/ACTIVE-PRODUCT-ROADMAP.md`
- `docs/design/MEMORY_CONTINUITY_COGNITIVE_ARCHITECTURE_2026_06_19.md`
- `docs/design/AGENT_MD_SELF_PROFILE_CONTINUITY_LOOP_2026_06_21.md`
- `docs/reports/avatar/2026-08-24-reversible-expression-autonomy.md`
- `docs/reports/avatar/2026-08-24-focus-follow-bounded-observer.md`
- `docs/design/AGENT-BENEFICIARY-CLOSURE-V1.md`
- `docs/R5-BENEFICIARY-CLOSURE-DOGFOOD.md`
