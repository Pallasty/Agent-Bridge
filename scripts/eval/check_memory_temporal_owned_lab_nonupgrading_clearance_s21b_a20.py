#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; C=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-clearance-contract-s21b-a20-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
try:
 packet=pathlib.Path(sys.argv[1]); statement=pathlib.Path(sys.argv[2]); c=json.loads(C.read_text(encoding="ascii")); raw=statement.read_bytes(); v=json.loads(raw); assert raw==canon(v); claimed=v.pop("nonupgrade_digest_sha256"); body=json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=c["verification_digest_domain"].encode("ascii"); assert claimed==hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest(); assert v["packet_sha256"]==hashlib.sha256(packet.read_bytes()).hexdigest() and v["capability_upgrade_allowed"] is False and v["freshness_state"]=="FRESH" and v["revocation_state"]=="CLEARED" and v["instantiation_allowed"] is False and v["request_instance_issued"] is False and v["execution_capability_present"] is False and v["owner_authority_present"] is False and v["result"]=="PRECONDITIONS_DO_NOT_UPGRADE_CAPABILITY" and v["side_effects_unlocked"]=="NONE" and v["test_only"] is True and v["validity_boundary"]==c["validity_boundary"]
 print("S21B_A20_NONUPGRADING_CLEARANCE_GATE\tPASS")
except Exception: sys.stderr.write("S21B_A20_NONUPGRADING_CLEARANCE_CHECK_REJECTED\n"); raise SystemExit(65)
