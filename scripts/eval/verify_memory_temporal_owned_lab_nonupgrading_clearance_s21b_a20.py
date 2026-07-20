#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; A19=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-fresh-revocation-clearance-contract-s21b-a19-v0.json"; A20=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-clearance-contract-s21b-a20-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",": ".replace(" ","")))+"\n").encode("ascii")
def load(p):
 raw=p.read_bytes(); v=json.loads(raw)
 if raw!=canon(v): raise ValueError()
 return v,raw
def digest(domain,payload):
 body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=domain.encode("ascii")
 return hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest()
def main():
 if len(sys.argv)!=2: raise SystemExit("usage: verifier PACKET")
 try:
  a19,a19raw=load(A19); a20,_=load(A20); packet,raw=load(pathlib.Path(sys.argv[1]))
  if hashlib.sha256(a19raw).hexdigest()!=a20["a19_contract_sha256"] or packet["format_id"]!=a20["format_id"]: raise ValueError()
  if packet["freshness_state"]!="FRESH" or packet["revocation_state"]!="CLEARED": raise ValueError()
  for key in ("accepted_for_capability_change","execution_capability_present","owner_authority_present","real_experiment_input_admitted","request_instance_issued","instantiation_allowed"):
   if packet[key] is not False: raise ValueError()
  if packet["side_effects_unlocked"]!="NONE" or packet["synthetic"] is not True or packet["test_only"] is not True: raise ValueError()
  payload={"a19_contract_sha256":a20["a19_contract_sha256"],"capability_upgrade_allowed":False,"execution_capability_present":False,"freshness_state":"FRESH","instantiation_allowed":False,"owner_authority_present":False,"packet_sha256":hashlib.sha256(raw).hexdigest(),"request_instance_issued":False,"result":"PRECONDITIONS_DO_NOT_UPGRADE_CAPABILITY","revocation_state":"CLEARED","side_effects_unlocked":"NONE","test_only":True,"validity_boundary":a20["validity_boundary"]}
  sys.stdout.buffer.write(canon({"nonupgrade_digest_sha256":digest(a20["verification_digest_domain"],payload),**payload})); return 0
 except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError): sys.stderr.write("S21B_A20_NONUPGRADING_CLEARANCE_REJECTED\n"); return 65
if __name__=="__main__": raise SystemExit(main())
