#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; CONTRACT=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-review-precondition-crosscheck-contract-s21b-a18-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def main():
 if len(sys.argv)!=3: raise SystemExit("usage: checker MATRIX CROSSCHECK")
 matrix,statement=map(pathlib.Path,sys.argv[1:]); c=json.loads(CONTRACT.read_text(encoding="ascii")); raw=statement.read_bytes(); v=json.loads(raw); assert raw==canon(v); claimed=v.pop("crosscheck_digest_sha256"); body=json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=c["verification_digest_domain"].encode("ascii")
 assert claimed==hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest(); assert v["format_id"]==c["format_id"] and v["input_matrix_sha256"]==hashlib.sha256(matrix.read_bytes()).hexdigest() and v["independent_review_structure_valid"] is True and v["fresh_bindings_all_present"] is False and v["instantiation_allowed"] is False and v["request_instance_issued"] is False and v["result"]=="REVIEW_STRUCTURE_CANNOT_SATISFY_FRESH_PRECONDITIONS" and v["side_effects_unlocked"]=="NONE" and v["test_only"] is True and v["validity_boundary"]==c["validity_boundary"]
 print("S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_GATE\tPASS")
if __name__=="__main__": main()
