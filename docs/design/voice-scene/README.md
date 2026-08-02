# Voice Scene S0 contract

Voice Scene is Agent-Bridge's shared event contract for story performance,
meeting reconstruction, and multi-agent theatre. S0 defines the data and
validation boundary only. It does not synthesize or record audio, load models,
write memories or forum posts, or mutate a running Agent-Bridge instance.

## Static commands

```bash
python3 scripts/voice_scene_contract.py validate \
  docs/design/voice-scene/fixtures/story.json --pretty

python3 scripts/voice_scene_contract.py plan \
  docs/design/voice-scene/fixtures/meeting.json --pretty
```

Both commands read one JSON document and print JSON to stdout. `validate`
returns a non-zero status for semantic contract violations. `plan` returns a
bounded summary whose status is `contract_ready_no_runtime`.

## S0 acceptance surface

- One schema covers `story`, `meeting`, and `agent_theater`.
- Sources carry exact content hashes and explicit versions.
- Timeline order and idempotency keys are deterministic and validated.
- Speaker identity and versioned voice profiles are separate.
- Claims distinguish source truth, observation, inference, and simulation.
- Simulation branches cannot write into the canonical branch.
- Every runtime-effect flag is required to be `false`.

The JSON Schema checks document shape. The Python validator checks
cross-reference and provenance invariants that JSON Schema alone cannot
express. A packet is S0-valid only when it passes both.

## Files

- `voice_scene.schema.json`: Draft 2020-12 interchange schema.
- `story_plan.schema.json`: S1 static story-ingest and review schema.
- `story_render_manifest.schema.json`: S2 segment/chapter render evidence.
- `story_command_integration_preflight.schema.json`: S5ZF non-actuating
  `/story` integration packet.
- `story_command_registration_contract.schema.json`: S5ZG default-hidden MCP
  registration proposal.
- `story_command_inprocess_adapter.schema.json`: S5ZH Python same-process
  adapter evidence.
- `story_rust_adapter_architecture_decision.schema.json`: S5ZI native-versus-
  embedded integration decision.
- `story_rust_contract_core.schema.json`: S5ZJ pure Rust request, canonical
  JSON, SHA-256, and cache-key parity receipt.
- `story_rust_source_ingest.schema.json`: S5ZK Rust source-byte, chapter-index,
  span, and selection parity receipt.
- `story_rust_voice_plan.schema.json`: S5ZL Rust role-voice, source-span,
  structural-transition, plan-hash, and cache-key parity receipt.
- `story_rust_preflight_adapter.schema.json`: S5ZM complete Rust composition
  and S5ZF output/negative-control parity receipt.
- `story_coordinated_wiring_review.schema.json`: S5ZR non-actuating shared-
  surface overlap decision and frozen minimal MCP wiring contract.
- `story_wiring_readiness_recheck.schema.json`: S5ZS freshness-versus-
  cleanliness recheck for shared Rust composition surfaces.
- `story_mcp_registry_wiring.schema.json`: S5ZT default-off, Niche Story MCP
  source wiring and clean staged-tree verification receipt.
- `story_mcp_deployment_adoption_review.schema.json`: S5ZU source, installed-
  binary, configuration, process, and live-client adoption decision.
- `story_source_configuration_adoption.schema.json`: S5ZV hash-bound fixture-
  pilot environment packet with source-origin adoption kept separate.
- `story_source_origin_adoption.schema.json`: S5ZW dual-remote source adoption
  receipt with configuration installation and deployment still closed.
- `story_fixture_configuration_installation.schema.json`: S5ZX installed
  fixture configuration, profile probe, rollback, and FUSE permission blocker.
- `story_secure_machine_env_relocation.schema.json`: S5ZY POSIX-backed secure
  target, compatibility symlink, rollback, and deployment dry-run admission.
- `story_deployment_dry_run.schema.json`: S5ZZ release candidate provenance,
  anti-regression gate, profile visibility, and non-deployment evidence.
- `story_guarded_deployment.schema.json`: S600 installed binary parity,
  recoverable backups, profile visibility, and stale-process separation.
- `story_codex_voice_adoption.schema.json`: S601 narrow codex-voice allowlist,
  deployed manifest proof, rollback, and current-client restart boundary.
- `story_fixture_mcp_preflight.schema.json`: S602 real installed-MCP fixture
  call, bounded render plan, provenance, and zero-actuation receipt.
- `story_fixture_bounded_render.schema.json`: S603 authorized three-segment
  fixture render, machine audio evidence, owner acceptance, and retained
  non-actuating Story-command boundary.
- `story_bounded_render_execution_contract.schema.json`: S604 hash-bound,
  fail-closed render/playback authority separation and fixture-pilot limits,
  with no runtime execution admitted.
- `story_bounded_render_executor_implementation_review.schema.json`: S605
  source-only executor boundary, output custody, authorization envelope, and
  sixteen-case failure matrix with implementation and execution still closed.
- `story_bounded_render_executor_source_review.schema.json`: S607 static S606
  source acceptance, verified enforcement order, and explicit external
  authority/model/nonce blockers with runtime still closed.
- `story_executor_authority_model_nonce_contract.schema.json`: S608 HMAC
  authorization, audited CPU INT4 bundle, fixed nonce custody, and receipt
  schema contract with runtime configuration and execution still closed.
