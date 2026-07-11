#!/usr/bin/env python3
"""Adversarial checks for the portfolio-continuity successor v3 preregistration."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "scripts" / "eval"
CONTRACT_PATH = (
    EVAL / "fixtures" / "portfolio_continuity_successor_v3_answer_contract.json"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "reports"
    / "goal-c-u"
    / "2026-07-10-portfolio-continuity-successor-v3-protocol-prereg.md"
)
sys.path.insert(0, str(EVAL))

import portfolio_continuity_successor_v3_trial as trial  # noqa: E402


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expect_rejected(callable_, label: str) -> None:
    try:
        callable_()
    except trial.TrialError:
        return
    raise AssertionError(f"adversarial mutation was accepted: {label}")


def make_receipt(
    contract: dict[str, object],
    contract_sha: str,
    blind: dict[str, object],
    blind_bytes: bytes,
    review: dict[str, object],
    review_bytes: bytes,
    command_bytes: bytes,
    response_bytes: bytes,
    completed_at: int,
) -> dict[str, object]:
    reviewer_slot = str(review["reviewer_slot"])
    roster = {
        row["reviewer_slot"]: row
        for row in contract["review_execution"]["reviewers"]  # type: ignore[index]
    }
    reviewer = roster[reviewer_slot]
    return {
        "schema": trial.REVIEW_RECEIPT_SCHEMA_V3,
        "trial_id": blind["trial_id"],
        "contract_sha256": contract_sha,
        "blind_packet_sha256": blind["blind_packet_sha256"],
        "reviewer_slot": reviewer_slot,
        "provider": reviewer["provider"],
        "model": reviewer["model"],
        "reasoning_effort": reviewer["reasoning_effort"],
        "cli": reviewer["cli"],
        "cli_version": reviewer["cli_version"],
        "command_profile": reviewer["command_profile"],
        "command_sha256": sha256(command_bytes),
        "request_sha256": sha256(
            trial.build_v3_review_request(contract, blind_bytes, reviewer_slot)
        ),
        "raw_response_sha256": sha256(response_bytes),
        "review_sha256": sha256(review_bytes),
        "session_id_sha256": sha256(f"session:{reviewer_slot}".encode()),
        "usage_sha256": sha256(f"usage:{reviewer_slot}".encode()),
        "invocation_index": 1,
        "retry_count": 0,
        "started_at": completed_at - 1,
        "completed_at": completed_at,
        "exit_code": 0,
        "workspace_file_count": 0,
        "workspace_tree_sha256": trial.EMPTY_WORKSPACE_SHA256,
        "model_pinned_in_command": True,
        "reasoning_effort_pinned_in_command": (
            reviewer["reasoning_effort"] != "cli_default"
        ),
        "custodian_generated": True,
        "project_context_loaded": False,
        "mcp_server_count": 0,
        "tool_events_observed": False,
        "conflicts_of_interest": {
            "scheduler_authored_some_evaluated_material": True,
            "provider_overlap_with_generator": reviewer[
                "provider_overlap_with_generator"
            ],
            "model_overlap_with_generator": reviewer["model_overlap_with_generator"],
        },
        "boundary": {
            "private": True,
            "raw_response_private": True,
            "blind_packet_only": True,
            "condition_labels_present": False,
            "self_attestation_used_for_provenance": False,
        },
    }


def validate_receipt(
    receipt: dict[str, object],
    command_bytes: bytes,
    response_bytes: bytes,
    review_bytes: bytes,
    review: dict[str, object],
    blind: dict[str, object],
    blind_bytes: bytes,
    contract: dict[str, object],
    contract_sha: str,
) -> dict[str, object]:
    receipt_bytes = trial.surface.render_json(receipt)
    return trial.validate_v3_review_receipt(
        receipt,
        receipt_bytes,
        command_bytes,
        response_bytes,
        review_bytes,
        review,
        blind,
        blind_bytes,
        contract,
        contract_sha,
    )


def exercise_v3_packet_chain(contract: dict[str, object]) -> None:
    synthetic = copy.deepcopy(contract)
    seed = "a7" * 32
    synthetic["blinding"]["seed_sha256"] = sha256(seed.encode())
    contract_sha = "b" * 64
    contract_commit = "c" * 40
    capture_sha = "d" * 64
    generation_sha = "e" * 64
    condition_ids = [row["condition_id"] for row in synthetic["conditions"]]
    invocation_order = {
        identity: index
        for index, identity in enumerate(
            sorted(
                [
                    (case["case_id"], condition)
                    for case in synthetic["cases"]
                    for condition in condition_ids
                ],
                key=lambda item: trial.generation_order(seed, item[0], item[1]),
            ),
            start=1,
        )
    }
    capture_cases = []
    generation_answers = {}
    blind_cases = []
    map_cases = []
    for case in synthetic["cases"]:
        case_id = case["case_id"]
        question = f"Synthetic question for {case_id}?"
        conditions = {}
        generated = {}
        blind_answers = []
        map_answers = []
        for condition in sorted(
            condition_ids,
            key=lambda value: trial.blind_order(seed, case_id, value),
        ):
            answer = f"Synthetic grounded answer for {case_id}."
            answer_sha = sha256(answer.encode())
            context_sha = sha256(f"context:{case_id}:{condition}".encode())
            answer_identifier = trial.answer_id(seed, case_id, condition)
            conditions[condition] = {
                "context_sha256": context_sha,
                "context_tokens_estimate": 100 if condition == condition_ids[0] else 20,
            }
            generated[condition] = {
                "answer_sha256": answer_sha,
                "context_sha256": context_sha,
                "invocation_index": invocation_order[(case_id, condition)],
            }
            blind_answers.append(
                {"answer_id": answer_identifier, "answer_markdown": answer}
            )
            map_answers.append(
                {
                    "answer_id": answer_identifier,
                    "condition": condition,
                    "answer_sha256": answer_sha,
                    "context_sha256": context_sha,
                }
            )
        opaque_forbidden = [
            {
                "forbidden_claim_id": trial.forbidden_claim_id(seed, case_id, claim_id),
                "claim_id": claim_id,
            }
            for claim_id in case["forbidden_claim_ids"]
        ]
        capture_cases.append(
            {
                **case,
                "prompt": question,
                "conditions": conditions,
            }
        )
        generation_answers[case_id] = generated
        blind_cases.append(
            {
                "case_id": case_id,
                "prompt_class": case["prompt_class"],
                "prompt_variant": case["prompt_variant"],
                "question": question,
                "required_claims": case["required_claims"],
                "optional_claims": case["optional_claims"],
                "forbidden_claim_ids": [
                    row["forbidden_claim_id"] for row in opaque_forbidden
                ],
                "requires_abstention": case["requires_abstention"],
                "answers": blind_answers,
            }
        )
        map_cases.append(
            {
                "case_id": case_id,
                "answers": map_answers,
                "forbidden_claims": opaque_forbidden,
            }
        )
    capture = {
        "trial_id": "synthetic_v3_chain",
        "contract_commit": contract_commit,
        "capture_sha256": capture_sha,
        "cases": capture_cases,
    }
    generation = {
        "generation_sha256": generation_sha,
        "answers": generation_answers,
    }
    blind_packet = {
        "schema": trial.versioned_schema(
            synthetic, trial.BLIND_PACKET_SCHEMA, trial.BLIND_PACKET_SCHEMA_V1
        ),
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": contract_commit,
        "capture_sha256": capture_sha,
        "generation_sha256": generation_sha,
        "review_scale": synthetic["review"],
        "cases": blind_cases,
        "boundary": {
            "condition_labels_present": False,
            "condition_mapping_present": False,
            "raw_context_present": False,
            "owner_review_required": False,
            "fixed_model_reviews_required": True,
            "review_receipts_required": True,
            "required_reviewer_count": 2,
            "unblinding_allowed": False,
        },
    }
    blind_bytes = trial.surface.render_json(blind_packet)
    blind = trial.validate_blind_packet(
        blind_packet,
        blind_bytes,
        synthetic,
        contract_sha,
        capture,
        generation,
    )
    blind_text = blind_bytes.decode()
    assert not any(
        claim_id in blind_text
        for case in synthetic["cases"]
        for claim_id in case["forbidden_claim_ids"]
    )
    mapping_packet = {
        "schema": trial.versioned_schema(
            synthetic, trial.BLIND_MAP_SCHEMA, trial.BLIND_MAP_SCHEMA_V1
        ),
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "capture_sha256": capture_sha,
        "generation_sha256": generation_sha,
        "blind_packet_sha256": sha256(blind_bytes),
        "blind_seed": seed,
        "blind_seed_sha256": sha256(seed.encode()),
        "cases": map_cases,
        "boundary": {
            "mapping_private": True,
            "reviewer_must_not_read_before_review": True,
        },
    }
    mapping = trial.validate_mapping(
        mapping_packet, blind, synthetic, capture, generation
    )
    normalized_reviews = []
    for index, roster_row in enumerate(synthetic["review_execution"]["reviewers"]):
        review_cases = []
        for blind_case in blind["cases"]:
            answers = []
            for blind_answer in blind_case["answers"]:
                answers.append(
                    {
                        "answer_id": blind_answer["answer_id"],
                        "claim_scores": [
                            {"claim_id": claim["claim_id"], "score": 2}
                            for claim in blind_case["required_claims"]
                        ],
                        "currentness": "pass",
                        "unsupported_assertion_count": 0,
                        "usefulness": 4,
                        "notes": "",
                        **(
                            {"abstention_pass": True}
                            if blind_case["requires_abstention"]
                            else {}
                        ),
                    }
                )
            review_cases.append(
                {
                    "case_id": blind_case["case_id"],
                    "answers": answers,
                    "preferred_answer_id": "tie",
                }
            )
        review_packet = {
            "schema": trial.versioned_schema(
                synthetic, trial.REVIEW_SCHEMA, trial.REVIEW_SCHEMA_V1
            ),
            "trial_id": capture["trial_id"],
            "blind_packet_sha256": sha256(blind_bytes),
            "reviewer_slot": roster_row["reviewer_slot"],
            "cases": review_cases,
        }
        normalized_reviews.append(
            trial.validate_review(review_packet, blind, synthetic)
        )
    for normalized in normalized_reviews:
        scored = trial.score_v1_slice(
            synthetic,
            capture,
            mapping,
            normalized,
            {case["case_id"] for case in capture_cases},
        )
        assert scored["case_count"] == 12
    agreement = trial.summarize_v3_review_agreement(
        [
            {
                "review": normalized,
                "reviewer_slot": normalized["reviewer_slot"],
                "provider": roster_row["provider"],
            }
            for normalized, roster_row in zip(
                normalized_reviews,
                synthetic["review_execution"]["reviewers"],
                strict=True,
            )
        ]
    )
    assert agreement["used_for_gate"] is False
    assert all(
        row["agreement_rate"] == 1.0
        for row in agreement["metrics"].values()
        if row["comparison_count"]
    )
    review_records = [
        {
            "review": normalized,
            "review_sha256": sha256(f"review:{index}".encode()),
            "reviewer_sha256": sha256(roster_row["reviewer_slot"].encode()),
            "reviewer_slot": roster_row["reviewer_slot"],
            "provider": roster_row["provider"],
            "model": roster_row["model"],
            "provider_overlap_with_generator": roster_row[
                "provider_overlap_with_generator"
            ],
            "review_receipt_sha256": sha256(f"receipt:{index}".encode()),
            "raw_response_sha256": sha256(f"response:{index}".encode()),
        }
        for index, (normalized, roster_row) in enumerate(
            zip(
                normalized_reviews,
                synthetic["review_execution"]["reviewers"],
                strict=True,
            )
        )
    ]
    with tempfile.TemporaryDirectory(prefix="ab-successor-v3-score-output-") as temporary:
        temporary_path = Path(temporary)
        map_path = temporary_path / "map.json"
        map_path.write_bytes(trial.surface.render_json(mapping_packet))
        output_path = temporary_path / "score.json"
        score = trial.score_trial_v1(
            synthetic,
            contract_sha,
            capture,
            generation,
            blind,
            map_path,
            mapping,
            review_records,
            output_path,
            (map_path,),
            "f" * 64,
        )
        assert score["schema"].endswith(".v3")
        assert score["score_claim_sha256"] == "f" * 64
        assert score["boundary"]["llm_judge"] is True
        assert score["boundary"]["pooled_reviewer_mean_used_for_gate"] is False
        assert score["cross_reviewer_agreement"]["used_for_gate"] is False
        assert output_path.stat().st_mode & 0o777 == 0o600


def main() -> None:
    raw_contract, contract_bytes = trial.read_json(CONTRACT_PATH)
    contract = trial.validate_contract(raw_contract)
    contract_sha = sha256(contract_bytes)
    report = REPORT_PATH.read_text(encoding="utf-8")
    reported = {
        key: re.search(rf"^{key}: ([0-9a-f]{{64}})$", report, re.MULTILINE)
        for key in {
            "contract_sha256",
            "harness_source_sha256",
            "surface_source_sha256",
            "blind_seed_sha256",
            "digest_key_sha256",
            "execution_repo_path_sha256",
        }
    }
    assert all(match is not None for match in reported.values())
    expected_reported = {
        "contract_sha256": contract_sha,
        "harness_source_sha256": raw_contract["harness_source_sha256"],
        "surface_source_sha256": raw_contract["surface_source_sha256"],
        "blind_seed_sha256": raw_contract["blinding"]["seed_sha256"],
        "digest_key_sha256": raw_contract["digest_key_sha256"],
        "execution_repo_path_sha256": raw_contract["execution_repo_path_sha256"],
    }
    assert {
        key: match.group(1) for key, match in reported.items() if match is not None
    } == expected_reported
    assert "NOT EXECUTED" in report
    assert "Gemini is not" in report
    assert contract["version"] == 3
    assert trial.surface.sha256_file(Path(trial.__file__)) == raw_contract[
        "harness_source_sha256"
    ]
    assert trial.surface.sha256_file(Path(trial.surface.__file__)) == raw_contract[
        "surface_source_sha256"
    ]
    exercise_v3_packet_chain(contract)

    expected_execution_path = (
        "/Data/CascadeProjects/.ab-worktrees/"
        "agent-bridge-portfolio-continuity-successor-v3-execution-20260710"
    )
    assert sha256(expected_execution_path.encode()) == contract[
        "execution_repo_path_sha256"
    ]
    seed_path = ROOT / "data" / "portfolio-continuity-successor-v3" / "blind_seed.txt"
    if seed_path.exists():
        seed = seed_path.read_text(encoding="ascii").strip()
        assert re.fullmatch(r"[0-9a-f]{64}", seed)
        assert sha256(seed.encode()) == contract["blinding"]["seed_sha256"]
        assert seed_path.stat().st_mode & 0o777 == 0o600
        assert seed not in report
        assert seed not in CONTRACT_PATH.read_text(encoding="utf-8")

    for case in contract["cases"]:
        opaque = [
            trial.forbidden_claim_id("a" * 64, case["case_id"], claim_id)
            for claim_id in case["forbidden_claim_ids"]
        ]
        assert len(opaque) == len(set(opaque))
        assert all(re.fullmatch(r"forbid_[0-9a-f]{24}", value) for value in opaque)
        assert not set(opaque) & set(case["forbidden_claim_ids"])

    blind_packet = {
        "schema": "synthetic-v3-blind",
        "trial_id": "synthetic_v3",
        "payload": "condition-neutral",
        "cases": [
            {
                "case_id": "synthetic_case",
                "required_claims": [],
                "requires_abstention": True,
                "answers": [{"answer_id": "ans_" + "1" * 24}],
            }
        ],
    }
    blind_bytes = trial.surface.render_json(blind_packet)
    blind = {
        "trial_id": "synthetic_v3",
        "blind_packet_sha256": sha256(blind_bytes),
    }
    for index, roster_row in enumerate(contract["review_execution"]["reviewers"]):
        review = {
            "reviewer_slot": roster_row["reviewer_slot"],
            "cases": {},
        }
        review_bytes = trial.surface.render_json(review)
        response_bytes = review_bytes
        command_bytes = (
            json.dumps({"slot": roster_row["reviewer_slot"], "argv": ["synthetic"]})
            + "\n"
        ).encode()
        receipt = make_receipt(
            contract,
            contract_sha,
            blind,
            blind_bytes,
            review,
            review_bytes,
            command_bytes,
            response_bytes,
            1_900_000_100 + index,
        )
        result = validate_receipt(
            receipt,
            command_bytes,
            response_bytes,
            review_bytes,
            review,
            blind,
            blind_bytes,
            contract,
            contract_sha,
        )
        assert result["reviewer_slot"] == roster_row["reviewer_slot"]

        mutations = {
            "model substitution": ("model", "wrong-model"),
            "request substitution": ("request_sha256", "0" * 64),
            "response substitution": ("raw_response_sha256", "0" * 64),
            "review substitution": ("review_sha256", "0" * 64),
            "retry": ("retry_count", 1),
            "nonempty workspace": ("workspace_file_count", 1),
            "tool event": ("tool_events_observed", True),
            "MCP context": ("mcp_server_count", 1),
            "project context": ("project_context_loaded", True),
        }
        for label, (key, value) in mutations.items():
            mutated = copy.deepcopy(receipt)
            mutated[key] = value
            expect_rejected(
                lambda mutated=mutated: validate_receipt(
                    mutated,
                    command_bytes,
                    response_bytes,
                    review_bytes,
                    review,
                    blind,
                    blind_bytes,
                    contract,
                    contract_sha,
                ),
                label,
            )
        expect_rejected(
            lambda: validate_receipt(
                receipt,
                command_bytes + b"tampered",
                response_bytes,
                review_bytes,
                review,
                blind,
                blind_bytes,
                contract,
                contract_sha,
            ),
            "command substitution",
        )
        reformatted_response = json.dumps(
            json.loads(response_bytes), separators=(",", ":")
        ).encode()
        rebound_response = copy.deepcopy(receipt)
        rebound_response["raw_response_sha256"] = sha256(reformatted_response)
        expect_rejected(
            lambda: validate_receipt(
                rebound_response,
                command_bytes,
                reformatted_response,
                review_bytes,
                review,
                blind,
                blind_bytes,
                contract,
                contract_sha,
            ),
            "response/review semantic-only rebinding",
        )
        mutated_coi = copy.deepcopy(receipt)
        mutated_coi["conflicts_of_interest"]["provider_overlap_with_generator"] = (
            not receipt["conflicts_of_interest"]["provider_overlap_with_generator"]
        )
        expect_rejected(
            lambda: validate_receipt(
                mutated_coi,
                command_bytes,
                response_bytes,
                review_bytes,
                review,
                blind,
                blind_bytes,
                contract,
                contract_sha,
            ),
            "COI substitution",
        )

    contract_mutations = [
        ("reviewer model", ("review_execution", "reviewers", 0, "model"), "other"),
        ("review retry", ("review_execution", "review_retry_limit"), 1),
        ("generator effort", ("generation", "reasoning_effort"), "high"),
        ("self attestation", ("review", "self_attestation_sufficient"), True),
        ("pooled mean", ("conflicts_of_interest", "pooled_reviewer_mean_allowed"), True),
        ("LLM judge denial", ("boundaries", "llm_judge"), False),
    ]
    for label, path, value in contract_mutations:
        mutated = copy.deepcopy(raw_contract)
        cursor = mutated
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = value
        expect_rejected(lambda mutated=mutated: trial.validate_contract(mutated), label)

    source = inspect.getsource(trial._score_trial_core)
    receipt_gate = source.index("validate_v3_review_receipt(")
    score_claim = source.index("claim_v3_score_attempt(")
    unblind = source.index("generation_raw, generation_bytes = read_json(generation_path)")
    assert receipt_gate < score_claim < unblind

    with tempfile.TemporaryDirectory(prefix="ab-successor-v3-score-claim-") as temporary:
        repo = Path(temporary) / "repo"
        repo.mkdir()
        (repo / ".gitignore").write_text("/data\n", encoding="ascii")
        subprocess.run(
            ["git", "init", "-q"], cwd=repo, check=True, capture_output=True
        )
        claim_contract = copy.deepcopy(contract)
        claim_contract["execution_repo_path_sha256"] = sha256(str(repo).encode())
        generation_claims = trial.claim_generation_attempt(
            repo=repo,
            contract=claim_contract,
            contract_sha=contract_sha,
            spec_sha="1" * 64,
            capture_sha="2" * 64,
            attempt=1,
            prior_receipt_sha=None,
            reserved_paths=(repo / "data" / "generation.json",),
        )
        generation_claim = json.loads(generation_claims[-1].read_text(encoding="utf-8"))
        assert generation_claim["schema"].endswith(".v3")
        assert generation_claim["execution_identity_sha256"] == sha256(
            (
                "agent_bridge.portfolio_continuity_answer_attempt_claim.v3\0"
                + contract_sha
            ).encode()
        )
        records = [
            {
                "review": {"reviewer_slot": row["reviewer_slot"]},
                "review_sha256": sha256(f"review:{index}".encode()),
                "review_receipt_sha256": sha256(f"receipt:{index}".encode()),
                "raw_response_sha256": sha256(f"response:{index}".encode()),
            }
            for index, row in enumerate(contract["review_execution"]["reviewers"])
        ]
        claim_path = repo / "data" / "score-claims" / "v3.json"
        claim_sha = trial.claim_v3_score_attempt(
            claim_path,
            repo,
            claim_contract,
            contract_sha,
            blind,
            records,
        )
        assert re.fullmatch(r"[0-9a-f]{64}", claim_sha)
        assert claim_path.stat().st_mode & 0o777 == 0o600
        expect_rejected(
            lambda: trial.claim_v3_score_attempt(
                claim_path,
                repo,
                claim_contract,
                contract_sha,
                blind,
                records,
            ),
            "score replay",
        )

    print("Portfolio continuity successor v3 preregistration verification passed")


if __name__ == "__main__":
    main()
