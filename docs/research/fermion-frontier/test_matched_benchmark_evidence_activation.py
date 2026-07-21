import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent/'matched_benchmark_evidence_activation_validator.py'
S=importlib.util.spec_from_file_location('activation',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_baseline_is_fail_closed(): assert M.verify()['status']=='BASELINE_UNRESOLVED_EXTERNAL_EVIDENCE_REQUIRED'
