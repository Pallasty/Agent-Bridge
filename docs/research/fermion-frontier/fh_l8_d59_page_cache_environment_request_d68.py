#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_d59_page_cache_environment_request_d68.json"
class D68Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["request_id"]!="FH-L8-D59-PAGE-CACHE-ENVIRONMENT-REQUEST-D68-V1":raise D68Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D68Error("pin")
 r=x["request"]
 if any(len(r[k])<3 for k in r) or x["state"]!="UNSENT_EMPTY_REQUEST" or any(x["authority"].values()):raise D68Error("coverage")
 return {"status":"VERIFIED_D68_UNSENT_D59_PAGE_CACHE_REQUEST","field_group_count":4,"production_io_executed":False}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
