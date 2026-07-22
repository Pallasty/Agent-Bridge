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
DELTA=struct.Struct(">16sqQ")
COUNT=213099;SHARD=4096
class RunnerError(ValueError):pass
def _dontneed(fd,offset,length):
 if hasattr(os,"posix_fadvise") and hasattr(os,"POSIX_FADV_DONTNEED"):os.posix_fadvise(fd,offset,length,os.POSIX_FADV_DONTNEED)
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
def _context(d5):
 c=d5._load_json(HERE/"fh_l8_symmetry_orbit_quotient_d5_contract.json");d4,d4c,_=d5._verify_parent_sources(c);d3=d4._load_d3(d4c);d3c=d5._load_json(HERE/"fh_l8_degree6_streaming_d3_contract.json");d2=d3._load_d2(d3c);d2c=d5._load_json(HERE/"fh_l8_two_step_scalar_defect_d2_contract.json");up=d2._load_upstream(d2c);backend=up._load_backend();bonds={n:backend._hopping_bonds(8,n) for n in ("H1","H2","H3","H4")};syms,_=d5._build_symmetries(c);return d4,backend,bonds,syms
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
def _read_checkpoint(payload,manifest,count):
 meta=_json(manifest);raw=payload.read_bytes()
 if len(raw)!=count*RECORD.size or hashlib.sha256(raw).hexdigest()!=meta.get("payload_sha256") or not meta.get("complete"):raise RunnerError("source checkpoint hash/size drift")
 return [(int.from_bytes(raw[i:i+16],"big"),RECORD.unpack(raw[i:i+RECORD.size])[1]) for i in range(0,len(raw),RECORD.size)]
