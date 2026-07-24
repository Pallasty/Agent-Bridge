#!/usr/bin/env python3
"""Public-synthetic R3 prospective episode-sidecar admission benchmark."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.episode_observation.v0"
REPORT_SCHEMA = "agent_bridge.free_recall_strategy_r3_report.v0"
SEED = 20260721
EPISODES = 24
ITEMS_PER_EPISODE = 8
VOCABULARY = 64
SOURCES = ("session", "curation_batch", "owner_bundle")


class ContractError(RuntimeError):
    pass


def canonical(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def episode_name(index: int) -> str:
    return f"synthetic-episode-{index:02d}"


def item_name(episode: int, position: int) -> str:
    return f"synthetic-occurrence-{episode:02d}-{position:02d}"


def make_event(event_id: str, episode_id: str, event_type: str, **payload: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "event_id": event_id,
        "episode_id": episode_id,
        "type": event_type,
        **payload,
    }


def generate_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for episode in range(EPISODES):
        episode_id = episode_name(episode)
        events.append(
            make_event(
                f"event-{episode:02d}-open",
                episode_id,
                "episode.open",
                source=SOURCES[episode % len(SOURCES)],
            )
        )
        for position in range(ITEMS_PER_EPISODE):
            vocabulary_id = (episode * 5 + position * 7) % VOCABULARY
            events.append(
                make_event(
                    f"event-{episode:02d}-item-{position:02d}",
                    episode_id,
                    "episode.item",
                    item_id=item_name(episode, position),
                    episode_position=position,
                    content_variant=f"v{(vocabulary_id + episode + position) % 4}",
                    vocabulary_id=vocabulary_id,
                )
            )
        events.append(
            make_event(
                f"event-{episode:02d}-close",
                episode_id,
                "episode.close",
                item_count=ITEMS_PER_EPISODE,
            )
        )
    return events


def basic_event_valid(event: dict[str, Any]) -> bool:
    required = {"schema", "event_id", "episode_id", "type"}
    if set(event) < required or event.get("schema") != SCHEMA:
        return False
    if not all(isinstance(event.get(field), str) and event[field] for field in ("event_id", "episode_id")):
        return False
    kind = event.get("type")
    if kind == "episode.open":
        return event.get("source") in SOURCES
    if kind == "episode.item":
        return (
            isinstance(event.get("item_id"), str)
            and bool(event["item_id"])
            and isinstance(event.get("episode_position"), int)
            and not isinstance(event["episode_position"], bool)
            and event["episode_position"] >= 0
            and isinstance(event.get("content_variant"), str)
            and isinstance(event.get("vocabulary_id"), int)
        )
    if kind == "episode.close":
        return (
            isinstance(event.get("item_count"), int)
            and not isinstance(event["item_count"], bool)
            and event["item_count"] > 0
        )
    return False


def reduce_events(events: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Fold an unordered event multiset into finalized episode bundles."""
    by_event: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    malformed_episodes: set[str] = set()
    for event in events:
        episode_id = event.get("episode_id")
        if not basic_event_valid(event):
            if isinstance(episode_id, str) and episode_id:
                malformed_episodes.add(episode_id)
            continue
        by_event[event["event_id"]][canonical(event)] = event

    canonical_events: list[dict[str, Any]] = []
    for variants in by_event.values():
        if len(variants) != 1:
            malformed_episodes.update(event["episode_id"] for event in variants.values())
            continue
        canonical_events.append(next(iter(variants.values())))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in canonical_events:
        grouped[event["episode_id"]].append(event)

    finalized: dict[str, tuple[str, ...]] = {}
    for episode_id in sorted(grouped):
        if episode_id in malformed_episodes:
            continue
        rows = grouped[episode_id]
        opens = {canonical(row) for row in rows if row["type"] == "episode.open"}
        closes = {canonical(row) for row in rows if row["type"] == "episode.close"}
        if len(opens) != 1 or len(closes) != 1:
            continue
        close = json.loads(next(iter(closes)))
        items = [row for row in rows if row["type"] == "episode.item"]
        positions = [row["episode_position"] for row in items]
        item_ids = [row["item_id"] for row in items]
        if len(set(positions)) != len(positions) or len(set(item_ids)) != len(item_ids):
            continue
        if sorted(positions) != list(range(close["item_count"])):
            continue
        ordered = tuple(
            row["item_id"] for row in sorted(items, key=lambda row: row["episode_position"])
        )
        finalized[episode_id] = ordered
    return finalized