- `story_bounded_render_receipt.schema.json`: machine-audio render receipt with
  playback and memory authority kept false.
- `story_executor_runtime_verifiers_review.schema.json`: S609 static acceptance
  of HMAC authority, streaming model-bundle, and fixed nonce-path verifiers;
  secure configuration and executor composition remain closed.
- `story_executor_secure_runtime_composition_review.schema.json`: S610
  preparation-only S606/S609 composition and corrected external tokenizer asset
  binding, with executor invocation and secure configuration still closed.
- `story_executor_secure_runtime_configuration_contract.schema.json`: S611
  POSIX private key/nonce custody, atomic installation and rollback contract;
  the legacy FUSE path, installation, and executor invocation remain closed.
- `story_executor_posix_runtime_binding_review.schema.json`: S612 active nonce
  migration plus fd-based authority-key loader, with installation, installed-key
  composition, and executor invocation still closed.
- `story_executor_installed_key_composition_review.schema.json`: S613
  installed-key-only public preparation, closed-envelope prevalidation,
  short-lived best-effort key clearing, and pinned keyless completion context;
  secure configuration installation and executor invocation remain closed.
- `story_render_secure_configuration_installation_result.schema.json`: redacted
  S614 fixed-path installation result; it records created custody objects while
  keeping nonce creation and executor/model/audio effects false.
- `s614_story_render_secure_configuration_installation_result.json`: actual
  owner-authorized S614 installation result with no key bytes or content digest;
  the nonce store and executor invocation remain absent.
- `story_executor_secure_configuration_installer_review.schema.json`: S614
  source-only installer acceptance with no-replace publication, durable owned
  rollback, and post-publication recovery gating; real installation and
  executor invocation remain closed.
- `story_render_authorization_proposal_review.schema.json`: S615 unsigned
  owner-review proposal acceptance, exact request/content binding, five-minute
  TTL, and fixed issuer/subject/key ID with real signing and execution closed.
- `s615_story_render_authorization_proposal_review.json`: S615 source review
  receipt proving metadata-only custody inspection, synthetic canonical-field
  compatibility, no real key read, no MAC, and no nonce-store creation.
- `S615_STORY_RENDER_AUTHORIZATION_PROPOSAL_REVIEW.md`: S615 authority boundary,
  verified behavior, non-goals, and the explicit next signing-preflight gate.
- `story_render_owner_signed_preparation_result.schema.json`: S616 exact,
  redacted single-key-load preparation result with real MAC generation admitted
  but nonce, executor, model, audio, and memory effects closed.
- `s616_story_render_owner_signed_preparation_result.json`: actual S616
  owner-authorized preparation receipt containing no MAC, nonce, authorization
  ID, key material, or replayable envelope.
- `S616_STORY_RENDER_OWNER_SIGNED_PREPARATION.md`: S616 single-read mechanism,
  S613 public-entrypoint evidence, grant-reference disposal, and next authority
  gate.
- `story_bounded_render_execution_result.schema.json`: S617 strict redacted
  result contract binding the successful render receipt, live WAV evidence,
  nonce audit count, and closed playback/memory gates.
- `s617_story_bounded_render_execution_result.json`: actual S617 CPU INT4
  three-segment render result, including the preserved pre-nonce rejection and
  post-nonce failed-attempt evidence without MAC, nonce, or authorization ID.
- `S617_STORY_BOUNDED_RENDER_EXECUTION.md`: S617 runtime boundary, the two
  integration defects discovered by real execution, their regression fixes,
  FUSE output-mode semantics, and the separate playback/review next gate.
- `story_bounded_render_acceptance_review.schema.json`: S618 strict read-only
  acceptance contract that distinguishes WAV container bytes from decoded PCM
  samples and keeps playback, memory, and Story runtime admission closed.
- `s618_story_bounded_render_acceptance_review.json`: S618 live evidence that
  all S617 segment files and the assembled PCM sample sequence match the
  previously owner-accepted S603 audible content exactly.
- `S618_STORY_BOUNDED_RENDER_ACCEPTANCE_REVIEW.md`: S618 acceptance provenance,
  container-header explanation, inherited human-audition boundary, and the
  separate Story render-runtime admission next gate.
- `story_render_runtime_admission_review.schema.json`: S619 strict source,
  installed-binary, live-manifest, authorization, cancellation, concurrency,
  output-custody, redaction, and deployment-freshness admission contract.
- `s619_story_render_runtime_admission_review.json`: S619 current-state decision
  blocking direct runtime wiring while selecting a one-shot supervised Python
  worker for the next bounded fixture-pilot contract.
- `S619_STORY_RENDER_RUNTIME_ADMISSION_REVIEW.md`: S619 architecture decision,
  rejected/deferred alternatives, accepted trade-offs, seven blockers, and the
  explicit S620 worker-protocol next gate.
- `story_render_one_shot_worker_protocol_contract.schema.json`: S620 strict
  one-request/one-response, host-wide admission, worker supervision, private
  custody, authority, and redacted-projection contract.
- `s620_story_render_one_shot_worker_protocol_contract.json`: S620 hash-bound
  static contract retaining only S602/S604 fixture provenance while rejecting
  the historical shared output root.
- `S620_STORY_RENDER_ONE_SHOT_WORKER_PROTOCOL.md`: S620 protocol ADR, including
  the host-wide `flock` decision, owned kill/reap sequence, failure semantics,
  explicit nonclaims, and the S621 implementation-review gate.
