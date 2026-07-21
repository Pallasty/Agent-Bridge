import importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('p11e4_result',HERE/'majorana_certificate_p11e4_source_evidence_analysis_result_validator.py')
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
def test_failure_record_verifies():
 assert MOD.verify()['status']=='PASS'
def test_zero_read_boundary():
 record=json.loads(MOD.R.read_bytes())
 assert record['source_text_read'] is False
 assert record['excerpt_count']==0
 assert record['scientific_authority']=='NONE'
def test_missing_declared_path_is_real():
 rows=json.loads(MOD.M.read_bytes())
 assert not any(row.get('relative_path')=='gcc/gcc.cc' and row.get('type')=='file' for row in rows)
 assert any(row.get('relative_path')=='gcc-15.2.0.tar.xz' and row.get('type')=='file' for row in rows)
