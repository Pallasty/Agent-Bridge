#!/usr/bin/env python3
"""D18 clean, bounded packed-q3 consumer; never runs more than 4,096 rows."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,shutil,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
CHECKPOINT=HERE/"fh_l8_packed_q3_checkpoint_d11_bundle/checkpoint.bin"
CHECKPOINT_SHA="db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231"
CHECKPOINT_BYTES=6819168; COUNT=213099; LIMIT=4096
class RunnerError(ValueError):pass
def _sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  while data:=f.read(1048576):h.update(data)
 return h.hexdigest()
def _json(p):return json.loads(p.read_text(encoding="utf-8"))
def _cgroup():
 line=next((x for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::")),None)
 root=Path("/sys/fs/cgroup")/(line.split(":",2)[2].lstrip("/") if line else "")
 def read(name):return (root/name).read_text().strip()
 return root,{name:read(name) for name in ("memory.current","memory.max","memory.high","memory.swap.max","memory.peak")}
def _load_legacy(contract):
 path=HERE/"fh_l8_checkpointed_quotient_h_d11_runner.py"
 if _sha(path)!=contract["source_pins"]["bounded_kernel"]:raise RunnerError("bounded kernel pin drift")
 spec=importlib.util.spec_from_file_location("d18_kernel",path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def run(contract,scratch):
 if _sha(Path(__file__))!=contract["runner_self_sha256"]:raise RunnerError("runner self pin drift")
 if _sha(HERE/"fh_l8_packed_consumer_forensic_d16_result.json")!=contract["source_pins"]["d16_forensic_result"]:raise RunnerError("forensic result pin drift")
 if scratch.exists():raise RunnerError("fresh scratch path must not exist")
 if CHECKPOINT.stat().st_size!=CHECKPOINT_BYTES or _sha(CHECKPOINT)!=CHECKPOINT_SHA:raise RunnerError("committed packed q3 drift")
 root,before=_cgroup()
 if before["memory.max"]!="1073741824" or before["memory.high"]!="805306368" or before["memory.swap.max"]!="0":raise RunnerError("D10 cgroup envelope absent")
 scratch.mkdir(mode=0o700,parents=False);source=scratch/"source";source.mkdir(mode=0o700)
 payload=source/"depth3-source.bin";shutil.copyfile(CHECKPOINT,payload)
 manifest=source/"depth3-source.manifest.json";manifest.write_text(json.dumps({"record_bytes":32,"record_count":COUNT,"payload_sha256":CHECKPOINT_SHA,"complete":True},sort_keys=True,separators=(",",":")),encoding="utf-8")
 kernel=_load_legacy(contract);legacy_contract={"d5_checker_sha256":contract["source_pins"]["d5_checker"]}
 started=time.monotonic();spill=kernel.spill(legacy_contract,source,scratch,LIMIT);merged=kernel.merge(scratch);verified=kernel.verify_merge(legacy_contract,source,scratch,LIMIT);elapsed=time.monotonic()-started
 _,after=_cgroup()
 receipt={"contract_id":contract["contract_id"],"status":"VERIFIED_D18_FRESH_EXCLUSIVE_PACKED_Q3_BOUNDED_PREFLIGHT","verified":True,"source_records":LIMIT,"source_checkpoint_sha256":CHECKPOINT_SHA,"scratch":str(scratch),"spill":spill,"merge":merged,"naive_equivalence":verified,"elapsed_seconds":round(elapsed,3),"cgroup_before":before,"cgroup_after":after,"full_53_shard_executed":False,"q5_executed":False,"next_gate":"CLEAN_BOUNDED_PREFLIGHT_REVIEW_AND_FULL_53_SHARD_AUTHORIZATION_DECISION"}
 path=scratch/"terminal_receipt.json";path.write_text(json.dumps(receipt,sort_keys=True,separators=(",",":")),encoding="utf-8");fd=os.open(path,os.O_RDONLY);os.fsync(fd);os.close(fd)
 return receipt
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--scratch",type=Path,required=True);a=p.parse_args(argv)
 try:print(json.dumps(run(_json(HERE/"fh_l8_clean_q3_preflight_d18_contract.json"),a.scratch),indent=2,sort_keys=True));return 0
 except Exception as e:print(json.dumps({"status":"RUNNER_FAILED","verified":False,"error":str(e)},sort_keys=True));return 1
if __name__=="__main__":raise SystemExit(main())