- `story_render_one_shot_worker_implementation_review.schema.json`: S621 strict
  staged-implementation, source-state, pure-codec, synthetic-supervisor,
  owner-authority, registration, and fault-matrix review contract.
- `s621_story_render_one_shot_worker_implementation_review.json`: S621
  hash-bound selection of a four-file pure protocol codec as the next patch,
  while preserving six explicit runtime blockers.
- `S621_STORY_RENDER_ONE_SHOT_WORKER_IMPLEMENTATION_REVIEW.md`: S621 staged
  implementation ADR and the separation between MCP invocation and independent
  owner grant authority.
- `story_render_descendant_custody_review.schema.json`: S632 strict source,
  host-capability, threat-boundary, mechanism-selection, lock-custody, and
  failure-matrix review contract.
- `s632_story_render_descendant_custody_review.json`: S632 hash-bound selection
  of a repository-owned Guardian for a dormant S633 prototype, while keeping
  cgroup/systemd hardening, Supervisor integration, execution, and deployment
  closed.
- `S632_STORY_RENDER_DESCENDANT_CUSTODY_REVIEW.md`: S632 architecture decision
  coupling descendant cleanup to shared `flock` custody and defining the
  single-failure boundary and S633 acceptance gate.
- `story_render_guardian_synthetic_prototype.schema.json`: S633 strict
  protocol, startup-gate, shared-lock-custody, single-failure proof, synthetic
  test-effect, authority, and runtime-nonadoption contract.
- `s633_story_render_guardian_synthetic_prototype.json`: S633 hash-bound
  evidence for eight real Linux synthetic tests, with Supervisor integration,
  real Worker execution, MCP, configuration, and deployment closed.
- `S633_STORY_RENDER_GUARDIAN_SYNTHETIC_PROTOTYPE.md`: S633 implementation and
  test evidence for Host EOF cleanup, Guardian-loss fallback, payload FD
  isolation, residual-descendant rejection, and the S634 integration-review
  gate.
- `story_render_guardian_supervisor_integration_review.schema.json`: S634
  strict current-source, ABG2 transport, custody state-machine, replay-order,
  rollout, rollback, authority, and runtime-nonadoption review contract.
- `s634_story_render_guardian_supervisor_integration_review.json`: S634
  hash-bound selection of a default-off GuardianV2 synthetic integration, with
  exact source changes and all real Worker/runtime effects still closed.
- `S634_STORY_RENDER_GUARDIAN_SUPERVISOR_INTEGRATION_REVIEW.md`: S634
  architecture decision for sealed execution-plan transport, Host-owned
  bounded stdio, async binding, last-close custody, replay continuity, and the
  S635 synthetic-integration gate.
- `s635_story_render_guardian_supervisor_synthetic_integration.json`: S635
  hash-bound default-off GuardianV2 implementation and synthetic verification
  receipt, with real Worker, runtime configuration, MCP, and deployment closed.
- `S635_STORY_RENDER_GUARDIAN_SUPERVISOR_SYNTHETIC_INTEGRATION.md`: S635 ABG2,
  sealed-plan, asynchronous binding, shared lock custody, cleanup, rollback,
  and runtime-nonadoption evidence.
- `story_render_guardian_runtime_adoption_review.schema.json`: S636 strict
  source, installed-binary, live-process, current-client, model/Python,
  packaging, authority, rollback, and implementation-ladder review contract.
- `s636_story_render_guardian_runtime_adoption_review.json`: S636 hash-bound
  decision that the model bundle is ready while eight Worker, identity,
  packaging, authority, MCP, and deployment blockers keep runtime adoption
  closed.
- `S636_STORY_RENDER_GUARDIAN_RUNTIME_ADOPTION_REVIEW.md`: S636 evidence-layer
  audit and ordered S637-S643 adoption path, beginning with a source-only real
  Worker protocol adapter.
- `character_state.schema.json`: S3 ledger and resume snapshot contract.
- `realtime_interaction.schema.json`: S4 PTT turn receipt and owner gates.
- `voice_audition.schema.json`: S5 blinded three-voice audition plan.
- `sherpa_render_pack.schema.json`: S5B atomic render and ASR receipt.
- `voice_backend_capabilities.json`: S5 backend provenance and capability matrix.
- `fixtures/story.json`: novel-performance contract example.
- `fixtures/story_s1.md`: deterministic TXT/Markdown ingest sample.
- `fixtures/meeting.json`: meeting reconstruction contract example.
- `fixtures/agent_theater.json`: multi-agent scene contract example.
- `ADR-0001-voice-scene-contract.md`: architecture decision and boundaries.
- `NOVEL_TTS_V1_MIGRATION.md`: mapping from the existing novel prototype.
- `ADR-0003-story-offline-render.md`: cache, assembly, and playback gates.
- `ADR-0004-memory-grounded-character-state.md`: knowledge and branch gates.
- `ADR-0005-realtime-story-interaction.md`: realtime state and consent gates.
- `ADR-0006-chinese-multispeaker-audition.md`: S5 audition and promotion gates.
- `ADR-0007-sherpa-render-asr-gate.md`: S5B integrity and atomic render gate.
- `ADR-0008-mi50-container-and-community-onnx-research-gate.md`: S5D
  static research and isolation gates.
