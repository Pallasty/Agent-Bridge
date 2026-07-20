#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; C=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-fresh-revocation-clearance-contract-s21b-a19-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",", ":"))+"\n").encode("ascii")
try:
 p=pathlib.Path(sys.argv[1]); packet=pathlib.Path(sys.argv[2]); c=json.loads(C.read_text(encoding="ascii")); raw=packet.read_bytes(); v=json.loads(raw); assert raw==canon(v); claimed=v.pop("clearance_digest_sha256"); body=json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=c["verification_digest_domain"].encode("ascii"); want=hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest(); assert claimed==want and v["packet_sha256"]==hashlib.sha256(p.read_bytes()).hexdigest() and v["freshness_state"]=="STALE" and v["revocation_state"]=="NOT_CLEARED" and v["instantiation_allowed"] is False and v["request_instance_issued"] is False and v["result"]=="FRESHNESS_OR_REVOCATION_CLEARANCE_REQUIRED" and v["side_effects_unlocked"]=="NONE" and v["test_only"] is True and v["validity_boundary"]==c["validity_boundary"]
 print("S21B_A19_FRESH_REVOCATION_CLEARANCE_GATE\tPASS")
except Exception: sys.stderr.write("S21B_A19_FRESH_REVOCATION_CLEARANCE_CHECK_REJECTED\n"); raise SystemExit(65)
