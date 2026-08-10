#!/usr/bin/env python3
"""Measure one frozen Qwen3-TTS module with a non-writing fake-Q8 forward proxy."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import signal
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.qwen3_tts.fake_q8_functional_sensitivity.v0"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.functional_sensitivity_policy.v0"
GATE_SCHEMA = "agent_bridge.qwen3_tts.functional_sensitivity_gate.v0"
ACTIVATION_POLICY_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_policy.v0"
MANIFEST_SCHEMA = "agent_bridge.qwen3_tts.inference_critical_manifest.v0"
CORPUS_SCHEMA = "agent_bridge.qwen3_tts.quantization_corpus.v0"
READY_GATE_STATUS = "READY_FOR_ONE_MODULE_FAKE_Q8_SMOKE"
SUCCESS_STATUS = "FAKE_Q8_FUNCTIONAL_MEASUREMENT_RESTORED_NON_PROMOTING"
CONTROL_BLOCKED_STATUS = "BLOCKED_CONTROL_NONDETERMINISM_OR_RESTORATION_UNPROVEN"
FAILED_RESTORED_STATUS = "FAILED_TRIAL_RESTORED"
FATAL_RESTORATION_STATUS = "FATAL_RESTORATION_UNPROVEN_PROCESS_TERMINATED"
LOCK_PATH = Path("/private/tmp/agent-bridge-qwen3-evaluation.lock")
TRIAL_ROOT = (
    Path.home()
    / ".local"
    / "state"
    / "agent-bridge"
    / "qwen3-evaluation-ledger"
)
EXPECTED_POLICY_SHA256 = (
    "43b07f5f30bdc5aad7569b1d3412ea44619bd460fa7925cc037384291e86addd"
)
EXPECTED_GATE_SHA256 = (
    "1d9f7f98ce628b6227c53c4843708dc3a84da255c638190e5a1ed2f489105f15"
)
EXPECTED_PREREQUISITE_HASHES = {
    "activation_plan": "d87deeeadf81aaba2d010bded7c60e8b0bd8f74419b6e6a132a46d1d9fd2fb12",
    "activation_gate": "369f7af4d964a5d285be8dd00865faf107060e8973003611c9329821113da8c9",
    "activation_capture": "365b9f9e9b7cd5a3b9890945ed8f4428cc9aa51b1c3dc3a448b1bdf2847fb4b4",
    "activation_policy": "9cf235640d5f8960393edef6600b137faaa939c3451bd46b91246686377da061",
    "perturbation_scope": "4a4abee2cdc336ea68af14413dacb7f91ea3a2c039ce51a058fdd5a37e97e7ec",
    "token_boundary_probe": "b04ec6601722221c4cf1df1f00c3d9d48c687711046d55dea52c5fbd25f00421",
    "runtime_manifest": "ec365c6890d01dfa4a24df2d181f9991461a689528c83b8ad9e223f2066b2ddc",
    "corpus": "9193f6e5359fcf3ecd9c0a5a2726886908ffa3a266ab7597f283629e710a7afd",
    "thresholds": "2b37447912a7e5af68ab1db724689fad8065c6ccba61a7609e6118dde63cc56d",
}
ASSET_RELATIVE_PATHS = {
    "talker": Path("model.safetensors"),
    "speech_tokenizer_codec": Path("speech_tokenizer") / "model.safetensors",
}
FROZEN_INPUT_FIELDS = {
    "activation_plan_sha256": "activation_plan",
    "activation_gate_sha256": "activation_gate",
    "activation_capture_sha256": "activation_capture",
    "perturbation_scope_sha256": "perturbation_scope",
    "token_boundary_probe_sha256": "token_boundary_probe",
    "runtime_manifest_sha256": "runtime_manifest",
    "corpus_sha256": "corpus",
    "thresholds_sha256": "thresholds",
}
FORBIDDEN_AUTHORITY_FIELDS = (
    "allows_additional_module_or_case",
    "allows_weight_mutation",
    "allows_quantized_weight_writing",
    "allows_packing_or_scale_storage_claim",
    "allows_runtime_candidate_generation",
    "allows_worker_socket_use",
    "allows_audio_decode_write_or_playback",
    "allows_runtime_wiring_fallback_deployment_or_promotion",
)


class TrialInterrupted(RuntimeError):
    """Raised when a catchable termination signal arrives during the isolated trial."""


class TokenTrialFailure(RuntimeError):
    """Carries cleanup evidence when a pre-codec trial fails."""

    def __init__(self, message: str, restoration_proven: bool, boundary: dict):
        super().__init__(message)
        self.restoration_proven = restoration_proven
        self.boundary = boundary


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return bytes_sha256(payload)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_path(output: Path, forbidden_roots: list[Path]) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite or follow an existing output path")
    if not output.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    resolved = output.resolve(strict=False)
    for root in forbidden_roots:
        if is_within(resolved, root.resolve()):
            raise ValueError(f"output is forbidden under runtime/model root: {root}")


def exclusive_write_json(path: Path, report: dict) -> None:
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        fsync_directory(path.parent)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
        fsync_directory(path.parent)


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_json_snapshot(path: Path) -> tuple[dict, str]:
    """Hash and parse one immutable byte snapshot without following symlinks."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        chunks = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or before.st_size != sum(len(block) for block in chunks)
    ):
        raise ValueError(f"input changed while being read: {path}")
    payload = b"".join(chunks)
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid frozen JSON input: {path}") from error
    if not isinstance(document, dict):
        raise ValueError(f"frozen JSON input is not an object: {path}")
    return document, bytes_sha256(payload)


def ensure_owner_trial_directory(path: Path) -> None:
    state_root = Path.home() / ".local" / "state"
    state_metadata = state_root.lstat()
    if (
        state_root.is_symlink()
        or not state_root.is_dir()
        or state_metadata.st_uid != os.getuid()
        or state_metadata.st_mode & 0o022
    ):
        raise ValueError("persistent state root is not owner-controlled")
    current = state_root
    for name in ("agent-bridge", "qwen3-evaluation-ledger"):
        child = current / name
        try:
            os.mkdir(child, 0o700)
            fsync_directory(current)
        except FileExistsError:
            pass
        metadata = child.lstat()
        if (
            child.is_symlink()
            or not child.is_dir()
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077
        ):
            raise ValueError(
                "persistent trial ledger must be owner-only and non-symlink"
            )
        current = child
    if current != path:
        raise ValueError("unexpected persistent trial ledger path")


def consume_trial_claim(claim_path: Path, result_path: Path, payload: dict) -> dict:
    """Consume the exact trial once; the claim is intentionally never removed."""
    if claim_path.parent != result_path.parent or not claim_path.parent.is_dir():
        raise ValueError("claim and result must share an existing trial directory")
    if result_path.exists() or result_path.is_symlink():
        raise ValueError("the fixed one-shot result path already exists")
    if claim_path.exists() or claim_path.is_symlink():
        raise ValueError("the fixed one-shot trial authorization is already consumed")
    claim = {
        "schema": "agent_bridge.qwen3_tts.fake_q8_trial_claim.v0",
        **payload,
        "claim_path": str(claim_path),
        "result_path": str(result_path),
        "claim_is_never_automatically_deleted": True,
    }
    exclusive_write_json(claim_path, claim)
    return {
        "path": str(claim_path),
        "sha256": sha256(claim_path),
        "mode": oct(claim_path.stat().st_mode & 0o777),
    }


