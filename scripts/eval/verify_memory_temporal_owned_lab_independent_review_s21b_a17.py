#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
CONTRACT=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-independent-review-contract-s21b-a17-v0.json"
HEX=re.compile(r"^[0-9a-f]{64}$")
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def load(p):
 raw=p.read_bytes(); v=json.loads(raw)
 if raw!=canon(v): raise ValueError(f"noncanonical JSON: {p.name}")
 return v,raw
def digest(domain,payload):
 body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=domain.encode("ascii")
 return hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest()
def verify(packet_path):
 contract,_=load(CONTRACT); packet,raw=load(packet_path)
 required=set(contract["minimum_fields"]+['accepted_for_capability_change','execution_capability_present','format_id','real_experiment_input_admitted','reviewer_is_subject','side_effects_unlocked','synthetic','subject_identity_sha256','test_only'])
 if set(packet)!=required: raise ValueError("review packet field set mismatch")
 if packet["format_id"]!=contract["format_id"]: raise ValueError("review format mismatch")
 for field in contract["minimum_fields"]:
  if not HEX.fullmatch(packet[field]): raise ValueError(f"{field} is not SHA-256 hex")
 if packet["reviewer_identity_sha256"]==packet["subject_identity_sha256"] or packet["reviewer_is_subject"] is not False: raise ValueError("reviewer is subject")
 if packet["accepted_for_capability_change"] is not False or packet["execution_capability_present"] is not False or packet["real_experiment_input_admitted"] is not False or packet["side_effects_unlocked"]!="NONE" or packet["synthetic"] is not True or packet["test_only"] is not True: raise ValueError("review acceptance boundary mismatch")
 payload={"format_id":contract["format_id"],"review_packet_sha256":hashlib.sha256(raw).hexdigest(),"reviewer_distinct_from_subject":True,"result":"STRUCTURE_VALID_SYNTHETIC_NOT_ACCEPTED","side_effects_unlocked":"NONE","test_only":True,"validity_boundary":contract["validity_boundary"]}
 return {"independent_review_structure_digest_sha256":digest(contract["verification_digest_domain"],payload),**payload}
def main():
 if len(sys.argv)!=2: raise SystemExit("usage: verifier REVIEW_PACKET")
 try: out=verify(pathlib.Path(sys.argv[1]))
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError): sys.stderr.write("S21B_A17_INDEPENDENT_REVIEW_REJECTED\n"); return 65
 sys.stdout.buffer.write(canon(out)); return 0
if __name__=="__main__": raise SystemExit(main())
