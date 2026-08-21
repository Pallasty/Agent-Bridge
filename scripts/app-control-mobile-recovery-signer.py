#!/usr/bin/env python3
"""Bounded ADB adapter for Android recovery-authorization UI and receipt export."""
import argparse, base64, json, os, re, subprocess

REQ="agent_bridge.app_control.recovery_authorization_broker_request.v0"
EXPORT="agent_bridge.android_companion.recovery_authorization_export.v0"
COMP="dev.agentbridge.companion/.RecoveryAuthorizationActivity"
PREFIX="AGENT_BRIDGE_COMPANION_RECOVERY_AUTH "
HEX64=re.compile(r"[0-9a-f]{64}")

def validate_request(p):
    keys={"schema","operation_id","record_sha256","request_sha256","workspace_sha256","session_sha256",
          "requested_at_unix_seconds","maximum_receipt_ttl_secs","request_nonce"}
    return isinstance(p,dict) and set(p)==keys and p["schema"]==REQ and re.fullmatch(r"ab-episode-[0-9a-f]{32}",p["operation_id"]) and all(HEX64.fullmatch(p[k]) for k in ("record_sha256","request_sha256","workspace_sha256","session_sha256")) and re.fullmatch(r"[0-9a-f]{32}",p["request_nonce"])

def request_argv(adb,serial,p):
    if not validate_request(p): raise ValueError("invalid_broker_request")
    out=[adb,"-s",serial,"shell","am","start","-W","-n",COMP]
    for key in ("operation_id","record_sha256","request_sha256","workspace_sha256","session_sha256","request_nonce"):
        out += ["--es",key,p[key]]
    return out

def parse_export(text,pinned):
    lines=[line[len(PREFIX):] for line in text.splitlines() if line.startswith(PREFIX)]
    if len(lines)!=1: raise ValueError("receipt_export_unavailable")
    p=json.loads(lines[0]);
    if p.get("schema")!=EXPORT or p.get("status")!="signed" or p.get("private_key_exported") is not False or p.get("action_invoked") is not False: raise ValueError("receipt_export_invalid")
    if p.get("public_key_b64")!=pinned: raise ValueError("device_public_key_conflict")
    if not isinstance(p.get("receipt"),str) or len(p["receipt"])>8192: raise ValueError("receipt_export_invalid")
    return {"schema":EXPORT,"status":"verified","receipt":p["receipt"],"public_key_bound":True,"private_key_exported":False,"action_invoked":False,"automatic_recovery_authorized":False}

def main():
    q=argparse.ArgumentParser(); q.add_argument("mode",choices=("request","collect")); q.add_argument("--serial",required=True); q.add_argument("--broker-request"); q.add_argument("--adb",default="adb"); a=q.parse_args()
    if a.mode=="request":
        p=json.loads(a.broker_request or "null"); argv=request_argv(a.adb,a.serial,p); subprocess.run(argv,check=True,timeout=5)
        out={"status":"presented","user_confirmation_required":True,"receipt_issued":False,"action_invoked":False}
    else:
        pin=os.environ.get("AB_APP_CONTROL_RECOVERY_AUTH_PUBLIC_KEY_B64")
        if not pin: raise SystemExit("authorization_source_unavailable")
        r=subprocess.run([a.adb,"-s",a.serial,"shell","dumpsys","activity","service","dev.agentbridge.companion/.CompanionService"],capture_output=True,text=True,check=True,timeout=5)
        out=parse_export(r.stdout,pin)
    print(json.dumps(out,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
