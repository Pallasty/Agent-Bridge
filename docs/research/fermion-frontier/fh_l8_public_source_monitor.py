#!/usr/bin/env python3
"""Read-only currentness monitor for named FH-L8 public evidence sources."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


ARXIV_API = (
    "https://export.arxiv.org/api/query?id_list=2505.10513,2605.12600"
)
GITHUB_API = (
    "https://api.github.com/search/repositories?"
    + urllib.parse.urlencode({"q": '"2505.10513" OR "2605.12600"', "per_page": 20})
)
NATIVE_FULL_TEXT = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    "PMC10468619/fullTextXML"
)
KNOWN_ARXIV_VERSIONS = {
    "2505.10513": 3,
    "2605.12600": 1,
}
KNOWN_NATIVE_DATA_STATEMENT = "All study data are included in the main text."


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, application/atom+xml, application/xml, text/xml",
            "User-Agent": "Agent-Bridge-FH-L8-public-source-monitor/1",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_arxiv_versions(raw: bytes) -> dict[str, int]:
    root = ET.fromstring(raw)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    versions: dict[str, int] = {}
    for entry in root.findall("atom:entry", namespace):
        identifier = entry.findtext("atom:id", default="", namespaces=namespace)
        tail = identifier.rsplit("/", 1)[-1]
        paper_id, marker, version_text = tail.rpartition("v")
        if not marker or not version_text.isdigit():
            continue
        versions[paper_id] = int(version_text)
    return versions


def parse_github_repository_count(raw: bytes) -> int:
    payload = json.loads(raw)
    count = payload.get("total_count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("GitHub search total_count must be a nonnegative integer")
    return count


def parse_native_data_statement(raw: bytes) -> str:
    root = ET.fromstring(raw)
    for section in root.iter():
        if section.attrib.get("sec-type") == "data-availability-statement":
            statement = " ".join(
                part.strip() for part in section.itertext() if part.strip()
            )
            prefix = "Data Availability Statement "
            return statement.removeprefix(prefix)
    raise ValueError("native article data-availability statement not found")


def evaluate(fetch: Callable[[str], bytes] = fetch_url) -> dict[str, Any]:
    arxiv_versions = parse_arxiv_versions(fetch(ARXIV_API))
    github_count = parse_github_repository_count(fetch(GITHUB_API))
    native_statement = parse_native_data_statement(fetch(NATIVE_FULL_TEXT))

    reasons: list[str] = []
    missing_arxiv = sorted(set(KNOWN_ARXIV_VERSIONS) - set(arxiv_versions))
    if missing_arxiv:
        reasons.append("arXiv API omitted tracked identifiers: " + ", ".join(missing_arxiv))
    for paper_id, known_version in KNOWN_ARXIV_VERSIONS.items():
        observed = arxiv_versions.get(paper_id)
        if observed is not None and observed != known_version:
            reasons.append(
                f"arXiv version changed for {paper_id}: v{known_version} -> v{observed}"
            )
    if github_count:
        reasons.append(f"GitHub exact-identifier search has {github_count} candidate repositories")
    if native_statement != KNOWN_NATIVE_DATA_STATEMENT:
        reasons.append("native-fermion data-availability statement changed")

    return {
        "schema_version": 1,
        "monitor_id": "FH-L8-PUBLIC-SOURCE-MONITOR-V1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "REVIEW_REQUIRED" if reasons else "UNCHANGED",
        "review_reasons": reasons,
        "observations": {
            "arxiv_versions": arxiv_versions,
            "github_exact_identifier_repository_count": github_count,
            "native_data_availability_statement": native_statement,
        },
        "boundary": (
            "Currentness signals only; UNCHANGED is not a global absence proof and "
            "REVIEW_REQUIRED is not scientific admission."
        ),
    }


def check() -> dict[str, Any]:
    try:
        return evaluate()
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as error:
        return {
            "schema_version": 1,
            "monitor_id": "FH-L8-PUBLIC-SOURCE-MONITOR-V1",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "CHECK_FAILED",
            "review_reasons": [],
            "failure": {
                "error_type": type(error).__name__,
                "message": str(error),
            },
            "boundary": (
                "Source currentness was not established. CHECK_FAILED must not be "
                "treated as UNCHANGED, source absence, or scientific admission."
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=argparse.FileType("w", encoding="utf-8"))
    args = parser.parse_args()
    result = check()
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.write(rendered + "\n")
    exit_codes = {"UNCHANGED": 0, "REVIEW_REQUIRED": 2, "CHECK_FAILED": 3}
    raise SystemExit(exit_codes[result["status"]])


if __name__ == "__main__":
    main()
