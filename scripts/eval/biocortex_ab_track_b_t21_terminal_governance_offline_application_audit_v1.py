"""Pure-offline, fail-closed terminal governance audit for Track B T01--T20."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = "scripts/eval/fixtures/biocortex_ab_track_b_t21_terminal_governance_offline_application_audit_v1.v0.json"
DOMAIN = "AB_TRACK_B_T21_TERMINAL_GOVERNANCE_OFFLINE_APPLICATION_AUDIT_V1"

def canon(x): return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
def sha(x): return hashlib.sha256(DOMAIN.encode()+b"\0"+canon(x)).hexdigest()
def load(): return json.loads((ROOT/FIXTURE).read_text())

def audit(x):
    assert set(x)=={"schema","chain","allowed_offline_applications","forbidden_capabilities","content_sha256"}
    assert x["schema"]=="agent_bridge.biocortex.track_b.t21_terminal_governance_audit.v1"
    chain=x["chain"]; assert len(chain)==20 and [v["unit"] for v in chain]==[f"T{i:02d}" for i in range(1,21)]
    assert all(set(v)=={"unit","coverage","artifact"} and v["coverage"]=="SYNTHETIC_OFFLINE_ONLY" and (ROOT/v["artifact"]).is_file() for v in chain)
    apps=x["allowed_offline_applications"]
    assert [v["id"] for v in apps]==["synthetic_packet_inspector","deterministic_replay_trainer","static_integration_linter"]
    assert all(v["read_only"] is True and v["network"] is False and v["real_evidence"] is False for v in apps)
    forbidden=x["forbidden_capabilities"]; names={"real_production_control","network_provider_runtime","real_evidence_ingestion","positive_production_decision","downstream_execution","successor_authorization"}
    assert set(forbidden)==names and all(forbidden.values())
    body=dict(x); claimed=body.pop("content_sha256"); assert claimed==sha(body)
    r={"schema":"agent_bridge.biocortex.track_b.t21_terminal_governance_audit.receipt.v0","status":"PASS_OFFLINE_APPLICATIONS_ONLY","covered_unit_count":20,"synthetic_only_unit_count":20,"allowed_application_count":3,"real_production_control":False,"network_provider_runtime":False,"real_evidence_ingestion":False,"positive_production_decision":False,"downstream_execution":False,"successor_authorization":False,"explainability_scope":"SYNTHETIC_RECEIPT_AND_POLICY_TRACE_ONLY","content_sha256":"0"*64}
    u=dict(r); u.pop("content_sha256"); r["content_sha256"]=sha(u); return r

if __name__=="__main__":
    print("\n".join(f"{k}\t{str(v).lower() if type(v) is bool else v}" for k,v in audit(load()).items()))
