#!/usr/bin/env python3
"""Deterministic, non-authoritative design probe for L8 adaptive-K v2."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import zlib
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple


KERNEL_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
ROOT_NAME = "hubbard_l8_observable_interval_step_checker.py"
EXPECTED_KERNEL_SHA256 = "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
EXPECTED_ROOT_SHA256 = "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a"
KERNEL_COMMIT = "d7092f453fda63d7c667d981f606f2a8bc08072d"
TICK_DENOMINATOR = 1 << 64
MAXIMUM_DROP_TICKS = TICK_DENOMINATOR // 4000

M_CANDIDATES = tuple(range(65_536, 327_680 + 1, 16_384))
D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496,
    114_688, 122_880, 131_072,
    147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
)

POLICY_CAPS_BASE = {
    "max_candidate_K": 327_680,
    "max_output_terms_if_successful": 327_680,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}

CONFIG = {
    "magnetization": {
        "observable_id": "staggered_magnetization",
        "input_step_index": 3,
        "child_step_index": 4,
        "parent_sources": {
            "hubbard_l8_magnetization_interval_step3_checker.py": "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717",
            "hubbard_l8_magnetization_interval_step3_contract.json": "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387",
            "hubbard_l8_magnetization_interval_step3_template.json": "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6",
        },
        "parent_expected_witness_sha256": "e5a1fec288bbb118fbc56adfa2ee9d21e0e5f4eb49196a7301d70b361c592ff7",
        "boundary_module": "hubbard_l8_magnetization_interval_step3_checker.py",
        "boundary_spec_name": "OUTPUT_CHECKPOINT_SPEC",
        "input_state_sha256": "093e4ccd1df0170afa357a93fd64656ff98e978192f9dc1dc35ef6a4d1a26add",
        "input_expansion_sha256": "3ce27ae55f05b8c2a71577a99f47af8b50563aaf7221f9f4e48b551d902e86ff",
        "input_cumulative_drop_ticks": 1_691_496_669_588_296,
        "input_transition_sha256": "a02d636d4e511f2399ddaa069ba443225bb8259dd8a9e3e5203ca2e21aa7a73d",
        "state_previous_transition_sha256": "019b813fcd2ff64b419d091785b78a9cb57dc3ccd4c35140059fc5e0279fed27",
        "candidates": M_CANDIDATES,
        "output_name": "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json",
    },
    "double_occupancy": {
        "observable_id": "double_occupancy",
        "input_step_index": 2,
        "child_step_index": 3,
        "parent_sources": {
            "hubbard_l8_observable_interval_two_step_checker.py": "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232",
            "hubbard_l8_observable_interval_two_step_contract.json": "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45",
            "hubbard_l8_observable_interval_two_step_template.json": "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1",
        },
        "parent_expected_witness_sha256": "b63bcf3b6b8b920630e639215281cd04c065e5226aa430dd417a5515df8ad623",
        "boundary_module": "hubbard_l8_observable_interval_two_step_checker.py",
        "boundary_spec_name": "DOUBLE_OCCUPANCY_BOUNDARY_2",
        "input_state_sha256": "8a3477bd3c145e95853e411ccdf60f6c23ce674dffa02fa0a1933c578a36979b",
        "input_expansion_sha256": "9376e6a4e2229ec0d995e36dbcf2a509a5dbf2f9bb276154458cb6ebcb91ff80",
        "input_cumulative_drop_ticks": 2_283_149_854_538_588,
        "input_transition_sha256": "57b8396e446f01ee6467ea2dee54a25af8bc257dea58ee5ed2b5abe77647fb71",
        "state_previous_transition_sha256": None,
        "candidates": D_CANDIDATES,
        "output_name": "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json",
    },
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def verify_source(path: Path, expected: str) -> bytes:
    payload = path.read_bytes()
    observed = sha256(payload)
    if observed != expected:
        raise RuntimeError(f"source pin drift for {path.name}: {observed}")
    return payload


def strict_json(raw: bytes) -> Any:
    def pairs(items: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        for key, value in items:
            if key in output:
                raise ValueError(f"duplicate key: {key}")
            output[key] = value
        return output

    return json.loads(
        raw.decode("ascii"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def exact_mask(value: Any) -> int:
    if type(value) is not str:
        raise RuntimeError("mask is not a string")
    parsed = int(value, 16)
    if value != hex(parsed) or parsed < 0 or parsed.bit_length() > 128:
        raise RuntimeError("mask is not canonical")
    return parsed


def exact_decimal(value: Any) -> int:
    if type(value) is not str:
        raise RuntimeError("tick is not a string")
    parsed = int(value)
    if value != str(parsed):
        raise RuntimeError("tick is not canonical")
    return parsed


def boundary_spec(mode: str, modules: Mapping[str, Any]) -> Mapping[str, Any]:
    cfg = CONFIG[mode]
    module = modules[cfg["boundary_module"]]
    if mode == "magnetization":
        return module.OUTPUT_CHECKPOINT_SPEC
    matches = [
        item for item in module.CHECKPOINT_SPECS
        if item["observable_id"] == cfg["observable_id"]
        and item["step_index"] == cfg["input_step_index"]
    ]
    if len(matches) != 1:
        raise RuntimeError("double-occupancy boundary spec is not unique")
    return matches[0]


def load_boundary(
    repo: Path,
    mode: str,
    modules: Mapping[str, Any],
    kernel: Any,
    root: Any,
) -> Tuple[Dict[Tuple[int, int], Tuple[int, int]], Mapping[str, Any], Dict[str, Any]]:
    cfg = CONFIG[mode]
    spec = boundary_spec(mode, modules)
    encoded = (repo / spec["relative_path"]).read_bytes()
    if sha256(encoded) != spec["encoded_sha256"]:
        raise RuntimeError("encoded boundary drift")
    compressed = base64.b85decode(b"".join(encoded.splitlines()))
    if sha256(compressed) != spec["compressed_sha256"]:
        raise RuntimeError("compressed boundary drift")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 67_108_865) + decoder.flush()
    if not decoder.eof or decoder.unused_data or len(raw) > 67_108_864:
        raise RuntimeError("bounded boundary decompression failed")
    if sha256(raw) != spec["raw_sha256"]:
        raise RuntimeError("raw boundary drift")
    payload = strict_json(raw)
    if canonical_bytes(payload) != raw:
        raise RuntimeError("boundary JSON is not canonical")
    if set(payload) != {"format", "state", "state_sha256", "terms"}:
        raise RuntimeError("boundary outer schema drift")
    state = payload["state"]
    if kernel.canonical_sha256(state) != payload["state_sha256"]:
        raise RuntimeError("boundary state digest drift")
    if payload["state_sha256"] != cfg["input_state_sha256"]:
        raise RuntimeError("boundary state pin drift")
    expansion: Dict[Tuple[int, int], Tuple[int, int]] = {}
    previous = None
    for record in payload["terms"]:
        if type(record) is not list or len(record) != 4:
            raise RuntimeError("boundary term schema drift")
        key = exact_mask(record[0]), exact_mask(record[1])
        interval = exact_decimal(record[2]), exact_decimal(record[3])
        if previous is not None and key <= previous:
            raise RuntimeError("boundary term order drift")
        if interval[0] > interval[1] or interval == (0, 0):
            raise RuntimeError("boundary sparse interval drift")
        expansion[key] = interval
        previous = key
    if kernel.tick_digest(expansion) != cfg["input_expansion_sha256"]:
        raise RuntimeError("v2 boundary expansion digest drift")
    if state["expansion_sha256"] != cfg["input_expansion_sha256"]:
        raise RuntimeError("boundary state expansion pin drift")
    if exact_decimal(state["cumulative_dropped_l1_ticks"]) != cfg["input_cumulative_drop_ticks"]:
        raise RuntimeError("boundary cumulative drop drift")
    state_previous_transition = state.get("previous_transition_sha256")
    if state_previous_transition != cfg["state_previous_transition_sha256"]:
        raise RuntimeError("boundary state previous-transition drift")
    expectation = kernel.expectation_ticks(expansion, root._neel_basis())
    stated = (
        exact_decimal(state["retained_Neel_expectation_lower_ticks"]),
        exact_decimal(state["retained_Neel_expectation_upper_ticks"]),
    )
    if expectation != stated:
        raise RuntimeError("v2 boundary expectation drift")
    custody = {
        "relative_path": spec["relative_path"],
        "encoded_sha256": spec["encoded_sha256"],
        "compressed_sha256": spec["compressed_sha256"],
        "raw_sha256": spec["raw_sha256"],
        "state_sha256": payload["state_sha256"],
        "expansion_sha256": state["expansion_sha256"],
        "term_count": len(expansion),
        "input_transition_sha256": cfg["input_transition_sha256"],
        "state_previous_transition_sha256": state_previous_transition,
    }
    return expansion, state, custody


def build_sequence(root: Any, kernel: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    groups = root._independent_groups(root._independent_bonds())
    _forward_stages, _forward_gates, stages, claim = root._sequence_records(groups)
    if claim["backprop_gate_records_sha256"] != "8504eae718b7a670fa71b79c789691e70a59365f0876f8acfdd4ea8dceee2df5":
        raise RuntimeError("backprop sequence drift")
    trig = {}
    trig_records = []
    theta_values = sorted({theta for stage in stages for _, theta in stage["gates"]})
    for theta in theta_values:
        sine, cosine, _record = root._taylor_trig_record(theta)
        trig[theta] = sine, cosine
        trig_records.append({
            "theta": f"{theta.numerator}/{theta.denominator}",
            "sine_ticks": [str(sine[0]), str(sine[1])],
            "cosine_ticks": [str(cosine[0]), str(cosine[1])],
        })
    sequence = {
        "backprop_gate_records_sha256": claim["backprop_gate_records_sha256"],
        "stage_groups": [stage["group"] for stage in stages],
        "stage_count": len(stages),
        "gate_count": sum(len(stage["gates"]) for stage in stages),
        "checkpoint_count": sum(len(stage["gates"]) // 8 for stage in stages),
        "gates_per_checkpoint": 8,
        "trig_records_sha256": kernel.canonical_sha256(trig_records),
        "Neel_basis_sha256": sha256((hex(root._neel_basis()) + "\n").encode("ascii")),
        "Neel_expectation_used_for_K_selection": False,
    }
    if sequence["stage_count"] != 9 or sequence["gate_count"] != 1152 or sequence["checkpoint_count"] != 144:
        raise RuntimeError("fixed sequence geometry drift")
    return stages, trig, sequence


def ranked_suffix_sha256(expansion: Mapping[Any, Any], ranked: Sequence[Any], suffix: Sequence[int]) -> str:
    digest = hashlib.sha256()
    digest.update(b"l8_adaptive_k_v2_ranked_suffix_v1\n")
    for index, key in enumerate(ranked):
        digest.update(
            f"{hex(key[0])},{hex(key[1])},{suffix[index]}\n".encode("ascii")
        )
    digest.update(f"tail,{suffix[-1]}\n".encode("ascii"))
    return digest.hexdigest()


def gate_batch_sha256(batch: Sequence[Any]) -> str:
    records = [
        [hex(generator[0]), hex(generator[1]), f"{theta.numerator}/{theta.denominator}"]
        for generator, theta in batch
    ]
    return sha256(canonical_bytes(records))


def minimum_effective_k(suffix: Sequence[int], slack: int) -> int:
    low, high = 0, len(suffix) - 1
    while low < high:
        middle = (low + high) // 2
        if suffix[middle] <= slack:
            high = middle
        else:
            low = middle + 1
    return low


def enforce_policy_caps(kernel: Any, counter: Any, term_count: int, caps: Mapping[str, int]) -> None:
    if term_count > caps["max_single_expansion_terms"]:
        raise RuntimeError("design policy live-term cap exceeded")
    if term_count > caps["max_digest_terms"]:
        raise RuntimeError("design policy digest cap exceeded")
    checks = {
        "max_term_gate_visits": counter.term_gate_visits,
        "max_expansion_coefficient_tick_bits": counter.maximum_expansion_coefficient_tick_bits,
        "max_product_bits": counter.maximum_product_bits,
    }
    for key, observed in checks.items():
        if observed > caps[key]:
            raise RuntimeError(f"design policy cap exceeded: {key}")
    if counter.window_peak_live_terms > caps["max_single_expansion_terms"]:
        raise RuntimeError("design policy transient live-term cap exceeded")
    for key, value in caps.items():
        kernel_key = {
            "max_candidate_K": "max_retained_K",
            "max_output_terms_if_successful": "max_retained_K",
        }.get(key, key)
        if kernel_key in kernel.RESOURCE_LIMITS and value > kernel.RESOURCE_LIMITS[kernel_key]:
            raise RuntimeError(f"design policy exceeds kernel capability: {key}")


def run(repo: Path, mode: str) -> Dict[str, Any]:
    cfg = CONFIG[mode]
    source_custody = {
        KERNEL_NAME: EXPECTED_KERNEL_SHA256,
        ROOT_NAME: EXPECTED_ROOT_SHA256,
        **cfg["parent_sources"],
    }
    for filename, expected in source_custody.items():
        verify_source(repo / filename, expected)
    kernel = load_module("v2_design_kernel", repo / KERNEL_NAME)
    root = load_module("v2_design_root", repo / ROOT_NAME)
    modules = {
        filename: load_module("v2_design_" + filename.replace(".", "_"), repo / filename)
        for filename in cfg["parent_sources"]
        if filename.endswith(".py")
    }
    root_before = kernel.root_global_snapshot(root)
    expansion, state, custody = load_boundary(repo, mode, modules, kernel, root)
    stages, trig, sequence = build_sequence(root, kernel)
    candidates = tuple(cfg["candidates"])
    caps = dict(POLICY_CAPS_BASE)
    caps["max_candidate_count"] = len(candidates)
    enforce_policy_caps(kernel, kernel.PropagationCounterV2(), len(expansion), caps)
    counter = kernel.PropagationCounterV2()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)
    E_input = cfg["input_cumulative_drop_ticks"]
    cumulative = E_input
    remaining_steps = 100 - cfg["input_step_index"]
    denominator = remaining_steps * 144
    records = []
    selected_history = []
    failure = None
    gate_index = 0
    for stage_index, stage in enumerate(stages):
        for batch_start in range(0, len(stage["gates"]), 8):
            checkpoint_index = len(records)
            checkpoint_number = checkpoint_index + 1
            batch = stage["gates"][batch_start:batch_start + 8]
            if len(batch) != 8:
                raise RuntimeError("partial checkpoint batch")
            input_count = len(expansion)
            input_sha = kernel.tick_digest(expansion)
            visits_before = counter.term_gate_visits
            rounding_before = counter.multiplication_rounding_l1_scaled_ticks_squared
            expansion = kernel.propagate_batch(expansion, batch, trig, counter)
            pre_count = len(expansion)
            enforce_policy_caps(kernel, counter, pre_count, caps)
            pre_sha = kernel.tick_digest(expansion)
            ranked, suffix = kernel.rank_with_suffix(expansion)
            prefix_cap = E_input + checkpoint_number * (MAXIMUM_DROP_TICKS - E_input) // denominator
            slack = prefix_cap - cumulative
            candidate_records, selected_index = kernel.evaluate_candidates(
                pre_count, suffix, candidates, cumulative, prefix_cap
            )
            base = {
                "checkpoint_index_zero_based": checkpoint_index,
                "checkpoint_number_one_based": checkpoint_number,
                "stage_index": stage_index,
                "stage_group": stage["group"],
                "batch_in_stage": batch_start // 8,
                "gate_occurrence_first_zero_based": gate_index,
                "gate_occurrence_last_zero_based": gate_index + 7,
                "gate_batch_sha256": gate_batch_sha256(batch),
                "input_expansion_count": input_count,
                "input_expansion_sha256": input_sha,
                "pretruncation_expansion_count": pre_count,
                "pretruncation_expansion_sha256": pre_sha,
                "ranked_suffix_sha256": ranked_suffix_sha256(expansion, ranked, suffix),
                "budget_prefix_cap_ticks": str(prefix_cap),
                "E_before_ticks": str(cumulative),
                "prefix_slack_before_selection_ticks": str(slack),
                "candidate_records": candidate_records,
                "peak_live_terms_this_checkpoint": counter.window_peak_live_terms,
                "peak_live_terms_cumulative": counter.peak_live_terms,
                "term_gate_visits_increment": counter.term_gate_visits - visits_before,
                "term_gate_visits_cumulative": counter.term_gate_visits,
                "rounding_increment_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared - rounding_before
                ),
                "rounding_cumulative_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                ),
                "maximum_expansion_coefficient_tick_bits": counter.maximum_expansion_coefficient_tick_bits,
                "maximum_product_bits": counter.maximum_product_bits,
            }
            gate_index += 8
            if selected_index is None:
                minimum_K = minimum_effective_k(suffix, slack)
                failure = {
                    **base,
                    "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                    "selected_candidate_index": None,
                    "selected_K": None,
                    "minimum_effective_K_to_meet_prefix": minimum_K,
                    "required_K_excess_over_policy_maximum": max(0, minimum_K - candidates[-1]),
                    "maximum_candidate_drop_excess_over_slack_ticks": str(
                        int(candidate_records[-1]["drop_ticks"]) - slack
                    ),
                }
                records.append(failure)
                break
            retained, truncation = kernel.commit_candidate(
                expansion,
                ranked,
                suffix,
                candidates,
                cumulative,
                prefix_cap,
                selected_index,
            )
            selected_K = candidate_records[selected_index]["configured_K"]
            drop = truncation["dropped_l1_ticks"]
            record = {
                **base,
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": selected_index,
                "selected_K": selected_K,
                "selected_effective_retained_count": truncation["effective_retained_count"],
                "selected_dropped_term_count": truncation["dropped_term_count"],
                "selected_drop_ticks": str(drop),
                "selected_dropped_terms_sha256": truncation["dropped_terms_sha256"],
                "retained_expansion_count": len(retained),
                "retained_expansion_sha256": truncation["retained_expansion_sha256"],
                "minimum_retained_abs_upper_ticks": str(truncation["minimum_retained_abs_upper_ticks"]),
                "maximum_dropped_abs_upper_ticks": str(truncation["maximum_dropped_abs_upper_ticks"]),
                "E_after_ticks": str(cumulative + drop),
            }
            records.append(record)
            selected_history.append(selected_K)
            cumulative += drop
            expansion = retained
        if failure is not None:
            break
    root_after = kernel.root_global_snapshot(root)
    if root_before != root_after:
        raise RuntimeError("root arithmetic globals changed")
    script_sha = sha256(Path(__file__).read_bytes())
    selected_history_sha = kernel.canonical_sha256(selected_history)
    records_sha = kernel.canonical_sha256(records)
    transcript = {
        "schema_version": 1,
        "transcript_fingerprint": "hubbard_l8_adaptive_k_v2_deterministic_design_probe_v1",
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "observable_id": cfg["observable_id"],
        "input_step_index": cfg["input_step_index"],
        "attempted_child_step_index": cfg["child_step_index"],
        "design_probe_source_sha256": script_sha,
        "arithmetic_kernel_commit": KERNEL_COMMIT,
        "source_custody": source_custody,
        "parent_expected_witness_sha256": cfg["parent_expected_witness_sha256"],
        "input_boundary_custody": custody,
        "input_cumulative_drop_ticks": str(E_input),
        "maximum_cumulative_drop_ticks": str(MAXIMUM_DROP_TICKS),
        "remaining_mapped_steps_including_attempt": remaining_steps,
        "future_checkpoint_denominator": denominator,
        "prefix_cap_formula": (
            f"E{cfg['input_step_index']}+floor(q*(B-E{cfg['input_step_index']})/({remaining_steps}*144))"
        ),
        "candidate_K_values": list(candidates),
        "candidate_K_values_sha256": kernel.canonical_sha256(list(candidates)),
        "candidate_policy_precommitted_at_probe_time": False,
        "selection_rule": "first_candidate_whose_exact_ranked_suffix_drop_respects_current_prefix_cap",
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "sequence": sequence,
        "kernel_capability_limits": dict(kernel.RESOURCE_LIMITS),
        "proposed_policy_caps": caps,
        "root_globals_before": root_before,
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "completed_checkpoint_count": len(records) - (1 if failure is not None else 0),
        "failure_checkpoint_included": failure is not None,
        "selected_K_history": selected_history,
        "selected_K_history_sha256": selected_history_sha,
        "records": records,
        "records_sha256": records_sha,
        "failure_record_sha256": kernel.canonical_sha256(failure) if failure is not None else None,
        "last_committed_cumulative_drop_ticks": str(cumulative),
        "observed_peak_single_expansion_terms": counter.peak_live_terms,
        "observed_term_gate_visits_including_failure": counter.term_gate_visits,
        "observed_maximum_expansion_coefficient_tick_bits": counter.maximum_expansion_coefficient_tick_bits,
        "observed_maximum_product_bits": counter.maximum_product_bits,
        "observed_rounding_cumulative_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
        ),
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
    }
    return transcript


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=tuple(CONFIG))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo.resolve(), args.mode)
    raw = canonical_bytes(result)
    output = args.output_dir / CONFIG[args.mode]["output_name"]
    output.write_bytes(raw)
    final_record = result["records"][-1] if result["records"] else None
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "selected_K_history": result["selected_K_history"],
        "final_status": final_record["status"] if final_record else None,
        "failure_minimum_effective_K": (
            final_record.get("minimum_effective_K_to_meet_prefix") if final_record else None
        ),
        "failure_required_K_excess": (
            final_record.get("required_K_excess_over_policy_maximum") if final_record else None
        ),
        "last_committed_cumulative_drop_ticks": result["last_committed_cumulative_drop_ticks"],
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_failure"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
