#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;C=HERE/"fh_l8_allocator_proof_interface_d64_contract.json";R=HERE/"fh_l8_allocator_proof_interface_d64_result.json"
class D64Error(RuntimeError):pass
def verify():
 c=json.loads(C.read_text())
 if c["contract_id"]!="FH-L8-ALLOCATOR-PROOF-INTERFACE-D64-V1":raise D64Error("id")
 for n,h in c["source_pins"].items():
  if hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h:raise D64Error("pin")
 if len(c["proof_slots"])!=6 or len(c["covered_d58_variables"])!=8 or len(c["rejection_rules"])!=4:raise D64Error("coverage")
 if c["intake_state"]!="EMPTY_NO_NUMERIC_PROOF_ACCEPTED" or c["authority"]!={"object_measurements_executed":0,"numeric_peak_memory_proven":False,"scientific_execution":False,"production_io":False,"full53_execution_authorized":False}:raise D64Error("authority")
 x={"status":"VERIFIED_D64_EMPTY_STATIC_ALLOCATOR_PROOF_INTERFACE","proof_slot_count":6,"covered_variable_count":8,"numeric_peak_memory_proven":False,"decision":c["decision"]}
 if json.loads(R.read_text())!=x:raise D64Error("result")
 return x
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
