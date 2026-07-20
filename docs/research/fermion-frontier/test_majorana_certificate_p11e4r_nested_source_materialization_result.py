import importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4r_nested_source_materialization_result_validator.py';S=importlib.util.spec_from_file_location('e4r_result',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_failure_record_verifies():assert M.verify()['status']=='PASS'
def test_no_materialization_or_semantic_read():
 r=json.loads(M.R.read_bytes());assert not r['derived_root_created'];assert not r['staging_directory_created'];assert not r['source_text_semantically_read']
def test_failure_is_routed_to_g17():assert json.loads(M.R.read_bytes())['next_gate']=='P11-G17-POST-NESTED-SOURCE-MATERIALIZATION-GOVERNANCE-V1'
