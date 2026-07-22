import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parent / "fh_l8_external_source_acquisition_validator.py"
SPEC = importlib.util.spec_from_file_location("fh_l8_source_acquisition", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_route_acquisition_plan_is_fail_closed_and_complete():
    result = MODULE.verify()
    assert result["status"] == "PASS"
    assert result["next_state"] == "REQUEST_OR_LOCATE_VERSIONED_PRIMARY_EXPORTS"
