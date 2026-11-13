#!/usr/bin/env python3
"""PreCompact receipt regression. Synthetic state only; never installs host hooks.

Fixtures cover false completion and uncertain/partial results. With --binary,
also run the real Hook/MCP on a new database, reopen it, and check all consumers.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT/'crates/bridge/src/hooks/ab-precompact-hook.sh'
spec = importlib.util.spec_from_file_location('mcp', ROOT/'scripts/check-capabilities-sections-mcp.py')
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)

FAKE = '''#!/usr/bin/python3
import json, os, sys, time
if sys.argv[1:] != ['mcp']:
 print('{}'); raise SystemExit(0)
sys.stdin.read()
mode = os.environ['AGENT_BRIDGE_FIXTURE_MODE']
if mode == 'timeout': time.sleep(28)
if mode == 'exit_error': raise SystemExit(7)
if mode == 'missing_response': raise SystemExit(0)
if mode == 'malformed': print('{broken'); raise SystemExit(0)
cur = {'dry_run':False, 'saved_count':0 if mode=='zero' else 2, 'skipped_duplicates':1, 'errors':[]}
fin = {'dry_run':False, 'removed_count':0, 'decay':{'archived_count':0}}
work = {'saved':True}
if mode == 'partial_curate': cur['errors'] = ['PRIVATE_ERROR_BODY']
if mode == 'partial_work': work = {'saved':False,'error':'PRIVATE_ERROR_BODY'}
if mode == 'bad_count': cur['saved_count'] = True
if mode == 'dry_run': fin['dry_run'] = True
obj = {'step':'precompact','session_curate':cur,'session_finalize':fin,'work_memory':work}
if mode == 'missing_finalize': del obj['session_finalize']
result = {'isError':mode=='tool_error','content':[{'type':'text','text':json.dumps(obj)}]}
if mode == 'empty_content': result['content'] = []
row = {'jsonrpc':'2.0','id':99 if mode=='wrong_id' else 2,'result':result}
if mode == 'rpc_error': row = {'jsonrpc':'2.0','id':2,'error':{'code':-32603,'message':'PRIVATE_ERROR_BODY'}}
print(json.dumps(row))
if mode == 'duplicate_response': print(json.dumps(row))
'''


def state_env(home):
    env = {'PATH':str(home/'bin')+':/usr/bin:/bin', 'HOME':str(home), 'LANG':'C.UTF-8',
           'AGENT_BRIDGE_DB':str(home/'state.db'), 'AGENT_BRIDGE_EMBED_BACKEND':'hash',
           'AGENT_BRIDGE_CREDS_FILE':str(home/'absent-creds'), 'AGENT_BRIDGE_HEADLESS':'1',
           'AGENT_BRIDGE_TOOLSET':'all-dev', 'AGENT_BRIDGE_MAX_BLOCKING_THREADS':'32',
           'AGENT_BRIDGE_TERMINAL':'pty', 'AB_ALLOW_BROWSER':'false', 'AB_PET_STATE_DISABLE':'1'}
    for name in ['CONFIG', 'DATA', 'CACHE', 'STATE']:
        env['XDG_'+name+'_HOME'] = str(home/name.lower())
    return env


def transcript(home, sid, text='lesson: Synthetic precompact fixture preserves explicit failure boundaries.'):
    p = home/'.codex/sessions'/f'{sid}.jsonl'; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({'type':'response_item', 'payload':{'type':'message',
        'role':'assistant','content':[{'type':'output_text','text':text}]}})+'\n')
    return p


def run_hook(home, env, sid, hook=HOOK, event='preCompact'):
    payload = json.dumps({'session_id':sid, 'prompt':'PRIVATE_PROMPT_BODY'})
    started = time.monotonic()
    p = subprocess.run(['bash', str(hook)], input=payload, text=True, capture_output=True,
                       env={**env,'AB_HOOK_EVENT':event}, cwd=home, timeout=40)
    assert p.returncode == 0, p
    assert not p.stderr, p.stderr
    return p, round(time.monotonic()-started, 3)


def fixtures(root, output, baseline):
    cases = [
        ('missing_session','skipped','session_id_missing','none'),
        ('missing_binary','skipped','binary_missing','none'),
        ('missing_transcript','skipped','transcript_missing','none'),
        ('empty_transcript','skipped','conversation_empty','none'),
        ('unreadable_transcript','failed','transcript_read_failed','none'),
        ('ok','completed','lifecycle_completed','lifecycle_response'),
        ('zero','completed','lifecycle_completed','lifecycle_response'),
        ('partial_curate','degraded','lifecycle_partial_result','lifecycle_response'),
        ('partial_work','degraded','lifecycle_partial_result','lifecycle_response'),
        ('tool_error','failed','lifecycle_tool_error','not_confirmed'),
        ('rpc_error','failed','lifecycle_rpc_error','not_confirmed'),
        ('exit_error','failed','lifecycle_process_failed','not_confirmed'),
        ('timeout','unknown','lifecycle_timeout','not_confirmed'),
        ('wrong_id','unknown','lifecycle_response_missing','not_confirmed'),
        ('missing_response','unknown','lifecycle_response_missing','not_confirmed'),
        ('malformed','unknown','lifecycle_response_missing','not_confirmed'),
        ('empty_content','unknown','lifecycle_response_invalid','not_confirmed'),
        ('missing_finalize','unknown','lifecycle_response_invalid','not_confirmed'),
        ('bad_count','unknown','lifecycle_response_invalid','not_confirmed'),
        ('dry_run','unknown','lifecycle_response_invalid','not_confirmed'),
        ('duplicate_response','unknown','lifecycle_response_invalid','not_confirmed'),
    ]
    results=[]
    for name,status,code,actual in cases:
        home=root/name; (home/'bin').mkdir(parents=True)
        fake=home/'bin/agent-bridge'
        if name!='missing_binary': fake.write_text(FAKE); fake.chmod(0o755)
        sid='' if name=='missing_session' else 'synthetic-'+name
        if name!='missing_transcript':
            p=transcript(home,sid)
            if name=='empty_transcript': p.write_text('{}\n')
            if name=='unreadable_transcript': p.write_bytes(b'\xff')
        env=state_env(home);env['AGENT_BRIDGE_FIXTURE_MODE']=name
        p,seconds=run_hook(home,env,sid)
        rows=[json.loads(line) for line in (home/'data/agent-bridge/hook-runs.jsonl').read_text().splitlines()]
        assert len(rows)==1,(name,rows)
        row=rows[0];feedback=row['effect_feedback']
        assert (feedback['status'],feedback['code'],feedback['actual'])==(status,code,actual),(name,row)
        assert row['output_bytes']==len(p.stdout.encode()),(name,row,p.stdout)
        assert row['session_id_sha256']==(hashlib.sha256(sid.encode()).hexdigest() if sid else None)
        assert feedback['verification_scope']=='hook_and_mcp_response_only'
        assert all(marker not in json.dumps(row)+p.stdout for marker in ['PRIVATE_PROMPT_BODY','PRIVATE_ERROR_BODY'])
        assert not sid or sid not in json.dumps(row)
        if actual=='none': assert p.stdout==''
        else:
            message=json.loads(p.stdout)['systemMessage']
            assert 'session_finalize done' not in message
            if status in ('unknown','failed','degraded'): assert 'not confirmed' in message
            if name=='zero': assert 'curated=0' in message and 'response confirmed' in message
        results.append({'case':name,'status':'PASS','seconds':seconds,'receipt':row,'stdout':p.stdout})
        if baseline and name=='tool_error':
            with sqlite3.connect(home/'state.db') as db:db.execute('create table memories(key text)')
            old,_=run_hook(home,env,sid,baseline)
            assert 'session_finalize done' in old.stdout,old.stdout
            (output/'baseline-false-completion.json').write_text(json.dumps({
                'status':'REPRODUCED','fixture':'tool_error','old_stdout':old.stdout,
                'new_stdout':p.stdout,'old_exit_code':old.returncode,'new_exit_code':p.returncode},indent=2)+'\n')
    return results


def client(binary,env,directory):
    directory.mkdir()
    c=mcp.Client([str(binary),'mcp'],env,directory)
    c.request('initialize',{'protocolVersion':'2024-11-05','capabilities':{},
        'clientInfo':{'name':'precompact-effects-isolated','version':'1'}})
    c.send({'jsonrpc':'2.0','method':'notifications/initialized'})
    return c


def call(c,name,args):
    result=c.request('tools/call',{'name':name,'arguments':args})
    assert not result.get('isError'),result
    return result


def real_hook(root,output,binary):
    home=root/'real';(home/'bin').mkdir(parents=True)
    (home/'bin/agent-bridge').symlink_to(binary)
    env=state_env(home)
    c=client(binary,env,output/'seed')
    try:call(c,'memory_save',{'key':'preserved-fixture','kind':'context',
        'content':'Synthetic control must remain after precompact.','importance':1.0})
    finally:c.close()
    sid='isolated-real-precompact';transcript(home,sid)
    runs=[]
    for event in ['preCompact','sessionEndCurate']:
        p,seconds=run_hook(home,env,sid,event=event)
        receipt=json.loads((home/'data/agent-bridge/hook-runs.jsonl').read_text().splitlines()[-1])
        assert receipt['event']==event and receipt['effect_feedback']['status']=='completed',receipt
        assert receipt['output_bytes']==len(p.stdout.encode())
        runs.append({'event':event,'receipt':receipt,'stdout':p.stdout,'seconds':seconds})
    # Independent persisted readback after both child MCP processes have exited.
    with sqlite3.connect(home/'state.db') as db:
        assert db.execute('pragma quick_check').fetchone()[0]=='ok'
        assert db.execute("select content from memories where key='preserved-fixture'").fetchone()[0]=='Synthetic control must remain after precompact.'
        keys=[r[0] for r in db.execute("select key from memories where kind='work_memory' and content like '%Synthetic precompact fixture%'")]
        assert keys, 'real precompact did not persist its work-memory snapshot'
    c=client(binary,env,output/'reopened-mcp')
    try:
        cap=json.loads(call(c,'capabilities',{'compact':True,'sections':['hooks']})['content'][0]['text'])
        audit=json.loads(call(c,'readiness_audit',{'include_local_install':True,'repo_root':str(ROOT)})['content'][0]['text'])
        status=json.loads(call(c,'hook_status',{'repo_hooks_dir':str(ROOT/'crates/bridge/src/hooks')})['content'][0]['text'])
        for run in runs:
            for group in [cap['hooks']['recent_runs'],audit['hooks'],status['hooks']]:
                row=next(x for x in group if x['event']==run['event'])
                assert row['last_effect_feedback_state']=='reported',row
                assert row['last_effect_feedback']==run['receipt']['effect_feedback']
                assert row['last_session_id_sha256']==hashlib.sha256(sid.encode()).hexdigest()
        for key in keys:
            got=call(c,'memory_get',{'key':key})
            assert 'Synthetic precompact fixture' in json.dumps(got)
    finally:c.close()
    return {'status':'PASS','runs':runs,'mcp_surfaces':3,'reopened_memory_readback':True,
            'control_memory_preserved':True,'database_quick_check':'ok','build':cap['build'],
            'scope':'New isolated synthetic database; no production lifecycle invocation.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path)
    p.add_argument('--binary',type=Path)
    p.add_argument('--real-only',action='store_true')
    args=p.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    if args.baseline: args.baseline=args.baseline.resolve()
    with tempfile.TemporaryDirectory(prefix='ab-precompact-effects-') as temp:
        root=Path(temp)
        results=[] if args.real_only else fixtures(root,args.output,args.baseline)
        real=real_hook(root,args.output,args.binary.resolve()) if args.binary else None
    report={'status':'PASS','fixture_count':len(results),'fixtures':results,'real_mcp':real,
            'production_hooks_or_data_modified':False}
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'PASS','fixture_count':len(results),'real_mcp':bool(real)}))


if __name__=='__main__':main()
