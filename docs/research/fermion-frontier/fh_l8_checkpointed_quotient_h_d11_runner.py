#!/usr/bin/env python3
"""Checkpoint producer for the D11 signed quotient-H runner.

This first implementation materializes only the hash-bound depth-3 source
checkpoint.  It deliberately has no depth-4 action mode until its spill/merge
consumer is separately reviewed.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
RECORD=struct.Struct(">16sqB7x")
COUNT=213099;SHARD=4096
class RunnerError(ValueError):pass
def _json(path):return json.loads(path.read_text(encoding="utf-8"))
def _load_d5(contract):
 path=HERE/"fh_l8_symmetry_orbit_quotient_d5_checker.py"
 if hashlib.sha256(path.read_bytes()).hexdigest()!=contract["d5_checker_sha256"]:raise RunnerError("D5B checker pin drift")
 spec=importlib.util.spec_from_file_location("d11_d5b",path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def _source(d5):
 c=d5._load_json(HERE/"fh_l8_symmetry_orbit_quotient_d5_contract.json");d4,d4c,_=d5._verify_parent_sources(c);d3=d4._load_d3(d4c);d3c=d5._load_json(HERE/"fh_l8_degree6_streaming_d3_contract.json");d2=d3._load_d2(d3c);d2c=d5._load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json");up=d2._load_upstream(d2c);backend=up._load_backend();bonds={n:backend._hopping_bonds(8,n) for n in ("H1","H2","H3","H4")};syms,_=d5._build_symmetries(c);q={up._neel_basis(8):1}
 for _ in range(3):q,_=d5._quotient_step(d4,backend,bonds,q,syms)
 if len(q)!=COUNT:raise RunnerError("depth3 quotient count drift")
 return sorted(q.items()),syms
def _cgroup_ok():
 line=next((x for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::")),None)
 root=Path("/sys/fs/cgroup")/(line.split(":",2)[2].lstrip("/") if line else "")
 def read(name):
  p=root/name;return p.read_text().strip() if p.is_file() else None
 return read("memory.max")=="1073741824" and read("memory.swap.max")=="0" and read("memory.high")=="805306368"
def checkpoint(contract,scratch):
 if not _cgroup_ok():raise RunnerError("D10 cgroup envelope absent")
 scratch.mkdir(parents=True,exist_ok=True)
 if scratch.stat().st_dev==Path("/tmp").stat().st_dev:raise RunnerError("scratch must not be tmpfs")
 d5=_load_d5(contract);records,syms=_source(d5);payload=scratch/"depth3-source.bin";manifest=scratch/"depth3-source.manifest.json";h=hashlib.sha256();shards=[]
 with payload.open("wb") as out:
  for start in range(0,COUNT,SHARD):
   block=records[start:start+SHARD];bh=hashlib.sha256()
   for rep,amp in block:
    orbit=d5._canonical_info(rep,syms)["orbit_size"]
    raw=RECORD.pack(rep.to_bytes(16,"big"),amp,orbit);out.write(raw);h.update(raw);bh.update(raw)
   out.flush();os.fsync(out.fileno());shards.append({"index":len(shards),"records":len(block),"sha256":bh.hexdigest()})
 doc={"contract_id":contract["contract_id"],"record_bytes":RECORD.size,"record_count":COUNT,"payload_sha256":h.hexdigest(),"shards":shards,"complete":True};tmp=manifest.with_suffix(".tmp");tmp.write_text(json.dumps(doc,sort_keys=True,separators=(",",":")),encoding="utf-8");os.replace(tmp,manifest)
 return {"status":"VERIFIED_D11_DEPTH3_CHECKPOINT_MATERIALIZED_NO_DEPTH4_ACTION","verified":True,"payload":str(payload),"manifest":str(manifest),"payload_bytes":payload.stat().st_size,"payload_sha256":h.hexdigest(),"shard_count":len(shards),"fourth_action_executed":False,"next_gate":"D11_SPILL_MERGE_CONSUMER_IMPLEMENTATION"}
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--scratch",required=True);a=p.parse_args(argv)
 try:print(json.dumps(checkpoint(_json(HERE/"fh_l8_checkpointed_quotient_h_d11_contract.json"),Path(a.scratch)),indent=2,sort_keys=True));return 0
 except Exception as e:print(json.dumps({"status":"RUNNER_FAILED","verified":False,"error":str(e)},sort_keys=True));return 1
if __name__=="__main__":raise SystemExit(main())
