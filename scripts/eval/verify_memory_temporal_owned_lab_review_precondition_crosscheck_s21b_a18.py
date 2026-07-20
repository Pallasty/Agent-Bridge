#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
A16=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-request-instantiation-precondition-contract-s21b-a16-v0.json"; A17=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-independent-review-contract-s21b-a17-v0.json"; A18=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-review-precondition-crosscheck-contract-s21b-a18-v0.json"; HEX=re.compile(r"^[0-9a-f]{64}$")
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def load(p):
 raw=p.read_bytes(); v=json.loads(raw)
 if raw!=canon(v): raise ValueError(f"noncanonical JSON: {p.name}")
 return v,raw
def digest(domain,payload):
 body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=domain.encode("ascii")
 return hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest()
def verify(matrix_path,review_path):
 a18,_=load(A18); a16,a16raw=load(A16); a17,a17raw=load(A17); matrix,matrixraw=load(matrix_path); review,reviewraw=load(review_path)
 if hashlib.sha256(a16raw).hexdigest()!=a18["a16_contract_sha256"] or hashlib.sha256(a17raw).hexdigest()!=a18["a17_contract_sha256"]: raise ValueError("contract version mismatch")
 if matrix["format_id"]!=a16["format_id"] or matrix["template_state"]!=a16["template_state"] or matrix["request_instance_issued"] is not False: raise ValueError("A16 matrix boundary mismatch")
 bindings=a18["required_fresh_bindings"]
 if any(item["instantiation_allowed"] is not False or [b["binding"] for b in item["fresh_bindings"]]!=bindings or any(b["status"]!="REQUIRED_ABSENT" for b in item["fresh_bindings"]) for item in matrix["matrix"]): raise ValueError("fresh preconditions not absent")
 required=set(a17["minimum_fields"]+["accepted_for_capability_change","execution_capability_present","format_id","real_experiment_input_admitted","reviewer_is_subject","side_effects_unlocked","synthetic","subject_identity_sha256","test_only"])
 if set(review)!=required or review["format_id"]!=a17["format_id"]: raise ValueError("review field set mismatch")
 if any(not HEX.fullmatch(review[f]) for f in a17["minimum_fields"]): raise ValueError("review digest missing")
 if review["reviewer_identity_sha256"]==review["subject_identity_sha256"] or review["reviewer_is_subject"] is not False: raise ValueError("reviewer is subject")
 if review["accepted_for_capability_change"] is not False or review["execution_capability_present"] is not False or review["real_experiment_input_admitted"] is not False or review["side_effects_unlocked"]!="NONE" or review["synthetic"] is not True or review["test_only"] is not True: raise ValueError("review boundary mismatch")
 payload={"fresh_bindings_all_present":False,"fresh_bindings_required":bindings,"format_id":a18["format_id"],"input_matrix_sha256":hashlib.sha256(matrixraw).hexdigest(),"independent_review_structure_valid":True,"review_packet_sha256":hashlib.sha256(reviewraw).hexdigest(),"instantiation_allowed":False,"result":"REVIEW_STRUCTURE_CANNOT_SATISFY_FRESH_PRECONDITIONS","request_instance_issued":False,"side_effects_unlocked":"NONE","test_only":True,"validity_boundary":a18["validity_boundary"]}
 return {"crosscheck_digest_sha256":digest(a18["verification_digest_domain"],payload),**payload}
def main():
 if len(sys.argv)!=3: raise SystemExit("usage: verifier A16_MATRIX A17_REVIEW")
 try: out=verify(pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]))
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError): sys.stderr.write("S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_REJECTED\n"); return 65
 sys.stdout.buffer.write(canon(out)); return 0
if __name__=="__main__": raise SystemExit(main())
