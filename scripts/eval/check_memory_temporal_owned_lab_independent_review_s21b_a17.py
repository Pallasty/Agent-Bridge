#!/usr/bin/env python3
import hashlib,json,pathlib,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; CONTRACT=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-independent-review-contract-s21b-a17-v0.json"
def canon(v): return (json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
def main():
 if len(sys.argv)!=3: raise SystemExit("usage: checker REVIEW_PACKET STATEMENT")
 packet,statement=map(pathlib.Path,sys.argv[1:]); c=json.loads(CONTRACT.read_text(encoding="ascii")); raw=statement.read_bytes(); v=json.loads(raw)
 assert raw==canon(v); claimed=v.pop("independent_review_structure_digest_sha256"); body=json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("ascii"); d=c["verification_digest_domain"].encode("ascii")
 assert claimed==hashlib.sha256(struct.pack(">I",len(d))+d+struct.pack(">Q",len(body))+body).hexdigest(); assert v["format_id"]==c["format_id"] and v["review_packet_sha256"]==hashlib.sha256(packet.read_bytes()).hexdigest(); assert v["reviewer_distinct_from_subject"] is True and v["result"]=="STRUCTURE_VALID_SYNTHETIC_NOT_ACCEPTED" and v["side_effects_unlocked"]=="NONE" and v["test_only"] is True and v["validity_boundary"]==c["validity_boundary"]
 print("S21B_A17_INDEPENDENT_REVIEW_GATE\tPASS")
if __name__=="__main__": main()
