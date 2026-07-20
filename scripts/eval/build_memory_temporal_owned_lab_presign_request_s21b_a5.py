#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,secrets,stat,struct,subprocess
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator

ROOT=pathlib.Path(__file__).resolve().parents[2]
SUBJECT_SCHEMA=ROOT/"docs/design/fixtures/biocortex-ab-track-b-owned-lab-refrozen-unsigned-subject-schema-s21b-a4-v0.json"
SUBJECT_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a4/refrozen-unsigned-subject/v1"
ANCHOR_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a5/pending-owner-anchor/v1"
PAYLOAD_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a5/owner-review-signed-payload/v1"
SIGNATURE_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a5/owner-review-signature/v1"
REQUEST_DOMAIN=b"agent-bridge/biocortex/owned-lab/s21b-a5/presign-request/v1"
def canon(v): return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def frame(domain,payload): return struct.pack(">I",len(domain))+domain+struct.pack(">Q",len(payload))+payload
def self_hash(v,field,domain): p=dict(v); claimed=p.pop(field); actual=sha(frame(domain,canon(p))); assert claimed==actual; return actual
def load_json(path):
    raw=path.read_bytes(); assert raw.endswith(b"\n") and not raw.endswith(b"\n\n"); value=json.loads(raw[:-1]); assert raw==canon(value)+b"\n"; return value,raw
def public_key(path):
    raw=path.read_bytes(); assert b"PRIVATE KEY" not in raw; key=serialization.load_pem_public_key(raw); assert isinstance(key,Ed25519PublicKey); assert raw==key.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo); public=key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); return public
