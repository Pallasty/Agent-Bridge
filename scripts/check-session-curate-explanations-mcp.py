#!/usr/bin/env python3
"""Compare baseline/candidate using real MCP and separate, disposable databases.

Only the candidate's explicit dry_run=true response may add explanations.
No production state, Codex session, deployment, or external inference is used.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mcp_client', ROOT/'scripts/check-capabilities-sections-mcp.py')
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)
FIXTURE = ROOT/'scripts/fixtures/session-curate-explanations.json'


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def stable(row):
    return {k: v for k, v in row.items() if k not in ('created_at', 'updated_at', 'last_accessed_at')}


def check_explanations(case, response):
    envelope = response['explanations']
    assert envelope['schema'] == 'agent_bridge.session_curate.explanations.v1'
    assert envelope['role_attribution'] == 'input_text_headers_only'
    assert envelope['task_state_assessed'] is False
    items = envelope['items']
    assert len(items) == len(response['candidates'])
    lines = case['text'].splitlines()
    for e, candidate in zip(items, response['candidates']):
        assert e['key'] == candidate['key']
        source = e['source']
        n = source['line_number']
        assert source['raw_line'] == lines[n-1]
        h = source['role_header_line']
        if h is None:
            assert source['role'] is None
        else:
            assert h <= n and lines[h-1].strip().lower() == '['+source['role']+']'
        assert abs(sum(s['weight'] for s in e['matched_signals'])-e['score']) < 0.00001
        for kind, vote in e['kind_votes'].items():
            assert abs(sum(s['weight'] for s in e['matched_signals'] if s['kind_vote'] == kind)-vote) < 0.00001
        assert abs(e['threshold']-case.get('threshold', 0.45)) < 0.00001
        if e['score_applied']:
            assert e['extraction'] == 'implicit' and e['score'] >= e['threshold']
        else:
            assert e['extraction'] in ('explicit_marker', 'explicit_section')
    if 'expected_source_lines' in case:
        assert [e['source']['line_number'] for e in items] == case['expected_source_lines']
    if case['id'] == 'E3':
        assert items[0]['source']['content_clipped'] is True
        assert '下一步' not in response['candidates'][0]['content']
        assert '下一步' in items[0]['source']['raw_line']
        assert items[0]['source']['role'] == 'assistant'
    if case['id'] == 'E4':
        assert items[0]['score_applied'] is False
        assert items[0]['score'] < items[0]['threshold']


def exercise(binary, output, home, project, candidate, cases):
    output.mkdir()
    home.mkdir()
    assert home.stat().st_uid == os.getuid(), 'SQLite fixture must be owner-owned.'
    db_path = home/'data/agent-bridge/state.db'
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'CODEX_HOME': str(home/'.codex'),
           'AGENT_BRIDGE_MACHINE_ENV': str(home/'absent-env'), 'AGENT_BRIDGE_DB': str(db_path),
           'AGENT_BRIDGE_EMBED_BACKEND': 'hash', 'AGENT_BRIDGE_HEADLESS': '1',
           'AGENT_BRIDGE_CREDS_FILE': str(home/'absent-creds'), 'AGENT_BRIDGE_TOOLSET': 'all-dev',
           'AGENT_BRIDGE_MAX_BLOCKING_THREADS': '32', 'AB_ALLOW_BROWSER': 'false',
           'AB_PET_STATE_DISABLE': '1', 'AB_INSTINCT_OBSERVER_ENABLED': '0',
           'AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS': 'eval'}
    for part in ('CONFIG', 'DATA', 'CACHE', 'STATE'):
        env['XDG_'+part+'_HOME'] = str(home/part.lower())
    client = mcp.Client([str(binary), 'mcp'], env, output)
    responses = {}

    def call(name, args):
        response = client.request('tools/call', {'name': name, 'arguments': args})
        assert not response.get('isError'), response
        return json.loads(response['content'][0]['text'])

    scope = 'project:'+str(project)
    try:
        client.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                       'clientInfo': {'name': 'session-curate-explanations-regression', 'version': '1'}})
        client.send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
        page = client.request('tools/list', {})
        tools = page['tools'][:]
        while page.get('nextCursor'):
            page = client.request('tools/list', {'cursor': page['nextCursor']})
            tools.extend(page['tools'])
        assert {'session_curate', 'session_handoff', 'memory_get'} <= {t['name'] for t in tools}
        build = call('capabilities', {'compact': True, 'sections': ['memory']})['build']
        fds = []
        for fd in Path(f'/proc/{client.proc.pid}/fd').iterdir():
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            if target.endswith(('state.db', 'state.db-wal', 'state.db-shm')):
                assert target.startswith(str(home)+'/'), target
                fds.append(target)
        assert str(db_path) in fds
        write(output/'identity-and-isolation.json', {'build': build, 'db_fds': fds,
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()})
        for case in cases:
            args = {'conversation_text': case['text'], 'session_id': 'explain-fixture',
                    'scope': scope, 'dry_run': True, 'max_items': case.get('max_items', 50),
                    'implicit_score_threshold': case.get('threshold', 0.45),
                    'implicit_dedup_jaccard': 0.55}
            response = call('session_curate', args)
            responses[case['id']] = response
            write(output/'dry-run-responses.json', responses)
            assert response['dry_run'] is True
            if candidate:
                check_explanations(case, response)
            else:
                assert 'explanations' not in response
            if case['id'] in [f'P{i}' for i in range(1, 9)]:
                assert any(c['kind'] == 'todo' for c in response['candidates'])
        with sqlite3.connect(db_path) as db:
            dry_run_rows = db.execute("select count(*) from memories where key like 'curated_%'").fetchone()[0]
        assert dry_run_rows == 0, 'Dry-run must not save candidate memories.'
        # Same fixed persistence batch on both servers. Neither save nor
        # handoff is permitted to gain diagnostic fields or altered semantics.
        batch = '\n'.join(c['text'] for c in cases[:11])
        saved = call('session_curate', {'conversation_text': batch, 'scope': scope,
                     'session_id': 'explain-fixture', 'dry_run': False, 'max_items': 50})
        assert saved['dry_run'] is False and 'explanations' not in saved
        assert saved['saved_count'] > 0 and not saved['errors']
        # Store writes stamp updated_at individually. A debug batch can cross
        # a second while a release batch does not; ByImportance uses that clock.
        # Preserve raw timing, then give both isolated consumers the same age
        # inputs rather than weakening the exact pending-order comparison.
        with sqlite3.connect(db_path) as db:
            raw_clocks = db.execute("select key,created_at,updated_at from memories where key like 'curated_%' order by key").fetchall()
            count = db.execute("update memories set updated_at=1700000000 where key like 'curated_%'").rowcount
        write(output/'fixture-sort-clock.json', {'raw_clocks': raw_clocks,
              'controlled_updated_at': 1700000000, 'fixture_rows_updated': count,
              'production_state_modified': False})
        handoff = call('session_handoff', {'cwd': str(project), 'max_todos': 20, 'max_handoff_memories': 0})
        assert 'explanations' not in handoff
        readback = [call('memory_get', {'key': row['key']}) for row in saved['new_memories']]
        result = {'dry_runs': responses, 'dry_run_candidate_rows': dry_run_rows,
                  'save': saved, 'pending_items': handoff['pending_items'],
                  'candidate_limit_reached': handoff['candidate_limit_reached'],
                  'readback': [stable(row) for row in readback]}
        write(output/'effect-receipts.json', result)
    finally:
        client.close()
    with sqlite3.connect(db_path) as source:
        with sqlite3.connect(output/'fixture-state.db') as backup:
            source.backup(backup)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(FIXTURE.read_text())['cases']
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='ab-curate-explanations-') as state:
        base = Path(state)
        project = base/'project'
        project.mkdir()
        baseline = exercise(args.baseline.resolve(), args.output/'baseline', base/'baseline', project, False, cases)
        candidate = exercise(args.candidate.resolve(), args.output/'candidate', base/'candidate', project, True, cases)
        for case in cases:
            old = baseline['dry_runs'][case['id']]
            new = candidate['dry_runs'][case['id']]
            assert {k: v for k, v in new.items() if k != 'explanations'} == old, case['id']
        for name in ('save', 'pending_items', 'candidate_limit_reached', 'readback'):
            assert baseline[name] == candidate[name], name
    summary = {'status': 'PASS', 'dry_run_pairs': len(cases), 'true_task_controls': 8,
               'actual_user_task_inputs': {c['id']: [r['kind'] for r in candidate['dry_runs'][c['id']]['candidates']]
                                           for c in cases if c['group'] == 'actual_user_task'},
               'explanation_only_addition': True, 'candidate_memories_saved_by_dry_run': 0,
               'saved_memories_compared': candidate['save']['saved_count'],
               'pending_items_compared': len(candidate['pending_items']),
               'save_and_handoff_unchanged': True, 'production_data_modified': False,
               'natural_recovery_samples': 0, 'rendering_mi50': 'deferred',
               'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}
    write(args.output/'SUMMARY.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
