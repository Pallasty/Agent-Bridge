#!/usr/bin/env python3
"""Read-only execution-contrast review for existing Experience Object v0 files.

Inspired by Harness²'s edit/observation separation; no upstream code copied.
Artifact integrity and numeric contrasts are checked, not causality, truthful
measurement, independent acceptance, complete attempt coverage, or transfer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re

MAX_BYTES = 8 * 1024 * 1024
CONDITIONS = ('task', 'input_sha256', 'model', 'environment')
COSTS = ('input_tokens', 'output_tokens', 'elapsed_ms')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def read_bytes(path):
    try:
        with path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError(f'cannot read artifact: {path.name}') from exc
    require(len(data) <= MAX_BYTES, 'artifact exceeds 8 MiB limit')
    return data


def parse_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f'non-finite JSON number: {value}')

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid UTF-8 JSON artifact') from exc


def artifact(ref, root):
    require(isinstance(ref, dict), 'artifact reference must be an object')
    rel = ref.get('path')
    require(nonempty(rel) and not Path(rel).is_absolute(), 'artifact path must be relative')
    path = (root / rel).resolve()
    require(path.is_relative_to(root), 'artifact path is outside evidence root')
    require(path.is_file(), f'missing artifact: {rel}')
    expected = ref.get('sha256')
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected),
            'artifact needs lowercase SHA-256 hash')
    data = read_bytes(path)
    require(hashlib.sha256(data).hexdigest() == expected, f'artifact hash mismatch: {rel}')
    return data


def run_record(ref, root):
    run = parse_json(artifact(ref, root))
    require(isinstance(run, dict) and nonempty(run.get('run_id')), 'run needs run_id')
    conditions = run.get('conditions')
    require(isinstance(conditions, dict) and all(nonempty(conditions.get(k)) for k in CONDITIONS),
            'run needs task, input_sha256, model and environment conditions')
    require(re.fullmatch('[0-9a-f]{64}', conditions['input_sha256']), 'invalid input_sha256')
    require(run.get('execution_status') in ('completed', 'failed', 'not_run'), 'invalid execution_status')
    require(isinstance(run.get('metrics'), dict), 'run metrics must be an object')
    require(all(nonempty(k) and number(v) for k, v in run['metrics'].items()),
            'metrics must be finite numbers, not booleans or strings')
    costs = run.get('cost', {})
    require(isinstance(costs, dict), 'cost must be an object')
    for key in COSTS:
        value = costs.get(key)
        require(value is None or (number(value) and value >= 0), 'cost must be nonnegative or null')
    return run


def review(experience, evidence_root):
    require(isinstance(experience, dict) and experience.get('schema') == 'agent_bridge.experience.v0',
            'expected agent_bridge.experience.v0')
    require(nonempty(experience.get('experience_id')) and nonempty(experience.get('goal')),
            'experience needs experience_id and goal')
    root = Path(evidence_root).resolve()
    spec = experience.get('execution_contrast', {})
    require(isinstance(spec, dict), 'execution_contrast must be an object')
    changes, metrics, pairs = [spec.get(key, []) for key in ('changes', 'metrics', 'pairs')]
    require(all(isinstance(items, list) for items in (changes, metrics, pairs)),
            'changes, metrics and pairs must be arrays')
    require(len(changes) <= 32 and len(metrics) <= 32 and len(pairs) <= 100,
            'review exceeds bounded input limits')
    edits = []
    components = set()
    for change in changes:
        require(isinstance(change, dict) and nonempty(change.get('component'))
                and nonempty(change.get('description')), 'change needs component and description')
        require(change['component'] not in components, 'duplicate component')
        components.add(change['component'])
        before = artifact(change.get('before'), root)
        after = artifact(change.get('after'), root)
        require(before != after, 'declared change has identical before/after bytes')
        edits.append({key: change[key] for key in ('component', 'description', 'before', 'after')})
    directions = {}
    for metric in metrics:
        require(isinstance(metric, dict) and nonempty(metric.get('name'))
                and metric.get('direction') in ('higher', 'lower'), 'invalid metric definition')
        require(metric['name'] not in directions, 'duplicate metric name')
        directions[metric['name']] = 1 if metric['direction'] == 'higher' else -1
    records = []
    runs = {'baseline': [], 'candidate': []}
    ids, hashes = set(), set()
    insufficient, confounds = [], []
    if not changes or not metrics or not pairs:
        insufficient.append('missing_changes_metrics_or_pairs')
    if len(changes) > 1:
        confounds.append('multiple_components_changed')
    if len(pairs) == 1:
        confounds.append('single_pair')
    signs = set()
    for index, pair in enumerate(pairs):
        require(isinstance(pair, dict), 'pair must be an object')
        parsed = {}
        for side in ('baseline', 'candidate'):
            ref = pair.get(side)
            run = run_record(ref, root)
            require(run['run_id'] not in ids and ref['sha256'] not in hashes,
                    'duplicate run or artifact cannot count as replication')
            ids.add(run['run_id']); hashes.add(ref['sha256'])
            parsed[side] = run
            runs[side].append(run)
        base, candidate = parsed['baseline'], parsed['candidate']
        reasons = []
        if base['conditions'] != candidate['conditions']:
            confounds.append(f'pair_{index}:conditions_differ')
            reasons.append('conditions_differ')
        deltas = {}
        for name, direction in directions.items():
            if name not in base['metrics'] or name not in candidate['metrics']:
                insufficient.append(f'pair_{index}:missing_metric:{name}')
                reasons.append(f'missing_metric:{name}')
                continue
            delta = candidate['metrics'][name] - base['metrics'][name]
            require(number(delta), 'metric delta is not finite')
            deltas[name] = delta
            if delta != 0:
                signs.add(1 if delta * direction > 0 else -1)
        if any(run['execution_status'] != 'completed' for run in parsed.values()):
            insufficient.append(f'pair_{index}:incomplete_execution')
            reasons.append('incomplete_execution')
        records.append({'index': index, 'baseline': pair['baseline'], 'candidate': pair['candidate'],
                        'baseline_run_id': base['run_id'], 'candidate_run_id': candidate['run_id'],
                        'baseline_status': base['execution_status'],
                        'candidate_status': candidate['execution_status'],
                        'deltas': deltas, 'issues': reasons})
    if len(signs) > 1:
        confounds.append('mixed_metric_directions')
    if insufficient:
        verdict = 'insufficient_evidence'
    elif confounds:
        verdict = 'confounded'
    else:
        verdict = 'helped' if signs == {1} else 'hurt' if signs == {-1} else 'no_observed_effect'
    costs = {}
    for side, side_runs in runs.items():
        costs[side] = {}
        for key in COSTS:
            values = [run.get('cost', {}).get(key) for run in side_runs]
            costs[side][key] = sum(values) if values and all(v is not None for v in values) else None
            require(costs[side][key] is None or number(costs[side][key]), 'cost total is not finite')
    costs['complete'] = all(costs[side][key] is not None for side in runs for key in COSTS)
    counts = {'pairs': len(pairs)}
    for side, side_runs in runs.items():
        for status in ('completed', 'failed', 'not_run'):
            counts[f'{side}_{status}'] = sum(run['execution_status'] == status for run in side_runs)
    return {'schema': 'agent_bridge.workflow_experience_contrast.v1',
            'experience_id': experience['experience_id'], 'goal': experience['goal'],
            'verdict': verdict, 'decision': 'REVIEW_LESSON' if verdict in ('helped', 'hurt') else 'NO_ENTRY',
            'reasons': insufficient + confounds, 'changes': edits, 'pairs': records,
            'counts': counts, 'cost': costs, 'read_only': True,
            'causal_effect_proven': False, 'runtime_influence_allowed': False,
            'limits': ['Observations and conditions are caller-supplied; hashes bind bytes, not truth.',
                       'Declared components do not prove that no other changes occurred.',
                       'Two pairs are a review minimum, not statistical or causal proof.',
                       'No independent task acceptance, transfer or total attempt coverage is certified.',
                       'No experience is written or promoted; costs are reported, not optimized.']}


def propose_draft(experience, evidence_root, lesson):
    """Package a caller-proposed lesson after fresh review; never promote it."""
    require(isinstance(lesson, dict), 'lesson must be an object')
    require(all(nonempty(lesson.get(key)) for key in ('cue', 'lesson', 'counterexample')),
            'lesson needs cue, lesson and counterexample')
    unknowns = lesson.get('unknowns')
    require(isinstance(unknowns, list) and bool(unknowns) and all(nonempty(x) for x in unknowns),
            'lesson needs an explicit nonempty unknowns list')
    result = review(experience, evidence_root)
    envelope = {'schema': 'agent_bridge.workflow_experience_draft.v1',
                'decision': 'NO_ENTRY', 'review': result, 'draft': None}
    if result['decision'] != 'REVIEW_LESSON':
        return envelope
    # Construct from a whitelist: old success/promotion assertions cannot leak in.
    draft = {
        'schema': 'agent_bridge.experience.v0',
        'experience_id': experience['experience_id'] + '::contrast-draft',
        'goal': experience['goal'],
        'execution_contrast': copy.deepcopy(experience['execution_contrast']),
        'trajectory': {'execution_review': copy.deepcopy(result)},
        'outcome': {'status': 'proposed', 'observed_verdict': result['verdict'],
                    'task_acceptance_verified': False, 'causal_effect_proven': False,
                    'cost': copy.deepcopy(result['cost']),
                    'known_limits': result['limits'] + list(unknowns)},
        'reflection': {'claim_status': 'caller_proposed', 'cue': lesson['cue'],
                       'lesson': lesson['lesson'], 'falsifier': lesson['counterexample'],
                       'unknowns': list(unknowns)},
        'source_anchors': {
            'source_experience_id': experience['experience_id'],
            'evidence_root': str(Path(evidence_root).resolve()),
            'review_canonical_sha256': hashlib.sha256(json.dumps(
                result, sort_keys=True, ensure_ascii=False, allow_nan=False
            ).encode('utf-8')).hexdigest()},
        'promotion': {'skill_candidate': False, 'runbook_candidate': False,
                      'memory_lesson_candidate': False, 'runtime_influence_allowed': False,
                      'owner_gate_required': True, 'suggested_trigger': lesson['cue']},
        'safety': {'fixture_writes_memory': False, 'fixture_changes_runtime': False,
                   'fixture_changes_retrieval_order': False,
                   'fixture_authorizes_future_runtime_influence': False},
    }
    for key in ('scope', 'lane'):
        if nonempty(experience.get(key)):
            draft[key] = experience[key]
    envelope.update(decision='DRAFT_PROPOSED', draft=draft)
    return envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experience', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path,
                        help='default: experience file parent; references must stay inside this root')
    parser.add_argument('--lesson', type=Path,
                        help='opt-in caller lesson JSON; emit a proposed draft only with sufficient contrast')
    args = parser.parse_args()
    try:
        experience = parse_json(read_bytes(args.experience))
        root = args.evidence_root or args.experience.resolve().parent
        result = (propose_draft(experience, root, parse_json(read_bytes(args.lesson)))
                  if args.lesson else review(experience, root))
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'invalid_input', 'decision': 'NO_ENTRY', 'error': str(exc)},
                         ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
