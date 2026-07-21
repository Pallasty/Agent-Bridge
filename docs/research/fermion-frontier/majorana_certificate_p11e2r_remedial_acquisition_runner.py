#!/usr/bin/env python3
"""Bounded P11-E2R runner: fresh root, fail-closed APT preflight, final-path receipts."""
from __future__ import annotations
import importlib.util, json, shutil, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "majorana_certificate_p11e1_source_archive_acquisition_runner.py"
SPEC = importlib.util.spec_from_file_location("p11e1_runner", SOURCE)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

RUNNER.ROOT = Path("/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e2r-source-custody")
RUNNER.SOURCES = RUNNER.SOURCES.replace("p11-e1-source-custody", "p11-e2r-source-custody")
RUNNER.APT_CONF_LINES = [
    f'Dir::Etc "{RUNNER.ROOT / "apt/etc"}";',
    'Dir::Etc::sourcelist "ubuntu.sources";',
    'Dir::Etc::sourceparts "sourceparts";',
    'Dir::Etc::main "apt.conf";',
    'Dir::Etc::parts "configparts";',
    f'Dir::State::Lists "{RUNNER.ROOT / "apt/lists"}";',
    f'Dir::State::status "{RUNNER.ROOT / "apt/empty-status"}";',
    f'Dir::Cache::archives "{RUNNER.ROOT / "apt/archives"}";',
    'Dir::Cache::pkgcache "";',
    'Dir::Cache::srcpkgcache "";',
    'APT::Get::List-Cleanup "false";',
    'APT::Get::Download-Only "true";',
    'APT::Get::Only-Source "true";',
    'Acquire::AllowInsecureRepositories "false";',
    'Acquire::AllowDowngradeToInsecureRepositories "false";',
    'Acquire::Check-Valid-Until "true";',
    'Acquire::Languages "none";',
    'Acquire::Retries "0";',
]

ORIGINAL_SETUP = RUNNER.setup


def setup() -> None:
    ORIGINAL_SETUP()
    etc = RUNNER.ROOT / "apt/etc"
    (etc / "sourceparts").mkdir(mode=0o700, parents=True, exist_ok=True)
    (etc / "configparts").mkdir(mode=0o700, parents=True, exist_ok=True)
    (etc / "ubuntu.sources").write_text(RUNNER.SOURCES, encoding="utf-8")
    (etc / "apt.conf").write_text("\n".join(RUNNER.APT_CONF_LINES) + "\n", encoding="utf-8")


RUNNER.setup = setup


def preflight() -> None:
    setup()
    result = RUNNER.run_command("APT_CONFIG_PREFLIGHT", ["/usr/bin/apt-config", "dump"], RUNNER.ROOT, 1)
    raw = (RUNNER.ROOT / "receipts/logs/APT_CONFIG_PREFLIGHT.attempt-1.stdout").read_bytes()
    err = (RUNNER.ROOT / "receipts/logs/APT_CONFIG_PREFLIGHT.attempt-1.stderr").read_bytes()
    if result["returncode"] != 0 or b"/etc/apt" in raw or b"/etc/apt" in err or b"Warning" in err or b"warning" in err:
        raise RUNNER.AcquisitionError("APT configuration preflight failed closed")


def rewrite_final_receipts(state: dict) -> dict:
    for package in state.get("packages", []):
        accepted = RUNNER.ROOT / package["accepted_relative_path"]
        for row in package["files"]:
            final = accepted / row["filename"]
            observed = RUNNER.digest(final)
            if observed["size_bytes"] != row["size_bytes"] or observed["sha256"] != row["sha256"]:
                raise RUNNER.AcquisitionError("final accepted byte rehash failed")
            row["relative_path"] = str(final.relative_to(RUNNER.ROOT))
        receipt_path = RUNNER.ROOT / "receipts" / f"{package['source_package']}.json"
        RUNNER.write_json(receipt_path, package)
    RUNNER.write_json(RUNNER.ROOT / "receipts/state.json", state)
    return state


def main() -> int:
    try:
        preflight()
        state = RUNNER.execute()
        state = rewrite_final_receipts(state)
        print(json.dumps({"outcome": state["outcome"], "accepted_packages": len(state["packages"])}, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"status": "FATAL_PREFLIGHT_OR_RUNNER_ERROR", "error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
