#!/usr/bin/env python3
"""Real stdio MCP regression for exact-project bootstrap handoff priority.

All writes use synthetic records in a new isolated database. No Codex thread,
production memory, external inference, or natural-recovery sample is created.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mcp_client', ROOT/'scripts/check-capabilities-sections-mcp.py')
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)
QUERY = '很好！我们按照你的思路落地下一步目标。'
KEY = 'current-project-handoff'
CONTENT = 'CURRENT: audit closed; unknown retained; recovery pending; render deferred.'

def exercise(binary, output, expect_fixed, expected_commit=None):
    output.mkdir(parents=True,exist_ok=False)
    state = tempfile.TemporaryDirectory(prefix='ab-bootstrap-handoff-')
    home = Path(state.name)
    assert home.stat().st_uid == os.getuid(), 'Fixture state must be owned by the current user.'
    project = home/'project'
    project.mkdir(parents=True)
    db_path = home/'data/agent-bridge/state.db'
    env = {'PATH':'/usr/bin:/bin','HOME':str(home),'CODEX_HOME':str(home/'.codex'),
           'AGENT_BRIDGE_MACHINE_ENV':str(home/'absent-env'),'AGENT_BRIDGE_DB':str(db_path),
           'AGENT_BRIDGE_EMBED_BACKEND':'hash','AGENT_BRIDGE_HEADLESS':'1',
           'AGENT_BRIDGE_CREDS_FILE':str(home/'absent-creds'),'AGENT_BRIDGE_TOOLSET':'all-dev',
           'AGENT_BRIDGE_MAX_BLOCKING_THREADS':'32','AB_ALLOW_BROWSER':'false',
           'AB_PET_STATE_DISABLE':'1','AB_INSTINCT_OBSERVER_ENABLED':'0'}
    for part in ['CONFIG','DATA','CACHE','STATE']:
        env['XDG_'+part+'_HOME'] = str(home/part.lower())
    client = mcp.Client([str(binary),'mcp'],env,output)
    checks = []
    def call(name,args):
        response=client.request('tools/call',{'name':name,'arguments':args})
        assert not response.get('isError'),(name,response)
        return response['content'][0]['text']
    def row(key,scope,created,accessed,tags=None):
        return (key,'session_handoff',CONTENT if key==KEY else 'Synthetic background.',
                json.dumps(tags or []),'[]',scope,created,created,accessed,0,0.8,'active')
    def insert(rows):
        with sqlite3.connect(db_path) as db:
            db.executemany('insert into memories(key,kind,content,tags,related_keys,scope,created_at,updated_at,last_accessed_at,access_count,importance,status) values(?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    try:
        client.request('initialize',{'protocolVersion':'2024-11-05','capabilities':{},
                       'clientInfo':{'name':'bootstrap-handoff-regression','version':'1'}})
        client.send({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})
        cap=json.loads(call('capabilities',{'compact':True,'sections':['memory']}))
        assert Path(cap['memory']['db_path'])==db_path
        if expected_commit:
            assert cap['build']['git_sha']==expected_commit[:12],cap['build']
        now=int(time.time())
        scope='project:'+str(project)
        tags=['continuity_role:state','continuity_confidence:observed','continuity_actionability:plan_influence']
        insert([row(KEY,scope,now-100,now-1000,tags)]+[
            row('global-'+str(i),None,now-1000,now+i) for i in range(12)])
        args={'cwd':str(project),'frontend':'cursor','query':QUERY,'limit':5}
        text=call('session_bootstrap',args)
        assert (KEY in text) is expect_fixed, text
        checks.append('generic continuation '+('restores current handoff' if expect_fixed else 'reproduces old omission'))
        if not expect_fixed:
            return {'status':'BASELINE_OMISSION_REPRODUCED','checks':checks,'build':cap['build'],'mechanism_only':True}
        assert CONTENT in text,text
        checks.append('current closed/unknown/pending/deferred content is visible')
        for query in ['Vork Agent-Bridge current delivery and deferred scope',QUERY]:
            text=call('session_bootstrap',{**args,'query':query,'limit':1})
            assert KEY in text and CONTENT in text
        checks.append('targeted and generic queries preserve priority at limit=1')
        text=call('session_bootstrap',{**args,'cwd':str(project)+'/'})
        assert KEY in text
        checks.append('trailing project slash preserves exact-scope eligibility')
        brief=json.loads(call('session_handoff',{'cwd':str(project),'max_todos':0,'max_handoff_memories':3}))
        assert any(r['key']==KEY for r in brief['session_handoff_memories'])
        other=json.loads(call('session_handoff',{'cwd':str(home/'other'),'max_todos':0,'max_handoff_memories':3}))
        assert not any(r['key']==KEY for r in other['session_handoff_memories'])
        checks.append('handoff consumer agrees and another project receives no priority handoff')
        insert([
            row('excluded-auto',scope,now+100,now+100,tags+['auto_curated']),
            row('excluded-stale',scope,now+101,now+101,[t for t in tags if not t.startswith('continuity_confidence:')]+['continuity_confidence:stale']),
            row('excluded-background',scope,now+102,now+102,['continuity_role:archive','continuity_actionability:background']),
            row('excluded-unverified',scope,now+103,now+103,tags+['unverified_identifier']),
        ])
        text=call('session_bootstrap',args)
        assert KEY in text and all(key not in text for key in ['excluded-auto','excluded-stale','excluded-background','excluded-unverified'])
        checks.append('existing auto/stale/background eligibility guards remain in force')
        # Make all 256 newest visible candidates global. A complete absence
        # claim must not bypass the explicit candidate-window omission notice.
        insert([row('window-global-'+str(i),None,now+1000+i,now+1000+i) for i in range(256)])
        text=call('session_bootstrap',args)
        assert 'Handoff candidate window limited' in text,text
        assert 'session_handoff' in text and 'memory_get' in text
        assert '(no scoped memories yet)' not in text
        checks.append('full candidate window with no eligible rows reports omission and follow-up')
        follow=json.loads(call('session_handoff',{'cwd':str(project),'max_todos':0,'max_handoff_memories':8}))
        assert follow['candidate_limit_reached']['session_handoffs'] is True
        saved=json.loads(call('memory_get',{'key':KEY}))
        assert saved['content']==CONTENT
        checks.append('reported follow-up and known-key lookup work under the same window limit')
        return {'status':'PASS','checks':checks,'build':cap['build'],'mechanism_only':True,
                'production_state_modified':False,'natural_recovery_verified':False}
    finally:
        try:
            client.close()
        finally:
            state.cleanup()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--baseline-binary',type=Path)
    p.add_argument('--expected-commit')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    result={}
    if a.baseline_binary:
        result['baseline']=exercise(a.baseline_binary.resolve(),a.output/'baseline',False)
    result['candidate']=exercise(a.binary.resolve(),a.output/'candidate',True,a.expected_commit)
    result['status']='PASS'
    (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
