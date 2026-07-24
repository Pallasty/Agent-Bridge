#!/usr/bin/env python3
"""D44 normalizes existing D43 receipt fields; no scientific action."""
from __future__ import annotations
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def normalize():
 r=json.loads((HERE/'fh_l8_local_cost_survey_replay_d43_result.json').read_text())
 if not r.get('structural_rows_match') or r.get('packed_q3_reads')!=0: raise ValueError('D43 structural receipt drift')
 return {'status':'VERIFIED_D44_RESOURCE_OBSERVATION_NORMALIZATION','structural_digest_authoritative':True,'structural_rows_sha256':r['d43_structural_rows_sha256'],'structural_rows_match':True,'rss_metric':'ru_maxrss_process_peak','rss_observed_min_kib':r['d43_peak_rss_observed_kib_min'],'rss_observed_max_kib':r['d43_peak_rss_observed_kib_max'],'rss_stable':False,'rss_difference_interpretation':'environment_or_allocator_variance_not_structural_output_drift','measurement_policy':{'sample_every_run':True,'record_process_peak':True,'record_kernel_only_delta':False,'same_cpu_affinity_required_for_comparison':True,'full_run_extrapolation_forbidden':True},'scientific_action_calls':0,'packed_q3_reads':0,'full_53_scientific_execution_authorized':False,'next_gate':'D45_REPLAY_WITH_CONTROLLED_RESOURCE_MEASUREMENT'}
if __name__=='__main__': print(json.dumps(normalize(),sort_keys=True))