- `voice_snapshot_static_audit.schema.json`: S5G downloaded-snapshot static
  audit receipt.
- `voice_cpu_int4_smoke_receipt.schema.json`: S5H CPU INT4 session-creation
  receipt with no graph execution.
- `voice_cpu_int4_numeric_probe.schema.json`: S5I bounded codec-embedding
  numeric probe receipt.
- `voice_cpu_int4_predictor_probe.schema.json`: S5J bounded code-predictor
  numeric probe receipt.

## S5 Chinese multi-speaker audition

`scripts/story_voice_audition.py` defines the static S5A gate. It validates
backend capability and license posture, creates a deterministic blinded plan
for narrator plus two distinct characters, computes Chinese ASR character error
rate, and evaluates explicit owner review receipts.

S5A does not install a backend, download a runtime model, render or play audio,
or bind a speaker to a character. AISHELL-3 remains local-evaluation-only while
its model-weight license is unverified. Full S5 exit requires three real,
hash-bound artifacts and owner confirmation.

## S5B integrity-gated render pack

`scripts/story_sherpa_render_gate.py` verifies the complete AISHELL-3 asset
manifest and an isolated synthesis binary before rendering. It publishes a
three-file pack atomically, refuses existing output directories, validates PCM
WAV shape, and binds file-level Chinese ASR results and CER into one receipt.

The machine-verified pack is not played automatically. Its speaker IDs remain
opaque until a separate owner-authorized blind audition records audibility,
naturalness, role fit, and pairwise distinguishability.

## S5D voice-model research gate

`scripts/story_voice_model_research_gate.py` performs a static, non-actuating
audit of an MI50 container configuration and experimental voice-model
manifest. It fails closed for broad GPU exposure, privileged containers,
unpinned images, runtime networking, writable root filesystems, or incomplete
community ONNX evidence.

S5E adds an inert least-privilege profile,
`mi50_qwen_onnx.compose.yaml`, and a metadata-only supply-chain snapshot for
the selected Qwen3-TTS streaming ONNX conversion. The profile cannot infer:
its runtime opt-in is false and its entrypoint is `/bin/false`. The snapshot
does not treat a model-card license declaration, remote file listing, or
historical revision as verified model weights.

S5F uses `scripts/story_voice_small_file_audit.py` for an owner-authorized,
fixed-revision, small-file-only acquisition. It never imports the downloaded
Python. Failed or incomplete acquisition leaves no final evidence directory.
The current fixed-revision transport result is recorded in
`s5f_small_file_acquisition_evidence.json`.

S5G uses `scripts/story_voice_snapshot_audit.py` for a separately downloaded
ModelScope snapshot. It streams complete file hashes, validates all six
variant manifests, scans Python with `ast`, and optionally parses ONNX protobuf
graphs with external tensor loading disabled. The current 1.7B CustomVoice
receipt is `s5g_modelscope_snapshot_static_audit.json`. Its status is blocked,
not trial-ready: ModelScope supplied mutable `master`, the snapshot lacks a
standalone license file, and a build utility contains a subprocess primitive.
The advertised CUDA execution provider is not evidence of MI50 support.

S5H uses `scripts/story_voice_cpu_int4_smoke_gate.py` to create isolated
ONNX Runtime sessions for only the seven graphs referenced by the CPU INT4
manifest. It pins `CPUExecutionProvider`, disables graph optimization, and
never calls `session.run()`. The current receipt,
`s5h_cpu_int4_session_smoke.json`, records successful session creation for all
seven graphs under ONNX Runtime 1.28.0. This is a compatibility precheck only:
it does not execute inference, synthesize audio, clear S5G supply-chain
blockers, or imply ROCm/MI50 support.

S5I uses `scripts/story_voice_cpu_int4_numeric_probe.py` to execute only the
CPU INT4 `codec_embed` graph twice with fixed synthetic IDs `[0,1,2,3]`. The
current `s5i_cpu_int4_codec_embed_numeric_probe.json` receipt records a finite,
deterministic `float32[1,4,2048]` output. The embedding is not forwarded to any
autoregressive or waveform graph, so this stage produces no token stream or
audio and makes no quality, parity, performance, or MI50 claim.

S5J uses `scripts/story_voice_cpu_int4_predictor_probe.py` to execute only the
CPU INT4 `code_predictor` graph with zero-valued hidden-state and codec-ID
fixtures. The current `s5j_cpu_int4_code_predictor_probe.json` receipt records
finite, deterministic `float32[1,15,2048]` logits. The probe performs no
argmax, sampling, recurrence, token generation, or audio work; it is graph
numerics evidence, not a generation or quality claim.

S5K uses `scripts/story_voice_cpu_int4_talker_cache_probe.py` to execute one
zero-history step of the CPU INT4 `talker_cache` graph with a bounded,
deterministic nonzero embedding. The
`s5k_cpu_int4_talker_cache_probe.json` receipt validates against
`voice_cpu_int4_talker_cache_probe.schema.json` and records nonzero finite
logits, a finite hidden state, 56 finite present-cache tensors, and identical
aggregate hashes across two runs. The cache is not fed back and the probe
performs no sampling, recurrence, token generation, waveform decoding, audio,
GPU work, or community-Python import.

