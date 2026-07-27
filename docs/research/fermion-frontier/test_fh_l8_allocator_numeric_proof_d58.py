import json
from pathlib import Path
from fh_l8_allocator_numeric_proof_d58 import verify

def test_d58_numeric_proof_is_fail_closed_and_covers_eight_variables():
    result = verify()
    assert result["variable_count"] == 8
    assert result["missing_variable_count"] == 8
    assert result["decision"] == "NO_GO_D58_NUMERIC_INPUTS_INCOMPLETE"
    assert result["numeric_peak_memory_proven"] is False
    assert result["full53_execution_authorized"] is False
