import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parent / "fh_l8_public_network_deep_audit_validator.py"
SPEC = importlib.util.spec_from_file_location("fh_l8_public_network_deep_audit", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_network_path_closes_without_false_admission():
    result = MODULE.verify()
    assert result == {"status": "PASS", "next_state": "PIVOT_TO_INDEPENDENT_REFERENCE_CERTIFICATION"}
