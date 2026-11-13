#!/usr/bin/env python3
"""Real stdio MCP + isolated setup regression for hook effect reporting.
All logs, setup writes and databases are isolated; never mutates host hooks.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mcp_client', ROOT/'scripts/check-capabilities-sections-mcp.py')
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)


def exercise(binary, output, state):
    env = {'PATH':'/usr/bin:/bin', 'HOME':str(state),
           'CODEX_HOME':str(state/'.codex'), 'AGENT_BRIDGE_DB':str(state/'state.db'),
           'AGENT_BRIDGE_EMBED_BACKEND':'hash', 'AGENT_BRIDGE_HEADLESS':'1',
           'AGENT_BRIDGE_TERMINAL':'pty', 'AB_ALLOW_BROWSER':'false',
           'AGENT_BRIDGE_CREDS_FILE':str(state/'absent-creds'),
           'AGENT_BRIDGE_TOOLSET':'all-dev', 'AGENT_BRIDGE_MAX_BLOCKING_THREADS':'32'}
    for name in ['CONFIG', 'DATA', 'CACHE', 'STATE']:
        env['XDG_'+name+'_HOME'] = str(state/name.lower())
    setup = subprocess.run([str(binary), 'setup', '--frontend', 'codex'], env=env,
                           text=True, capture_output=True, timeout=45)
    (output/'setup.stdout.log').write_text(setup.stdout)
    (output/'setup.stderr.log').write_text(setup.stderr)
    assert setup.returncode == 0, setup.stderr
    hashes = {}
    for name, source in [('ab-memory-hook','ab-memory-hook.sh'),
                         ('ab-precompact-hook','ab-precompact-hook.sh'),
                         ('ab-session-end-hook','ab-session-end-hook.sh'),
                         ('ab-instinct-observer-hook','ab-instinct-observer-hook.py')]:
        installed = (state/'.local/bin'/name).read_bytes()
        expected = (ROOT/'crates/bridge/src/hooks'/source).read_bytes()
        assert installed == expected, 'stale embedded template: '+name
        hashes[name] = hashlib.sha256(installed).hexdigest()
    # A second setup must not regress the repaired templates either.
    repeated = subprocess.run([str(binary), 'setup', '--frontend', 'codex'], env=env,
                              text=True, capture_output=True, timeout=45)
    assert repeated.returncode == 0
    for name, digest in hashes.items():
        assert hashlib.sha256((state/'.local/bin'/name).read_bytes()).hexdigest() == digest

    path = state/'data/agent-bridge/hook-runs.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    client = mcp.Client([str(binary), 'mcp'], env, output)
    checks = []
    def call(name, args):
        result = client.request('tools/call', {'name':name, 'arguments':args})
        assert not result.get('isError'), result
        return json.loads(result['content'][0]['text'])
    def latest():
        cap = call('capabilities', {'compact':True, 'sections':['hooks']})
        assert cap['hooks']['run_scope'] == 'latest_record_per_event_not_current_session'
        assert 'memory' in cap['_selection']['omitted_sections']
        audit = call('readiness_audit', {'include_local_install':True, 'repo_root':str(ROOT)})
        status = call('hook_status', {'repo_hooks_dir':str(ROOT/'crates/bridge/src/hooks')})
        groups = [cap['hooks']['recent_runs'], audit['hooks'], status['hooks']]
        return [next(r for r in rows if r['event']=='beforeSubmitPrompt') for rows in groups]
    try:
        client.request('initialize', {'protocolVersion':'2024-11-05', 'capabilities':{},
                       'clientInfo':{'name':'hook-effects-integration','version':'1'}})
        client.send({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})
        build = call('capabilities', {'sections':['hooks'], 'compact':True})['build']
        for label, feedback in [
            ('missing', None), ('legacy', None),
            ('emitted', {'status':'emitted','code':'bootstrap_context_emitted','actual':'bootstrap_context_payload'}),
            ('degraded', {'status':'degraded','code':'static_fallback_emitted','actual':'static_context_payload'}),
            ('cooldown', {'status':'skipped','code':'cooldown','actual':'none'}),
            ('failed', {'status':'failed','code':'static_query_failed','actual':'none'}),
            ('latest_legacy', None),
            ('invalid', {'status':'private prompt fixture'})]:
            row={'event':'beforeSubmitPrompt','ts':'2026-11-12T00:00:00Z','exit_code':0,'output_bytes':0}
            if feedback is not None:
                row['effect_feedback']={**feedback,'requested':'bootstrap_context',
                    'dropped':['bootstrap_context_selection'] if label=='degraded' else [],
                    'verification_scope':'hook_payload_only','prompt':'DO_NOT_FORWARD_PRIVATE_BODY'}
                row['session_id_sha256']='a'*64
            if label=='invalid':row['session_id_sha256']='DO_NOT_FORWARD_SESSION'
            if label!='missing':
                with path.open('a') as stream:
                    stream.write(json.dumps(row)+'\n')
                    stream.write('{broken trailing line\n')
            rows=latest()
            expected='invalid' if label=='invalid' else 'unreported' if feedback is None else 'reported'
            for item in rows:
                assert item['last_effect_feedback_state']==expected, (label,item)
                if expected=='reported':
                    clean={k:v for k,v in row['effect_feedback'].items() if k!='prompt'}
                    assert item['last_effect_feedback']==clean
                    assert item['last_session_id_sha256']=='a'*64
                else:assert item['last_effect_feedback'] is None
                assert 'DO_NOT_FORWARD' not in json.dumps(item)
            checks.append(label)
        hidden = call('readiness_audit', {'include_local_install':False,'repo_root':str(ROOT)})
        assert all(r['last_effect_feedback_state']=='unreported' and r['last_session_id_sha256'] is None for r in hidden['hooks'])
        checks.append('local_diagnostics_opt_out')
    finally:
        client.close()
    return {'status':'PASS','build':build,'cases':checks,'mcp_surfaces':3,
            'embedded_templates':hashes,'repeat_setup_preserves_templates':True,
            'production_state_modified':False,'clean_eof_exit':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ab-hook-effects-') as temp:
        result=exercise(a.binary.resolve(),a.output,Path(temp))
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
