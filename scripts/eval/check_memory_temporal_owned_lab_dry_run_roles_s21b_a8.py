#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
CONTRACT=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-role-contract-s21b-a8-v0.json"
ROLES=("controller","observer","runner","validator")
def canonical(v): return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":"))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-dir",type=pathlib.Path,required=True); ns=ap.parse_args(); contract=json.loads(CONTRACT.read_text())
    packets={}
    for role in ROLES:
        raw=(ns.output_dir/f"{role}.json").read_text(); assert raw.endswith("\n") and not raw.endswith("\n\n"); value=json.loads(raw); assert raw==canonical(value)+"\n"; packets[role]=value
        expected=contract["roles"][role]; assert value["role"]==role and value["operation"]==expected["operation"] and value["state"]==expected["state"] and value["next_role"]==expected["next_role"]
        for key,want in contract["forbidden"].items(): assert value[key]==want
        assert value["arguments_accepted"] is True and value["test_only"] is True and value["operational_mode"]=="NON_LIVE_PROTOCOL_DRY_RUN_ONLY"
    assert len({canonical(v) for v in packets.values()})==4
    print("S21B_A8_DRY_RUN_ROLE_GATE\tPASS")
if __name__=="__main__": main()
