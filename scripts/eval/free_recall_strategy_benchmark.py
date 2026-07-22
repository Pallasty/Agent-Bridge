#!/usr/bin/env python3
"""Offline public-synthetic memory-strategy benchmark.

This is a strategy-shape experiment inspired by Li et al. (2026), not a
reimplementation of their neural model. It never opens the Agent-Bridge store,
calls MCP, trains a model, or changes retrieval order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.free_recall_strategy_fixture.v0"
REPORT_SCHEMA = "agent_bridge.free_recall_strategy_report.v0"
ARMS = ("content", "scoped_content", "recency", "scaffold", "graph", "router")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != SCHEMA:
        raise ValueError(f"fixture schema must be {SCHEMA}")
    items = value.get("items")
    queries = value.get("queries")
    if not isinstance(items, list) or not items or not isinstance(queries, list) or not queries:
        raise ValueError("fixture requires non-empty items and queries")
    keys = [item["key"] for item in items]
    if len(keys) != len(set(keys)):
        raise ValueError("item keys must be unique")
    key_set = set(keys)
    for item in items:
        if not set(item.get("parents", [])).issubset(key_set):
            raise ValueError(f"{item['key']} has unknown parent")
    for query in queries:
        if not set(query["gold"]).issubset(key_set):
            raise ValueError(f"{query['id']} has unknown gold key")
        if query.get("target") is not None and query["target"] not in key_set:
            raise ValueError(f"{query['id']} has unknown target")
        if query["budget"] <= 0:
            raise ValueError(f"{query['id']} budget must be positive")
    return value


def infer_route(text: str) -> str:
    """Route from request text only; fixture intent is deliberately ignored."""
    lowered = text.lower()
    if re.search(r"为什么|原因|因果|追溯|\bwhy\b|\bcause", lowered):
        return "graph"
    if re.search(r"刚才|做到哪里|下一步|当前锚点|\bcurrent\b|\bnext\b", lowered):
        return "recency"
    if re.search(r"完整|全部|盘点|按顺序|\bcomplete\b|\ball\b|\border", lowered):
        return "scaffold"
    return "content"


def content_rank(items: list[dict[str, Any]], query: dict[str, Any]) -> list[str]:
    """Small deterministic lexical ranker standing in for relevance retrieval."""
    qterms = set(query.get("terms", []))
    document_frequency = Counter(term for item in items for term in set(item["terms"]))
    n = len(items)

    def score(item: dict[str, Any]) -> tuple[float, int, str]:
        overlap = qterms.intersection(item["terms"])
        lexical = sum(math.log((n + 1) / (document_frequency[t] + 1)) + 1 for t in overlap)
        return lexical, item["position"], item["key"]

    ranked = sorted(items, key=score, reverse=True)
    return [item["key"] for item in ranked[: query["budget"]]]


def scoped_content_rank(items: list[dict[str, Any]], query: dict[str, Any]) -> list[str]:
    """Stronger control: relevance receives the same explicit episode scope."""
    scope = query.get("scope")
    scoped = items if scope is None else [item for item in items if item["episode"] == scope]
    return content_rank(scoped, query)


def recency_rank(items: list[dict[str, Any]], query: dict[str, Any]) -> list[str]:
    scoped = [item for item in items if query.get("scope") in (None, item["episode"])]
    ranked = sorted(scoped, key=lambda item: (item["position"], item["key"]), reverse=True)
    return [item["key"] for item in ranked[: query["budget"]]]


def scaffold_rank(items: list[dict[str, Any]], query: dict[str, Any]) -> list[str]:
    scope = query.get("scope")
    if scope is None:
        return []  # fail closed: no stable episode scaffold was supplied
    scoped = [item for item in items if item["episode"] == scope]
    ranked = sorted(scoped, key=lambda item: (item["position"], item["key"]))
    return [item["key"] for item in ranked[: query["budget"]]]


def graph_rank(items: list[dict[str, Any]], query: dict[str, Any]) -> list[str]:
    target = query.get("target")
    scope = query.get("scope")
    if target is None or scope is None:
        return []
    by_key = {item["key"]: item for item in items}
    if target not in by_key or by_key[target]["episode"] != scope:
        return []
    queue = deque(by_key[target].get("parents", []))
    seen: set[str] = set()
    out: list[str] = []
    while queue and len(out) < query["budget"]:
        key = queue.popleft()
        if key in seen:
            continue
        seen.add(key)
        if by_key[key]["episode"] != scope:
            continue
        out.append(key)
        queue.extend(by_key[key].get("parents", []))
    return out


def run_arm(name: str, items: list[dict[str, Any]], query: dict[str, Any]) -> tuple[list[str], str]:
    selected = infer_route(query["text"]) if name == "router" else name
    functions = {
        "content": content_rank,
        "scoped_content": scoped_content_rank,
        "recency": recency_rank,
        "scaffold": scaffold_rank,
        "graph": graph_rank,
    }
    return functions[selected](items, query), selected


def pairwise_order_score(retrieved: list[str], gold: list[str], ordered: bool) -> float:
    if not ordered:
        return 1.0
    present = [key for key in retrieved if key in set(gold)]
    if len(present) < 2:
        return 0.0
    expected = {key: index for index, key in enumerate(gold)}
    pairs = 0
    correct = 0
    for left in range(len(present)):
        for right in range(left + 1, len(present)):
            pairs += 1
            correct += expected[present[left]] < expected[present[right]]
    return correct / pairs if pairs else 0.0


def score_result(retrieved: list[str], query: dict[str, Any]) -> dict[str, float | int]:
    gold = query["gold"]
    gold_set = set(gold)
    hits = sum(key in gold_set for key in retrieved)
    recall = hits / len(gold)
    precision = hits / len(retrieved) if retrieved else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    order = pairwise_order_score(retrieved, gold, query.get("ordered", False))
    task_score = f1 * (0.75 if query.get("ordered") else 1.0)
    if query.get("ordered"):
        task_score += 0.25 * order
    return {
        "hits": hits,
        "returned": len(retrieved),
        "recall": round(recall, 6),
        "precision": round(precision, 6),
        "f1": round(f1, 6),
        "order": round(order, 6),
        "task_score": round(task_score, 6),
    }


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(row[key] for row in rows) / len(rows), 6) if rows else 0.0


def run(fixture: dict[str, Any]) -> dict[str, Any]:
    items = fixture["items"]
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cases: list[dict[str, Any]] = []
    route_hits = 0
    route_hits_by_split: dict[str, int] = defaultdict(int)
    route_total_by_split: dict[str, int] = defaultdict(int)
    oracle_rows: list[dict[str, Any]] = []
    expected_routes = {
        "exhaustive": "scaffold",
        "conditional": "content",
        "causal": "graph",
        "continuity": "recency",
    }
    for query in fixture["queries"]:
        split = query.get("split", "unspecified")
        case = {"id": query["id"], "split": split, "intent": query["intent"], "arms": {}}
        for arm in ARMS:
            retrieved, selected = run_arm(arm, items, query)
            scored = score_result(retrieved, query)
            scored.update({"selected": selected, "retrieved": retrieved})
            case["arms"][arm] = scored
            by_arm[arm].append({"intent": query["intent"], "split": split, **scored})
        expected_route = expected_routes[query["intent"]]
        oracle_retrieved, _ = run_arm(expected_route, items, query)
        oracle_score = score_result(oracle_retrieved, query)
        case["oracle_upper_bound"] = {"selected": expected_route, **oracle_score}
        oracle_rows.append({"split": split, **oracle_score})
        route_match = case["arms"]["router"]["selected"] == expected_route
        route_hits += route_match
        route_hits_by_split[split] += route_match
        route_total_by_split[split] += 1
        cases.append(case)

    summary: dict[str, Any] = {}
    intents = sorted({query["intent"] for query in fixture["queries"]})
    for arm in ARMS:
        rows = by_arm[arm]
        summary[arm] = {
            "macro_f1": mean(rows, "f1"),
            "macro_task_score": mean(rows, "task_score"),
            "mean_recall": mean(rows, "recall"),
            "mean_precision": mean(rows, "precision"),
            "by_intent": {
                intent: {
                    "f1": mean([row for row in rows if row["intent"] == intent], "f1"),
                    "task_score": mean([row for row in rows if row["intent"] == intent], "task_score"),
                }
                for intent in intents
            },
            "by_split": {
                split: {
                    "f1": mean([row for row in rows if row["split"] == split], "f1"),
                    "task_score": mean(
                        [row for row in rows if row["split"] == split], "task_score"
                    ),
                }
                for split in sorted(route_total_by_split)
            },
        }
    summary["router"]["route_accuracy"] = round(route_hits / len(fixture["queries"]), 6)
    summary["router"]["route_accuracy_by_split"] = {
        split: round(route_hits_by_split[split] / total, 6)
        for split, total in sorted(route_total_by_split.items())
    }
    single_best = max(
        (arm for arm in ARMS if arm != "router"),
        key=lambda arm: summary[arm]["macro_task_score"],
    )
    summary["comparison"] = {
        "best_single_arm": single_best,
        "best_single_task_score": summary[single_best]["macro_task_score"],
        "router_task_score": summary["router"]["macro_task_score"],
        "router_lift": round(
            summary["router"]["macro_task_score"] - summary[single_best]["macro_task_score"], 6
        ),
        "oracle_router_upper_bound": mean(oracle_rows, "task_score"),
        "router_to_oracle_gap": round(
            mean(oracle_rows, "task_score") - summary["router"]["macro_task_score"], 6
        ),
    }
    return {
        "schema": REPORT_SCHEMA,
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": hashlib.sha256(canonical_bytes(fixture)).hexdigest(),
        "public_synthetic": True,
        "read_only": True,
        "trained_model": False,
        "calls_memory_search": False,
        "changes_default_search_order": False,
        "summary": summary,
        "cases": cases,
    }


def selftest(fixture: dict[str, Any], report: dict[str, Any]) -> None:
    # Router must not read the gold intent label.
    relabelled = json.loads(json.dumps(fixture))
    for query in relabelled["queries"]:
        query["intent"] = {
            "exhaustive": "conditional",
            "conditional": "causal",
            "causal": "continuity",
            "continuity": "exhaustive",
        }[query["intent"]]
    for original, changed in zip(fixture["queries"], relabelled["queries"]):
        original_keys, _ = run_arm("router", fixture["items"], original)
        changed_keys, _ = run_arm("router", relabelled["items"], changed)
        if original_keys != changed_keys:
            raise AssertionError("router leaked fixture intent label")

    # Input order must not matter; every arm has explicit deterministic ties.
    reversed_fixture = json.loads(json.dumps(fixture))
    reversed_fixture["items"].reverse()
    reversed_report = run(reversed_fixture)
    if report["summary"] != reversed_report["summary"] or report["cases"] != reversed_report["cases"]:
        raise AssertionError("benchmark depends on fixture item order")

    # Structured strategies must abstain rather than silently widen authority.
    no_scope = {**fixture["queries"][0], "scope": None}
    no_target = {**fixture["queries"][2], "target": None}
    if scaffold_rank(fixture["items"], no_scope):
        raise AssertionError("scaffold did not fail closed without episode scope")
    if graph_rank(fixture["items"], no_target):
        raise AssertionError("graph did not fail closed without causal target")
    graph_no_scope = {**fixture["queries"][2], "scope": None}
    if graph_rank(fixture["items"], graph_no_scope):
        raise AssertionError("graph did not fail closed without episode scope")
    cross_scope_items = json.loads(json.dumps(fixture["items"]))
    for item in cross_scope_items:
        if item["key"] == "release.r6":
            item["parents"].insert(0, "world.w7")
    if "world.w7" in graph_rank(cross_scope_items, fixture["queries"][2]):
        raise AssertionError("graph traversed a parent outside the query scope")

    summary = report["summary"]
    if summary["scaffold"]["by_intent"]["exhaustive"]["task_score"] != 1.0:
        raise AssertionError("scaffold falsifier failed")
    if summary["content"]["by_intent"]["conditional"]["f1"] != 1.0:
        raise AssertionError("content falsifier failed")
    if summary["graph"]["by_intent"]["causal"]["f1"] != 1.0:
        raise AssertionError("graph falsifier failed")
    if summary["recency"]["by_intent"]["continuity"]["f1"] != 1.0:
        raise AssertionError("recency falsifier failed")
    if summary["router"]["route_accuracy_by_split"].get("calibration") != 1.0:
        raise AssertionError("router calibration classification failed")
    if summary["router"]["route_accuracy_by_split"].get("paraphrase_challenge", 1.0) >= 1.0:
        raise AssertionError("paraphrase challenge failed to expose router brittleness")
    if summary["comparison"]["router_lift"] < 0.10:
        raise AssertionError("router did not clear the preregistered synthetic lift floor")


def main() -> int:
    default_fixture = Path(__file__).with_name("fixtures") / "free_recall_strategy_benchmark_v0.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=default_fixture)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    report = run(fixture)
    if args.selftest:
        selftest(fixture, report)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