def spill(contract,source_dir,scratch,source_count):
 if not _cgroup_ok():raise RunnerError("D10 cgroup envelope absent")
 if not 1<=source_count<=SHARD:raise RunnerError("bounded spill source count required")
 payload=source_dir/"depth3-source.bin";manifest=source_dir/"depth3-source.manifest.json";sources=_read_checkpoint(payload,manifest,COUNT)[:source_count]
 d5=_load_d5(contract);d4,backend,bonds,syms=_context(d5);run=scratch/"spill-shard-0000";run.mkdir(parents=True,exist_ok=True);buffers={};written=0;reduced=0;dropped=0
 for rep,amp in sources:
   column,_,zero=d5._reduced_column(d4,backend,bonds,rep,syms);dropped+=zero;reduced+=len(column)
   for target,coefficient in column.items():
    if 8%coefficient.denominator:raise RunnerError("non-octadic quotient coefficient")
    delta=amp*coefficient.numerator*(8//coefficient.denominator)
    if not -(1<<63)<=delta<(1<<63):raise RunnerError("scaled delta i64 overflow")
    part=hashlib.sha256(target.to_bytes(16,"big")).digest()[0];path=run/f"p{part:03d}.bin"
    buffers.setdefault(part,bytearray()).extend(DELTA.pack(target.to_bytes(16,"big"),delta,0));written+=1
 for part,raw in buffers.items():
  path=run/f"p{part:03d}.bin"
  with path.open("wb") as out:out.write(raw);out.flush();os.fsync(out.fileno())
 parts=[]
 for path in sorted(run.glob("p*.bin")):
  raw=path.read_bytes();
  if len(raw)%DELTA.size:raise RunnerError("spill record alignment drift")
  parts.append({"path":path.name,"records":len(raw)//DELTA.size,"sha256":hashlib.sha256(raw).hexdigest()})
 doc={"source_count":source_count,"record_bytes":DELTA.size,"scaled_denominator":8,"records":written,"reduced_columns":reduced,"projected_zero":dropped,"partitions":parts,"complete":True};(run/"manifest.json").write_text(json.dumps(doc,sort_keys=True,separators=(",",":")),encoding="utf-8")
 return {"status":"VERIFIED_D11_BOUNDED_SIGNED_SPILL_NO_FULL_ACTION","verified":True,"source_count":source_count,"spill_records":written,"reduced_columns":reduced,"projected_zero":dropped,"partition_count":len(parts),"manifest":str(run/"manifest.json"),"fourth_action_executed":False,"next_gate":"D11_SORT_MERGE_EQUIVALENCE"}
def merge(scratch):
 run=scratch/"spill-shard-0000";meta=_json(run/"manifest.json")
 if not meta.get("complete") or meta.get("record_bytes")!=DELTA.size:raise RunnerError("spill manifest drift")
 output=run/"merged.bin";h=hashlib.sha256();count=0
 with output.open("wb") as out:
  for part in meta["partitions"]:
   raw=(run/part["path"]).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=part["sha256"]:raise RunnerError("partition hash drift")
   values=[DELTA.unpack(raw[i:i+DELTA.size]) for i in range(0,len(raw),DELTA.size)];values.sort(key=lambda x:x[0]);index=0
   while index<len(values):
    target=values[index][0];total=0
    while index<len(values) and values[index][0]==target:total+=values[index][1];index+=1
    if not total:continue
    if total%8:raise RunnerError("scaled merge nondivisible by eight")
    packed=DELTA.pack(target,total//8,0);out.write(packed);h.update(packed);count+=1
  out.flush();os.fsync(out.fileno())
 return {"status":"VERIFIED_D11_BOUNDED_SORT_MERGE_NO_FULL_ACTION","verified":True,"merged_records":count,"merged_sha256":h.hexdigest(),"payload_bytes":output.stat().st_size,"fourth_action_executed":False,"next_gate":"D11_NAIVE_EQUIVALENCE_CHECK"}
def verify_merge(contract,source_dir,scratch,source_count):
 sources=_read_checkpoint(source_dir/"depth3-source.bin",source_dir/"depth3-source.manifest.json",COUNT)[:source_count];d5=_load_d5(contract);d4,backend,bonds,syms=_context(d5);expected={}
 for rep,amp in sources:
  column,_,_=d5._reduced_column(d4,backend,bonds,rep,syms)
  for target,coefficient in column.items():expected[target]=expected.get(target,0)+amp*coefficient
 expected={target:value.numerator for target,value in expected.items() if value}
 raw=(scratch/"spill-shard-0000"/"merged.bin").read_bytes();actual={}
 for i in range(0,len(raw),DELTA.size):target,value,_=DELTA.unpack(raw[i:i+DELTA.size]);actual[int.from_bytes(target,"big")]=value
 if actual!=expected:raise RunnerError("spill/merge differs from naive signed quotient action")
 return {"status":"VERIFIED_D11_BOUNDED_SPILL_MERGE_NAIVE_EQUIVALENCE","verified":True,"source_count":source_count,"target_count":len(actual),"fourth_action_executed":False,"next_gate":"D11_FULL_SHARD_SPILL_MERGE_PREFLIGHT"}
def full_spill(contract,source_dir,scratch):
 if not _cgroup_ok():raise RunnerError("D10 cgroup envelope absent")
 sources=_read_checkpoint(source_dir/"depth3-source.bin",source_dir/"depth3-source.manifest.json",COUNT);d5=_load_d5(contract);d4,backend,bonds,syms=_context(d5);spool=scratch/"full-spool";checks=scratch/"full-checkpoints";spool.mkdir(parents=True,exist_ok=True);checks.mkdir(parents=True,exist_ok=True);done=0;written=0
 for shard,start in enumerate(range(0,COUNT,SHARD)):
  receipt=checks/f"shard-{shard:03d}.json"
  if receipt.is_file() and _json(receipt).get("complete"):
   prior=_json(receipt)
   for chunk in prior["chunks"]:
    path=spool/f"p{chunk['partition']:03d}.bin";raw=path.read_bytes()[chunk["offset"]:chunk["offset"]+chunk["bytes"]]
    if len(raw)!=chunk["bytes"] or hashlib.sha256(raw).hexdigest()!=chunk["sha256"]:raise RunnerError("resume shard hash drift")
    with path.open("rb") as cached:_dontneed(cached.fileno(),chunk["offset"],chunk["bytes"])
   done+=1;continue
  buffers={};reduced=0;dropped=0
  for rep,amp in sources[start:start+SHARD]:
   column,_,zero=d5._reduced_column(d4,backend,bonds,rep,syms);dropped+=zero;reduced+=len(column)
   for target,coefficient in column.items():
    if 8%coefficient.denominator:raise RunnerError("non-octadic quotient coefficient")
    delta=amp*coefficient.numerator*(8//coefficient.denominator)
    if not -(1<<63)<=delta<(1<<63):raise RunnerError("scaled delta i64 overflow")
    part=hashlib.sha256(target.to_bytes(16,"big")).digest()[0];buffers.setdefault(part,bytearray()).extend(DELTA.pack(target.to_bytes(16,"big"),delta,0))
  chunks=[]
  for part,raw in buffers.items():
   path=spool/f"p{part:03d}.bin";offset=path.stat().st_size if path.is_file() else 0
   with path.open("ab") as out:
    out.write(raw);out.flush();os.fsync(out.fileno());_dontneed(out.fileno(),offset,len(raw))
   chunks.append({"partition":part,"offset":offset,"bytes":len(raw),"records":len(raw)//DELTA.size,"sha256":hashlib.sha256(raw).hexdigest()});written+=len(raw)//DELTA.size
  doc={"shard":shard,"source_start":start,"source_records":min(SHARD,COUNT-start),"reduced_columns":reduced,"projected_zero":dropped,"chunks":sorted(chunks,key=lambda x:x["partition"]),"complete":True};tmp=receipt.with_suffix(".tmp");tmp.write_text(json.dumps(doc,sort_keys=True,separators=(",",":")),encoding="utf-8");os.replace(tmp,receipt);done+=1
 return {"status":"VERIFIED_D11_FULL_SPILL_CHECKPOINTS_COMPLETE_NO_MERGE","verified":True,"completed_shards":done,"new_spill_records":written,"fourth_action_executed":False,"next_gate":"D11_FULL_PARTITION_SORT_MERGE"}
def full_merge(scratch):
 spool=scratch/"full-spool";checks=scratch/"full-checkpoints";receipts=sorted(checks.glob("shard-*.json"))
 if len(receipts)!=53 or any(not _json(x).get("complete") for x in receipts):raise RunnerError("incomplete hash-bound shard set")
 output=scratch/"depth4-target.bin";h=hashlib.sha256();count=0
 with output.open("wb") as out:
  for path in sorted(spool.glob("p*.bin")):
   raw=path.read_bytes()
   if len(raw)%DELTA.size:raise RunnerError("full spill record alignment drift")
   values=[DELTA.unpack(raw[i:i+DELTA.size]) for i in range(0,len(raw),DELTA.size)];values.sort(key=lambda x:x[0]);index=0
   while index<len(values):
    target=values[index][0];total=0
    while index<len(values) and values[index][0]==target:total+=values[index][1];index+=1
    if not total:continue
    if total%8:raise RunnerError("full scaled merge nondivisible by eight")
    packed=DELTA.pack(target,total//8,0);out.write(packed);h.update(packed);count+=1
  out.flush();os.fsync(out.fileno())
 return {"status":"VERIFIED_D11_FULL_DEPTH3_TO_DEPTH4_SIGNED_QUOTIENT_ACTION","verified":True,"target_records":count,"target_payload_bytes":output.stat().st_size,"target_sha256":h.hexdigest(),"fourth_action_executed":True,"degree6_remainder_bounded":False,"two_step_cumulative_error_bounded":False,"full_R100_error_bounded":False,"physical_reference_qualified":False,"ready_gate_eligible":False}
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--scratch",required=True);p.add_argument("--spill-source",type=int);p.add_argument("--source-dir",type=Path);p.add_argument("--merge",action="store_true");p.add_argument("--verify-source",type=int);p.add_argument("--full-spill",action="store_true");p.add_argument("--full-merge",action="store_true");a=p.parse_args(argv);contract=_json(HERE/"fh_l8_checkpointed_quotient_h_d11_contract.json")
 try:
  if a.full_merge:evidence=full_merge(Path(a.scratch))
  elif a.full_spill:evidence=full_spill(contract,a.source_dir,Path(a.scratch))
  elif a.verify_source:evidence=verify_merge(contract,a.source_dir,Path(a.scratch),a.verify_source)
  elif a.merge:evidence=merge(Path(a.scratch))
  elif a.spill_source:evidence=spill(contract,a.source_dir,Path(a.scratch),a.spill_source)
  else:evidence=checkpoint(contract,Path(a.scratch))
  print(json.dumps(evidence,indent=2,sort_keys=True));return 0
 except Exception as e:print(json.dumps({"status":"RUNNER_FAILED","verified":False,"error":str(e)},sort_keys=True));return 1
if __name__=="__main__":raise SystemExit(main())
