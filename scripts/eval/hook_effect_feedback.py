#!/usr/bin/env python3
"""Bounded process regression for memory outcomes and machine environment paths.
No production DB/config, model call, hook installation, or network is used.
"""
import hashlib,json,os,sqlite3,subprocess,tempfile,time,uuid
from contextlib import nullcontext
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output-dir',type=Path,required=True)
opt=parser.parse_args()
OUT=opt.output_dir.resolve();OUT.mkdir(parents=True,exist_ok=True)
WORK=OUT/'fixtures';WORK.mkdir(exist_ok=True)
HOOKS=Path(__file__).resolve().parents[2]/'crates/bridge/src/hooks'
CANDIDATE=HOOKS/'ab-memory-hook.sh'
schema='CREATE TABLE memories(kind TEXT,key TEXT,tags TEXT,scope TEXT,content TEXT,status TEXT,access_count INTEGER,updated_at REAL,importance REAL)'
cases=[
 ('bootstrap_ok','ok',False,False,False,'emitted','bootstrap_context_emitted','bootstrap_context_payload'),
 ('mcp_error_fallback','error',False,False,False,'degraded','static_fallback_emitted','static_context_payload'),
 ('binary_missing_fallback','missing',False,False,False,'degraded','static_fallback_emitted','static_context_payload'),
 ('explicit_static','ok',True,False,False,'emitted','static_requested_emitted','static_context_payload'),
 ('cooldown','ok',False,True,False,'skipped','cooldown','none'),
 ('missing_db','ok',False,False,False,'skipped','database_missing','none'),
 ('empty_db','error',False,False,False,'skipped','no_context_emitted','none'),
 ('broken_db','error',False,False,False,'failed','static_query_failed','none'),
 ('curator_guard','ok',False,False,True,'skipped','curator_guard','none'),
 ('mcp_timeout_fallback','timeout',False,False,False,'degraded','static_fallback_emitted','static_context_payload'),
]
results=[]
WORK.mkdir(parents=True,exist_ok=True)
# Retain synthetic fixtures for review; FUSE can keep open unlinked files.
with nullcontext(tempfile.mkdtemp(prefix='hook-fixture-',dir=WORK)) as tmp:
 root=Path(tmp)
 fake=root/'fake-ab';fake.write_text('#!/usr/bin/python3\nimport os,sys,json,time\nsys.stdin.read()\nmode=os.environ["FIXTURE_MCP_MODE"]\nif mode=="timeout":time.sleep(3.75)\nprint(json.dumps({"jsonrpc":"2.0","id":2,"result":{"isError":mode=="error","content":[{"type":"text","text":"fixture bootstrap context 测试"}]}}))\n');fake.chmod(0o755)
 for name,mode,static,cooldown,guard,expected_status,expected_code,actual in cases:
  case=root/name;case.mkdir();db=case/'state.db'
  if name=='broken_db':db.write_text('invalid sqlite fixture')
  elif name!='missing_db':
   with sqlite3.connect(db) as conn:
    conn.execute(schema)
    if name!='empty_db':conn.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?)',('concept','fixture-key','','global','fixture content only','active',0,1.0,0.5))
  sid='vork-effect-fixture-'+uuid.uuid4().hex;lock=Path('/tmp')/('ab-mem-injected-'+sid)
  payload=json.dumps({'hook_event_name':'UserPromptSubmit','session_id':sid,'cwd':str(case),'prompt':'synthetic retrieval test'})
  env={'PATH':'/usr/bin:/bin','HOME':str(case),'XDG_DATA_HOME':str(case/'data'),'AGENT_BRIDGE_DB':str(db),'AB_PET_STATE_DISABLE':'1','AB_MEMORY_HOOK_AB_BIN':str(fake if mode!='missing' else root/'absent-bin'),'FIXTURE_MCP_MODE':mode,'AB_MEMORY_COOLDOWN_TURNS':'8','AB_MEMORY_HOOK_STATIC':'1' if static else '0','AB_MEMORY_CURATOR':'1' if guard else '0','LANG':'C.UTF-8'}
  observed=[]
  try:
   for hook in [CANDIDATE]:
    if cooldown:lock.write_text('1\n')
    else:lock.unlink(missing_ok=True)
    log=case/'data/agent-bridge/hook-runs.jsonl';log.unlink(missing_ok=True)
    start=time.monotonic();p=subprocess.run(['/bin/bash',str(hook)],input=payload,text=True,capture_output=True,cwd=case,env=env,timeout=7)
    rows=[json.loads(x) for x in log.read_text().splitlines()]
    assert len(rows)==1,(name,rows)
    observed.append((p,rows[0],time.monotonic()-start))
   new=observed[0]
   assert new[0].returncode==0,name
   if actual=="none":assert not new[0].stdout.strip(),name
   else:assert json.loads(new[0].stdout)["hookSpecificOutput"]["additionalContext"],name
   f=new[1]['effect_feedback'];assert(f['status'],f['code'],f['actual'])==(expected_status,expected_code,actual),(name,f)
   assert f['verification_scope']=='hook_payload_only'
   assert f['dropped']==(['bootstrap_context_selection'] if expected_status=='degraded' else []),(name,f)
   assert new[1]['session_id_sha256']==(None if guard else hashlib.sha256(sid.encode()).hexdigest())
   raw=json.dumps(new[1]);assert sid not in raw and 'synthetic retrieval test' not in raw and 'fixture content only' not in raw
   results.append({'case':name,'status':'PASS','outer_exit_code':new[0].returncode,'candidate_seconds':round(new[2],3),'candidate_receipt':new[1]})
  finally:lock.unlink(missing_ok=True)
report={'status':'PASS','case_count':len(results),'scope':'Isolated process fixtures; hook output and receipt only. No real host injection or retrieval quality claim.','results':results}
(OUT/'fixture-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'cases':report['case_count'],'outer_exit_codes':sorted({r['outer_exit_code'] for r in results}),'effect_statuses':sorted({r['candidate_receipt']['effect_feedback']['status'] for r in results})},ensure_ascii=False,indent=2))
