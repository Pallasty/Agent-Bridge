"""Create and inspect local film production records without invoking generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FILES = ("brief.json", "bible.json", "shots.json", "generations.json", "handoff.json")
TEMPLATES = Path(__file__).resolve().parents[1] / "assets/templates"


def file_hash(path: Path) -> str:
    """Hash even large media files with bounded memory use."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_project(root: Path, project_id: str) -> None:
    """Create five empty project records; refuse to overwrite an existing path."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", project_id):
        raise ValueError("project_id must be 1-64 ASCII letters, digits, hyphens or underscores")
    templates = {name: json.loads((TEMPLATES / name).read_text()) for name in FILES}
    root.mkdir(parents=True, exist_ok=False)
    for name, value in templates.items():
        value["project_id"] = project_id
        _write(root / name, value)


def _docs(root: Path) -> dict[str, Any]:
    docs = {name: json.loads((root / name).read_text(encoding="utf-8")) for name in FILES}
    project_id = docs["brief.json"].get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("missing project_id")
    for name, value in docs.items():
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError(f"unsupported schema: {name}")
        if value.get("project_id") != project_id:
            raise ValueError(f"project_id mismatch: {name}")
    return docs


def _indexed(doc: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows = doc.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"{key} must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError(f"missing id in {key}")
        if row["id"] in result:
            raise ValueError(f"duplicate id in {key}: {row['id']}")
        result[row["id"]] = row
    return result


def _check_file(root: Path, ref: dict[str, Any]) -> None:
    name, digest = ref.get("path"), ref.get("sha256")
    if not isinstance(name, str) or not name:
        raise ValueError("missing artifact path")
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path outside project")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError(f"missing or invalid hash: {name}")
    if not path.is_file():
        raise ValueError(f"missing artifact: {name}")
    if file_hash(path) != digest:
        raise ValueError(f"artifact hash mismatch: {name}")


def recover(root: Path) -> dict[str, Any]:
    """Read current records and propose next steps; never generate, select or publish."""
    docs = _docs(root)
    brief, handoff = docs["brief.json"], docs["handoff.json"]
    mode = brief.get("source_mode")
    if mode not in {"fiction", "documentary", "simulation_replay"}:
        raise ValueError("unknown source_mode")
    assets = _indexed(docs["bible.json"], "assets")
    shots = _indexed(docs["shots.json"], "shots")
    generations = _indexed(docs["generations.json"], "generations")
    hashes = {name: file_hash(root / name) for name in FILES[:-1]}
    matches = handoff.get("document_sha256") == hashes
    errors: list[str] = []
    selected: dict[str, str] = {}
    next_actions: list[dict[str, str]] = []
    script = brief.get("script", {})
    if not isinstance(script, dict) or not isinstance(script.get("revision"), str):
        raise ValueError("missing script revision")

    for sid, shot in shots.items():
        try:
            _check_file(root, script)
            if shot.get("script_revision") != script["revision"]:
                raise ValueError("script revision changed")
            refs = shot.get("asset_versions")
            if not isinstance(refs, dict):
                raise ValueError("missing asset_versions")
            for aid, version in refs.items():
                asset = assets.get(aid)
                if not asset or not isinstance(version, str) or asset.get("version") != version:
                    raise ValueError(f"asset version changed/missing: {aid}")
                if asset.get("approved") is not True or not asset.get("rights"):
                    raise ValueError(f"asset review/rights record missing: {aid}")
                _check_file(root, asset)
            if mode != "fiction":
                evidence = shot.get("source_refs")
                if not isinstance(evidence, list) or not evidence:
                    raise ValueError("source evidence required for factual shot")
                for source in evidence:
                    _check_file(root, source)

            gid = shot.get("selected_generation_id")
            if gid is not None:
                take = generations.get(gid)
                if not take or take.get("shot_id") != sid:
                    raise ValueError("selected generation does not belong to shot")
                if take.get("status") != "generated" or take.get("review", {}).get("decision") != "accepted":
                    raise ValueError("selected generation must have accepted review")
                if take.get("script_revision") != script["revision"] or take.get("asset_versions") != refs:
                    raise ValueError("selected generation input versions differ")
                _check_file(root, take.get("output", {}))
                selected[sid] = gid
            else:
                candidates = [g for g in generations.values()
                              if g.get("shot_id") == sid and g.get("status") == "generated"
                              and g.get("script_revision") == script["revision"]
                              and g.get("asset_versions") == refs
                              and g.get("review", {}).get("decision") != "rejected"]
                for candidate in candidates:
                    _check_file(root, candidate.get("output", {}))
                action = "review_candidates" if candidates else "plan_generation"
                next_actions.append({"shot_id": sid, "action": action})
        except (ValueError, OSError, TypeError, AttributeError) as exc:
            errors.append(f"{sid}: {exc}")
            next_actions.append({"shot_id": sid, "action": "reconcile_records"})

    return {
        "project_id": brief["project_id"],
        "status": "needs_review" if errors else "record_consistent" if shots else "planning",
        "phase": brief.get("phase"),
        "source_mode": mode,
        "script_revision": script["revision"],
        "asset_versions": {aid: value.get("version") for aid, value in assets.items()},
        "selected": selected,
        "next_actions": next_actions,
        "handoff_matches_files": matches,
        "handoff_summary": handoff.get("summary", "") if matches and not errors else None,
        "handoff_next_actions": handoff.get("next_actions", []) if matches and not errors else [],
        "handoff_unresolved": handoff.get("unresolved", []) if matches and not errors else [],
        "document_sha256": hashes,
        "errors": errors,
        "limits": "Record/file consistency only; no media quality, factual truth, rights or publication approval.",
    }


def checkpoint(root: Path) -> dict[str, Any]:
    """Bind an existing handoff to current files after checking record consistency."""
    report = recover(root)
    if report["errors"]:
        raise ValueError("resolve recovery errors before checkpoint")
    path = root / "handoff.json"
    handoff = json.loads(path.read_text(encoding="utf-8"))
    handoff["document_sha256"] = report["document_sha256"]
    _write(path, handoff)
    return recover(root)


def main() -> int:
    """Run an explicit local operation and return nonzero on record errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "recover", "checkpoint"))
    parser.add_argument("project", type=Path)
    parser.add_argument("--project-id")
    args = parser.parse_args()
    try:
        if args.command == "init":
            if not args.project_id:
                parser.error("init requires --project-id")
            init_project(args.project, args.project_id)
        report = checkpoint(args.project) if args.command == "checkpoint" else recover(args.project)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
