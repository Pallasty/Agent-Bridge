#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; A18=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-review-precondition-crosscheck-contract-s21b-a18-v0.json"; A19=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-fresh-revocation-clearance-contract-s21b-a19-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",", ":"))+"\n").encode("ascii")
def load(p):
 raw=p.read_bytes(); v=json.loads(raw)
 if raw!=canon(v): raise ValueError("noncanonical")
 return v,raw
def digest(domain,payload):
 body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=domain.encode("ascii")
 return hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest()
def main():
 if len(sys.argv)!=2: raise SystemExit("usage: verifier PACKET")
 try:
  a18,a18raw=load(A18); a19,_=load(A19); packet,raw=load(pathlib.Path(sys.argv[1]))
  if hashlib.sha256(a18raw).hexdigest()!=a19["a18_contract_sha256"] or packet["format_id"]!=a19["format_id"]: raise ValueError()
  if [x["binding"] for x in packet["binding_statuses"]]!=a19["required_bindings"]: raise ValueError()
  if packet["freshness_state"]!="STALE" or packet["revocation_state"]!="NOT_CLEARED" or packet["instantiation_allowed"] is not False or packet["request_instance_issued"] is not False or packet["side_effects_unlocked"]!="NONE" or packet["synthetic"] is not True or packet["test_only"] is not True: raise ValueError()
  expected=["STALE","MISSING","NOT_CLEARED","ABSENT"]
  if [x["status"] for x in packet["binding_statuses"]]!=expected: raise ValueError()
  payload={"a18_contract_sha256":a19["a18_contract_sha256"],"freshness_state":"STALE","instantiation_allowed":False,"packet_sha256":hashlib.sha256(raw).hexdigest(),"request_instance_issued":False,"result":"FRESHNESS_OR_REVOCATION_CLEARANCE_REQUIRED","revocation_state":"NOT_CLEARED","side_effects_unlocked":"NONE","test_only":True,"validity_boundary":a19["validity_boundary"]}
  out={"clearance_digest_sha256":digest(a19["verification_digest_domain"],payload),**payload}; sys.stdout.buffer.write(canon(out)); return 0
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError): sys.stderr.write("S21B_A19_FRESH_REVOCATION_CLEARANCE_REJECTED\n"); return 65
if __name__=="__main__": raise SystemExit(main())