S5L uses `scripts/story_voice_cpu_int4_cache_feedback_probe.py` to run two
independent copies of an exactly two-step CPU sequence. Within each sequence,
the first step's 56 present KV tensors are fed back once with position one and
a two-token attention mask. The
`s5l_cpu_int4_cache_feedback_probe.json` receipt validates against
`voice_cpu_int4_cache_feedback_probe.schema.json` and records deterministic
cache growth from `[1,8,1,128]` to `[1,8,2,128]`. The second embedding remains
a synthetic fixture rather than a sampled/model-derived token representation;
no sampling, further recurrence, decoding, audio, GPU work, or
community-Python import occurs.

S5M uses `scripts/story_voice_cpu_int4_residual_embed_probe.py` to execute only
the CPU INT4 `residual_embed` graph twice with the fixed synthetic codec IDs
`[0..15]`. The `s5m_cpu_int4_residual_embed_probe.json` receipt validates
against `voice_cpu_int4_residual_embed_probe.schema.json` and records a finite,
nonzero, deterministic `float32[1,2048]` step embedding. The output is not
forwarded, so this remains isolated graph evidence rather than a generated
codec frame or connected autoregressive path.

S5N uses `scripts/story_voice_cpu_int4_single_frame_loop_probe.py` to connect
the CPU INT4 talker cache, code predictor, and residual embed graphs for one
raw-greedy codec frame and one cache feedback. The
`s5n_cpu_int4_single_frame_loop_probe.json` receipt validates against
`voice_cpu_int4_single_frame_loop_probe.schema.json`, records the selected
16-code frame, and binds deterministic full-sequence hashes. Because this
snapshot lacks local model configuration, the probe applies no codec-EOS or
reserved-token suppression and explicitly makes no reference-generation
equivalence claim. It stops before a second frame, waveform decoding, audio,
GPU work, or community-Python import.

S5O uses `scripts/story_voice_config_provenance_gate.py` to hash-check an
official Qwen configuration observed through ModelScope and reconcile it with
fresh metadata from the three CPU INT4 graphs. The
`s5o_config_provenance_gate.json` receipt validates against
`voice_config_provenance_gate.schema.json`. All model dimensions and codec
IDs match the graph contracts, but the converter did not record its upstream
revision, ModelScope exposed only mutable `master`, and fixed-revision
Hugging Face raw transfer was unavailable. The receipt therefore retains
`reference_generation_ready=false` and blocks reference-compatible
multi-frame claims despite structural compatibility.

S5P uses `scripts/story_voice_provenance_remediation_decision.py` to make the
next provenance action executable and fail closed. Published converter
evidence identifies the official base model but does not bind the current ONNX
artifacts to an upstream revision, so path A cannot currently close lineage.
The decision selects path B: an isolated re-export from immutable official
Qwen commit `6c3e96b6a2c593ce3e546ee699a5d944de81850e`, beginning with a CPU FP32
reference lane before quantization comparison. Path A remains reopenable only
with artifact-bound publisher evidence. The
`s5p_provenance_remediation_decision.json` receipt records no downloads,
converter or graph execution, snapshot replacement, GPU use, playback, or
global memory/forum writes. Weight acquisition and every later adoption step
remain separately authorized; `reference_generation_ready=false`.

S5Q uses `scripts/story_voice_fixed_source_acquisition_plan.py` to produce a
revision-pinned, small-file-only offline acquisition packet. Its explicit
11-path allowlist contains no `.safetensors`; no weight command is emitted.
The isolated destination is outside the current ModelScope ONNX snapshot, and
the planner fails closed on an existing/overlapping destination or less than
the 128 GiB workspace policy floor. Because fixed-revision Hugging Face
transport remains unavailable on this host, the SHA-256 ledger stays pending
until offline acquisition rather than being inferred from mutable files. The
`s5q_fixed_source_acquisition_plan.json` receipt records zero network,
filesystem-creation, model-execution, GPU, and playback effects.

S5R uses `scripts/story_voice_fixed_source_acquisition_gate.py` to hash every
byte of the downloaded ModelScope `master` weight payload and compare it with
the two SHA-256 values published at the immutable official Qwen revision.
Both weight files match exactly and their Safetensors headers parse, so the
receipt promotes only `weight_payload_fixed_revision_equivalent=true`.
ModelScope packaging still differs from the Hugging Face tree (including an
extra root `configuration.json` and a different README), so
`packaging_exact_fixed_revision=false` and `conversion_ready=false`. No model
or converter execution, snapshot replacement, GPU work, or playback occurs.

S5S uses `scripts/story_voice_quantization_toolchain_audit.py` to inspect the
community converter, its dependency declarations, existing precision variants,
the MI50 lane, and the local `arrowquant-rocm:5.7` image without running any of
them. Olive block-wise asymmetric RTN (`int4`, block 32) is implemented and is
the selected candidate only after a fresh fixed-source CPU FP32 reference.
The audit blocks execution because most dependencies float, two Transformers
requirements conflict, `uv` is absent, and the converter writes inside its own
snapshot. CUDA artifacts remain non-evidence for ROCm. The ArrowQuant image is
not admitted for TTS because it is mutable, package-mutating, contains a
network-tunnel build step, and lacks identified Olive/ORT versions.
The community manifest-declared CPU INT4 payload is 1.962 GB versus 8.641 GB
for FP32 (4.403× smaller), but size is not treated as parity, quality, or speed
evidence.

