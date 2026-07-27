#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;P=H/"fh_l8_d23_external_capacity_receipt_request_d67.json"
class D67Error(RuntimeError):pass
def verify():
 x=json.loads(P.read_text())
 if x["request_id"]!="FH-L8-D23-EXTERNAL-CAPACITY-RECEIPT-REQUEST-D67-V1":raise D67Error("id")
 for n,v in x["source_pins"].items():
  if hashlib.sha256((H/n).read_bytes()).hexdigest()!=v:raise D67Error("pin")
 r=x["request"]
 if r["required_bytes"]!=3110572064 or r["required_blocks_512_or_more"]!=6081196 or any(len(r[k])<3 for k in ("issuer_fields","receipt_fields","verification_fields")):raise D67Error("fields")
 if x["state"]!="UNSENT_EMPTY_REQUEST" or any(x["authority"].values()):raise D67Error("authority")
 return {"status":"VERIFIED_D67_UNSENT_D23_EXTERNAL_CAPACITY_REQUEST","required_bytes":r["required_bytes"],"external_request_sent":False}
if __name__=="__main__":print(json.dumps(verify(),sort_keys=True))
