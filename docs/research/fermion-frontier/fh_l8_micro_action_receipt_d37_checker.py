#!/usr/bin/env python3
"""Read-only fail-closed verifier for the D26/D27/D30/D31/D36 micro trace."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
P={"d30":"fh_l8_single_micro_action_d30.py","d5":"fh_l8_symmetry_orbit_quotient_d5_checker.py","d4":"fh_l8_scalar_supremum_d4_checker.py","backend":"hubbard_strang_commutator_checker.py"}
class Error(ValueError):pass
def verify(root=HERE):
 root=Path(root); x=json.loads((root/'fh_l8_micro_action_timing_d36_result.json').read_text()); hashes={k:hashlib.sha256((root/v).read_bytes()).hexdigest() for k,v in P.items()}
 if x.get('source_sha256')!=hashes: raise Error('source custody drift')
 if x.get('fixture')!='D5_CONTRACT_NEEL_NONMATERIALIZED_SINGLE_REPRESENTATIVE' or x.get('representative_hex')!='0x66669999666699996666999966669999': raise Error('fixture drift')
 if x.get('scientific_action_calls')!=1 or x.get('packed_q3_reads')!=0 or x.get('full_53_scientific_execution_authorized') is not False: raise Error('authority drift')
 if not isinstance(x.get('elapsed_seconds'),(int,float)) or x['elapsed_seconds']<=0 or x.get('reduced_column_entries')!=29: raise Error('receipt drift')
 d30=json.loads((root/'fh_l8_single_micro_action_d30_result.json').read_text()); d31=json.loads((root/'fh_l8_micro_action_replay_d31_result.json').read_text())
 if d30['column_sha256']!=x['column_sha256'] or not d31['output_digest_match'] or d31['d31_column_sha256']!=x['column_sha256']: raise Error('replay drift')
 return {'status':'VERIFIED_D37_MICRO_ACTION_RECEIPT_CUSTODY_AND_REPLAY','scientific_action_calls':0,'packed_q3_reads':0,'full_53_scientific_execution_authorized':False}