S5S1 uses `scripts/story_voice_offline_lock_contract.py` to select an exact
CPython 3.12 CPU conversion baseline and reserve a fail-closed isolated
workspace layout. The receipt deliberately distinguishes exact critical direct
pins from a complete transitive lock: the wheelhouse, full SHA-256 ledger,
offline installation, and converter command all remain absent or blocked.
TorchAudio and ONNX Runtime GenAI are excluded from the selected conversion
lane because neither is used by the admitted converter path. No packages,
directories, model files, ONNX graphs, GPU work, or audio are produced.

S5T uses `scripts/story_voice_existing_onnx_adoption_decision.py` to promote
the already downloaded community CPU INT4 ONNX snapshot to the active trial
lane. This is supported by the existing six-variant inventory, seven-graph CPU
session gate, bounded component numerics, and single-codec-frame loop. The
multi-gigabyte conversion wheelhouse and fixed-source re-export are paused as
fallback-only work. The retained original weights remain a future reference.
The current minimal ONNX runtime lacks Transformers, SoundFile, and Librosa;
closing that smaller runtime gap and attempting bounded text-to-WAV synthesis
is the next gate. No dependency installation, graph execution, rendering,
playback, GPU work, or model conversion occurs in this decision stage.

S5U creates a 303 MB isolated inference environment with ONNX Runtime,
Transformers, and SoundFile—no Torch, Olive, Librosa, or source builds—and
runs the existing CPU INT4 CustomVoice path on a bounded Chinese prompt. The
receipt `s5u_existing_onnx_text_to_wav_receipt.json` binds the downloaded
inference driver, manifest, environment, request, and resulting 0.64-second
mono PCM16 24 kHz WAV. The artifact is non-silent and machine-verified but was
not played. A Transformers warning requires the next trusted runner to set
`fix_mistral_regex=True`; therefore linguistic correctness and naturalness
remain unclaimed.

S5V adds `scripts/story_voice_existing_onnx_trusted_runner.py`, which
SHA-256-binds the audited community inference source, forces offline tokenizer
loading with `fix_mistral_regex=True`, hides all GPU devices, and produces a
deterministic Vivian audition candidate. SenseVoice recognized the generated
4.8-second WAV as `你好，我是小树，请听听这段声音。`; the 60-frame cap
truncated the requested suffix. Owner-authorized playback completed and the
owner reported `清晰，温柔。`. Those human claims apply only to this candidate;
full-sentence completion, general naturalness, MI50, and production admission
remain open.

S5W makes reaching `max_new_tokens` a hard truncation failure. The next Vivian
candidate naturally emitted EOS at frame 58 under a 100-frame cap, and
SenseVoice recovered the complete sentence `你好，我是小树，今天很高兴和你说话。`.
The 4.64-second WAV was played under owner authorization. The committed receipt
records the owner's `完整！清晰，自然` acceptance. Story-renderer mapping remains
the next gate.

S5X adds `scripts/story_voice_mapping.py`, a deterministic one-to-one mapping
from S1 speaker IDs to Qwen CustomVoice speakers and bounded style
instructions. The current fixture maps narrator to owner-accepted Vivian,
林默 to Dylan, and 苏岚 to Serena. The two character voices remain audition
pending, so chapter rendering fails closed. Mapping stability is bound to the
source hash, speaker ID, Qwen speaker, and profile version; changes require a
new version and re-audition. This stage loads no model and emits no audio.

S5Y forwards each S5X style instruction into the trusted ONNX runner. Dylan's
林默 line and Serena's 苏岚 line both naturally emitted EOS and achieved full
SenseVoice transcripts before owner-authorized playback. The committed receipt
records owner acceptance of both voices as natural, intelligible, and usable,
plus an appropriate inter-clip interval. A small clarity increase is a
non-blocking preference only if naturalness is preserved. After replay, the
owner explicitly confirmed that Dylan and Serena are easy to distinguish and
clearly identifiable. S5Y is accepted and the three-role story excerpt is the
next gate.

S5Z adds `scripts/story_voice_excerpt_renderer.py`, which binds the S5X mapping
to the S5Y acceptance, preserves source segment order, and fail-closes on an
unknown role or missing authorization. Its first four-segment scene combines
Vivian, Dylan, Serena, then Vivian with exact 0.8-second transition gaps. All
admitted segments naturally emitted EOS; one longer Serena attempt hit the
100-frame cap and correctly produced no WAV. The final 17.52-second PCM16
24 kHz artifact is finite and non-silent, and SenseVoice found all story
content with a single combined-ASR homophone substitution. Owner playback
accepted naturalness, clarity, and role identifiability, but found the fixed
0.8-second gaps slightly short and correctly noted that pacing depends on
paragraph context. Voice quality is accepted; chapter admission remains
blocked on a paragraph-aware dynamic pause policy.

S5ZA extends the excerpt renderer with explicit structural transitions and a
bounded pause table: 0.65 seconds for same-paragraph continuation, 1.0 for a
speaker turn, 1.4 for a paragraph break, and 2.2 for a scene break. Unknown
labels fail closed. The current trial reuses the four hash-identical S5Z source
segments and applies 1.4, 1.0, then 1.4 seconds without executing TTS. The
18.92-second assembly is finite/non-silent and retains the same combined ASR
content. Owner playback accepted this bounded dynamic timing baseline. The next
gate is a non-actuating chapter voice render preflight derived from a real
`/story` static plan.

