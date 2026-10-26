#!/usr/bin/env python3
"""Offline provenance-hidden text comparison; no model calls or task execution.

Only packet.json is intended for the reviewer. mapping.json is private.
Selection is a preference, never independent task acceptance or experience lift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import stat

from workflow_experience_contrast import MAX_BYTES, artifact, nonempty, parse_json, read_bytes, require


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')


def text_artifact(ref, root):
    data=artifact(ref,root)
    try:
        text=data.decode('utf-8')
    except UnicodeError as exc:
        raise ValueError('only UTF-8 text artifacts are supported') from exc
    require(bool(text.strip()), 'empty artifacts cannot be silently excluded')
    return text


def read_spec(path):
    path=Path(path).resolve()
    raw=read_bytes(path);spec=parse_json(raw)
    require(isinstance(spec,dict), 'spec must be an object')
    candidates=spec.get('candidates')
    require(isinstance(candidates,list) and 1<=len(candidates)<=7,
            'spec needs 1..7 candidates plus baseline')
    task=text_artifact(spec.get('task'),path.parent)
    entries={'baseline':{'artifact':spec.get('baseline'),
                         'text':text_artifact(spec.get('baseline'),path.parent)}}
    for c in candidates:
        require(isinstance(c,dict) and nonempty(c.get('label')), 'candidate needs a label')
        label=c['label'];require(label not in entries, 'duplicate or reserved candidate label')
        entries[label]={'artifact':c.get('artifact'), 'text':text_artifact(c.get('artifact'),path.parent)}
    return raw,task,entries


def private_write(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        require(stat.S_IMODE(os.fstat(stream.fileno()).st_mode)==0o600,
                'filesystem does not enforce private file permissions')
        stream.write(data)


def prepare(spec_path,output_dir):
    spec_path=Path(spec_path).resolve()
    raw,task,entries=read_spec(spec_path)
    labels=list(entries)
    random.SystemRandom().shuffle(labels)
    mapping={chr(65+i):label for i,label in enumerate(labels)}
    packet={'schema':'agent_bridge.artifact_comparison_packet.v1','task':task,
            'candidates':[{'id':i,'text':entries[label]['text']} for i,label in mapping.items()]}
    packet_bytes=encode(packet)
    require(len(packet_bytes)<=MAX_BYTES, 'combined packet exceeds 8 MiB limit')
    private={'schema':'agent_bridge.artifact_comparison_mapping.v1',
             'spec_path':str(spec_path),'spec_sha256':digest(raw),
             'packet_sha256':digest(packet_bytes),'id_to_label':mapping}
    output_dir=Path(output_dir)
    output_dir.mkdir(mode=0o700)  # Exclusive: never reuse/overwrite a prior review.
    require(stat.S_IMODE(output_dir.stat().st_mode)==0o700,
            'filesystem does not enforce private directory permissions; use native private storage')
    private_write(output_dir/'mapping.json',encode(private))
    private_write(output_dir/'packet.json',packet_bytes)
    return {'status':'PREPARED','packet':str(output_dir/'packet.json'),
            'packet_sha256':private['packet_sha256'],'candidate_count':len(mapping),
            'instruction':'Give only packet.json to the reviewer; retain mapping.json privately.'}


def resolve(review_dir,decision):
    review_dir=Path(review_dir)
    private=parse_json(read_bytes(review_dir/'mapping.json'))
    require(isinstance(private,dict) and private.get('schema')=='agent_bridge.artifact_comparison_mapping.v1',
            'invalid private mapping')
    packet_bytes=read_bytes(review_dir/'packet.json')
    packet_hash=digest(packet_bytes)
    require(packet_hash==private.get('packet_sha256'), 'packet hash mismatch')
    require(isinstance(decision,dict) and decision.get('packet_sha256')==packet_hash,
            'decision must bind the reviewed packet hash')
    require('choice' in decision and nonempty(decision.get('rationale')), 'choice and rationale are required')
    require(nonempty(private.get('spec_path')), 'mapping is missing spec path')
    raw,task,entries=read_spec(Path(private['spec_path']))
    require(digest(raw)==private.get('spec_sha256'), 'original specification changed')
    packet=parse_json(packet_bytes)
    require(isinstance(packet,dict) and packet.get('schema')=='agent_bridge.artifact_comparison_packet.v1'
            and packet.get('task')==task, 'packet does not match source task')
    mapping=private.get('id_to_label')
    require(isinstance(mapping,dict) and all(isinstance(v,str) for v in mapping.values()), 'invalid ID mapping')
    require(len(mapping)==len(entries) and set(mapping.values())==set(entries), 'mapping must be a bijection')
    expected_ids=[chr(65+i) for i in range(len(entries))]
    require(set(mapping)==set(expected_ids), 'invalid anonymous IDs')
    expected=[{'id':i,'text':entries[mapping[i]]['text']} for i in expected_ids]
    require(packet.get('candidates')==expected, 'packet contents do not match mapped artifacts')
    choice=decision['choice']
    require(choice is None or (isinstance(choice,str) and choice in mapping), 'unknown candidate choice')
    label=mapping[choice] if choice is not None else None
    return {'schema':'agent_bridge.artifact_comparison_selection.v1',
            'status':'SELECTED_FOR_REVIEW' if label else 'ABSTAINED',
            'packet_sha256':packet_hash,'choice':choice,'selected_label':label,
            'selected_artifact':entries[label]['artifact'] if label else None,
            'rationale':decision['rationale'],'task_acceptance_verified':False,
            'runtime_influence_allowed':False,
            'limits':['Labels/paths were hidden; content identity cues were not removed.',
                      'Reviewer identity, independence and correctness are not authenticated.',
                      'File hashes bind local bytes, not hostile tamper resistance or causal benefit.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p=sub.add_parser('resolve');p.add_argument('--review-dir',type=Path,required=True)
    p.add_argument('--decision',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=(prepare(args.spec,args.output_dir) if args.command=='prepare' else
                resolve(args.review_dir,parse_json(read_bytes(args.decision))))
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'INVALID_INPUT','error':str(exc)},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
