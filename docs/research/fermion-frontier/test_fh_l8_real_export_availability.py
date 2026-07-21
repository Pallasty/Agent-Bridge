import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent/'fh_l8_real_export_availability_validator.py'
S=importlib.util.spec_from_file_location('availability',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_fail_closed_availability(): assert M.verify()['status']=='PASS'
