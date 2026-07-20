#!/usr/bin/env python3
"""Generate or independently verify the external S21B-A4 unsigned subject."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, stat, struct, subprocess, tempfile
from jsonschema import Draft202012Validator

ROOT=pathlib.Path(__file__).resolve().parents[2]
SUBJECT_SCHEMA=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-refrozen-unsigned-subject-schema-s21b-a4-v0.json"
RECEIPT_SCHEMA=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-postintegration-refreeze-receipt-schema-s21b-a3-v0.json"
SUBJECT_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a4/refrozen-unsigned-subject/v1"
RECEIPT_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a3/postintegration-refreeze-receipt/v1"
ROLES=("controller","observer","runner","validator")

def nodup(pairs):
    value={}
    for key,item in pairs:
        assert key not in value, f"duplicate JSON key: {key}"
        value[key]=item
    return value
def canon(value): return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode()
def digest(data): return hashlib.sha256(data).hexdigest()
def framed(domain,payload): return struct.pack(">I",len(domain))+domain+struct.pack(">Q",len(payload))+payload
def git_bytes(*args): return subprocess.check_output(["git",*args],cwd=ROOT)
def git_text(*args): return git_bytes(*args).decode("ascii").strip()
def load_canonical(path):
    raw=path.read_bytes(); assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    value=json.loads(raw[:-1],object_pairs_hook=nodup); assert raw==canon(value)+b"\n"
    return value,raw
def self_hash(value,field,domain):
    payload=dict(value); claimed=payload.pop(field); actual=digest(framed(domain,canon(payload))); assert claimed==actual
    return actual
def archive_binding(commit):
    with tempfile.NamedTemporaryFile(prefix="s21b-a4-archive-",dir="/Data/.ab-gate-tmp") as out:
        subprocess.run(["git","-c","tar.umask=0022","archive","--format=tar",commit],cwd=ROOT,stdout=out,check=True); out.flush(); out.seek(0); raw=out.read()
    return digest(raw),len(raw)
def validate_receipt(path,commit):
    receipt,raw=load_canonical(path); Draft202012Validator(json.loads(RECEIPT_SCHEMA.read_text())).validate(receipt); self_hash(receipt,"role_build_receipt_sha256",RECEIPT_DOMAIN)
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    assert receipt["synthetic"] is False and receipt["rebuilds"]["double_rebuild_complete"] is True
    assert receipt["rebuilds"]["all_role_outputs_byte_equal"] is True and receipt["rebuilds"]["all_closure_digests_equal"] is True
    target=receipt["target_binding"]; assert target["integration_commit"]==commit and target["target_refrozen"] is True
    assert target["integration_tree"]==git_text("show","-s","--format=%T",commit)
    parents=git_text("show","-s","--format=%P",commit).split(); assert len(parents)==2 and target["integration_first_parent"]==parents[0] and target["integration_second_parent"]==parents[1]
    archive_sha,archive_bytes=archive_binding(commit); assert target["archive_sha256"]==archive_sha and target["archive_byte_count"]==archive_bytes
    assert target["cargo_lock_sha256"]==digest(git_bytes("show",f"{commit}:Cargo.lock"))
    closures=receipt["closure_bindings"]
    for key in ("toolchain_manifest_sha256","feature_set_sha256","schema_set_sha256","schema_content_set_sha256","build_recipes_sha256"): assert isinstance(closures[key],str) and len(closures[key])==64
    assert closures["candidate_supplied_expected_digests_used"] is False
    for role in ROLES:
        item=receipt["role_artifacts"][role]
        for key in ("raw_sha256","identity_sha256","build_recipe_sha256"): assert isinstance(item[key],str) and len(item[key])==64
        assert item["raw_bytes_equal"] and item["identity_sha256_equal"] and item["build_recipe_sha256_equal"]
    return receipt,raw
def expected_subject(receipt,receipt_raw):
    target=receipt["target_binding"]; closures={k:receipt["closure_bindings"][k] for k in ("toolchain_manifest_sha256","feature_set_sha256","schema_set_sha256","schema_content_set_sha256","build_recipes_sha256")}
    roles={role:{k:receipt["role_artifacts"][role][k] for k in ("binary","raw_sha256","identity_sha256","build_recipe_sha256")} for role in ROLES}
    value={"schema":"agent_bridge.memory_temporal_owned_lab_refrozen_unsigned_subject_s21b_a4.v0","packet_kind":"S21B_A4_REFROZEN_UNSIGNED_SUBJECT","canonicalization":"AB_RESTRICTED_CANONICAL_JSON_S21B_A4_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT","subject_state":"FINAL_POST_INTEGRATION_UNSIGNED_SUBJECT_VERIFIED_NON_LIVE","test_only":False,"synthetic":False,"target_binding":{k:target[k] for k in ("integration_commit","integration_tree","integration_first_parent","integration_second_parent","archive_sha256","archive_byte_count","cargo_lock_sha256")},"receipt_binding":{"schema":receipt["schema"],"packet_kind":receipt["packet_kind"],"file_sha256":digest(receipt_raw),"self_sha256":receipt["role_build_receipt_sha256"],"double_rebuild_complete":True,"external_mode_octal":"0600"},"closure_bindings":closures,"role_artifacts":roles,"signing_boundary":{"signature_present":False,"owner_private_key_read":False,"owner_signature_may_be_requested_after_independent_verification":True,"external_input_admission_may_begin":False,"live_execution_may_begin":False,"side_effects_unlocked":"NONE"},"hashing_contract":{"hash_algorithm":"SHA-256","digest_domain":"agent-bridge/biocortex/owned-lab/s21b-a4/refrozen-unsigned-subject/v1","digest_framing":"U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD","hash_scope":"ENTIRE_PACKET_EXCEPT_SUBJECT_SHA256","self_hash_field":"subject_sha256","self_hash_field_excluded":True,"repository_framing_lf_excluded":True,"candidate_reported_matches_authoritative":False},"nonclaims":{"subject_is_owner_signature":False,"subject_is_owner_authority":False,"subject_is_execution_capability":False,"subject_authorizes_live_execution":False,"side_effects_unlocked":"NONE"}}
    value["subject_sha256"]=digest(framed(SUBJECT_DOMAIN,canon(value))); Draft202012Validator(json.loads(SUBJECT_SCHEMA.read_text())).validate(value)
    return value
def outside_repo(path):
    resolved=path.resolve(); assert not resolved.is_relative_to(ROOT.resolve()); return resolved
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="command",required=True)
    for name in ("generate","verify"):
        p=sub.add_parser(name); p.add_argument("--commit",required=True); p.add_argument("--receipt",type=pathlib.Path,required=True); p.add_argument("--subject",type=pathlib.Path,required=True)
    sub.add_parser("check-schema"); ns=ap.parse_args()
    if ns.command=="check-schema": Draft202012Validator.check_schema(json.loads(SUBJECT_SCHEMA.read_text())); print("S21B_A4_SCHEMA\tPASS"); return
    commit=git_text("rev-parse",ns.commit); receipt,receipt_raw=validate_receipt(ns.receipt.resolve(),commit); expected=expected_subject(receipt,receipt_raw); expected_raw=canon(expected)+b"\n"; subject_path=outside_repo(ns.subject)
    if ns.command=="generate":
        fd=os.open(subject_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as out: out.write(expected_raw); out.flush(); os.fsync(out.fileno())
    observed,raw=load_canonical(subject_path); Draft202012Validator(json.loads(SUBJECT_SCHEMA.read_text())).validate(observed); self_hash(observed,"subject_sha256",SUBJECT_DOMAIN); assert raw==expected_raw and stat.S_IMODE(subject_path.stat().st_mode)==0o600
    print(f"S21B_A4_UNSIGNED_SUBJECT_{ns.command.upper()}\tPASS"); print(f"subject_sha256\t{observed['subject_sha256']}")
if __name__=="__main__": main()