S5ZB adds `scripts/story_chapter_voice_plan.py`. It binds the S1 source plan,
S5X mapping, S5Y voice acceptance, and S5ZA pacing acceptance before deriving
chapter, paragraph, and speaker transitions. The `story_s1.md` preflight found
five ordered segments and a real cross-chapter scene break, but it also blocked
two attributed-dialogue lines whose narration and quoted speech are not yet
split. The durable receipt remains `chapter_render_ready=false`; source-grounded
utterance segmentation is the next gate. No model, audio, playback, or runtime
`/story` registration is involved.

S5ZC upgrades the chapter preflight with source-grounded attributed-dialogue
segmentation. One complete Chinese or ASCII quote pair becomes a Vivian
attribution segment and an accepted character dialogue segment, each bound to
the original event and exact source character slice. Colon-to-full-stop is the
only spoken punctuation normalization and is recorded explicitly. Ambiguous or
unbalanced quotes remain blocked. The real fixture expands from five events to
seven voice segments with an empty review queue and
`chapter_render_ready=true`; bounded first-chapter Qwen rendering is the next
gate, not an action performed by S5ZC.

S5ZD adds `scripts/story_bounded_chapter_render.py` and renders only the four
S5ZC segments before the first scene break; all second-chapter segments remain
excluded. Three Vivian segments naturally emitted EOS and the hash-identical
Dylan audition was reused. Segment verification recomputes WAV hashes and
requires exact non-entity ASR; a finite allowlist handles the inherently
homophonic Chinese names while explicitly not claiming Hanzi identity. The
11.05-second PCM16 artifact uses 0.65, 1.0, and 1.0-second pauses. Machine gates
passed, and owner playback accepted its continuity, naturalness, clarity, and
intervals. This admits the bounded first chapter only; cross-chapter continuity
is next, while production `/story` registration remains out of scope.

S5ZE generalizes the bounded selector to any available 1-based chapter and
fail-closes out-of-range requests. The three second-chapter segments reuse the
accepted Serena line and generate only two new Vivian lines; the accepted first
chapter is not rerendered. The 6.88-second second chapter uses two 1.0-second
speaker-turn pauses, then joins chapter one with the source-derived 2.2-second
scene break. Hash, PCM, finite/non-silent, segment ASR, and combined ASR gates
pass for the 20.13-second result. Owner playback accepted cross-chapter
continuity and the overall result. Greater separation between the two female
voices is recorded as a character-setting-dependent, non-blocking preference.
Cross-chapter continuity is admitted; production `/story` registration remains
out of scope, and its non-actuating integration preflight is the next gate.

S5ZF adds `scripts/story_command_integration_preflight.py`. It rereads and
hashes the requested source, confirms the selected chapter, binds the accepted
mapping, role audition, voice plan, cross-chapter result, and model inference
hash, then derives version-sensitive per-segment cache keys. The real chapter
two packet selects three segments and preserves its two 1.0-second internal
gaps plus the preceding 2.2-second scene break. Runtime flags and unavailable
chapters fail closed. All runtime effects remain false: this does not register
`/story`, execute ONNX, render or play audio, or write cache or memory. A static
production-registration contract is the next gate.

S5ZG adds `scripts/story_command_registration_contract.py`. It proposes the
Niche `story_command_preflight` MCP boundary with no default, codex-essential,
or codex-voice exposure. The accepted input has only a TXT/Markdown path,
explicit chapter selector, and `dry_run=true`; its handler remains a future
isolated adapter with subprocess use forbidden. The durable contract binds the
S5ZF receipt, implementation, output schema, and the exact inspected Rust
registry source hash, while a negative control rejects a pre-existing tool-name
collision. No Rust registry is changed and no runtime tool exists. An isolated
in-process preflight adapter is the next gate.

S5ZH adds `scripts/story_command_inprocess_adapter.py`. It accepts the exact
structured S5ZG arguments and directly calls the S5ZF function in the same
Python interpreter after rechecking every bound implementation, schema,
receipt, and registry-source hash. AST and runtime tests show no shell or child
process path. This is intentionally not described as a Rust in-process result:
the Rust registry remains untouched, no MCP tool exists, and production still
has no embedded/native adapter. A Rust-native versus embedded-interpreter
design decision is the next gate.

S5ZI adds `scripts/story_rust_adapter_architecture_decision.py` and accepts an
incremental Rust-native port over embedding Python. The audited 1694-line
Python surface is standard-library-only; bridge already has `serde_json` and
`sha2`, no PyO3/libpython lifecycle, and a native-binary deployment contract.
Python remains a non-authoritative golden oracle across four reversible parity
stages (S5ZJ-S5ZM). No Cargo dependency, Rust adapter, registry entry, model, or
audio action is added. The pure Rust story contract core is the next gate.

S5ZJ adds an intentionally unexported `crates/bridge/src/story_contract.rs`.
The pure module provides the typed S5ZG request, fail-closed dry-run validation,
recursively canonical JSON, SHA-256, and the S5ZF segment cache key. Fixed Rust
tests reproduce Python-oracle hashes, including UTF-8 content. It performs no
source ingest, is absent from the Rust module tree and MCP registry, and has no
model, audio, cache, or memory effects. Rust source ingest parity is the next
gate.

