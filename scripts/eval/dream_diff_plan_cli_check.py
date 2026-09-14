#!/usr/bin/env python3
"""Compare isolated diff output and read telemetry to the pinned pre-extraction oracle."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from dream_identity_cli_parity import setup, invoke

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / 'crates/bridge/tests/fixtures/dream_diff_cli_baseline.json'
BASE = 'e34700ca0adf5b21c892d872f6ab8fa09f146fa3'


def cases():
    old = {'schema_version': 1, 'captured_at': 100, 'memory': {'active_total': 4, 'by_kind_non_skill': [{'kind': 'z', 'count': 2}]}, 'access': {'top_10_keys': [{'key': 'shared', 'access_count': 1}, {'key': 'drop', 'access_count': 7}]}}
    new = {'schema_version': 2, 'captured_at': 3700, 'memory': {'active_total': 9, 'by_kind_non_skill': [{'kind': 'a', 'count': 1}]}, 'access': {'top_10_keys': [{'key': 'shared', 'access_count': 5}, {'key': 'enter', 'access_count': 3}]}, 'topology': {'non_skill_active_total': 2, 'orphan_count': 1, 'p4_evolved_coverage': 1, 'top_5_hubs': [{'key': 'hub', 'degree': 4}]}, 'transitions': {'top_5': [{'from': 'x', 'to': 'y', 'count': 3}]}}
    def row(key, value, kind='snapshot', created=100, status='active'):
        return [key, kind, value if isinstance(value,str) else json.dumps(value), created, status]
    standard = [row('a', old), row('b', new, created=200)]
    result = [('help', ['--help'], []), ('missing-a', [], standard), ('missing-b', ['a'], standard), ('not-found-a', ['absent', 'b'], standard), ('not-found-b', ['a', 'absent'], standard)]
    result += [('kind-before-json', ['a','b'], [row('a',old,'fact'),row('b','{')]), ('parse-a-first', ['a','b'], [row('a','{'),row('b','[')]), ('parse-b', ['a','b'], [row('a',old),row('b','[')]), ('unsupported-schema', ['a','b'], [row('a',{'schema_version':3}),row('b',new)]), ('missing-schema', ['a','b'], [row('a',{}),row('b',new)])]
    for mode in [[], ['--json']]:
        suffix = 'json' if mode else 'text'
        result += [('mixed-'+suffix,['a','b',*mode],standard), ('reverse-'+suffix,['b','a',*mode],standard), ('same-key-'+suffix,['a','a',*mode],standard), ('quiet-'+suffix,['a','b',*mode],[row('a',{'schema_version':1}),row('b',{'schema_version':1})])]
    tied = copy.deepcopy(standard); value=json.loads(tied[1][2]);value['captured_at']=100;tied[1][2]=json.dumps(value)
    result += [('equal-time',['b','a','--json'],tied), ('auto-empty',['--auto','--json'],[]), ('auto-one',['--auto'],[row('snapshot_daily_one',old)])]
    result += [('auto-pair',['--auto','--json'],[row('snapshot_daily_old',old,status='superseded'),row('snapshot_daily_new',new,created=200),row('snapshot_daily_archived',new,created=300,status='archived')])]
    return result


def execute(binary, argv, rows):
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);env,db=setup(root)
        bootstrap,_,_=invoke(binary,root,env,['dream','identity','--json'])
        assert bootstrap.returncode == 0, bootstrap.stderr.decode()
        with sqlite3.connect(db) as connection:
            for key,kind,content,created,status in rows:
                connection.execute('INSERT INTO memories (key,kind,content,created_at,updated_at,last_accessed_at,status) VALUES (?,?,?,?,?,0,?)',(key,kind,content,created,created,status))
            connection.executescript('CREATE TABLE read_trace (key TEXT); CREATE TRIGGER trace_access AFTER UPDATE OF access_count ON memories BEGIN INSERT INTO read_trace VALUES (NEW.key); END;')
        run,start,end=invoke(binary,root,env,['dream','diff',*argv])
        with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as connection:
            cursor=connection.execute('SELECT * FROM memories ORDER BY key');names=[column[0] for column in cursor.description]
            state=[dict(zip(names,row)) for row in cursor]
            trace=[row[0] for row in connection.execute('SELECT key FROM read_trace ORDER BY rowid')]
        for row in state:
            if row['access_count']:
                assert int(start)<=row['last_accessed_at']<=int(end),row
                row['last_accessed_at']='<READ_TIME>'
        return {'exit':run.returncode,'stdout':run.stdout.decode().replace(str(root),'<FIXTURE>'),'stderr':run.stderr.decode().replace(str(root),'<FIXTURE>'),'memories':state,'read_trace':trace}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--record',action='store_true',help='explicitly regenerate the oracle using the reviewed baseline binary')
    args=parser.parse_args();binary=args.binary.resolve()
    sha=hashlib.file_digest(binary.open('rb'),'sha256').hexdigest()
    if args.record:
        known=json.loads((ROOT/'docs/reports/main-rs-governance/2026-09-14-civil-date-cli-bundle/summary.json').read_text())
        assert sha==known['candidate']['sha256'],'record requires the verified pre-extraction binary'
    actual={name:execute(binary,argv,rows) for name,argv,rows in cases()}
    if args.record:
        GOLDEN.write_text(json.dumps({'source_commit':BASE,'binary_sha256':sha,'cases':actual},indent=2,ensure_ascii=False)+'\n')
        print(f'Recorded {len(actual)} baseline CLI cases')
        return
    expected=json.loads(GOLDEN.read_text())
    assert expected['source_commit']==BASE
    assert set(actual)==set(expected['cases'])
    for name,value in actual.items():
        assert value==expected['cases'][name],f'{name}: CLI output or database/read-order effects changed'
    print(f'PASS: {len(actual)} exact CLI output/state/read-order cases')


if __name__=='__main__':
    main()