def write_new(path,data,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    with os.fdopen(fd,"wb") as out: out.write(data); out.flush(); os.fsync(out.fileno())
def subject(path):
    value,raw=load_json(path); Draft202012Validator(json.loads(SUBJECT_SCHEMA.read_text())).validate(value); self_hash(value,"subject_sha256",SUBJECT_DOMAIN); assert stat.S_IMODE(path.stat().st_mode)==0o600; return value,raw
def objects(subject_value,subject_raw,public,key_id,challenge,capability):
    anchor={"algorithm":"Ed25519","anchor_state":"PENDING_OWNER_POSSESSION_PROOF_NOT_INSTALLED","audience":"agent-bridge/biocortex/owned-lab/s21b-a5/exact-subject-owner-review/v1","key_id":key_id,"key_version":1,"public_key_hex":public.hex(),"public_key_sha256":sha(public),"private_key_read":False,"repository_key_material_present":False}; anchor["anchor_sha256"]=sha(frame(ANCHOR_DOMAIN,canon(anchor)))
    target=subject_value["target_binding"]
    payload={"anchor_sha256":anchor["anchor_sha256"],"audience":anchor["audience"],"automatic_retry_allowed":False,"capability_nonce_sha256":sha(capability),"challenge_nonce_sha256":sha(challenge),"decision":"CONFIRM_EXACT_UNSIGNED_SUBJECT_FOR_NEXT_NON_LIVE_REVIEW_ONLY","execution_start_permitted":False,"external_input_admission_permitted":False,"integration_commit":target["integration_commit"],"integration_tree":target["integration_tree"],"key_id":key_id,"key_version":1,"side_effects_unlocked":"NONE","single_use":True,"subject_file_sha256":sha(subject_raw),"subject_sha256":subject_value["subject_sha256"]}
    payload_sha=sha(frame(PAYLOAD_DOMAIN,canon(payload))); message=struct.pack(">I",len(SIGNATURE_DOMAIN))+SIGNATURE_DOMAIN+struct.pack(">Q",32)+bytes.fromhex(payload_sha)
    request={"anchor":anchor,"hashing":{"anchor_domain":ANCHOR_DOMAIN.decode(),"payload_domain":PAYLOAD_DOMAIN.decode(),"request_domain":REQUEST_DOMAIN.decode(),"signature_domain":SIGNATURE_DOMAIN.decode(),"signature_message_framing":"U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_SIGNED_PAYLOAD_SHA256"},"nonclaims":{"execution_capability_present":False,"external_input_admission_present":False,"live_execution_permitted":False,"owner_authority_established":False,"owner_signature_present":False,"side_effects_unlocked":"NONE"},"packet_kind":"S21B_A5_OWNER_PRESIGN_REQUEST","payload":payload,"payload_sha256":payload_sha,"signature_message_byte_count":len(message),"signature_message_sha256":sha(message),"state":"PENDING_OWNER_DETACHED_ED25519_SIGNATURE"}; request["request_sha256"]=sha(frame(REQUEST_DOMAIN,canon(request)))
    return anchor,payload,message,request
def verify(directory,subject_path,public_path):
    sv,sraw=subject(subject_path); pub=public_key(public_path); challenge=(directory/"challenge-nonce.bin").read_bytes(); capability=(directory/"capability-nonce.bin").read_bytes(); assert len(challenge)==len(capability)==32 and challenge!=capability
    observed_anchor,_=load_json(directory/"pending-anchor.json"); observed_payload,_=load_json(directory/"signed-payload.json"); observed_request,_=load_json(directory/"presign-request.json"); message=(directory/"signing-message.bin").read_bytes(); expected=objects(sv,sraw,pub,observed_anchor["key_id"],challenge,capability)
    assert (observed_anchor,observed_payload,message,observed_request)==expected
    for name in ("challenge-nonce.bin","capability-nonce.bin","pending-anchor.json","signed-payload.json","signing-message.bin","presign-request.json"): assert stat.S_IMODE((directory/name).stat().st_mode)==0o600
    assert stat.S_IMODE(directory.stat().st_mode)==0o700; return observed_request
def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True); p=sub.add_parser("prepare"); p.add_argument("--subject",type=pathlib.Path,required=True); p.add_argument("--public-key",type=pathlib.Path,required=True); p.add_argument("--key-id",required=True); p.add_argument("--output-dir",type=pathlib.Path,required=True); v=sub.add_parser("verify"); v.add_argument("--subject",type=pathlib.Path,required=True); v.add_argument("--public-key",type=pathlib.Path,required=True); v.add_argument("--request-dir",type=pathlib.Path,required=True); sub.add_parser("self-test"); ns=ap.parse_args()
    if ns.cmd=="self-test": assert len(frame(b"x",b"y"))==14; print("S21B_A5_PRESIGN_KAT\tPASS"); return
    if ns.cmd=="prepare":
        sv,sraw=subject(ns.subject.resolve()); pub=public_key(ns.public_key.resolve()); out=ns.output_dir.resolve(); assert not out.exists() and not out.is_relative_to(ROOT.resolve()); out.mkdir(mode=0o700)
        challenge=secrets.token_bytes(32); capability=secrets.token_bytes(32); assert challenge!=capability; anchor,payload,message,request=objects(sv,sraw,pub,ns.key_id,challenge,capability)
        for name,data in (("challenge-nonce.bin",challenge),("capability-nonce.bin",capability),("pending-anchor.json",canon(anchor)+b"\n"),("signed-payload.json",canon(payload)+b"\n"),("signing-message.bin",message),("presign-request.json",canon(request)+b"\n")): write_new(out/name,data)
        observed=verify(out,ns.subject.resolve(),ns.public_key.resolve())
    else: observed=verify(ns.request_dir.resolve(),ns.subject.resolve(),ns.public_key.resolve())
    print(f"S21B_A5_PRESIGN_{ns.cmd.upper()}\tPASS\nrequest_sha256\t{observed['request_sha256']}\npayload_sha256\t{observed['payload_sha256']}\nsigning_message_sha256\t{observed['signature_message_sha256']}")
if __name__=="__main__": main()
