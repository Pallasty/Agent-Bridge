#!/usr/bin/env python3
"""Normalize StructMemEval accounting settlement answers without running a benchmark.

This helper is standard-library-only. It loads a StructMemEval-style accounting
case, normalizes reference settlement answers into canonical transaction tuples,
and optionally compares candidate answers by exact transaction-set equality. It
does not import the official benchmark runner, call an LLM, or write AB memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.structmemeval_accounting_normalizer.v0"
REVIEW_SUMMARY_SCHEMA = "agent_bridge.structmemeval_accounting_normalizer_review_summary.v0"
SOURCE_HEAD = "64d2c9b242deb394e3ef94a318868a55261e141b"
DEFAULT_ACCOUNTING_CASE = (
    "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
    f"{SOURCE_HEAD}/benchmark/data/accounting/debt_tracker_10_1.json"
)
COUNT_TABLES = ["memories", "memory_edges", "semantic_events"]

PERSON = r"[A-Z][A-Za-z .'-]*"
EURO_SYMBOL = r"\u20ac"
RIGHT_ARROW = r"\u2192"
AMOUNT = (
    rf"(?:EUR\s*)?{EURO_SYMBOL}?\s*(?P<amount>\d+(?:\.\d{{1,2}})?)"
    rf"\s*(?P<currency>EUR|{EURO_SYMBOL})?"
)
AMOUNT_NAMED = (
    rf"(?:EUR\s*)?{EURO_SYMBOL}?\s*(?P<{{name}}>\d+(?:\.\d{{{{1,2}}}})?)"
    rf"\s*(?P<{{currency}}>EUR|{EURO_SYMBOL})?"
)

PATTERNS = [
    (
        "arrow",
        re.compile(
            rf"(?P<payer>{PERSON})\s*(?:->|{RIGHT_ARROW})\s*"
            rf"(?P<payee>{PERSON})\s*[:=]?\s*{AMOUNT}",
            re.IGNORECASE,
        ),
    ),
    (
        "pays_amount_to",
        re.compile(
            rf"(?P<payer>{PERSON})\s+pays\s+"
            + AMOUNT_NAMED.format(name="amount", currency="currency")
            + rf"\s+to\s+(?P<payee>{PERSON})",
            re.IGNORECASE,
        ),
    ),
    (
        "pays_payee_amount",
        re.compile(
            rf"(?P<payer>{PERSON})\s+pays\s+(?P<payee>{PERSON})\s+"
            + AMOUNT_NAMED.format(name="amount", currency="currency"),
            re.IGNORECASE,
        ),
    ),
    (
        "owes",
        re.compile(
            rf"(?P<payer>{PERSON})\s+owes\s+(?P<payee>{PERSON})\s+"
            + AMOUNT_NAMED.format(name="amount", currency="currency"),
            re.IGNORECASE,
        ),
    ),
    (
        "receives_from",
        re.compile(
            rf"(?P<payee>{PERSON})\s+receives\s+"
            + AMOUNT_NAMED.format(name="amount", currency="currency")
            + rf"\s+from\s+(?P<payer>{PERSON})",
            re.IGNORECASE,
        ),
    ),
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_source(source: str, allow_other_url: bool) -> tuple[bytes, str]:
    if source.startswith("http://"):
        fail("http URLs are refused; use https")
    if source.startswith("https://"):
        expected_prefix = (
            "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
            f"{SOURCE_HEAD}/"
        )
        if not allow_other_url and not source.startswith(expected_prefix):
            fail(
                "URL must be pinned to yandex-research/StructMemEval "
                f"{SOURCE_HEAD}; use --allow-other-url for review-only overrides"
            )
        with urllib.request.urlopen(source, timeout=30) as response:
            return response.read(), "url"
    path = Path(source)
    if not path.is_file():
        fail(f"case file not found: {source}")
    return path.read_bytes(), "file"


def require_obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
    return value


def require_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value


def sanitize_key_part(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", value.strip())
    return out.strip("_") or "unknown"


def normalize_person(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip(" \t\r\n,:;."))
    value = re.sub(
        r"^(?:settlement|final settlement|transaction|transactions)\s*[:=-]?\s*",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(r"^(?:and)\s+", "", value, flags=re.I)
    value = value.strip(" \t\r\n,:;.")
    if not re.match(r"^[A-Za-z][A-Za-z .'-]*$", value):
        fail(f"invalid participant name after normalization: {value!r}")
    return " ".join(part.capitalize() for part in value.split(" "))


def amount_to_cents(value: str) -> int:
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        fail(f"invalid amount: {value!r}")
    if decimal <= 0:
        fail(f"amount must be positive: {value!r}")
    cents_decimal = (decimal * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if decimal.quantize(Decimal("0.01")) != decimal:
        fail(f"amount must have at most two decimal places: {value!r}")
    return int(cents_decimal)


def cents_to_amount(cents: int) -> str:
    return f"{Decimal(cents) / Decimal('100'):.2f}"


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def span_overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(max(start, other_start) < min(end, other_end) for other_start, other_end in spans)


def unparsed_fragment(text: str, spans: list[tuple[int, int]]) -> str:
    leftovers = []
    cursor = 0
    for start, end in merge_spans(spans):
        leftovers.append(text[cursor:start])
        cursor = end
    leftovers.append(text[cursor:])
    fragment = " ".join(leftovers)
    fragment = re.sub(r"\b(?:settlement|final|plan|transaction|transactions|and|etc)\b", " ", fragment, flags=re.I)
    fragment = re.sub(r"[\s,;:.\-\[\]()]+", " ", fragment).strip()
    return fragment


def canonical_transaction(raw: dict[str, str]) -> tuple[str, str, str, int]:
    payer = normalize_person(raw["payer"])
    payee = normalize_person(raw["payee"])
    if payer == payee:
        fail(f"payer and payee must differ: {payer!r}")
    currency = (raw.get("currency") or "EUR").upper()
    if currency == "\u20ac":
        currency = "EUR"
    if currency != "EUR":
        fail(f"unsupported currency: {currency!r}")
    return payer, payee, currency, amount_to_cents(raw["amount"])


def normalize_answer(answer: str) -> dict[str, Any]:
    text = answer.replace("\u2192", "->")
    transactions: dict[tuple[str, str, str], int] = {}
    spans: list[tuple[int, int]] = []
    matched_patterns: set[str] = set()

    for pattern_name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if span_overlaps(span, spans):
                continue
            raw = {
                "payer": match.group("payer"),
                "payee": match.group("payee"),
                "amount": match.group("amount"),
                "currency": match.groupdict().get("currency") or "EUR",
            }
            payer, payee, currency, cents = canonical_transaction(raw)
            key = (payer, payee, currency)
            transactions[key] = transactions.get(key, 0) + cents
            spans.append(span)
            matched_patterns.add(pattern_name)

    if not transactions:
        fail("answer does not contain any supported settlement transaction")

    fragment = unparsed_fragment(text, spans)
    if fragment:
        fail(f"answer has unsupported leftover text: {fragment!r}")

    canonical = [
        {
            "payer": payer,
            "payee": payee,
            "currency": currency,
            "amount_cents": cents,
            "amount": cents_to_amount(cents),
        }
        for (payer, payee, currency), cents in sorted(transactions.items())
    ]
    canonical_key = "|".join(
        f"{item['payer']}->{item['payee']}:{item['amount_cents']}:{item['currency']}"
        for item in canonical
    )
    return {
        "source_text_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "source_text_bytes": len(answer.encode("utf-8")),
        "transaction_count": len(canonical),
        "transactions": canonical,
        "canonical_key_sha256": hashlib.sha256(canonical_key.encode("utf-8")).hexdigest(),
        "matched_patterns": sorted(matched_patterns),
    }


def normalize_case(raw: bytes, source: str, source_mode: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - report exact parse failure to operator
        fail(f"failed to parse {source}: {exc}")

    obj = require_obj(data, "case")
    case_id = sanitize_key_part(require_str(obj.get("case_id"), "case.case_id"))
    queries = require_list(obj.get("queries"), "case.queries")
    variants: list[dict[str, Any]] = []
    for query_index, query_raw in enumerate(queries, start=1):
        query = require_obj(query_raw, f"queries[{query_index - 1}]")
        reference_answer = require_list(
            query.get("reference_answer"), f"queries[{query_index - 1}].reference_answer"
        )
        for variant_index, variant_raw in enumerate(reference_answer, start=1):
            variant = require_obj(
                variant_raw,
                f"queries[{query_index - 1}].reference_answer[{variant_index - 1}]",
            )
            answer_text = require_str(
                variant.get("text"),
                f"queries[{query_index - 1}].reference_answer[{variant_index - 1}].text",
            )
            normalized = normalize_answer(answer_text)
            normalized["query_index"] = query_index
            normalized["variant_index"] = variant_index
            variants.append(normalized)

    if not variants:
        fail("case has no reference answer variants")

    return {
        "case_id": case_id,
        "source": source,
        "source_mode": source_mode,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "query_count": len(queries),
        "reference_variant_count": len(variants),
        "reference_variants": variants,
    }


def compare_candidate(candidate: str, references: list[dict[str, Any]], index: int) -> dict[str, Any]:
    normalized = normalize_answer(candidate)
    matches = [
        ref["variant_index"]
        for ref in references
        if ref["canonical_key_sha256"] == normalized["canonical_key_sha256"]
    ]
    return {
        "candidate_index": index,
        "source_text_sha256": normalized["source_text_sha256"],
        "source_text_bytes": normalized["source_text_bytes"],
        "transaction_count": normalized["transaction_count"],
        "transactions": normalized["transactions"],
        "canonical_key_sha256": normalized["canonical_key_sha256"],
        "matched_patterns": normalized["matched_patterns"],
        "exact_reference_match": bool(matches),
        "matched_reference_variant_indices": matches,
    }


def table_count(con: sqlite3.Connection, table: str) -> int | None:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return None
    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def store_counts(db_path: str) -> dict[str, int | None]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {table: table_count(con, table) for table in COUNT_TABLES}
    finally:
        con.close()


def no_write_packet(db_path: str | None, before: dict[str, int | None] | None) -> dict[str, Any]:
    if not db_path or before is None:
        return {
            "checked": False,
            "reason": "store_db_not_provided",
            "memory_rows_delta": None,
            "memory_edges_delta": None,
            "semantic_events_delta": None,
        }
    after = store_counts(db_path)
    deltas: dict[str, int | None] = {}
    for table in COUNT_TABLES:
        if before[table] is None or after[table] is None:
            deltas[table] = None
        else:
            deltas[table] = after[table] - before[table]
    return {
        "checked": True,
        "store_db": db_path,
        "before": before,
        "after": after,
        "memory_rows_delta": deltas["memories"],
        "memory_edges_delta": deltas["memory_edges"],
        "semantic_events_delta": deltas["semantic_events"],
        "passed": all(deltas[table] == 0 for table in COUNT_TABLES),
    }


def compact_no_write(proof: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked": proof.get("checked"),
        "passed": proof.get("passed"),
        "memory_rows_delta": proof.get("memory_rows_delta"),
        "memory_edges_delta": proof.get("memory_edges_delta"),
        "semantic_events_delta": proof.get("semantic_events_delta"),
    }


def review_variant(variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_index": variant["query_index"],
        "variant_index": variant["variant_index"],
        "source_text_sha256": variant["source_text_sha256"],
        "source_text_bytes": variant["source_text_bytes"],
        "transaction_count": variant["transaction_count"],
        "canonical_key_sha256": variant["canonical_key_sha256"],
        "matched_patterns": variant["matched_patterns"],
        "transactions": variant["transactions"],
    }


def review_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_index": candidate["candidate_index"],
        "source_text_sha256": candidate["source_text_sha256"],
        "source_text_bytes": candidate["source_text_bytes"],
        "transaction_count": candidate["transaction_count"],
        "canonical_key_sha256": candidate["canonical_key_sha256"],
        "matched_patterns": candidate["matched_patterns"],
        "transactions": candidate["transactions"],
        "exact_reference_match": candidate["exact_reference_match"],
        "matched_reference_variant_indices": candidate["matched_reference_variant_indices"],
    }


def review_summary_packet(packet: dict[str, Any]) -> dict[str, Any]:
    case = packet["case"]
    return {
        "schema": REVIEW_SUMMARY_SCHEMA,
        "source_schema": packet["schema"],
        "source_head": packet["source_head"],
        "family": packet["family"],
        "official_runner_import_allowed": packet["official_runner_import_allowed"],
        "third_party_runtime_dependencies": packet["third_party_runtime_dependencies"],
        "api_key_required": packet["api_key_required"],
        "private_memory_export_allowed": packet["private_memory_export_allowed"],
        "writes_ab_store": packet["writes_ab_store"],
        "raw_content_in_output": packet["raw_content_in_output"],
        "comparison_mode": packet["comparison_mode"],
        "case": {
            "case_id": case["case_id"],
            "source_mode": case["source_mode"],
            "sha256": case["sha256"],
            "bytes": case["bytes"],
            "query_count": case["query_count"],
            "reference_variant_count": case["reference_variant_count"],
        },
        "summary": packet["summary"],
        "reference_variants": [
            review_variant(variant) for variant in packet["reference_variants"]
        ],
        "candidate_reviews": [
            review_candidate(candidate) for candidate in packet["candidate_answers"]
        ],
        "no_write_invariant": compact_no_write(packet["no_write_invariant"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        default=DEFAULT_ACCOUNTING_CASE,
        help="Accounting case path or pinned URL. Defaults to the pinned StructMemEval accounting sample.",
    )
    parser.add_argument(
        "--answer",
        action="append",
        default=[],
        help="Optional candidate answer text to normalize and compare. Repeatable.",
    )
    parser.add_argument("--output", help="Write JSON packet to this path.")
    parser.add_argument("--store-db", help="Optional SQLite DB for no-write row-count proof.")
    parser.add_argument(
        "--review-summary",
        action="store_true",
        help="Emit a compact human-review summary instead of the full normalizer packet.",
    )
    parser.add_argument(
        "--allow-other-url",
        action="store_true",
        help="Review-only override for non-default URLs. Verification should not use this.",
    )
    args = parser.parse_args()

    before = store_counts(args.store_db) if args.store_db else None
    raw, source_mode = load_source(args.case, args.allow_other_url)
    case = normalize_case(raw, args.case, source_mode)
    candidate_answers = [
        compare_candidate(answer, case["reference_variants"], index)
        for index, answer in enumerate(args.answer, start=1)
    ]

    transaction_counts = [variant["transaction_count"] for variant in case["reference_variants"]]
    packet = {
        "schema": SCHEMA,
        "source_head": SOURCE_HEAD,
        "family": "accounting",
        "official_runner_import_allowed": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "raw_content_in_output": False,
        "comparison_mode": "exact_canonical_transaction_set",
        "grammar": [name for name, _pattern in PATTERNS],
        "case": {
            key: value
            for key, value in case.items()
            if key != "reference_variants"
        },
        "summary": {
            "reference_variant_count": len(case["reference_variants"]),
            "reference_transaction_count_min": min(transaction_counts),
            "reference_transaction_count_max": max(transaction_counts),
            "candidate_answer_count": len(candidate_answers),
            "candidate_exact_match_count": sum(
                1 for candidate in candidate_answers if candidate["exact_reference_match"]
            ),
        },
        "reference_variants": case["reference_variants"],
        "candidate_answers": candidate_answers,
        "no_write_invariant": no_write_packet(args.store_db, before),
    }

    if packet["no_write_invariant"].get("checked") and not packet["no_write_invariant"].get("passed"):
        if args.output:
            Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        fail("no-write invariant failed")

    if args.review_summary:
        packet = review_summary_packet(packet)

    text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
