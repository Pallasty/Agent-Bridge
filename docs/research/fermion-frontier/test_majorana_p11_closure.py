import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_p11_closure_validator.py'
S=importlib.util.spec_from_file_location('p11_closure',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_pass(): assert M.verify()['status']=='PASS'
