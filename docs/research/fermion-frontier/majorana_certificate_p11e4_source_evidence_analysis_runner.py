#!/usr/bin/env python3
"""Execute the single G14-authorized, bounded P11-E4 source analysis read."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "majorana_certificate_p11e4_version_bound_source_evidence_analysis_contract.json"
G14 = HERE / "majorana_certificate_p11_g14_source_evidence_analysis_authorization_record.json"
OUTPUT = HERE / "majorana_certificate_p11e4_source_evidence_analysis_result.json"
EVIDENCE = Path("/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e3r-source-inspection")
AUTHORIZED_PARENT = "7b2aa7fe1f54a3beaaadf7c68f481292185febc0"
PACKAGE_KEYS = {
    "gcc-15=15.2.0-16ubuntu1": "gcc-15",
    "binutils=2.46-3ubuntu2": "binutils",
    "linux=7.0.0-28.28": "linux",
    "linux-signed=7.0.0-28.28": "linux-signed",
}


def canon(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def manifest(package_key: str) -> dict[str, dict[str, object]]:
    path = EVIDENCE / "receipts" / f"{package_key}.tree.json"
    rows = json.loads(path.read_bytes())
    return {row["relative_path"]: row for row in rows if row["type"] == "file"}


def verified_lines(source: str, relative_path: str, rows: dict[str, dict[str, object]]) -> tuple[list[str], str]:
    row = rows.get(relative_path)
    if row is None or "sha256" not in row:
        raise ValueError(f"path absent from tree manifest: {source}:{relative_path}")
    root = (EVIDENCE / "trees" / source).resolve(strict=True)
    path = EVIDENCE / "trees" / source / relative_path
    resolved = path.resolve(strict=True)
    if root not in (resolved, *resolved.parents):
        raise ValueError(f"resolved path escapes tree: {source}:{relative_path}")
    data = path.read_bytes()
    if digest(data) != row["sha256"]:
        raise ValueError(f"manifest hash mismatch: {source}:{relative_path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid UTF-8: {source}:{relative_path}") from exc
    return text.splitlines(keepends=True), str(row["sha256"])


def merged_windows(lines: list[str], queries: list[str], radius: int) -> list[dict[str, object]]:
    matches = []
    for line_number, line in enumerate(lines, 1):
        found = sorted(query for query in queries if query in line)
        if found:
            matches.append((line_number, found))
    windows = []
    for line_number, found in matches:
        start, end = max(1, line_number - radius), min(len(lines), line_number + radius)
        if windows and start <= windows[-1]["end"] + 1:
            windows[-1]["end"] = max(windows[-1]["end"], end)
            windows[-1]["matches"].append((line_number, found))
        else:
            windows.append({"start": start, "end": end, "matches": [(line_number, found)]})
    return windows


def main() -> int:
    if git("rev-parse", "HEAD") != AUTHORIZED_PARENT:
        raise ValueError("runner must execute exactly at the G14 authorization commit")
    if OUTPUT.exists():
        raise ValueError("single authorized run already has an output")
    contract = json.loads(CONTRACT.read_bytes())
    auth = json.loads(G14.read_bytes())
    if auth["disposition"] != "AUTHORIZE_ONE_P11_E4_VERSION_BOUND_SOURCE_EVIDENCE_ANALYSIS_RUN":
        raise ValueError("G14 authorization missing")
    limits = contract["future_evidence_admission"]
    radius = limits["context_window_lines_each_side"]
    excerpts = []
    tracks = []
    manifests: dict[str, dict[str, dict[str, object]]] = {}
    for track in contract["analysis_tracks"]:
        source = track["source"]
        key = PACKAGE_KEYS[source]
        rows = manifests.setdefault(key, manifest(key))
        track_excerpt_ids = []
        bounded_absences = []
        for relative_path in track["paths"]:
            lines, file_sha = verified_lines(source, relative_path, rows)
            windows = merged_windows(lines, track["queries"], radius)
            present_queries = set()
            for window in windows:
                matched_queries = sorted({q for _, qs in window["matches"] for q in qs})
                present_queries.update(matched_queries)
                excerpt = "".join(lines[window["start"] - 1 : window["end"]]).encode()
                if len(excerpt) > limits["maximum_excerpt_bytes"]:
                    raise ValueError(f"oversized merged excerpt: {source}:{relative_path}")
                excerpt_id = f"E{len(excerpts) + 1:02d}"
                track_excerpt_ids.append(excerpt_id)
                excerpts.append({
                    "excerpt_id": excerpt_id,
                    "source_identity": source,
                    "relative_path": relative_path,
                    "file_sha256": file_sha,
                    "query": matched_queries,
                    "match_line": [line for line, _ in window["matches"]],
                    "start_line": window["start"],
                    "end_line": window["end"],
                    "excerpt_size_bytes": len(excerpt),
                    "excerpt_sha256": digest(excerpt),
                    "excerpt_text": excerpt.decode("utf-8"),
                })
            for query in track["queries"]:
                if query not in present_queries:
                    bounded_absences.append({"relative_path": relative_path, "query": query})
        tracks.append({
            "track_id": track["track_id"],
            "source_identity": source,
            "excerpt_ids": track_excerpt_ids,
            "bounded_path_query_absences": bounded_absences,
        })
    if len(excerpts) > limits["maximum_admitted_excerpts_total"]:
        raise ValueError(f"excerpt count exceeds cap: {len(excerpts)}")
    result = {
        "schema_version": 1,
        "result_id": "MAJORANA-P11-E4-VERSION-BOUND-SOURCE-EVIDENCE-ANALYSIS-RESULT-V1",
        "authorization_commit": AUTHORIZED_PARENT,
        "contract_sha256": digest(CONTRACT.read_bytes()),
        "E3R_external_root": str(EVIDENCE),
        "execution_status": "BOUNDED_SOURCE_READ_COMPLETE_AWAITING_G15_GOVERNANCE",
        "scientific_authority": "NONE",
        "limits": {
            "context_lines_each_side": radius,
            "maximum_excerpt_bytes": limits["maximum_excerpt_bytes"],
            "maximum_excerpt_count": limits["maximum_admitted_excerpts_total"],
        },
        "tracks": tracks,
        "excerpts": excerpts,
        "interpretations": [],
        "unresolved_gap_ledger": [],
        "next_gate": "P11-G15-POST-SOURCE-EVIDENCE-ANALYSIS-GOVERNANCE-V1",
    }
    OUTPUT.write_bytes(canon(result))
    print(canon({"excerpt_count": len(excerpts), "output_sha256": digest(OUTPUT.read_bytes()), "status": "PASS"}).decode())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