def acquire_process_lock(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    stream = os.fdopen(descriptor, "r+")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise ValueError("another Qwen3 evaluation process holds the owner lock") from None
    return stream


def model_tree_manifest(model_root: Path, verified_assets: list[dict]) -> dict:
    asset_hashes = {
        row["relative_path"]: row["sha256"] for row in verified_assets
    }
    rows = []
    for path in sorted(model_root.rglob("*"), key=lambda item: str(item)):
        relative = str(path.relative_to(model_root))
        metadata = path.lstat()
        if path.is_symlink():
            rows.append(
                {
                    "relative_path": relative,
                    "kind": "symlink",
                    "target": os.readlink(path),
                    "inode": metadata.st_ino,
                }
            )
        elif path.is_dir():
            rows.append(
                {
                    "relative_path": relative,
                    "kind": "directory",
                    "mode": oct(metadata.st_mode & 0o777),
                    "inode": metadata.st_ino,
                }
            )
        elif path.is_file():
            rows.append(
                {
                    "relative_path": relative,
                    "kind": "file",
                    "bytes": metadata.st_size,
                    "inode": metadata.st_ino,
                    "sha256": asset_hashes.get(relative) or sha256(path),
                }
            )
        else:
            raise ValueError(f"unsupported model-tree entry: {relative}")
    return {
        "entry_count": len(rows),
        "manifest_sha256": canonical_json_sha256(rows),
    }


def quantize_groupwise_q8_numpy(array, group_size: int) -> dict:
    """Apply the frozen row-local symmetric Q8 reference without changing input."""
    import numpy as np

    source = np.asarray(array)
    if source.ndim != 2:
        raise ValueError("fake-Q8 source must be rank 2")
    if not isinstance(group_size, int) or group_size <= 0:
        raise ValueError("group size must be a positive integer")
    rows, columns = source.shape
    if columns == 0 or columns % group_size != 0:
        raise ValueError("each source row must be divisible by the group size")
    if not np.issubdtype(source.dtype, np.number):
        raise ValueError("fake-Q8 source must be numeric")
    if not np.all(np.isfinite(source)):
        raise ValueError("fake-Q8 source contains a non-finite value")

    q = np.empty((rows, columns), dtype=np.int8)
    dequant = np.empty((rows, columns), dtype=np.float16)
    groups_per_row = columns // group_size
    zero_group_count = 0
    scale_min_nonzero = None
    scale_max = 0.0
    squared_error = 0.0
    source_energy = 0.0
    absolute_error = 0.0
    max_abs_error = 0.0
    changed_elements_vs_source_fp16 = 0

    # A small row block keeps f64 reference math bounded for multi-gigabyte models.
    row_block = 32
    for start in range(0, rows, row_block):
        stop = min(start + row_block, rows)
        block = source[start:stop].astype(np.float64, copy=True)
        groups = block.reshape(-1, group_size)
        max_abs = np.max(np.abs(groups), axis=1)
        scales = max_abs / 127.0
        zero_mask = max_abs == 0.0
        zero_group_count += int(np.count_nonzero(zero_mask))
        nonzero_scales = scales[~zero_mask]
        if nonzero_scales.size:
            block_min = float(np.min(nonzero_scales))
            scale_min_nonzero = (
                block_min
                if scale_min_nonzero is None
                else min(scale_min_nonzero, block_min)
            )
            scale_max = max(scale_max, float(np.max(nonzero_scales)))

        normalized = np.zeros_like(groups, dtype=np.float64)
        np.divide(
            groups,
            scales[:, None],
            out=normalized,
            where=~zero_mask[:, None],
        )
        rounded = np.sign(normalized) * np.floor(np.abs(normalized) + 0.5)
        quantized = np.clip(rounded, -127.0, 127.0).astype(np.int8)
        reconstructed = quantized.astype(np.float64) * scales[:, None]
        reconstructed[zero_mask] = 0.0
        q[start:stop] = quantized.reshape(stop - start, columns)
        reconstructed_fp16 = reconstructed.reshape(stop - start, columns).astype(
            np.float16
        )
        dequant[start:stop] = reconstructed_fp16
        changed_elements_vs_source_fp16 += int(
            np.count_nonzero(reconstructed_fp16 != block.astype(np.float16))
        )

        error = reconstructed - groups
        squared_error += float(np.sum(error * error, dtype=np.float64))
        source_energy += float(np.sum(groups * groups, dtype=np.float64))
        absolute_error += float(np.sum(np.abs(error), dtype=np.float64))
        max_abs_error = max(max_abs_error, float(np.max(np.abs(error))))

    elements = int(source.size)
    source_dequant_nrmse = (
        (squared_error / source_energy) ** 0.5
        if source_energy > 0.0
        else 0.0
    )
    return {
        "q": q,
        "dequant": dequant,
        "group_count": rows * groups_per_row,
        "zero_group_count": zero_group_count,
        "q_min": int(q.min()) if q.size else None,
        "q_max": int(q.max()) if q.size else None,
        "q_sha256": bytes_sha256(q.tobytes(order="C")),
        "dequant_sha256": bytes_sha256(dequant.tobytes(order="C")),
        "scale_min_nonzero": scale_min_nonzero,
        "scale_max": scale_max,
        "source_dequant_nrmse": source_dequant_nrmse,
        "mean_abs_error": absolute_error / elements if elements else 0.0,
        "max_abs_error": max_abs_error,
        "changed_elements_vs_source_fp16": changed_elements_vs_source_fp16,
    }


def canonical_code_sha256(codes) -> str:
    import numpy as np

    matrix = np.asarray(codes, dtype=np.int64)
    header = json.dumps(
        {"shape": list(matrix.shape), "dtype": "int64"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return bytes_sha256(header + b"\n" + matrix.tobytes(order="C"))


def levenshtein_distance(left: list[int], right: list[int]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def code_divergence_metrics(control, fake) -> dict:
    """Summarize two realized [T,16] code matrices without retaining their values."""
    import numpy as np

    control_codes = np.asarray(control, dtype=np.int64)
    fake_codes = np.asarray(fake, dtype=np.int64)
    if (
        control_codes.ndim != 2
        or fake_codes.ndim != 2
        or control_codes.shape[1] != 16
        or fake_codes.shape[1] != 16
    ):
        raise ValueError("realized code matrices must both have shape [T,16]")
    control_steps = int(control_codes.shape[0])
    fake_steps = int(fake_codes.shape[0])
    aligned_steps = min(control_steps, fake_steps)
    overlap_control = control_codes[:aligned_steps]
    overlap_fake = fake_codes[:aligned_steps]
    equal = overlap_control == overlap_fake
    per_codebook = (
        np.mean(equal, axis=0).astype(np.float64).tolist()
        if aligned_steps
        else [0.0] * 16
    )
    frame_equal = np.all(equal, axis=1) if aligned_steps else np.empty(0, dtype=bool)
    common_prefix = 0
    while common_prefix < aligned_steps and bool(frame_equal[common_prefix]):
        common_prefix += 1
    exact_equal = bool(
        control_steps == fake_steps and np.array_equal(control_codes, fake_codes)
    )
    if exact_equal:
        first_divergent_frame = None
    elif common_prefix < aligned_steps:
        first_divergent_frame = common_prefix
    else:
        first_divergent_frame = aligned_steps
    edit_distance = levenshtein_distance(
        control_codes[:, 0].tolist(),
        fake_codes[:, 0].tolist(),
    )
    normalizer = max(control_steps, fake_steps, 1)
    return {
        "control_sha256": canonical_code_sha256(control_codes),
        "fake_sha256": canonical_code_sha256(fake_codes),
        "control_time_steps": control_steps,
        "fake_time_steps": fake_steps,
        "absolute_length_drift": abs(fake_steps - control_steps),
        "time_step_delta": fake_steps - control_steps,
        "relative_length_drift": abs(fake_steps - control_steps)
        / max(control_steps, 1),
        "per_codebook_agreement": per_codebook,
        "first_codebook_agreement": per_codebook[0],
        "full_frame_agreement": (
            float(np.mean(frame_equal)) if aligned_steps else 0.0
        ),
        "element_mismatch_fraction": (
            float(1.0 - np.mean(equal)) if aligned_steps else 0.0
        ),
        "common_prefix_frames": common_prefix,
        "first_divergent_frame": first_divergent_frame,
        "first_codebook_normalized_edit_distance": edit_distance / normalizer,
        "exact_equal": exact_equal,
    }


def _log_softmax(array):
    import numpy as np

    maximum = np.max(array, axis=1, keepdims=True)
    shifted = array - maximum
    return shifted - np.log(np.sum(np.exp(shifted), axis=1, keepdims=True))


def summarize_logit_pair(control_steps, fake_steps, top_k: int = 8) -> dict:
    """Return aggregate distribution drift for aligned raw-logit rows."""
    import numpy as np

    control = np.asarray(control_steps, dtype=np.float64)
    fake = np.asarray(fake_steps, dtype=np.float64)
    if control.ndim != 2 or fake.ndim != 2:
        raise ValueError("logit inputs must both be rank 2")
    if control.shape[1] == 0 or control.shape[1] != fake.shape[1]:
        raise ValueError("logit vocabularies must be equal and non-empty")
    if not np.all(np.isfinite(control)) or not np.all(np.isfinite(fake)):
        raise ValueError("logit inputs contain a non-finite value")
    if not isinstance(top_k, int) or not 1 <= top_k <= control.shape[1]:
        raise ValueError("top_k must fit the frozen vocabulary")
    aligned = min(control.shape[0], fake.shape[0])
    if aligned == 0:
        raise ValueError("at least one aligned logit step is required")
    control = control[:aligned]
    fake = fake[:aligned]
    control_logp = _log_softmax(control)
    fake_logp = _log_softmax(fake)
    control_p = np.exp(control_logp)
    fake_p = np.exp(fake_logp)
    kl = np.sum(control_p * (control_logp - fake_logp), axis=1)
    mixture = 0.5 * (control_p + fake_p)
    mixture_log = np.log(mixture)
    js = 0.5 * (
        np.sum(control_p * (control_logp - mixture_log), axis=1)
        + np.sum(fake_p * (fake_logp - mixture_log), axis=1)
    )
    control_top = np.argpartition(control, -top_k, axis=1)[:, -top_k:]
    fake_top = np.argpartition(fake, -top_k, axis=1)[:, -top_k:]
    retention = [
        len(set(control_top[row].tolist()) & set(fake_top[row].tolist())) / top_k
        for row in range(aligned)
    ]
    control_centered = control - np.mean(control, axis=1, keepdims=True)
    fake_centered = fake - np.mean(fake, axis=1, keepdims=True)
    numerator = float(
        np.sqrt(np.mean((control_centered - fake_centered) ** 2))
    )
    denominator = float(np.sqrt(np.mean(control_centered**2)))
    centered_nrmse = (
        numerator / denominator
        if denominator > 0.0
        else (0.0 if numerator == 0.0 else None)
    )
    return {
        "aligned_steps": int(aligned),
        "control_to_fake_kl_mean": float(np.mean(kl)),
        "jensen_shannon_mean": float(np.mean(js)),
        "top1_agreement": float(
            np.mean(np.argmax(control, axis=1) == np.argmax(fake, axis=1))
        ),
        "top8_retention": float(np.mean(retention)),
        "centered_logit_nrmse": centered_nrmse,
    }


@contextmanager
def temporary_linear_forward_proxy(module, fake_weight, restoration: dict):
    """Override only one Linear instance's forward call; never replace its Parameter."""
    import torch

    if type(module) is not torch.nn.Linear:
        raise ValueError("the frozen target must be an exact torch.nn.Linear")
    marker = "_ab_fake_q8_forward_proxy_active"
    if module.__dict__.get(marker, False):
        raise ValueError("nested fake-Q8 forward proxy is forbidden")
    if (
        not torch.is_tensor(fake_weight)
        or isinstance(fake_weight, torch.nn.Parameter)
        or fake_weight.requires_grad
    ):
        raise ValueError("fake-Q8 proxy weight must be a detached ordinary Tensor")
    original_parameter = module.weight
    original_bias = module.bias
    if (
        fake_weight.shape != original_parameter.shape
        or fake_weight.dtype != original_parameter.dtype
        or fake_weight.device != original_parameter.device
    ):
        raise ValueError("fake-Q8 proxy shape, dtype, or device drift")
    if "forward" in module.__dict__:
        raise ValueError("pre-existing instance-level Linear.forward is forbidden")
    proxy_call_count = 0
    input_contract_exact = True
    input_last_dimensions: set[int] = set()
    input_dtypes: set[str] = set()
    input_devices: set[str] = set()

    def proxy_forward(inputs):
        nonlocal proxy_call_count, input_contract_exact
        valid = (
            torch.is_tensor(inputs)
            and inputs.ndim >= 1
            and inputs.shape[-1] == original_parameter.shape[1]
            and inputs.dtype == original_parameter.dtype
            and inputs.device == original_parameter.device
        )
        if not valid:
            input_contract_exact = False
            raise RuntimeError("fake-Q8 proxy input signature drift")
        proxy_call_count += 1
        input_last_dimensions.add(int(inputs.shape[-1]))
        input_dtypes.add(str(inputs.dtype).removeprefix("torch."))
        input_devices.add(str(inputs.device))
        return torch.nn.functional.linear(inputs, fake_weight, original_bias)

    try:
        setattr(module, marker, True)
        setattr(module, "forward", proxy_forward)
        yield
    finally:
        if "forward" in module.__dict__:
            delattr(module, "forward")
        if marker in module.__dict__:
            delattr(module, marker)
        restoration.update(
            {
                "forward_instance_shadow_restored": (
                    "forward" not in module.__dict__
                ),
                "proxy_marker_removed": marker not in module.__dict__,
                "parameter_identity_preserved": module.weight is original_parameter,
                "bias_identity_preserved": module.bias is original_bias,
                "proxy_call_count": proxy_call_count,
                "proxy_was_exercised": proxy_call_count > 0,
                "proxy_input_contract_exact": input_contract_exact,
                "proxy_input_last_dimensions": sorted(input_last_dimensions),
                "proxy_input_dtypes": sorted(input_dtypes),
                "proxy_input_devices": sorted(input_devices),
            }
        )


@contextmanager
def temporary_instance_override(instance, name: str, value, restoration: dict):
    had_instance_value = name in instance.__dict__
    previous_instance_value = instance.__dict__.get(name)
    try:
        setattr(instance, name, value)
        yield
    finally:
        if had_instance_value:
            setattr(instance, name, previous_instance_value)
        else:
            delattr(instance, name)
        restoration[name] = (
            (name in instance.__dict__) == had_instance_value
            and (
                not had_instance_value
                or instance.__dict__.get(name) is previous_instance_value
            )
        )


def tensor_byte_sha256(tensor) -> str:
    import torch

    cpu = tensor.detach().to(device="cpu").contiguous()
    return bytes_sha256(cpu.view(torch.uint8).numpy().tobytes(order="C"))


def parameter_manifest(model) -> dict:
    rows = []
    total_elements = 0
    for name, parameter in model.named_parameters():
        total_elements += int(parameter.numel())
        rows.append(
            {
                "name": name,
                "object_id": id(parameter),
                "storage_data_ptr": int(parameter.untyped_storage().data_ptr()),
                "storage_offset": int(parameter.storage_offset()),
                "shape": list(parameter.shape),
                "stride": list(parameter.stride()),
                "dtype": str(parameter.dtype).removeprefix("torch."),
                "device": str(parameter.device),
                "requires_grad": bool(parameter.requires_grad),
                "version": int(parameter._version),
            }
        )
    return {
        "parameter_count": len(rows),
        "parameter_elements": total_elements,
        "manifest_sha256": canonical_json_sha256(rows),
    }


def state_key_manifest(model) -> dict:
    keys = list(model.state_dict().keys())
    return {
        "key_count": len(keys),
        "keys_sha256": canonical_json_sha256(keys),
    }


def resolve_module(root, dotted_path: str):
    current = root
    for part in dotted_path.split("."):
        current = current[int(part)] if part.isdigit() else getattr(current, part)
    return current


def verify_model_assets(model_root: Path, policy: dict) -> list[dict]:
    expected = {
        row.get("partition"): row for row in policy.get("source_assets", [])
    }
    verified = []
    for partition, relative_path in ASSET_RELATIVE_PATHS.items():
        row = expected.get(partition)
        path = model_root / relative_path
        if row is None or not path.is_file():
            raise ValueError(f"missing frozen source asset: {partition}")
        observed = {
            "partition": partition,
            "relative_path": str(relative_path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        if (
            observed["bytes"] != row.get("bytes")
            or observed["sha256"] != row.get("sha256")
        ):
            raise ValueError(f"frozen source asset drift: {partition}")
        verified.append(observed)
    return verified


def verify_critical_manifest(
    manifest: dict,
    runtime_root: Path,
    model_root: Path,
    observed_packages: dict,
) -> tuple[list[dict], list[dict]]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected inference-critical manifest schema")
    if manifest.get("packages") != observed_packages:
        raise ValueError("inference-critical package versions do not match")

    def verify_rows(root: Path, rows: list[dict], label: str) -> list[dict]:
        verified = []
        for row in rows:
            relative = Path(row.get("relative_path", ""))
            path = root / relative
            if not path.is_file() or sha256(path) != row.get("sha256"):
                raise ValueError(f"inference-critical {label} drift: {relative}")
            verified.append(
                {
                    "relative_path": str(relative),
                    "sha256": row["sha256"],
                }
            )
        if not verified:
            raise ValueError(f"inference-critical {label} manifest is empty")
        return verified

    return (
        verify_rows(runtime_root, manifest.get("runtime_files", []), "runtime"),
        verify_rows(model_root, manifest.get("model_files", []), "model"),
    )


def functional_package_roots() -> dict[str, Path]:
    roots = {}
    for package in ("qwen_tts", "transformers", "safetensors"):
        specification = importlib.util.find_spec(package)
        if specification is None or specification.origin is None:
            raise ValueError(f"the frozen {package} package is unavailable")
        roots[package] = Path(specification.origin).resolve().parent
    return roots


def verify_functional_runtime_source_pins(
    policy: dict,
    package_roots: dict[str, Path],
) -> list[dict]:
    rows = policy.get("functional_runtime_source_pins", [])
    if len(rows) != 6:
        raise ValueError("expected six functional runtime source pins")
    verified = []
    for row in rows:
        root = package_roots.get(row.get("package"))
        relative = Path(row.get("relative_path", ""))
        if root is None or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid functional runtime source pin")
        path = root / relative
        if (
            not path.is_file()
            or path.stat().st_size != row.get("bytes")
            or sha256(path) != row.get("sha256")
        ):
            raise ValueError(f"functional runtime source drift: {relative}")
        verified.append(
            {
                "package": row["package"],
                "relative_path": str(relative),
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        )
    return verified


def runtime_package_tree_manifest(package_roots: dict[str, Path]) -> dict:
    rows = []
    for package, root in sorted(package_roots.items()):
        for path in sorted(root.rglob("*"), key=lambda item: str(item)):
            relative = str(path.relative_to(root))
            metadata = path.lstat()
            row = {
                "package": package,
                "relative_path": relative,
                "inode": metadata.st_ino,
            }
            if path.is_symlink():
                row.update({"kind": "symlink", "target": os.readlink(path)})
            elif path.is_dir():
                row.update(
                    {
                        "kind": "directory",
                        "mode": oct(metadata.st_mode & 0o777),
                    }
                )
            elif path.is_file():
                row.update(
                    {
                        "kind": "file",
                        "bytes": metadata.st_size,
                        "sha256": sha256(path),
                    }
                )
            else:
                raise ValueError(
                    f"unsupported runtime package entry: {package}/{relative}"
                )
            rows.append(row)
    return {
        "package_roots": {
            package: str(root) for package, root in sorted(package_roots.items())
        },
        "entry_count": len(rows),
        "manifest_sha256": canonical_json_sha256(rows),
    }


def select_case(corpus: dict, case_id: str) -> dict:
    matches = [row for row in corpus.get("cases", []) if row.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one frozen case named {case_id}")
    return matches[0]


def verify_frozen_chain(
    policy: dict,
    gate: dict,
    activation_gate: dict,
    activation_policy: dict,
    manifest: dict,
    corpus: dict,
    input_hashes: dict[str, str],
) -> dict:
    for input_name, expected_hash in EXPECTED_PREREQUISITE_HASHES.items():
        if input_hashes.get(input_name) != expected_hash:
            raise ValueError(f"trusted prerequisite drift: {input_name}")
    if input_hashes.get("policy") != EXPECTED_POLICY_SHA256:
        raise ValueError("execution entry does not trust this policy hash")
    if input_hashes.get("gate") != EXPECTED_GATE_SHA256:
        raise ValueError("execution entry does not trust this gate hash")
    if (
        policy.get("schema") != POLICY_SCHEMA
        or policy.get("status") != "FROZEN_ONE_MODULE_ONE_CASE_SMOKE_ONLY"
    ):
        raise ValueError("one-module functional-sensitivity policy is not frozen")
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != READY_GATE_STATUS:
        raise ValueError("exact one-module fake-Q8 gate is not ready")
    if gate.get("policy_sha256") != input_hashes["policy"]:
        raise ValueError("functional-sensitivity gate does not bind the policy")
    frozen_inputs = policy.get("inputs", {})
    for policy_field, input_name in FROZEN_INPUT_FIELDS.items():
        expected_hash = input_hashes[input_name]
        if (
            frozen_inputs.get(policy_field) != expected_hash
            or gate.get(policy_field) != expected_hash
        ):
            raise ValueError(f"frozen prerequisite hash drift: {policy_field}")
    if gate.get("target") != policy.get("target") or gate.get("case") != policy.get(
        "case"
    ):
        raise ValueError("gate target or case is not the frozen policy target")
    if gate.get("functional_runtime_source_pins") != policy.get(
        "functional_runtime_source_pins"
    ):
        raise ValueError("gate does not bind functional runtime source pins")
    if gate.get("allows_exactly_one_module_one_case_fake_q8_smoke") is not True:
        raise ValueError("gate does not authorize the exact one-trial smoke")
    for field in (
        "allows_weight_mutation",
        "allows_quantized_weight_writing",
        "allows_runtime_candidate_generation",
        "allows_worker_socket_use",
        "allows_audio_decode_write_or_playback",
        "allows_runtime_wiring_fallback_deployment_or_promotion",
    ):
        if gate.get(field) is not False:
            raise ValueError(f"gate authority drift: {field}")
    if (
        activation_gate.get("schema")
        != "agent_bridge.qwen3_tts.activation_calibration_gate.v0"
        or activation_gate.get("status")
        != "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN"
        or activation_gate.get("policy_sha256")
        != input_hashes["activation_policy"]
    ):
        raise ValueError("activation gate does not bind the supplied policy")
    for field in (
        "allows_fake_quant_execution",
        "allows_quantized_weight_writing",
        "allows_runtime_candidate_generation",
        "allows_runtime_wiring_or_promotion",
    ):
        if activation_gate.get(field) is not False:
            raise ValueError(f"activation gate authority drift: {field}")
    authorization = policy.get("authorization", {})
    if (
        authorization.get("allows_exactly_one_module_one_case_fake_q8_smoke")
        is not True
    ):
        raise ValueError("policy does not authorize the exact one-trial smoke")
    for field in FORBIDDEN_AUTHORITY_FIELDS:
        if authorization.get(field) is not False:
            raise ValueError(f"policy authority drift: {field}")
    execution = policy.get("execution", {})
    trial_id = "qwen3-tts-q2-fs-v0-l6-gate-proj-zh-short-neutral-serena-001"
    expected_claim = TRIAL_ROOT / f"{trial_id}.claim.json"
    expected_result = TRIAL_ROOT / f"{trial_id}.result.json"
    expected_trial = {
        "trial_id": trial_id,
        "claim_path": str(expected_claim),
        "result_path": str(expected_result),
        "one_shot_claim_o_excl": True,
        "claim_is_never_automatically_deleted": True,
        "claim_and_result_parent_directory_fsync": True,
        "gate_evaluator_sha256": execution.get("gate_evaluator_sha256"),
    }
    if gate.get("trial") != expected_trial:
        raise ValueError("functional gate does not bind the exact one-shot trial")
    for field, expected in expected_trial.items():
        if execution.get(field) != expected:
            raise ValueError(f"one-shot execution identity drift: {field}")
    gate_evaluator_path = Path(__file__).resolve().with_name(
        "qwen3_functional_sensitivity_gate.py"
    )
    if (
        not gate_evaluator_path.is_file()
        or sha256(gate_evaluator_path)
        != execution.get("gate_evaluator_sha256")
    ):
        raise ValueError("functional gate evaluator source drift")
    if (
        execution.get("processes"),
        execution.get("modules"),
        execution.get("cases"),
        execution.get("fake_trials"),
    ) != (1, 1, 1, 1):
        raise ValueError("policy is not exactly one process/module/case/fake trial")
    if (
        execution.get("device") != "mps"
        or execution.get("runtime_dtype") != "float16"
        or execution.get("do_sample") is not False
        or execution.get("subtalker_dosample") is not False
        or execution.get("audio_decode") is not False
        or execution.get("audio_write") is not False
        or execution.get("explicit_cli_flag") != "--execute-frozen-one-trial"
        or execution.get("max_new_tokens") != 256
    ):
        raise ValueError("frozen execution boundary drift")
    target = policy.get("target", {})
    if (
        target.get("module") != "talker.model.layers.6.mlp.gate_proj"
        or target.get("tensor")
        != "talker.model.layers.6.mlp.gate_proj.weight"
        or target.get("shape") != [6144, 2048]
        or target.get("elements") != 12582912
        or policy.get("case")
        != {
            "id": "zh-short-neutral-serena",
            "speaker": "Serena",
            "language": "Chinese",
        }
    ):
        raise ValueError("trusted exact target or case drift")
    quantizer = policy.get("quantizer", {})
    if (
        quantizer.get("identity")
        != "ab_qwen_quant_groupwise_symmetric_q8_reference_v0"
        or quantizer.get("grouping") != "row-local contiguous C-order groups"
        or quantizer.get("group_size") != 128
        or quantizer.get("scale_math") != "f64 max_abs / 127"
        or quantizer.get("rounding") != "half_away_from_zero"
        or quantizer.get("qmin") != -127
        or quantizer.get("qmax") != 127
        or quantizer.get("dequant_runtime_dtype") != "float16"
        or quantizer.get("no_scale_storage_or_packing_claim") is not True
    ):
        raise ValueError("frozen quantizer identity drift")
    if activation_policy.get("schema") != ACTIVATION_POLICY_SCHEMA:
        raise ValueError("unexpected activation policy schema")
    source_model = activation_policy.get("source_model", {})
    if (
        source_model.get("device") != "mps"
        or source_model.get("runtime_dtype") != "float16"
    ):
        raise ValueError("activation policy does not freeze MPS/float16")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected runtime manifest schema")
    if corpus.get("schema") != CORPUS_SCHEMA:
        raise ValueError("unexpected frozen corpus schema")
    case = select_case(corpus, policy["case"]["id"])
    if (
        case.get("speaker") != policy["case"].get("speaker")
        or policy["case"].get("language") != "Chinese"
    ):
        raise ValueError("frozen case identity drift")
    return case


def _capture_logit_vector(output):
    import torch

    tensor = output[0] if isinstance(output, tuple) else output
    if not torch.is_tensor(tensor) or tensor.ndim not in (2, 3):
        raise RuntimeError("unexpected raw-logit head output")
    last = tensor[:, -1, :] if tensor.ndim == 3 else tensor
    if last.shape[0] != 1:
        raise RuntimeError("frozen logit capture requires batch size one")
    return last[0].detach().to(device="cpu", dtype=torch.float32).numpy().copy()


def _stack_logit_rows(rows: list):
    import numpy as np

    if not rows:
        raise RuntimeError("expected at least one raw-logit row")
    return np.stack(rows, axis=0)


def validate_logit_alignment(time_steps: int, talker, predictors: list) -> dict:
    """Enforce the frozen GenerationMixin T+1/T head-call contract."""
    import numpy as np

    talker_rows = np.asarray(talker)
    predictor_rows = [np.asarray(rows) for rows in predictors]
    if (
        not isinstance(time_steps, int)
        or time_steps <= 0
        or talker_rows.shape != (time_steps + 1, 3072)
        or len(predictor_rows) != 15
        or any(rows.shape != (time_steps, 2048) for rows in predictor_rows)
    ):
        raise ValueError("raw-logit capture violates frozen T+1/T alignment")
    return {
        "talker_observed_steps": int(talker_rows.shape[0]),
        "talker_vocab": int(talker_rows.shape[1]),
        "talker_alignment": "T+1_terminal_or_next_token_inclusive",
        "predictor_observed_steps": [
            int(rows.shape[0]) for rows in predictor_rows
        ],
        "predictor_vocab": [int(rows.shape[1]) for rows in predictor_rows],
        "predictor_alignment": "T_realized_frames_per_head",
        "alignment_contract_exact": True,
    }


def run_token_trial(model, case: dict, max_new_tokens: int, capture_logits: bool) -> dict:
    """Run one greedy pre-codec trial and return transient codes/logits plus summaries."""
    import numpy as np
    import torch

    inner = model.model
    tokenizer = inner.speech_tokenizer
    original_generate = inner.generate
    sample_rate = int(tokenizer.get_output_sample_rate())
    generated_codes: list = []
    decode_codes: list = []
    logit_rows: dict[str, Any] = {
        "talker": [],
        "predictors": [[] for _ in range(15)],
    }
    hook_handles = []
    hooked_modules = [inner.talker.codec_head]
    predictor_heads = list(inner.talker.code_predictor.lm_head)
    if len(predictor_heads) != 15:
        raise RuntimeError("frozen model must expose 15 code-predictor heads")
    hooked_modules.extend(predictor_heads)
    hook_keys_before = [
        list(module._forward_hooks.keys()) for module in hooked_modules
    ]
    restoration: dict[str, bool] = {}
    generate_calls = 0
    decode_intercept_calls = 0

    def capture_generate(*call_args, **call_kwargs):
        nonlocal generate_calls
        codes, hidden_states = original_generate(*call_args, **call_kwargs)
        generate_calls += 1
        generated_codes.extend(
            tensor.detach().to(device="cpu").clone() for tensor in codes
        )
        return codes, hidden_states

    def intercept_decode(items):
        nonlocal decode_intercept_calls
        decode_intercept_calls += 1
        decode_codes.extend(
            item["audio_codes"].detach().to(device="cpu").clone() for item in items
        )
        return [np.empty((0,), dtype=np.float32) for _ in items], sample_rate

    inference_exception = None
    hook_removal_errors = []
    override_attempted = False
    returned_wave_samples = None
    returned_sample_rate = None
    try:
        if capture_logits:
            hook_handles.append(
                inner.talker.codec_head.register_forward_hook(
                    lambda _module, _inputs, output: logit_rows["talker"].append(
                        _capture_logit_vector(output)
                    )
                )
            )
            for index, head in enumerate(predictor_heads):
                hook_handles.append(
                    head.register_forward_hook(
                        lambda _module, _inputs, output, index=index: logit_rows[
                            "predictors"
                        ][index].append(_capture_logit_vector(output))
                    )
                )
        override_attempted = True
        with temporary_instance_override(
            inner,
            "generate",
            capture_generate,
            restoration,
        ), temporary_instance_override(
            tokenizer,
            "decode",
            intercept_decode,
            restoration,
        ):
            with torch.inference_mode():
                wavs, returned_sample_rate = model.generate_custom_voice(
                    text=case["text"],
                    language="Chinese",
                    speaker=case["speaker"],
                    instruct=case.get("instruct") or None,
                    do_sample=False,
                    subtalker_dosample=False,
                    max_new_tokens=max_new_tokens,
                )
            returned_wave_samples = [int(item.shape[0]) for item in wavs]
    except BaseException as error:  # restoration must also cover interrupts.
        inference_exception = error
    finally:
        for handle in reversed(hook_handles):
            try:
                handle.remove()
            except BaseException as error:
                hook_removal_errors.append(f"{type(error).__name__}: {error}")
    hook_keys_after = [
        list(module._forward_hooks.keys()) for module in hooked_modules
    ]
    overrides_restored = (
        (
            restoration.get("generate") is True
            and restoration.get("decode") is True
        )
        if override_attempted
        else True
    )
    hooks_restored = (
        not hook_removal_errors and hook_keys_before == hook_keys_after
    )
    cleanup_proven = overrides_restored and hooks_restored
    boundary = {
        "generate_calls": generate_calls,
        "decode_intercept_calls": decode_intercept_calls,
        "actual_codec_decode_calls": 0,
        "returned_wave_samples": returned_wave_samples,
        "returned_sample_rate": returned_sample_rate,
        "producer_consumer_codes_exact": (
            len(generated_codes) == 1
            and len(decode_codes) == 1
            and torch.equal(generated_codes[0], decode_codes[0])
        ),
        "instance_overrides_restored": restoration,
        "logit_hooks_restored": hooks_restored,
        "hook_removal_errors": hook_removal_errors,
        "cleanup_proven": cleanup_proven,
    }
    boundary_valid = (
        generate_calls != 1
    )
    boundary_valid = not (
        boundary_valid
        or decode_intercept_calls != 1
        or len(generated_codes) != 1
        or len(decode_codes) != 1
        or not boundary["producer_consumer_codes_exact"]
        or list(generated_codes[0].shape)[1:] != [16]
        or generated_codes[0].shape[0] <= 0
        or returned_wave_samples != [0]
        or returned_sample_rate != sample_rate
        or not cleanup_proven
    )
    if inference_exception is not None or not boundary_valid:
        message = (
            f"{type(inference_exception).__name__}: {inference_exception}"
            if inference_exception is not None
            else "pre-codec trial boundary was not proven"
        )
        raise TokenTrialFailure(message, cleanup_proven, boundary)
    codes = generated_codes[0].to(dtype=torch.int64).numpy().copy()
    result = {
        "codes": codes,
        "boundary": boundary,
        "code_summary": {
            "shape": list(codes.shape),
            "time_steps": int(codes.shape[0]),
            "codebooks": int(codes.shape[1]),
            "canonical_sha256": canonical_code_sha256(codes),
            "min": int(codes.min()),
            "max": int(codes.max()),
        },
        "logits": None,
        "logit_capture_summary": None,
    }
    if capture_logits:
        try:
            talker = _stack_logit_rows(logit_rows["talker"])
            predictors = [
                _stack_logit_rows(rows) for rows in logit_rows["predictors"]
            ]
            time_steps = int(codes.shape[0])
            logit_alignment = validate_logit_alignment(
                time_steps,
                talker,
                predictors,
            )
        except BaseException as error:
            raise TokenTrialFailure(
                f"{type(error).__name__}: {error}",
                cleanup_proven,
                boundary,
            ) from error
        result["logits"] = {"talker": talker, "predictors": predictors}
        result["logit_capture_summary"] = logit_alignment
    return result


def aggregate_predictor_logit_metrics(control_rows: list, fake_rows: list) -> dict:
    if len(control_rows) != 15 or len(fake_rows) != 15:
        raise ValueError("predictor logit metrics require all 15 heads")
    per_head = [
        summarize_logit_pair(control, fake, top_k=8)
        for control, fake in zip(control_rows, fake_rows)
    ]
    aligned_total = sum(row["aligned_steps"] for row in per_head)
    aggregate = {"aligned_steps": aligned_total}
    for field in (
        "control_to_fake_kl_mean",
        "jensen_shannon_mean",
        "top1_agreement",
        "top8_retention",
        "centered_logit_nrmse",
    ):
        usable = [
            row for row in per_head if row[field] is not None and row["aligned_steps"]
        ]
        aggregate[field] = (
            sum(row[field] * row["aligned_steps"] for row in usable)
            / sum(row["aligned_steps"] for row in usable)
            if usable
            else None
        )
    return {"aggregate": aggregate, "per_predictor_head": per_head}


def canonical_array_sha256(array) -> str:
    import numpy as np

    value = np.ascontiguousarray(array)
    header = json.dumps(
        {"shape": list(value.shape), "dtype": str(value.dtype)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return bytes_sha256(header + b"\n" + value.tobytes(order="C"))


def control_logit_replay_evidence(control: dict, replay: dict) -> dict:
    import numpy as np

    control_talker = control["talker"]
    replay_talker = replay["talker"]
    control_predictors = control["predictors"]
    replay_predictors = replay["predictors"]
    if len(control_predictors) != 15 or len(replay_predictors) != 15:
        raise ValueError("control replay requires all 15 predictor heads")
    control_talker_sha = canonical_array_sha256(control_talker)
    replay_talker_sha = canonical_array_sha256(replay_talker)
    control_predictor_sha = [
        canonical_array_sha256(rows) for rows in control_predictors
    ]
    replay_predictor_sha = [
        canonical_array_sha256(rows) for rows in replay_predictors
    ]
    talker_exact = control_talker_sha == replay_talker_sha
    predictor_exact = [
        left == right
        for left, right in zip(
            control_predictor_sha,
            replay_predictor_sha,
        )
    ]
    return {
        "exact": talker_exact and all(predictor_exact),
        "talker_exact": talker_exact,
        "predictor_heads_exact": predictor_exact,
        "comparison": "canonical_shape_dtype_and_bytes",
        "control_talker_sha256": control_talker_sha,
        "replay_talker_sha256": replay_talker_sha,
        "control_predictor_sha256": control_predictor_sha,
        "replay_predictor_sha256": replay_predictor_sha,
        "retains_full_logits": False,
    }


def install_signal_guards():
    previous = {}

    def interrupt(signum, _frame):
        raise TrialInterrupted(f"received signal {signum}")

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupt)
    return previous


def restore_signal_guards(previous: dict) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--activation-plan", required=True, type=Path)
    parser.add_argument("--activation-gate", required=True, type=Path)
    parser.add_argument("--activation-capture", required=True, type=Path)
    parser.add_argument("--activation-policy", required=True, type=Path)
    parser.add_argument("--perturbation-scope", required=True, type=Path)
    parser.add_argument("--token-boundary-probe", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--execute-frozen-one-trial", action="store_true")
    args = parser.parse_args()
    if not args.execute_frozen_one_trial:
        parser.error("the frozen one-trial execution flag is required")

    input_paths = {
        "policy": args.policy,
        "gate": args.gate,
        "activation_plan": args.activation_plan,
        "activation_gate": args.activation_gate,
        "activation_capture": args.activation_capture,
        "activation_policy": args.activation_policy,
        "perturbation_scope": args.perturbation_scope,
        "token_boundary_probe": args.token_boundary_probe,
        "runtime_manifest": args.runtime_manifest,
        "corpus": args.corpus,
        "thresholds": args.thresholds,
    }
    if not all(path.is_file() for path in input_paths.values()):
        parser.error("all frozen prerequisite files must exist")
    model_root = args.model.expanduser().resolve()
    if not model_root.is_dir():
        parser.error("--model must be a complete local snapshot directory")

    os.umask(0o077)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    sys.dont_write_bytecode = True
    documents = {}
    input_hashes = {}
    try:
        for name, path in input_paths.items():
            documents[name], input_hashes[name] = load_json_snapshot(path)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    policy = documents["policy"]
    gate = documents["gate"]
    activation_policy = documents["activation_policy"]
    activation_gate = documents["activation_gate"]
    manifest = documents["runtime_manifest"]
    corpus = documents["corpus"]
    try:
        case = verify_frozen_chain(
            policy,
            gate,
            activation_gate,
            activation_policy,
            manifest,
            corpus,
            input_hashes,
        )
        assets_before = verify_model_assets(model_root, policy)
        model_tree_before = model_tree_manifest(model_root, assets_before)
    except ValueError as error:
        parser.error(str(error))

    import numpy as np
    import torch

    observed_packages = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "qwen_tts": importlib.metadata.version("qwen-tts"),
        "transformers": importlib.metadata.version("transformers"),
    }
    try:
        package_roots = functional_package_roots()
        runtime_root = package_roots["qwen_tts"]
        runtime_sources, model_inference_files = verify_critical_manifest(
            manifest,
            runtime_root,
            model_root,
            observed_packages,
        )
        functional_runtime_sources = verify_functional_runtime_source_pins(
            policy,
            package_roots,
        )
        runtime_package_tree_before = runtime_package_tree_manifest(package_roots)
    except ValueError as error:
        parser.error(str(error))
    manifest_boundary = manifest.get("execution_boundary", {})
    if manifest_boundary != {
        "local_snapshot_required": True,
        "device": "mps",
        "runtime_dtype": "float16",
        "network_download_allowed": False,
        "audio_decode_allowed": False,
        "audio_write_allowed": False,
        "weight_mutation_allowed": False,
        "candidate_generation_allowed": False,
        "runtime_wiring_or_promotion_allowed": False,
    }:
        parser.error("inference-critical execution boundary drift")
    if not torch.backends.mps.is_available():
        parser.error("the frozen MPS execution device is unavailable")

    execution = policy["execution"]
    claim_path = Path(execution["claim_path"])
    result_path = Path(execution["result_path"])
    worker_runtime_root = (Path.home() / ".cache" / "agent-bridge" / "qwen3").resolve()
    forbidden_output_roots = [
        model_root,
        worker_runtime_root,
        Path.home() / ".local" / "share" / "agent-bridge",
        Path.home() / "Library" / "Application Support" / "agent-bridge",
        Path.cwd().resolve(),
    ]
    try:
        ensure_owner_trial_directory(TRIAL_ROOT)
        if claim_path.parent != TRIAL_ROOT or result_path.parent != TRIAL_ROOT:
            raise ValueError("one-shot claim/result escaped the frozen trial root")
        validate_output_path(result_path, forbidden_output_roots)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    try:
        lock_stream = acquire_process_lock(LOCK_PATH)
    except ValueError as error:
        parser.error(str(error))
    signals = install_signal_guards()
    try:
        claim_receipt = consume_trial_claim(
            claim_path,
            result_path,
            {
                "trial_id": execution["trial_id"],
                "policy_sha256": input_hashes["policy"],
                "functional_sensitivity_gate_sha256": input_hashes["gate"],
                "harness_sha256": sha256(Path(__file__).resolve()),
                "pid": os.getpid(),
            },
        )
    except (OSError, ValueError) as error:
        restore_signal_guards(signals)
        lock_stream.close()
        parser.error(str(error))

    report = None
    exit_code = 2
    try:
        import qwen_tts
        from qwen_tts import Qwen3TTSModel
        from safetensors import safe_open

        if Path(inspect.getfile(qwen_tts)).resolve().parent != runtime_root:
            raise RuntimeError("imported qwen_tts package root drift")
        model = Qwen3TTSModel.from_pretrained(
            str(model_root),
            device_map="mps",
            dtype=torch.float16,
        )
        inner = model.model
        target_policy = policy["target"]
        target_module = resolve_module(inner, target_policy["module"])
        if type(target_module) is not torch.nn.Linear:
            raise RuntimeError("frozen target did not resolve to an exact Linear")
        if "forward" in target_module.__dict__:
            raise RuntimeError("frozen target has an unexpected instance forward")
        runtime_weight = target_module.weight
        target_forward_shadow_before = "forward" in target_module.__dict__
        if (
            list(runtime_weight.shape) != target_policy["shape"]
            or runtime_weight.numel() != target_policy["elements"]
            or runtime_weight.dtype is not torch.float16
            or str(runtime_weight.device) != "mps:0"
        ):
            raise RuntimeError("loaded target runtime tensor identity drift")
        observed_contract = {
            "talker_layers": len(inner.talker.model.layers),
            "talker_hidden_size": int(inner.config.talker_config.hidden_size),
            "codebooks": int(inner.config.talker_config.num_code_groups),
            "codec_eos_token_id": int(inner.config.talker_config.codec_eos_token_id),
            "sample_rate": int(inner.speech_tokenizer.get_output_sample_rate()),
        }
        if observed_contract != manifest.get("model_contract"):
            raise RuntimeError("loaded model contract drift")

        parameter_before = parameter_manifest(inner)
        state_keys_before = state_key_manifest(inner)
        target_parameter_id = id(runtime_weight)
        target_weight_sha_before = tensor_byte_sha256(runtime_weight)
        talker_asset = model_root / ASSET_RELATIVE_PATHS["talker"]
        with safe_open(talker_asset, framework="pt", device="cpu") as handle:
            source_weight = handle.get_tensor(target_policy["tensor"])
        if (
            str(source_weight.dtype) != "torch.bfloat16"
            or list(source_weight.shape) != target_policy["shape"]
            or source_weight.numel() != target_policy["elements"]
        ):
            raise RuntimeError("frozen BF16 source tensor identity drift")
        source_bf16_sha = tensor_byte_sha256(source_weight)
        source_fp16 = source_weight.to(dtype=torch.float16).contiguous()
        source_fp16_sha = tensor_byte_sha256(source_fp16)
        if source_fp16_sha != target_weight_sha_before:
            raise RuntimeError("runtime FP16 weight is not the exact BF16-to-FP16 source")

        source_numpy = source_weight.to(dtype=torch.float32).numpy()
        quantized = quantize_groupwise_q8_numpy(
            source_numpy,
            policy["quantizer"]["group_size"],
        )
        fake_weight = (
            torch.from_numpy(quantized["dequant"])
            .to(device="mps", dtype=torch.float16)
            .detach()
        )
        if fake_weight.requires_grad or list(fake_weight.shape) != target_policy["shape"]:
            raise RuntimeError("fake-Q8 proxy tensor identity drift")
        quantization_summary = {
            key: value
            for key, value in quantized.items()
            if key not in ("q", "dequant")
        }
        if (
            quantization_summary["dequant_sha256"] == source_fp16_sha
            or quantization_summary["changed_elements_vs_source_fp16"] <= 0
        ):
            raise RuntimeError("frozen fake-Q8 quantizer produced no FP16 perturbation")
        del source_numpy
        del source_fp16
        del quantized

        control_before = None
        fake = None
        control_after = None
        proxy_restoration: dict[str, bool] = {}
        proxy_attempted = False
        proxy_entered = False
        trial_boundary_cleanup_proven = True
        completed_trial_boundaries = []
        failed_trial_boundary = None
        trial_error = None
        try:
            control_before = run_token_trial(
                model,
                case,
                policy["execution"]["max_new_tokens"],
                capture_logits=True,
            )
            completed_trial_boundaries.append(control_before["boundary"])
            proxy_attempted = True
            with temporary_linear_forward_proxy(
                target_module,
                fake_weight,
                proxy_restoration,
            ):
                proxy_entered = True
                fake = run_token_trial(
                    model,
                    case,
                    policy["execution"]["max_new_tokens"],
                    capture_logits=True,
                )
            completed_trial_boundaries.append(fake["boundary"])
            control_after = run_token_trial(
                model,
                case,
                policy["execution"]["max_new_tokens"],
                capture_logits=True,
            )
            completed_trial_boundaries.append(control_after["boundary"])
        except TokenTrialFailure as error:
            trial_boundary_cleanup_proven = error.restoration_proven
            failed_trial_boundary = error.boundary
            trial_error = f"{type(error).__name__}: {error}"
        except BaseException as error:
            trial_error = f"{type(error).__name__}: {error}"

        parameter_after = parameter_manifest(inner)
        state_keys_after = state_key_manifest(inner)
        target_weight_sha_after = tensor_byte_sha256(target_module.weight)
        assets_after = verify_model_assets(model_root, policy)
        model_tree_after = model_tree_manifest(model_root, assets_after)
        runtime_sources_after, model_inference_files_after = verify_critical_manifest(
            manifest,
            runtime_root,
            model_root,
            observed_packages,
        )
        functional_runtime_sources_after = verify_functional_runtime_source_pins(
            policy,
            package_roots,
        )
        runtime_package_tree_after = runtime_package_tree_manifest(package_roots)
        parameter_manifest_exact = parameter_before == parameter_after
        state_keys_exact = state_keys_before == state_keys_after
        target_forward_shadow_after = "forward" in target_module.__dict__
        proxy_cleanup_exact = (
            target_forward_shadow_before == target_forward_shadow_after
            and not target_forward_shadow_after
            and "_ab_fake_q8_forward_proxy_active" not in target_module.__dict__
        )
        proxy_measurement_executed = (
            proxy_restoration.get("proxy_was_exercised") is True
            and proxy_restoration.get("proxy_input_contract_exact") is True
        )
        target_invariants = {
            "parameter_object_identity_exact": id(target_module.weight)
            == target_parameter_id,
            "runtime_weight_byte_sha_exact": target_weight_sha_after
            == target_weight_sha_before,
            "parameter_manifest_exact": parameter_manifest_exact,
            "state_dict_keys_exact": state_keys_exact,
            "source_assets_exact": assets_after == assets_before,
            "model_tree_exact": model_tree_after == model_tree_before,
            "runtime_sources_exact": runtime_sources_after == runtime_sources,
            "model_inference_files_exact": (
                model_inference_files_after == model_inference_files
            ),
            "functional_runtime_sources_exact": (
                functional_runtime_sources_after == functional_runtime_sources
            ),
            "runtime_package_tree_exact": (
                runtime_package_tree_after == runtime_package_tree_before
            ),
            "trial_boundary_cleanup_proven": trial_boundary_cleanup_proven
            and all(
                boundary.get("cleanup_proven") is True
                for boundary in completed_trial_boundaries
            ),
            "forward_proxy_restoration": proxy_restoration,
            "forward_proxy_restored": proxy_cleanup_exact,
            "proxy_measurement_executed": proxy_measurement_executed,
            "proxy_attempted": proxy_attempted,
            "proxy_entered": proxy_entered,
        }
        restoration_proven = all(
            value
            for key, value in target_invariants.items()
            if key
            not in (
                "forward_proxy_restoration",
                "proxy_measurement_executed",
                "proxy_attempted",
                "proxy_entered",
            )
        )
        control_replay = None
        control_logit_replay = None
        fake_divergence = None
        bounded_logits = None
        if control_before is not None and control_after is not None:
            control_replay = code_divergence_metrics(
                control_before["codes"],
                control_after["codes"],
            )
            control_logit_replay = control_logit_replay_evidence(
                control_before["logits"],
                control_after["logits"],
            )
        if control_before is not None and fake is not None:
            fake_divergence = code_divergence_metrics(
                control_before["codes"],
                fake["codes"],
            )
            common_realized_steps = min(
                control_before["codes"].shape[0],
                fake["codes"].shape[0],
            )
            equal_realized_lengths = (
                control_before["codes"].shape[0] == fake["codes"].shape[0]
            )
            terminal_comparison = (
                {
                    "status": "COMPARED_AT_EQUAL_REALIZED_LENGTH",
                    **summarize_logit_pair(
                        control_before["logits"]["talker"][
                            control_before["codes"].shape[0] :
                            control_before["codes"].shape[0] + 1
                        ],
                        fake["logits"]["talker"][
                            fake["codes"].shape[0] : fake["codes"].shape[0] + 1
                        ],
                        top_k=8,
                    ),
                }
                if equal_realized_lengths
                else {
                    "status": "NOT_COMPARED_BECAUSE_REALIZED_LENGTHS_DIFFER",
                    "control_terminal_index": int(
                        control_before["codes"].shape[0]
                    ),
                    "fake_terminal_index": int(fake["codes"].shape[0]),
                }
            )
            bounded_logits = {
                "talker_frame_aligned_first_codebook": summarize_logit_pair(
                    control_before["logits"]["talker"][:common_realized_steps],
                    fake["logits"]["talker"][:common_realized_steps],
                    top_k=8,
                ),
                "talker_terminal_or_next_token_decision": terminal_comparison,
                "code_predictor": aggregate_predictor_logit_metrics(
                    control_before["logits"]["predictors"],
                    fake["logits"]["predictors"],
                ),
                "retains_full_logits": False,
            }

        if not restoration_proven:
            status = FATAL_RESTORATION_STATUS
        elif trial_error is not None:
            status = FAILED_RESTORED_STATUS
        elif not proxy_measurement_executed:
            status = FAILED_RESTORED_STATUS
            trial_error = "fake-Q8 proxy measurement was not exercised"
        elif (
            control_replay is None
            or not control_replay["exact_equal"]
            or control_logit_replay is None
            or not control_logit_replay["exact"]
        ):
            status = CONTROL_BLOCKED_STATUS
        else:
            status = SUCCESS_STATUS
            exit_code = 0
        report = {
            "schema": SCHEMA,
            "status": status,
            "policy_sha256": input_hashes["policy"],
            "functional_sensitivity_gate_sha256": input_hashes["gate"],
            "one_shot_trial": {
                "trial_id": execution["trial_id"],
                "claim": claim_receipt,
                "result_path": str(result_path),
                "claim_is_never_automatically_deleted": True,
            },
            "frozen_inputs": {
                field: input_hashes[name]
                for field, name in FROZEN_INPUT_FIELDS.items()
            },
            "model": str(model_root),
            "model_assets_before": assets_before,
            "model_assets_after": assets_after,
            "model_tree_before": model_tree_before,
            "model_tree_after": model_tree_after,
            "runtime": {
                **observed_packages,
                "qwen_tts_package": str(Path(inspect.getfile(qwen_tts)).resolve()),
                "device": "mps",
                "dtype": "float16",
                "generation_api": "generate_custom_voice",
                "do_sample": False,
                "subtalker_dosample": False,
                "max_new_tokens": policy["execution"]["max_new_tokens"],
                "offline_local_snapshot_only": True,
            },
            "runtime_sources": runtime_sources,
            "runtime_sources_after": runtime_sources_after,
            "functional_runtime_sources": functional_runtime_sources,
            "functional_runtime_sources_after": functional_runtime_sources_after,
            "runtime_package_tree_before": runtime_package_tree_before,
            "runtime_package_tree_after": runtime_package_tree_after,
            "model_inference_files": model_inference_files,
            "model_inference_files_after": model_inference_files_after,
            "model_contract": observed_contract,
            "target": target_policy,
            "case": {
                "id": case["id"],
                "speaker": case["speaker"],
                "language": "Chinese",
                "text_sha256": bytes_sha256(case["text"].encode("utf-8")),
            },
            "quantizer": {
                "identity": policy["quantizer"]["identity"],
                "source_dtype": "bfloat16",
                "runtime_proxy_dtype": "float16",
                "group_size": policy["quantizer"]["group_size"],
                "scale_math": policy["quantizer"]["scale_math"],
                "rounding": policy["quantizer"]["rounding"],
                "qrange": [-127, 127],
                "source_bf16_sha256": source_bf16_sha,
                "source_fp16_sha256": source_fp16_sha,
                **quantization_summary,
                "scale_storage_or_packing_claim": False,
            },
            "trial_order": policy["execution"]["trial_order"],
            "control_before": (
                {
                    "codes": control_before["code_summary"],
                    "boundary": control_before["boundary"],
                    "logit_capture": control_before["logit_capture_summary"],
                }
                if control_before is not None
                else None
            ),
            "fake_q8": (
                {
                    "codes": fake["code_summary"],
                    "boundary": fake["boundary"],
                    "logit_capture": fake["logit_capture_summary"],
                }
                if fake is not None
                else None
            ),
            "control_after": (
                {
                    "codes": control_after["code_summary"],
                    "boundary": control_after["boundary"],
                    "logit_capture": control_after["logit_capture_summary"],
                }
                if control_after is not None
                else None
            ),
            "fake_code_divergence": fake_divergence,
            "bounded_raw_logit_divergence": bounded_logits,
            "control_replay": control_replay,
            "control_logit_replay": control_logit_replay,
            "failed_trial_boundary": failed_trial_boundary,
            "restoration": {
                **target_invariants,
                "parameter_manifest_before": parameter_before,
                "parameter_manifest_after": parameter_after,
                "state_dict_keys_before": state_keys_before,
                "state_dict_keys_after": state_keys_after,
                "target_runtime_weight_sha256_before": target_weight_sha_before,
                "target_runtime_weight_sha256_after": target_weight_sha_after,
                "proven": restoration_proven,
            },
            "trial_error": trial_error,
            "actual_codec_decode_calls": 0,
            "writes_audio": False,
            "mutates_weights": False,
            "writes_quantized_weights": False,
            "creates_runtime_candidate": False,
            "uses_worker_socket": False,
            "allows_additional_fake_q8_trial": False,
            "allows_runtime_wiring_fallback_deployment_or_promotion": False,
            "interpretation": (
                "observational functional sensitivity only; this receipt does not "
                "approve the tensor, a precision, a packed candidate, or runtime use"
            ),
        }
    except BaseException as error:
        # Fail closed. If the model was loaded but the final restoration proof could
        # not be assembled, no positive functional-sensitivity result is emitted.
        if report is None:
            report = {
                "schema": SCHEMA,
                "status": FATAL_RESTORATION_STATUS,
                "policy_sha256": input_hashes["policy"],
                "functional_sensitivity_gate_sha256": input_hashes["gate"],
                "one_shot_trial": {
                    "trial_id": execution["trial_id"],
                    "claim": claim_receipt,
                    "result_path": str(result_path),
                    "claim_is_never_automatically_deleted": True,
                },
                "trial_error": f"{type(error).__name__}: {error}",
                "writes_audio": False,
                "mutates_weights": False,
                "writes_quantized_weights": False,
                "creates_runtime_candidate": False,
                "uses_worker_socket": False,
                "allows_runtime_wiring_fallback_deployment_or_promotion": False,
            }
        exit_code = 2
    finally:
        restore_signal_guards(signals)
        lock_stream.close()

    try:
        exclusive_write_json(result_path, report)
    except (FileExistsError, OSError) as error:
        parser.error(f"exclusive owner-only report write failed: {error}")
    print(
        json.dumps(
            {
                "status": report["status"],
                "target_module": policy["target"]["module"],
                "case_id": policy["case"]["id"],
                "restoration_proven": report.get("restoration", {}).get(
                    "proven", False
                ),
                "fake_codes_exact": (
                    report.get("fake_code_divergence") or {}
                ).get("exact_equal"),
                "trial_error": report.get("trial_error"),
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
