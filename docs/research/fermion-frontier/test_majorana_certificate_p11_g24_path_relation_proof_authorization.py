import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11_g24_path_relation_proof_authorization_validator.py'
S=importlib.util.spec_from_file_location('g24',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_pass(): assert M.verify()['status']=='PASS'
