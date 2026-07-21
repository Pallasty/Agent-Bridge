import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent/'majorana_certificate_p11e4s_archive_metadata_inspection_result_validator.py';S=importlib.util.spec_from_file_location('e4s_result',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_result_verifies():assert M.verify()['status']=='PASS'
def test_payload_boundary():
 r=M.json.loads(M.R.read_bytes());assert r['source_payload_bytes_read']==0 and not r['source_text_semantically_read'] and not r['verbatim_member_path_or_link_target_recorded']
def test_sparse_and_xattr_classes_absent():
 c=M.json.loads(M.R.read_bytes())['header_counts'];assert all(c[k]==0 for k in ['gnu_sparse_typeflag','pax_sparse_keys','tarinfo_sparse_map','xattr_or_acl_or_capability_keys'])