S5ZK extends that unexported module with bounded TXT/Markdown file reading,
exact source-byte hashing, strict UTF-8 decoding, stable source/chapter IDs,
Unicode character spans, and `from_start` or explicit-chapter selection. The
`story_s1.md` golden packet matches the Python oracle; missing chapters and
non-UTF-8 files fail closed. Cast/event extraction and voice planning remain
outside this unit, with no registry or runtime effects. Rust voice-plan parity
is the next gate.

S5ZL adds accepted role/pacing evidence validation, attributed-dialogue
splitting, narrator/character voice projection, Unicode source spans, four
explicit structural transitions, and canonical voice-plan hashing. A fixed
five-segment vector reproduces both the Python plan digest and a
model-provenance-bound segment cache key. The module remains unexported and
does not execute a model or touch audio/cache/runtime state. Complete Rust
preflight adapter parity is the next gate.

S5ZM composes the four native migration stages into one pure Rust preflight.
For the accepted chapter-two fixture its complete value equals the frozen S5ZF
Python receipt, including three render requests and the preflight digest;
from-start selects the four bounded first-chapter segments. Runtime flags and
provenance/acceptance drift fail closed. This proves unexported preflight
parity only: no Rust module export, MCP registration, embedded interpreter,
model/audio action, or execution authorization is added. A separate
owner-authorized Rust registration review is the next gate.

S5ZN completes that registration review without modifying the module tree or
MCP registry. The review selects native-adapter hardening before registration:
the current reader has neither an allowed-root/byte-ceiling admission policy,
nor a configured resolver for the accepted evidence bundle, nor an async
cancellation ownership contract. A machine-readable receipt binds the current
registry, library, native module, and S5ZM evidence hashes; collision and
mutated-authority controls fail closed. The future surface remains a gated
Niche `story_command_preflight`, but it is not registered, deployed, exposed,
or execution-authorized. Rust story preflight adapter hardening is the next
gate.

S5ZO hardens the still-unexported native adapter. Story sources now require a
canonical configured root and fixed byte ceiling; the four accepted evidence
documents are root-, size-, and SHA-256-bound; and an async wrapper cooperatively
cancels chunked blocking reads and joins owned work before returning. The
hardened path preserves the S5ZF preflight digest and rejects root escape,
oversize input, evidence drift, pre-cancelled work, and runtime flags. This does
not export the module, register or expose a tool, deploy a binary, or authorize
execution. An owner-authorized Rust story registration implementation review is
the next gate.

S5ZP reviews the Rust MCP registration implementation against the live module
tree, registry, and MCP cancellation path. It admits an isolated
`mcp_tools/story.rs` adapter but rejects registry wiring: MCP cancellation
aborts and drops the tool future, so the adapter still needs a drop-to-token
cancellation guard, while both `lib.rs` and `mcp_tools.rs` contain active
unrelated work. The future tool remains gated, Niche, and absent from all eager
Codex extras. No module export, registry edit, deployment, or runtime action is
performed. The isolated Rust story MCP adapter is the next gate.

S5ZQ adds the isolated `mcp_tools/story.rs` transport and path-bound tests. Its
configuration parser fails closed unless activation plus every root, byte
limit, evidence path, and SHA-256 is present; strict arguments admit only
source, chapter selector, and `dry_run=true`. A drop guard converts MCP future
abort into native cancellation, while accepted output preserves the S5ZF
digest and is returned through structured and text channels. The adapter file
is still absent from the product module tree and registry, so no tool is
exposed or callable. Coordinated module and registry wiring review is the next
gate.

## S4 realtime story interaction

`scripts/story_realtime_interaction.py` provides a bounded push-to-talk turn
orchestrator. It pauses the story, captures only with explicit microphone
authorization, routes the stable transcript through S3 grounding and spoiler
checks, renders a response, emits it only under a separate output gate, and
resumes the exact playback position.

Fixture tests do not open a microphone or sound device. A real closed-loop
trial remains a separate explicit owner-authorized acceptance action.

For retained session artifacts, `withdraw_artifacts()` requires separate owner
authorization and deletes only the explicitly named files; directories and
unrelated session files are never recursively removed.

## S3 memory-grounded character state

`scripts/story_character_state.py` provides append-only canon, character
knowledge, and interaction ledgers; cursor-bounded `/story ask`; a spoiler
falsifier; inferential psychological profiles; and deterministic session
snapshot/resume projections.

```bash
python3 scripts/story_character_state.py /story ask \
  --snapshot docs/design/voice-scene/fixtures/s3/character_state.json \
  --character character_lin \
  --question '钥匙在哪里？'
```

S3 is text-only. Story state snapshots retain
`proposal_only_owner_review_required` and do not silently write simulations or
unreviewed story facts into global AB memory.

## S2 offline render

`scripts/story_offline_render.py` provides the render-only contract,
version-bound segment cache, bounded retry, PCM WAV validation, chapter
assembly, integrity verification, and `ChapterPlayer` state machine.

Playback is never implicit. `ChapterPlayer.start()` and `.resume()` require an
explicit owner authorization argument. Machine-verified WAV output remains
`human_audition=pending` until the owner listens to that exact artifact.

## S1 static story ingest

```bash
python3 scripts/story_static_ingest.py \
  /story docs/design/voice-scene/fixtures/story_s1.md chapter 2 --pretty
```

The command prints a deterministic, reviewable story plan. It does not create
an output file. Character, relationship, event, and emotion extraction is
deliberately heuristic and remains in `needs_review`.
