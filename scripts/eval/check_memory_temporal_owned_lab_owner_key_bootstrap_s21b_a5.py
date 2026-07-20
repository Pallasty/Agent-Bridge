#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,pathlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT=pathlib.Path(__file__).resolve().parents[2]
def inspect(path):
    resolved=path.resolve(strict=True); assert not resolved.is_relative_to(ROOT.resolve()),"real owner public key must remain outside repository"
    raw=resolved.read_bytes(); assert b"PRIVATE KEY" not in raw and raw.count(b"-----BEGIN PUBLIC KEY-----")==1 and raw.count(b"-----END PUBLIC KEY-----")==1
    key=serialization.load_pem_public_key(raw); assert isinstance(key,Ed25519PublicKey),"public key is not Ed25519"
    canonical=key.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo); assert raw==canonical,"public key PEM is not canonical SPKI"
    raw_key=key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw); assert len(raw_key)==32
    return raw_key.hex(),hashlib.sha256(raw_key).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--public-key",type=pathlib.Path); ap.add_argument("--self-test",action="store_true"); ns=ap.parse_args()
    if ns.self_test:
        key=Ed25519PublicKey.from_public_bytes(bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")); pem=key.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo); loaded=serialization.load_pem_public_key(pem); assert isinstance(loaded,Ed25519PublicKey); print("S21B_A5_PUBLIC_KEY_KAT\tPASS"); return
    assert ns.public_key is not None; raw,fingerprint=inspect(ns.public_key); print(f"algorithm\tEd25519\nraw_public_key_hex\t{raw}\nraw_public_key_sha256\t{fingerprint}\ngate\tPASS")
if __name__=="__main__": main()