def truth() -> dict[str, tuple[str, ...]]:
    return {
        episode_name(episode): tuple(
            item_name(episode, position) for position in range(ITEMS_PER_EPISODE)
        )
        for episode in range(EPISODES)
    }


def membership_metrics(
    observed: dict[str, tuple[str, ...]], expected: dict[str, tuple[str, ...]]
) -> dict[str, float | int]:
    observed_members = {(episode, item) for episode, items in observed.items() for item in items}
    expected_members = {(episode, item) for episode, items in expected.items() for item in items}
    tp = len(observed_members & expected_members)
    precision = tp / len(observed_members) if observed_members else 0.0
    recall = tp / len(expected_members) if expected_members else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    correct_positions = sum(
        1
        for episode, items in observed.items()
        for position, item in enumerate(items)
        if episode in expected
        and position < len(expected[episode])
        and expected[episode][position] == item
    )
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "position_accuracy": round(
            correct_positions / len(expected_members) if expected_members else 0.0, 6
        ),
        "finalized_episodes": len(observed),
    }


def baseline_page(episode: int) -> list[str]:
    page = [item_name(episode, 0)]
    for offset in range(1, ITEMS_PER_EPISODE):
        distractor_episode = (episode + offset) % EPISODES
        page.append(item_name(distractor_episode, offset))
    return page


def expand_page(
    baseline: list[str], finalized: dict[str, tuple[str, ...]]
) -> tuple[list[str], bool]:
    seed = baseline[0]
    matches = [items for items in finalized.values() if seed in items]
    if len(matches) != 1:
        return list(baseline), False
    return list(matches[0]), True


def set_recall(page: list[str], expected: tuple[str, ...]) -> float:
    return len(set(page) & set(expected)) / len(expected)


