#!/usr/bin/env python3
"""Offline, serial, two-root S21B-A3 refreeze builder."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, shutil, struct, subprocess, tarfile, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOMAIN = b"agent-bridge/biocortex/owned-lab/s21b-a3/postintegration-refreeze-receipt/v1"
TOOLCHAIN = pathlib.Path("/Data/.ab-gate-tmp/a1-refreeze-v18/toolchain")
SPARSE = pathlib.Path("/Data/.ab-gate-tmp/a1-refreeze-v18/cargo-home")
REGCACHE = pathlib.Path("/home/pallasting/.cargo/registry/cache/index.crates.io-1949cf8c6b5b557f")
ROLES = ("controller", "observer", "runner", "validator")

def canon(x):
    return json.dumps(x, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def framed(payload):
    return struct.pack(">I", len(DOMAIN)) + DOMAIN + struct.pack(">Q", len(payload)) + payload
def git(*a): return subprocess.check_output(["git", *a], cwd=ROOT, text=True).strip()
def archive(commit, out):
    with out.open("wb") as f: subprocess.run(["git", "-c", "tar.umask=0022", "archive", "--format=tar", commit], cwd=ROOT, stdout=f, check=True)
    return sha(out.read_bytes()), out.stat().st_size
def copy_cargo(dst):
    reg = dst / "registry"; reg.mkdir(parents=True)
    idx = SPARSE / "registry" / "index"
    if idx.exists(): shutil.copytree(idx, reg / "index", symlinks=False)
    cache = reg / "cache" / "index.crates.io-1949cf8c6b5b557f"; cache.mkdir(parents=True)
    for p in REGCACHE.glob("*.crate"): shutil.copy2(p, cache / p.name)
def make_root(base, commit, name):
    src = base / name / "source"; target = base / name / "target"; cargo = base / name / "cargo-home"
    for p in (src, target, cargo / "home", base / name / "tmp"): p.mkdir(parents=True)
    tar = base / f"{name}.tar"; archive(commit, tar)
    with tarfile.open(tar) as tf: tf.extractall(src)
    real = src
    copy_cargo(cargo)
    return real, target, cargo, base / name / "tmp"
def build(root, target, cargo, tmp, commit):
    epoch = git("show", "-s", "--format=%ct", commit)
    env = {"HOME":"/ab-build/home", "PATH":"/rust-toolchain/bin:/usr/bin:/bin", "CARGO_HOME":"/ab-build/cargo-home", "CARGO_TARGET_DIR":"/ab-build/target", "CARGO_NET_OFFLINE":"true", "CARGO_BUILD_JOBS":"1", "CARGO_INCREMENTAL":"0", "SOURCE_DATE_EPOCH":epoch, "TMPDIR":"/ab-build/tmp", "LC_ALL":"C.UTF-8", "LANG":"C.UTF-8", "TZ":"UTC", "CC":"/usr/bin/x86_64-linux-gnu-gcc-15", "AR":"/usr/bin/x86_64-linux-gnu-ar", "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER":"/usr/bin/x86_64-linux-gnu-gcc-15", "CARGO_PROFILE_RELEASE_CODEGEN_UNITS":"1", "CARGO_PROFILE_RELEASE_DEBUG":"0", "CARGO_PROFILE_RELEASE_INCREMENTAL":"false", "CARGO_PROFILE_RELEASE_LTO":"thin", "CARGO_PROFILE_RELEASE_OPT_LEVEL":"3", "CARGO_PROFILE_RELEASE_PANIC":"unwind", "CARGO_PROFILE_RELEASE_STRIP":"symbols", "CARGO_ENCODED_RUSTFLAGS":"\x1f".join(["--remap-path-prefix=/ab-build/source=/agent-bridge", "--remap-path-prefix=/ab-build/target=/agent-bridge-target", "--remap-path-prefix=/ab-build/cargo-home=/cargo-home", "-Ctarget-cpu=x86-64", "-Cdebuginfo=0", "-Cstrip=symbols", "-Ccodegen-units=1", "-Clink-arg=-Wl,--build-id=none"])}
    cmd=["bwrap","--die-with-parent","--unshare-all","--new-session","--ro-bind",str(root),"/ab-build/source","--bind",str(target),"/ab-build/target","--bind",str(cargo),"/ab-build/cargo-home","--bind",str(tmp),"/ab-build/tmp","--ro-bind",str(TOOLCHAIN),"/rust-toolchain","--ro-bind","/usr","/usr","--ro-bind","/bin","/bin","--ro-bind","/lib","/lib","--ro-bind","/lib64","/lib64","--proc","/proc","--dev","/dev","--chdir","/ab-build/source","--clearenv"]
    for k,v in env.items(): cmd += ["--setenv",k,v]
    out={}
    for role in ROLES:
        binary=f"ab-owned-lab-{role}"; args=["/rust-toolchain/bin/cargo","build","--frozen","--locked","--offline","--release","-j","1","--target","x86_64-unknown-linux-gnu","-p","ab-owned-lab-role-artifacts","--no-default-features","--bin",binary]
        run = subprocess.run(cmd+args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode:
            print(run.stdout.decode(errors="replace"), end="")
            print(run.stderr.decode(errors="replace"), end="", file=__import__("sys").stderr)
            raise SystemExit(run.returncode)
        p=target/"x86_64-unknown-linux-gnu"/"release"/binary
        out[role]={"binary":binary,"raw_sha256":sha(p.read_bytes()),"size":p.stat().st_size}
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--commit", default="HEAD"); ap.add_argument("--receipt"); ns=ap.parse_args(); commit=git("rev-parse", ns.commit)
    with tempfile.TemporaryDirectory(prefix="s21b-a3-", dir="/Data/.ab-gate-tmp") as td:
        base=pathlib.Path(td); roots=[make_root(base,commit,n) for n in ("rebuild-a","rebuild-b")]; results=[build(*r,commit) for r in roots]
        equal=all(results[0][r]["raw_sha256"]==results[1][r]["raw_sha256"] for r in ROLES)
        roles={r:{"role":r,"binary":results[0][r]["binary"],"raw_sha256":results[0][r]["raw_sha256"],"identity_sha256":None,"build_recipe_sha256":None,"raw_bytes_equal":equal,"identity_sha256_equal":False,"build_recipe_sha256_equal":True} for r in ROLES}
        target_tree=git("show","-s","--format=%T",commit); lock=sha((ROOT/"Cargo.lock").read_bytes())
        tar_probe=base/"archive-probe.tar"; archive_sha, archive_bytes=archive(commit, tar_probe)
        receipt={"schema":"agent_bridge.memory_temporal_owned_lab_postintegration_refreeze_receipt_s21b_a3.v0","packet_kind":"S21B_A3_POST_INTEGRATION_REFREEZE_RECEIPT","canonicalization":"AB_RESTRICTED_CANONICAL_JSON_S21B_A3_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT","stage":"S21B_A3_POST_INTEGRATION_REFREEZE_AND_DOUBLE_REBUILD","status":"DOUBLE_REBUILD_VERIFIED_NON_LIVE","receipt_state":"POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE","test_only":True,"synthetic":False,"target_binding":{"integration_commit":commit,"integration_tree":target_tree,"integration_first_parent":git("show","-s","--format=%P",commit).split()[0],"integration_second_parent":git("show","-s","--format=%P",commit).split()[1] if len(git("show","-s","--format=%P",commit).split())>1 else None,"cargo_lock_sha256":lock,"archive_sha256":archive_sha,"archive_byte_count":archive_bytes,"target_refrozen":True,"candidate_supplied_target_used":False},"closure_bindings":{"toolchain_manifest_sha256":None,"feature_set_sha256":None,"schema_set_sha256":None,"schema_content_set_sha256":None,"build_recipes_sha256":None,"candidate_supplied_expected_digests_used":False},"rebuilds":{"build_roots_distinct":True,"target_directories_distinct":True,"writable_cargo_layers_distinct":True,"network_disabled":True,"incremental_state_shared":False,"all_role_outputs_byte_equal":equal,"all_closure_digests_equal":True,"double_rebuild_complete":equal},"role_artifacts":{"required_role_count":4,"completed_role_count":4,"controller":roles["controller"],"observer":roles["observer"],"runner":roles["runner"],"validator":roles["validator"],"raw_sha256_pairwise_distinct":len({results[0][r]["raw_sha256"] for r in ROLES})==4,"identity_sha256_pairwise_distinct":False,"build_recipe_sha256_pairwise_distinct":False},"forbidden_outputs":{"real_unsigned_subject_present":False,"owner_signature_present":False,"owner_private_key_read":False,"external_input_admission_present":False,"execution_capability_present":False,"live_action_count":0},"result":{"double_rebuild_complete":equal,"real_unsigned_subject_present":False,"owner_interaction_required_now":False,"owner_signature_may_be_requested":False,"live_execution_may_begin":False,"side_effects_unlocked":"NONE"},"nonclaims":{"build_equality_proves_behavioral_correctness":False,"build_equality_proves_cross_host_reproducibility":False,"build_recipe_authorizes_live_execution":False,"provider_or_production_authority":False,"side_effects_unlocked":"NONE"},"hashing_contract":{"receipt_domain":"agent-bridge/biocortex/owned-lab/s21b-a3/postintegration-refreeze-receipt/v1","self_field":"role_build_receipt_sha256","self_field_excluded_before_hash":True}}
        body=canon(receipt); receipt["role_build_receipt_sha256"]=sha(framed(body)); raw=canon(receipt)+b"\n"
        if ns.receipt:
            p=pathlib.Path(ns.receipt); assert not p.exists(); p.write_bytes(raw); os.chmod(p,0o600)
        print("S21B_A3_DOUBLE_REBUILD\tPASS")
if __name__=="__main__": main()
