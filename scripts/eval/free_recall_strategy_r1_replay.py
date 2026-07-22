#!/usr/bin/env python3
"""R1 frozen-snapshot replay for task-conditioned AB retrieval strategies.

The source SQLite connection is read-only. Every memory_search call targets a
disposable clone selected through AGENT_BRIDGE_DB. The committed result is
aggregate-only: no memory content, raw query, embedding, or database is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPORT_SCHEMA = "agent_bridge.free_recall_strategy_r1_report.v0"
MODES = ("fts", "hybrid", "semantic")
BUDGET = 20
SEED_COUNT = 10
RRF_K = 60
FIXTURES = {
    "retrieval": (
        "retrieval_pairs.json",
        "26dd84b7caab2161adab3cef3c6c41e5e747cc1f7ab38ec15d16e7d4abd9a362",
    ),
    "relational": (
        "relational_pairs.json",
        "a9fbb4b5d33c26843966b24e5d1c2f399e8aa88ae62ef4cfb178b44557e44375",
    ),
    "synthesis": (
        "synthesis_queries.json",
        "b4eb4bc7b977c4df3773478eed68c763331a2e161088e4f27485cc2bc04b5522",
    ),
}
ARMS = (
    "content_hybrid",
    "multimode_rrf",
    "temporal_adjacency",
    "graph_expansion",
    "text_router",
    "oracle_router_upper_bound",
)
KEY_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_:.\-]*[A-Za-z0-9_]")


class ReplayError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def load_cases(eval_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    fixture_dir = eval_dir / "fixtures"
    cases: list[dict[str, Any]] = []
    observed_hashes: dict[str, str] = {}
    for task_class, (name, expected_sha) in FIXTURES.items():
        path = fixture_dir / name
        observed = sha256_file(path)
        if observed != expected_sha:
            raise ReplayError(f"fixture hash drift: {name}")
        observed_hashes[name] = observed
        value = json.loads(path.read_text(encoding="utf-8"))
        if task_class in {"retrieval", "relational"}:
            for index, pair in enumerate(value["pairs"], start=1):
                accepted = pair.get("expected_any") or [pair["expected_key"]]
                cases.append(
                    {
                        "id": f"Q-{task_class[:3].upper()}-{pair.get('id') or index}",
                        "task_class": task_class,
                        "query": pair["query"],
                        "gold": list(accepted),
                    }
                )
        else:
            for index, query in enumerate(value["queries"], start=1):
                cases.append(
                    {
                        "id": f"Q-SYN-{query.get('id') or index}",
                        "task_class": "synthesis",
                        "query": query["query"],
                        "gold": list(query["gold_set"]),
                    }
                )
    return cases, observed_hashes


def all_gold(cases: list[dict[str, Any]]) -> set[str]:
    return {key for case in cases for key in case["gold"]}


def read_only_backup(source: Path, destination: Path) -> tuple[int, int]:
    source_uri = source.resolve().as_uri() + "?mode=ro"
    source_db = sqlite3.connect(source_uri, uri=True)
    before = source_db.total_changes
    try:
        source_db.execute("PRAGMA query_only=ON")
        dest_db = sqlite3.connect(destination)
        try:
            source_db.backup(dest_db)
        finally:
            dest_db.close()
    finally:
        after = source_db.total_changes
        source_db.close()
    if before != 0 or after != 0:
        raise ReplayError("source connection recorded an unexpected write")
    return before, after


def clone_snapshot(source: Path, destination: Path) -> None:
    command = (
        ["cp", "-c", str(source), str(destination)]
        if os.uname().sysname == "Darwin"
        else ["cp", "--reflink=auto", str(source), str(destination)]
    )
    completed = subprocess.run(command, capture_output=True, check=False, timeout=60)
    if completed.returncode != 0:
        shutil.copy2(source, destination)


def active_gold_state(db_path: Path, keys: set[str]) -> dict[str, Any]:
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        placeholders = ",".join("?" for _ in keys)
        rows = dict(
            db.execute(
                f"SELECT key, status FROM memories WHERE key IN ({placeholders})",
                tuple(sorted(keys)),
            )
        )
    finally:
        db.close()
    return {
        "fixture_key_count": len(keys),
        "present_count": len(rows),
        "active_count": sum(status == "active" for status in rows.values()),
        "missing_count": len(keys - set(rows)),
        "non_active_count": sum(status != "active" for status in rows.values()),
    }


class McpClient:
    def __init__(self, binary: Path, snapshot: Path, stderr_path: Path):
        env = os.environ.copy()
        env.update(
            {
                "AGENT_BRIDGE_DB": str(snapshot),
                "AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS": "eval",
                "AB_BIOCORTEX_RETRIEVAL_DISABLE": "1",
                "AGENT_BRIDGE_SEED_BOOST_DISABLE": "1",
                "AGENT_BRIDGE_OUTCOME_COLLECTOR": "0",
            }
        )
        self.stderr_handle = stderr_path.open("wb")
        self.proc = subprocess.Popen(
            [str(binary), "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr_handle,
            text=True,
            env=env,
        )
        self.request_id = 0
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "free-recall-r1", "version": "0"},
            },
        )
        assert self.proc.stdin is not None
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self.proc.stdin.flush()

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
            )
            + "\n"
        )
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise ReplayError("unexpected EOF from MCP child")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == self.request_id:
                if "error" in message:
                    raise ReplayError(f"MCP error: {message['error']}")
                return message["result"]

    def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, float]:
        start = time.perf_counter()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        elapsed_ms = (time.perf_counter() - start) * 1000
        content = result.get("content", [])
        if not content or content[0].get("type") != "text":
            raise ReplayError(f"{name} returned no text result")
        return content[0]["text"], elapsed_ms

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=5)
        finally:
            self.stderr_handle.close()


def parse_search_keys(text: str) -> list[str]:
    rows = json.loads(text)
    keys: list[str] = []
    for row in rows:
        record = row.get("record", row)
        key = record.get("key")
        if not isinstance(key, str) or not key:
            raise ReplayError("memory_search returned a row without a key")
        keys.append(key)
    return keys


def run_search_mode(
    binary: Path,
    base_snapshot: Path,
    work_dir: Path,
    mode: str,
    cases: list[dict[str, Any]],
    suffix: str,
) -> tuple[dict[str, list[str]], dict[str, float], dict[str, Any]]:
    clone = work_dir / f"state.{mode}.{suffix}.db"
    stderr_path = work_dir / f"mcp.{mode}.{suffix}.stderr.log"
    clone_snapshot(base_snapshot, clone)
    if sha256_file(clone) != sha256_file(base_snapshot):
        raise ReplayError("disposable clone did not start from frozen base")
    client = McpClient(binary, clone, stderr_path)
    results: dict[str, list[str]] = {}
    timings: dict[str, float] = {}
    try:
        capabilities, _ = client.call("capabilities", {"compact": True})
        cap = json.loads(capabilities)
        observed_db = cap.get("memory", {}).get("db_path")
        if observed_db is None or Path(observed_db).resolve() != clone.resolve():
            raise ReplayError("MCP child did not bind to the disposable snapshot")
        identity = {
            "version": cap.get("version"),
            "git_sha": cap.get("build", {}).get("git_sha"),
            "git_describe": cap.get("build", {}).get("git_describe"),
            "embedding_backend": cap.get("memory", {}).get("embedding", {}).get("backend"),
            "embedding_dim": cap.get("memory", {}).get("embedding", {}).get("dim"),
        }
        for case in cases:
            text, elapsed = client.call(
                "memory_search",
                {"query": case["query"], "mode": mode, "limit": BUDGET, "compact": True},
            )
            results[case["id"]] = parse_search_keys(text)
            timings[case["id"]] = elapsed
    finally:
        client.close()
    return results, timings, identity


def rrf_fuse(mode_rows: dict[str, list[str]]) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    best_rank: dict[str, int] = {}
    for mode in MODES:
        for rank, key in enumerate(mode_rows[mode], start=1):
            scores[key] += 1.0 / (RRF_K + rank)
            best_rank[key] = min(rank, best_rank.get(key, rank))
    return sorted(scores, key=lambda key: (-scores[key], best_rank[key], key))[:BUDGET]


def load_structure(db_path: Path) -> dict[str, Any]:
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            "SELECT key, scope, created_at, related_keys, content "
            "FROM memories WHERE status='active' ORDER BY key"
        ).fetchall()
        active = {row[0] for row in rows}
        scope = {row[0]: row[1] for row in rows}
        related: dict[str, list[str]] = {}
        cited: dict[str, list[str]] = {}
        temporal_by_scope: dict[str | None, list[str]] = defaultdict(list)
        created = {row[0]: row[2] for row in rows}
        for key, row_scope, _, raw_related, content in rows:
            related[key] = [
                child
                for child in json.loads(raw_related or "[]")
                if child in active and child != key and scope.get(child) == row_scope
            ]
            seen: set[str] = set()
            cited[key] = []
            for child in KEY_TOKEN_RE.findall(content or ""):
                if (
                    child in active
                    and child != key
                    and child not in seen
                    and scope.get(child) == row_scope
                ):
                    seen.add(child)
                    cited[key].append(child)
            temporal_by_scope[row_scope].append(key)
        for row_scope, keys in temporal_by_scope.items():
            keys.sort(key=lambda key: (created[key], key))
        edges: dict[str, list[str]] = defaultdict(list)
        for left, right in db.execute(
            "SELECT from_key, to_key FROM memory_edges "
            "WHERE edge_type != 'coactivation' ORDER BY from_key, to_key"
        ):
            if left in active and right in active and scope[left] == scope[right]:
                edges[left].append(right)
                edges[right].append(left)
    finally:
        db.close()
    return {
        "active": active,
        "scope": scope,
        "related": related,
        "cited": cited,
        "edges": dict(edges),
        "temporal": dict(temporal_by_scope),
    }


def fill_budget(seeds: list[str], candidates: Iterable[str]) -> list[str]:
    out = list(seeds[:SEED_COUNT])
    seen = set(out)
    for key in candidates:
        if len(out) >= BUDGET:
            break
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def temporal_expand(rrf: list[str], structure: dict[str, Any]) -> tuple[list[str], int]:
    considered = 0

    def candidates() -> Iterable[str]:
        nonlocal considered
        for seed in rrf[:SEED_COUNT]:
            row_scope = structure["scope"].get(seed)
            ordered = structure["temporal"].get(row_scope, [])
            if seed not in ordered:
                continue
            index = ordered.index(seed)
            for distance in range(1, len(ordered)):
                for neighbor_index in (index - distance, index + distance):
                    if 0 <= neighbor_index < len(ordered):
                        key = ordered[neighbor_index]
                        if structure["scope"].get(key) != row_scope:
                            raise ReplayError("temporal expansion crossed scope")
                        considered += 1
                        yield key

    return fill_budget(rrf, candidates()), considered


def graph_expand(rrf: list[str], structure: dict[str, Any]) -> tuple[list[str], int]:
    considered = 0

    def candidates() -> Iterable[str]:
        nonlocal considered
        for seed in rrf[:SEED_COUNT]:
            row_scope = structure["scope"].get(seed)
            for channel in ("related", "cited", "edges"):
                for key in structure[channel].get(seed, []):
                    if structure["scope"].get(key) != row_scope:
                        raise ReplayError("graph expansion crossed scope")
                    considered += 1
                    yield key

    return fill_budget(rrf, candidates()), considered


def infer_route(text: str) -> str:
    lowered = text.lower()
    if re.search(r"为什么|原因|因果|追溯|\bwhy\b|\bcause", lowered):
        return "graph_expansion"
    if re.search(r"完整|全部|盘点|按顺序|\bcomplete\b|\ball\b|\border", lowered):
        return "temporal_adjacency"
    return "multimode_rrf"


def score(keys: list[str], case: dict[str, Any]) -> dict[str, float | int]:
    gold = set(case["gold"])
    if case["task_class"] == "synthesis":
        hits = len(gold.intersection(keys[:BUDGET]))
        value = hits / len(gold)
        return {
            "rank": 0,
            "hit_at_10": 0,
            "set_recall_at_20": round(value, 6),
            "task_score": round(value, 6),
            "returned": len(keys),
        }
    ranks = [keys.index(key) + 1 for key in gold if key in keys[:BUDGET]]
    rank = min(ranks) if ranks else 0
    hit = int(0 < rank <= 10)
    return {
        "rank": rank,
        "hit_at_10": hit,
        "set_recall_at_20": 0.0,
        "task_score": float(hit),
        "returned": len(keys),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, Any] = {}
    classes = ("retrieval", "relational", "synthesis")
    for arm in ARMS:
        class_scores = {}
        for task_class in classes:
            rows = [case["arms"][arm] for case in cases if case["task_class"] == task_class]
            class_scores[task_class] = {
                "cases": len(rows),
                "task_score": round(mean([float(row["task_score"]) for row in rows]), 6),
                "mean_rank": round(mean([float(row["rank"]) for row in rows]), 6),
            }
        by_arm[arm] = {
            "by_class": class_scores,
            "macro_task_score": round(
                mean([class_scores[task_class]["task_score"] for task_class in classes]), 6
            ),
        }
    return by_arm


def evaluate(
    cases: list[dict[str, Any]],
    searches: dict[str, dict[str, list[str]]],
    timings: dict[str, dict[str, float]],
    structure: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_cases: list[dict[str, Any]] = []
    route_hits = 0
    latencies: dict[str, list[float]] = defaultdict(list)
    oracle_map = {
        "retrieval": "multimode_rrf",
        "relational": "graph_expansion",
        "synthesis": "temporal_adjacency",
    }
    for case in cases:
        mode_rows = {mode: searches[mode][case["id"]] for mode in MODES}
        rrf = rrf_fuse(mode_rows)
        temporal_start = time.perf_counter()
        temporal, temporal_considered = temporal_expand(rrf, structure)
        temporal_ms = (time.perf_counter() - temporal_start) * 1000
        graph_start = time.perf_counter()
        graph, graph_considered = graph_expand(rrf, structure)
        graph_ms = (time.perf_counter() - graph_start) * 1000
        pages = {
            "content_hybrid": mode_rows["hybrid"][:BUDGET],
            "multimode_rrf": rrf,
            "temporal_adjacency": temporal,
            "graph_expansion": graph,
        }
        selected = infer_route(case["query"])
        oracle_selected = oracle_map[case["task_class"]]
        pages["text_router"] = pages[selected]
        pages["oracle_router_upper_bound"] = pages[oracle_selected]
        route_hits += selected == oracle_selected

        search_ms = sum(timings[mode][case["id"]] for mode in MODES)
        selected_expansion_ms = {
            "temporal_adjacency": temporal_ms,
            "graph_expansion": graph_ms,
        }.get(selected, 0.0)
        arm_latency = {
            "content_hybrid": timings["hybrid"][case["id"]],
            "multimode_rrf": search_ms,
            "temporal_adjacency": search_ms + temporal_ms,
            "graph_expansion": search_ms + graph_ms,
            "text_router": search_ms + selected_expansion_ms,
            "oracle_router_upper_bound": search_ms
            + (
                temporal_ms
                if oracle_selected == "temporal_adjacency"
                else graph_ms if oracle_selected == "graph_expansion" else 0
            ),
        }
        arms = {}
        for arm in ARMS:
            arms[arm] = score(pages[arm], case)
            arms[arm]["latency_ms"] = round(arm_latency[arm], 6)
            latencies[arm].append(arm_latency[arm])
        base_gold = set(case["gold"]).intersection(rrf)
        output_cases.append(
            {
                "id": case["id"],
                "task_class": case["task_class"],
                "text_route": selected,
                "oracle_route": oracle_selected,
                "temporal_considered": temporal_considered,
                "graph_considered": graph_considered,
                "temporal_gained_count": len(set(case["gold"]).intersection(temporal) - base_gold),
                "temporal_lost_count": len(base_gold - set(temporal)),
                "graph_gained_count": len(set(case["gold"]).intersection(graph) - base_gold),
                "graph_lost_count": len(base_gold - set(graph)),
                "arms": arms,
            }
        )

    summary = summarize(output_cases)
    for arm in ARMS:
        summary[arm]["p95_latency_ms"] = round(percentile(latencies[arm], 0.95), 6)
    summary["text_router"]["route_accuracy"] = round(route_hits / len(cases), 6)
    best_global = max(
        ("content_hybrid", "multimode_rrf"),
        key=lambda arm: summary[arm]["macro_task_score"],
    )
    best_score = summary[best_global]["macro_task_score"]
    oracle_score = summary["oracle_router_upper_bound"]["macro_task_score"]
    router_score = summary["text_router"]["macro_task_score"]
    a1 = summary["multimode_rrf"]["by_class"]
    a2 = summary["temporal_adjacency"]["by_class"]
    a3 = summary["graph_expansion"]["by_class"]
    conditional_regression = max(
        0.0,
        a1["retrieval"]["task_score"]
        - summary["text_router"]["by_class"]["retrieval"]["task_score"],
    )
    gates = {
        "strategy_potential": oracle_score >= best_score + 0.05,
        "temporal_mechanism": a2["synthesis"]["task_score"] >= a1["synthesis"]["task_score"] + 0.05,
        "graph_mechanism": a3["relational"]["task_score"] >= a1["relational"]["task_score"] + 0.05,
        "conditional_non_regression": conditional_regression <= 0.02,
        "router_accuracy": summary["text_router"]["route_accuracy"] >= 0.80,
        "router_lift": router_score >= best_score + 0.05,
        "router_near_oracle": router_score >= oracle_score - 0.05,
        "temporal_cost": summary["temporal_adjacency"]["p95_latency_ms"]
        <= 2 * summary["multimode_rrf"]["p95_latency_ms"],
        "graph_cost": summary["graph_expansion"]["p95_latency_ms"]
        <= 2 * summary["multimode_rrf"]["p95_latency_ms"],
    }
    summary["comparison"] = {
        "best_global_arm": best_global,
        "best_global_score": best_score,
        "oracle_score": oracle_score,
        "oracle_lift": round(oracle_score - best_score, 6),
        "router_score": router_score,
        "router_lift": round(router_score - best_score, 6),
        "router_to_oracle_gap": round(oracle_score - router_score, 6),
        "conditional_regression": round(conditional_regression, 6),
    }
    summary["gates"] = gates
    return output_cases, summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    eval_dir = Path(__file__).resolve().parent
    cases, fixture_hashes = load_cases(eval_dir)
    source_db = args.source_db.resolve()
    binary = args.binary.resolve()
    if not source_db.is_file():
        raise ReplayError("source DB does not exist")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ReplayError("binary is not executable")
    harness_source_commit = subprocess.check_output(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True
    ).strip()

    with tempfile.TemporaryDirectory(prefix="ab-free-recall-r1-") as temp:
        work_dir = Path(temp)
        base_snapshot = work_dir / "state.base.db"
        source_before, source_after = read_only_backup(source_db, base_snapshot)
        base_sha_before = sha256_file(base_snapshot)
        corpus = active_gold_state(base_snapshot, all_gold(cases))
        if corpus["missing_count"] or corpus["non_active_count"]:
            raise ReplayError(f"CORPUS_DRIFT_BLOCKED: {json.dumps(corpus, sort_keys=True)}")
        structure = load_structure(base_snapshot)
        searches: dict[str, dict[str, list[str]]] = {}
        timings: dict[str, dict[str, float]] = {}
        identities: list[dict[str, Any]] = []
        for mode in MODES:
            searches[mode], timings[mode], identity = run_search_mode(
                binary, base_snapshot, work_dir, mode, cases, "forward"
            )
            identities.append(identity)
        if any(identity != identities[0] for identity in identities[1:]):
            raise ReplayError("binary identity changed across forward observations")

        # Query-order falsifier on independent clones. Do not publish a verdict
        # if access/coactivation side effects make rankings order-dependent.
        reversed_cases = list(reversed(cases))
        for mode in MODES:
            reversed_rows, _, reverse_identity = run_search_mode(
                binary, base_snapshot, work_dir, mode, reversed_cases, "reverse"
            )
            if reverse_identity != identities[0]:
                raise ReplayError("binary identity changed during order falsifier")
            if searches[mode] != reversed_rows:
                raise ReplayError(f"ORDER_DEPENDENT_BLOCKED: {mode}")

        result_cases, summary = evaluate(cases, searches, timings, structure)
        base_sha_after = sha256_file(base_snapshot)
        if base_sha_before != base_sha_after:
            raise ReplayError("frozen base snapshot changed during replay")

    return {
        "schema": REPORT_SCHEMA,
        "status": "REPLAY_COMPLETE_NO_RUNTIME_AUTHORITY",
        "read_only_source": True,
        "public_result_private_snapshot": True,
        "calls_live_memory_search": False,
        "changes_default_search_order": False,
        "runs_biocortex": False,
        "live_memory_writes": 0,
        "candidate_budget": BUDGET,
        "search_calls_per_multimode_query": 3,
        "fixture_hashes": fixture_hashes,
        "harness_source_commit": harness_source_commit,
        "binary_capabilities": identities[0],
        "binary_sha256": sha256_file(binary),
        "snapshot_sha256_before": base_sha_before,
        "snapshot_sha256_after": base_sha_after,
        "source_total_changes_before": source_before,
        "source_total_changes_after": source_after,
        "corpus_preflight": corpus,
        "summary": summary,
        "cases": result_cases,
    }


def selftest() -> None:
    rows = {
        "fts": ["a", "b", "c"],
        "hybrid": ["b", "a", "d"],
        "semantic": ["a", "e", "b"],
    }
    fused = rrf_fuse(rows)
    if fused[:2] != ["a", "b"]:
        raise AssertionError("RRF ordering drift")
    structure = {
        "scope": {"a": "s1", "b": "s1", "c": "s1", "x": "s2"},
        "temporal": {"s1": ["a", "b", "c"], "s2": ["x"]},
        "related": {"a": ["b"]},
        "cited": {"a": ["c"]},
        "edges": {"a": ["b"]},
    }
    temporal, _ = temporal_expand(["b"], structure)
    if temporal[:3] != ["b", "a", "c"] or "x" in temporal:
        raise AssertionError("temporal scope/order drift")
    graph, _ = graph_expand(["a"], structure)
    if graph[:3] != ["a", "b", "c"] or "x" in graph:
        raise AssertionError("graph channel/scope drift")
    if infer_route("完整盘点全部记录") != "temporal_adjacency":
        raise AssertionError("temporal route drift")
    if infer_route("为什么失败，追溯原因") != "graph_expansion":
        raise AssertionError("graph route drift")
    if infer_route("查找 WIT 证据") != "multimode_rrf":
        raise AssertionError("content route drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--source-db", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        selftest()
        if args.source_db is None:
            print("selftest: PASS")
            return 0
    if args.source_db is None or args.binary is None or args.out is None:
        parser.error("--source-db, --binary, and --out are required for replay")
    report = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
