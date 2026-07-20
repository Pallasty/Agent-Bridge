#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
A14=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-proof-boundary-contract-s21b-a14-v0.json"
A15=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-evidence-request-template-contract-s21b-a15-v0.json"
REQUEST_IDS=("S21B_A15_CREDENTIAL_ENVIRONMENT_V1","S21B_A15_OWNER_AUTHORIZATION_V1","S21B_A15_REAL_INPUT_SCOPE_V1","S21B_A15_RUNTIME_PATH_V1","S21B_A15_FRESHNESS_REVOCATION_V1","S21B_A15_LIVE_OUTPUT_BOUNDARY_V1")

def canonical_bytes(value): return (json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def load(path):
 raw=path.read_bytes(); value=json.loads(raw)
 if raw!=canonical_bytes(value): raise ValueError(f"noncanonical JSON: {path.name}")
 return value,raw
def digest(domain,payload):
 body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=domain.encode("ascii")
 return hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest()
def build(register_path):
 a15,_=load(A15); a14,a14_raw=load(A14)
 if hashlib.sha256(a14_raw).hexdigest()!=a15["a14_contract_sha256"]: raise ValueError("A14 contract version mismatch")
 reg,reg_raw=load(register_path)
 expected={"a13_audit_digest_sha256","a13_audit_sha256","capability_change_requires_all_uncovered_requirements","execution_capability_present","format_id","input_mode","owner_authority_present","proof_boundary_register_digest_sha256","real_experiment_input_admitted","side_effects_unlocked","test_only","uncovered_requirements","validity_boundary"}
 if set(reg)!=expected: raise ValueError("A14 register field set mismatch")
 claimed=reg.pop("proof_boundary_register_digest_sha256")
 if claimed!=digest(a14["verification_digest_domain"],reg): raise ValueError("A14 register self digest mismatch")
 if reg["format_id"]!=a14["format_id"] or reg["input_mode"]!=a14["input_mode"]: raise ValueError("A14 register contract mismatch")
 if reg["capability_change_requires_all_uncovered_requirements"] is not True: raise ValueError("A14 closure rule mismatch")
 if any(reg[k] is not False for k in ("execution_capability_present","owner_authority_present","real_experiment_input_admitted")): raise ValueError("A14 capability boundary mismatch")
 req=[item["requirement"] for item in reg["uncovered_requirements"]]
 if req!=a14["required_uncovered_requirements"] or any(item["status"]!="UNPROVEN_REQUIRED_FOR_CAPABILITY_CHANGE" for item in reg["uncovered_requirements"]): raise ValueError("A14 requirements mismatch")
 templates=[{"prior_response_reuse_allowed":False,"real_input_admission_present":False,"request_id":request_id,"request_is_execution_capability":False,"request_is_owner_authority":False,"requirement":requirement,"single_use_response_binding_required":True,"state":a15["template_state"]} for request_id,requirement in zip(REQUEST_IDS,req,strict=True)]
 payload={"a14_register_digest_sha256":claimed,"a14_register_sha256":hashlib.sha256(reg_raw).hexdigest(),"execution_capability_present":False,"format_id":a15["format_id"],"input_mode":a15["input_mode"],"owner_authority_present":False,"side_effects_unlocked":"NONE","template_state":a15["template_state"],"templates":templates,"test_only":True,"validity_boundary":a15["validity_boundary"]}
 return {"template_set_digest_sha256":digest(a15["verification_digest_domain"],payload),**payload}
def main():
 if len(sys.argv)!=2: raise SystemExit("usage: builder A14_REGISTER")
 try: result=build(pathlib.Path(sys.argv[1]))
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError): sys.stderr.write("S21B_A15_EVIDENCE_TEMPLATE_SET_REJECTED\n"); return 65
 sys.stdout.buffer.write(canonical_bytes(result)); return 0
if __name__=="__main__": raise SystemExit(main())
