#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[2]
PFX="docs/design/fixtures/biocortex-ab-track-b-owned-lab-postintegration-refreeze"
CONTRACT=ROOT/f"{PFX}-contract-s21b-a3-v0.json"
SCHEMA=ROOT/f"{PFX}-receipt-schema-s21b-a3-v0.json"
FIXTURE=ROOT/f"{PFX}-receipt-synthetic-s21b-a3-v0.json"
DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a3/postintegration-refreeze-receipt/v1"

def nodup(pairs):
    value={}
    for key, item in pairs:
        assert key not in value, f"duplicate JSON key: {key}"
        value[key]=item
    return value

def load(p):
    raw=p.read_bytes(); assert raw.endswith(b"\n") and raw[:-1].isascii()
    value=json.loads(raw[:-1], object_pairs_hook=nodup)
    assert raw==json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode()+b"\n"
    return value,raw

def check():
    contract,_=load(CONTRACT); schema,_=load(SCHEMA); fixture,raw=load(FIXTURE)
    Draft202012Validator(schema).validate(fixture)
    payload=dict(fixture); claimed=payload.pop("role_build_receipt_sha256")
    body=json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode()
    actual=hashlib.sha256(struct.pack(">I",len(DOMAIN))+DOMAIN+struct.pack(">Q",len(body))+body).hexdigest()
    assert claimed==actual and claimed!="0"*64
    p=contract["a2_predecessor_binding"]
    assert p["integration_commit"]=="65614271a7170d52c1eaef78ff3ec35cc02fdae5"
    assert p["integration_tree"]=="dd889e6e7700aef3d384cc7add39b5341f52b83a"
    assert p["a2_delta_added_path_count"]==9
    assert fixture["test_only"] and fixture["synthetic"]
    assert fixture["target_binding"]["target_refrozen"] is False
    assert fixture["rebuilds"]["double_rebuild_complete"] is False
    assert fixture["role_artifacts"]["completed_role_count"]==0
    assert fixture["result"]["real_unsigned_subject_present"] is False
    assert fixture["result"]["owner_signature_may_be_requested"] is False
    assert fixture["result"]["live_execution_may_begin"] is False
    assert fixture["result"]["side_effects_unlocked"]=="NONE"
    return [("schema",fixture["schema"]),("packet_kind",fixture["packet_kind"]),("receipt_state",fixture["receipt_state"]),("receipt_sha256",actual),("fixture_sha256",hashlib.sha256(raw).hexdigest()),("a2_predecessor",p["integration_commit"]),("double_rebuild","PENDING"),("real_unsigned_subject","NOT_GENERATED"),("owner_signature","NOT_REQUESTED"),("live_execution","NOT_RUN"),("side_effects_unlocked","NONE"),("gate","PASS")]

def main():
    argparse.ArgumentParser().parse_args()
    print("\n".join(f"{k}\t{v}" for k,v in check()))

if __name__=="__main__": main()
