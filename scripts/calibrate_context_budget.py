#!/usr/bin/env python3
"""
Calibrate/validate the context_budget text heuristic against a tokenizer baseline.

Default baseline uses tiktoken cl100k_base.
Usage:
  python3 scripts/calibrate_context_budget.py --files README.md CHANGELOG.md
  python3 scripts/calibrate_context_budget.py --glob "crates/**/*.rs" --glob "scripts/*.sh"
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
from dataclasses import dataclass


def is_cjk(ch: str) -> bool:
    return (
        ("\u3000" <= ch <= "\u303f")
        or ("\u3040" <= ch <= "\u309f")
        or ("\u30a0" <= ch <= "\u30ff")
        or ("\u3400" <= ch <= "\u4dbf")
        or ("\u4e00" <= ch <= "\u9fff")
        or ("\uf900" <= ch <= "\ufaff")
    )


def heuristic_tokens(text: str, non_cjk_divisor: float, cjk_divisor: float) -> int:
    non_cjk = 0
    cjk = 0
    for ch in text:
        if ch.isspace():
            continue
        if is_cjk(ch):
            cjk += 1
        else:
            non_cjk += 1
    return math.ceil(non_cjk / non_cjk_divisor) + math.ceil(cjk / cjk_divisor)


@dataclass
class Row:
    path: pathlib.Path
    actual: int
    estimated: int

    @property
    def abs_pct_err(self) -> float:
        return abs(self.estimated - self.actual) * 100.0 / max(self.actual, 1)


def load_tiktoken_encoder():
    try:
        import tiktoken
    except Exception as exc:  # pragma: no cover
        print(
            "ERROR: tiktoken is required for calibration.\n"
            "Create a venv and install it, e.g.:\n"
            "  python3 -m venv /tmp/ab-calib-venv\n"
            "  /tmp/ab-calib-venv/bin/pip install tiktoken\n"
            "  /tmp/ab-calib-venv/bin/python scripts/calibrate_context_budget.py ...\n"
            f"Reason: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return tiktoken.get_encoding("cl100k_base")


def collect_paths(root: pathlib.Path, files: list[str], globs: list[str]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for f in files:
        p = (root / f).resolve()
        if p.is_file():
            out.append(p)
    for g in globs:
        out.extend(sorted((root).glob(g)))
    dedup: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for p in out:
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        dedup.append(p)
    return dedup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--files", nargs="*", default=[], help="Explicit relative files")
    parser.add_argument(
        "--glob",
        dest="globs",
        nargs="*",
        default=[],
        help="Glob patterns relative to root (e.g. 'crates/**/*.rs')",
    )
    parser.add_argument("--non-cjk-divisor", type=float, default=3.3)
    parser.add_argument("--cjk-divisor", type=float, default=1.5)
    parser.add_argument("--max-files", type=int, default=50)
    parser.add_argument("--max-chars", type=int, default=120_000)
    parser.add_argument("--target-mape", type=float, default=15.0)
    parser.add_argument(
        "--default-set",
        action="store_true",
        help="Use default representative corpus if no files/globs passed",
    )
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    files = list(args.files)
    globs = list(args.globs)
    if args.default_set and not files and not globs:
        files = [
            "README.md",
            "CHANGELOG.md",
            "crates/bridge/src/mcp_tools.rs",
            "crates/terminal/src/warp.rs",
            "scripts/verify_warp_integration.sh",
        ]

    paths = collect_paths(root, files, globs)
    if not paths:
        print("ERROR: no input files matched", file=sys.stderr)
        return 2
    if len(paths) > args.max_files:
        paths = paths[: args.max_files]

    enc = load_tiktoken_encoder()
    rows: list[Row] = []
    for p in paths:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if len(txt) > args.max_chars:
            txt = txt[: args.max_chars]
        actual = len(enc.encode(txt))
        estimated = heuristic_tokens(txt, args.non_cjk_divisor, args.cjk_divisor)
        rows.append(Row(path=p, actual=actual, estimated=estimated))

    rows.sort(key=lambda r: r.abs_pct_err, reverse=True)
    mape = sum(r.abs_pct_err for r in rows) / len(rows)
    worst = rows[0].abs_pct_err

    print("context_budget calibration report")
    print(
        f"non_cjk_divisor={args.non_cjk_divisor} cjk_divisor={args.cjk_divisor} "
        f"files={len(rows)}"
    )
    print(f"MAPE={mape:.2f}% worst={worst:.2f}% target<={args.target_mape:.2f}%")
    print("")
    print("Top errors:")
    for r in rows[: min(10, len(rows))]:
        print(
            f"- {r.path.relative_to(root)} actual={r.actual} est={r.estimated} "
            f"abs_err={r.abs_pct_err:.2f}%"
        )

    return 0 if mape <= args.target_mape else 1


if __name__ == "__main__":
    raise SystemExit(main())

