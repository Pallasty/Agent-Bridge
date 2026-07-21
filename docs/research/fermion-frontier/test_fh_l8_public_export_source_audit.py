import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parent / "fh_l8_public_export_source_audit_validator.py"
SPEC = importlib.util.spec_from_file_location("fh_l8_public_export_source_audit", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_source_audit_remains_fail_closed():
    assert MODULE.verify()["status"] == "PASS"
