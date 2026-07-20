#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
CONTRACT=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-evidence-request-template-contract-s21b-a15-v0.json"
def canonical_bytes(value): return (json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def main():
 if len(sys.argv)!=3: raise SystemExit("usage: checker A14_REGISTER TEMPLATE_SET")
 register_path,templates_path=map(pathlib.Path,sys.argv[1:]); contract=json.loads(CONTRACT.read_text(encoding="ascii")); raw=templates_path.read_bytes(); value=json.loads(raw)
 assert raw==canonical_bytes(value); claimed=value.pop("template_set_digest_sha256"); body=json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); domain=contract["verification_digest_domain"].encode("ascii")
 assert claimed==hashlib.sha256(struct.pack(">I",len(domain))+domain+struct.pack(">Q",len(body))+body).hexdigest()
 assert value["format_id"]==contract["format_id"] and value["input_mode"]==contract["input_mode"]
 assert value["a14_register_sha256"]==hashlib.sha256(register_path.read_bytes()).hexdigest()
 assert value["execution_capability_present"] is False and value["owner_authority_present"] is False and value["side_effects_unlocked"]=="NONE" and value["test_only"] is True
 assert value["template_state"]==contract["template_state"] and value["validity_boundary"]==contract["validity_boundary"]
 assert [x["request_id"] for x in value["templates"]]==contract["required_request_ids"]
 assert all(x["state"]==contract["template_state"] and x["single_use_response_binding_required"] is True and x["prior_response_reuse_allowed"] is False and x["request_is_execution_capability"] is False and x["request_is_owner_authority"] is False and x["real_input_admission_present"] is False for x in value["templates"])
 print("S21B_A15_EVIDENCE_TEMPLATE_SET_GATE\tPASS")
if __name__=="__main__": main()