def recall_metrics(finalized: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    baseline_scores: list[float] = []
    sidecar_scores: list[float] = []
    regressions = 0
    expansions = 0
    for episode in range(EPISODES):
        expected = truth()[episode_name(episode)]
        baseline = baseline_page(episode)
        sidecar, expanded = expand_page(baseline, finalized)
        if len(sidecar) != ITEMS_PER_EPISODE:
            raise ContractError("fixed budget violated")
        base_score = set_recall(baseline, expected)
        sidecar_score = set_recall(sidecar, expected)
        baseline_scores.append(base_score)
        sidecar_scores.append(sidecar_score)
        expansions += int(expanded)
        regressions += int(sidecar_score < base_score)
    baseline_mean = sum(baseline_scores) / len(baseline_scores)
    sidecar_mean = sum(sidecar_scores) / len(sidecar_scores)
    return {
        "baseline_set_recall_at_8": round(baseline_mean, 6),
        "sidecar_set_recall_at_8": round(sidecar_mean, 6),
        "lift": round(sidecar_mean - baseline_mean, 6),
        "expanded_pages": expansions,
        "regressions": regressions,
        "budget": ITEMS_PER_EPISODE,
    }


def changed_episode(events: list[dict[str, Any]], episode: int, mutation: str) -> list[dict[str, Any]]:
    rows = copy.deepcopy(events)
    target = episode_name(episode)
    if mutation == "missing_item":
        return [
            row
            for row in rows
            if not (
                row["episode_id"] == target
                and row["type"] == "episode.item"
                and row["episode_position"] == 3
            )
        ]
    if mutation == "duplicate_position":
        for row in rows:
            if row["episode_id"] == target and row["type"] == "episode.item" and row["episode_position"] == 4:
                row["episode_position"] = 3
                return rows
    if mutation == "duplicate_item":
        prior = item_name(episode, 3)
        for row in rows:
            if row["episode_id"] == target and row["type"] == "episode.item" and row["episode_position"] == 4:
                row["item_id"] = prior
                return rows
    if mutation == "conflicting_event_id":
        conflict = next(
            copy.deepcopy(row)
            for row in rows
            if row["episode_id"] == target and row["type"] == "episode.item"
        )
        conflict["content_variant"] = "conflict"
        rows.append(conflict)
        return rows
    if mutation == "missing_open":
        return [row for row in rows if not (row["episode_id"] == target and row["type"] == "episode.open")]
    if mutation == "missing_close":
        return [row for row in rows if not (row["episode_id"] == target and row["type"] == "episode.close")]
    raise ContractError(f"unknown mutation: {mutation}")


def malformed_metrics(events: list[dict[str, Any]], expected: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    clean_hashes = {episode: digest(items) for episode, items in expected.items()}
    for index, mutation in enumerate(
        (
            "missing_item",
            "duplicate_position",
            "duplicate_item",
            "conflicting_event_id",
            "missing_open",
            "missing_close",
        )
    ):
        target = episode_name(index)
        reduced = reduce_events(changed_episode(events, index, mutation))
        unaffected = {
            episode: digest(items)
            for episode, items in reduced.items()
            if episode != target
        }
        expected_unaffected = {
            episode: row_hash for episode, row_hash in clean_hashes.items() if episode != target
        }
        baseline = baseline_page(index)
        page, expanded = expand_page(baseline, reduced)
        scenarios[mutation] = {
            "target_abstained": target not in reduced,
            "unrelated_episodes_unchanged": unaffected == expected_unaffected,
            "page_equals_baseline": page == baseline,
            "expanded": expanded,
            "partial_membership_leaked": target in reduced,
        }
    return scenarios


def ambiguous_seed_falsifier(expected: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    modified = dict(expected)
    shared = expected[episode_name(0)][0]
    second = list(modified[episode_name(1)])
    second[0] = shared
    modified[episode_name(1)] = tuple(second)
    baseline = baseline_page(0)
    page, expanded = expand_page(baseline, modified)
    return {"abstained": not expanded, "page_equals_baseline": page == baseline}


def run() -> dict[str, Any]:
    events = generate_events()
    expected = truth()
    rng = random.Random(SEED)
    shuffled = copy.deepcopy(events)
    rng.shuffle(shuffled)
    duplicated = copy.deepcopy(events) + [copy.deepcopy(row) for row in events[::5]]
    close_first = sorted(
        copy.deepcopy(events),
        key=lambda row: {"episode.close": 0, "episode.item": 1, "episode.open": 2}[row["type"]],
    )
    content_permuted = copy.deepcopy(events)
    for row in content_permuted:
        if row["type"] == "episode.item":
            row["content_variant"] = f"permuted-{3 - int(row['content_variant'][1:])}"

    streams = {
        "original": events,
        "reversed": list(reversed(copy.deepcopy(events))),
        "shuffled": shuffled,
        "duplicated": duplicated,
        "close_first": close_first,
        "content_permuted": content_permuted,
    }
    reduced = {name: reduce_events(rows) for name, rows in streams.items()}
    reference = reduced["original"]
    metamorphic = {
        name: {
            "bundle_hash": digest(bundle),
            "equals_original": bundle == reference,
        }
        for name, bundle in reduced.items()
    }
    membership = membership_metrics(reference, expected)
    recall = recall_metrics(reference)
    malformed = malformed_metrics(events, expected)
    ambiguous = ambiguous_seed_falsifier(expected)
    gates = {
        "membership": all(
            membership[field] == 1.0
            for field in ("precision", "recall", "f1", "position_accuracy")
        ),
        "metamorphic": all(row["equals_original"] for row in metamorphic.values()),
        "fail_closed": all(
            row["target_abstained"]
            and row["unrelated_episodes_unchanged"]
            and row["page_equals_baseline"]
            and not row["expanded"]
            and not row["partial_membership_leaked"]
            for row in malformed.values()
        ),
        "recall_lift": recall["lift"] >= 0.50 and recall["regressions"] == 0,
        "fixed_budget": recall["budget"] == ITEMS_PER_EPISODE,
        "ambiguous_seed_abstains": ambiguous["abstained"] and ambiguous["page_equals_baseline"],
    }
    return {
        "schema": REPORT_SCHEMA,
        "status": "PUBLIC_SYNTHETIC_COMPLETE_NO_RUNTIME_AUTHORITY",
        "fixture_seed": SEED,
        "episodes": EPISODES,
        "items_per_episode": ITEMS_PER_EPISODE,
        "vocabulary_size": VOCABULARY,
        "event_count": len(events),
        "membership": membership,
        "recall": recall,
        "metamorphic": metamorphic,
        "malformed": malformed,
        "ambiguous_seed": ambiguous,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def selftest() -> None:
    first = run()
    second = run()
    if first != second:
        raise AssertionError("determinism drift")
    if not first["all_gates_pass"]:
        raise AssertionError(json.dumps(first["gates"], sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = run()
    if args.selftest:
        selftest()
        print("selftest: PASS")
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif not args.selftest:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
