"""Behavior checks for the offline experience review, using isolated artifacts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/eval'))
import workflow_experience_contrast as contrast


class ContrastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exp = {'schema': 'agent_bridge.experience.v0', 'experience_id': 'test',
                    'goal': 'Return the correct saved commitment',
                    'execution_contrast': {
                        'changes': [{'component': 'query', 'description': 'Keep project name',
                                     'before': self.file('before.txt', b'query'),
                                     'after': self.file('after.txt', b'project query')}],
                        'metrics': [{'name': 'correct', 'direction': 'higher'}], 'pairs': []}}
        for n in range(2):
            self.exp['execution_contrast']['pairs'].append({
                'baseline': self.run_artifact(f'b{n}', 0, n), 'candidate': self.run_artifact(f'c{n}', 1, n)})

    def file(self, name, data):
        (self.root / name).write_bytes(data)
        return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}

    def run_artifact(self, name, value, task):
        return self.file(name+'.json', json.dumps({
            'run_id': name, 'conditions': {'task': str(task), 'input_sha256': 'a'*64,
                'model': 'test-model', 'environment': 'fixture-v1'},
            'execution_status': 'completed', 'metrics': {'correct': value},
            'cost': {'input_tokens': 10, 'output_tokens': 2, 'elapsed_ms': 100}
        }).encode())

    def change_run(self, side, index=0, **updates):
        pair = self.exp['execution_contrast']['pairs'][index]
        ref = pair[side]; obj = json.loads((self.root/ref['path']).read_text())
        obj.update(updates)
        pair[side] = self.file(ref['path'], json.dumps(obj).encode())

    def review(self):
        return contrast.review(self.exp, self.root)

    def test_observed_help_is_not_causal_or_runtime_authority(self):
        result = self.review()
        self.assertEqual(result['verdict'], 'helped')
        self.assertEqual(result['decision'], 'REVIEW_LESSON')
        self.assertFalse(result['causal_effect_proven'])
        self.assertFalse(result['runtime_influence_allowed'])
        self.assertEqual(result['counts']['pairs'], 2)
        self.assertEqual(result['cost']['candidate']['input_tokens'], 20)

    def test_negative_and_no_effect_preserved(self):
        for value, verdict, decision in [(-1, 'hurt', 'REVIEW_LESSON'),
                                          (0, 'no_observed_effect', 'NO_ENTRY')]:
            for n in range(2): self.change_run('candidate', n, metrics={'correct': value})
            result = self.review()
            self.assertEqual((result['verdict'], result['decision']), (verdict, decision))

    def test_single_pair_is_confounded(self):
        self.exp['execution_contrast']['pairs'].pop()
        self.assertEqual(self.review()['verdict'], 'confounded')

    def test_multiple_edits_cannot_claim_attribution(self):
        change = copy.deepcopy(self.exp['execution_contrast']['changes'][0])
        change['component'] = 'prompt'
        self.exp['execution_contrast']['changes'].append(change)
        self.assertEqual(self.review()['verdict'], 'confounded')

    def test_mismatched_conditions_and_mixed_results(self):
        self.change_run('candidate', conditions={'task': 'different', 'input_sha256': 'a'*64,
                                               'model': 'test-model', 'environment': 'fixture-v1'})
        self.assertEqual(self.review()['verdict'], 'confounded')
        self.setUp()
        self.change_run('candidate', metrics={'correct': -1})
        self.assertEqual(self.review()['verdict'], 'confounded')

    def test_failure_stays_in_denominator(self):
        self.change_run('candidate', execution_status='failed')
        result = self.review()
        self.assertEqual(result['counts']['candidate_failed'], 1)
        self.assertEqual(result['counts']['pairs'], 2)
        self.assertEqual(result['decision'], 'NO_ENTRY')
        self.assertEqual(len(result['pairs']), 2)

    def test_missing_metric_or_cost_is_explicit(self):
        self.change_run('candidate', metrics={})
        self.assertEqual(self.review()['verdict'], 'insufficient_evidence')
        self.setUp()
        self.change_run('candidate', cost={})
        result = self.review()
        self.assertFalse(result['cost']['complete'])
        self.assertIsNone(result['cost']['candidate']['input_tokens'])

    def test_duplicate_runs_rejected_not_counted_as_replication(self):
        pairs = self.exp['execution_contrast']['pairs']
        pairs[1] = copy.deepcopy(pairs[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.review()

    def test_tampered_or_missing_artifact_rejected(self):
        (self.root/'c0.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash'): self.review()
        (self.root/'c0.json').unlink()
        with self.assertRaises(ValueError): self.review()

    def test_root_escape_rejected(self):
        ref = self.exp['execution_contrast']['changes'][0]['before']
        for path in ['../outside', '/etc/passwd']:
            ref['path'] = path
            with self.assertRaisesRegex(ValueError, 'relative|outside'): self.review()

    def test_invalid_numeric_metrics_rejected(self):
        for value in [True, '1', float('nan'), float('inf')]:
            self.change_run('candidate', metrics={'correct': value})
            with self.assertRaises(ValueError): self.review()

    def test_extreme_numeric_values_fail_cleanly(self):
        self.change_run('candidate', metrics={'correct': 10**400})
        with self.assertRaises(ValueError): self.review()
        self.setUp()
        for n in range(2):
            self.change_run('candidate', n, cost={'elapsed_ms': 1e308})
        with self.assertRaises(ValueError): self.review()

    def test_lower_is_better_and_mixed_metrics_are_not_hidden(self):
        self.exp['execution_contrast']['metrics'][0]['direction'] = 'lower'
        self.assertEqual(self.review()['verdict'], 'hurt')
        self.exp['execution_contrast']['metrics'].append({'name': 'errors', 'direction': 'lower'})
        for n in range(2):
            self.change_run('baseline', n, metrics={'correct': 0, 'errors': 3})
            self.change_run('candidate', n, metrics={'correct': 1, 'errors': 0})
        self.assertEqual(self.review()['verdict'], 'confounded')

    def test_duplicate_json_keys_are_invalid(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            contrast.parse_json(b'{"score": 0, "score": 1}')

    def test_report_does_not_mutate_input_or_artifacts(self):
        before = {f.name: f.read_bytes() for f in self.root.iterdir()}
        exp = copy.deepcopy(self.exp)
        self.review()
        self.assertEqual(self.exp, exp)
        self.assertEqual({f.name: f.read_bytes() for f in self.root.iterdir()}, before)

    def test_existing_experience_remains_read_only_and_no_entry(self):
        path = ROOT/'docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json'
        before = path.read_bytes()
        result = contrast.review(json.loads(before), path.parent)
        self.assertEqual(result['verdict'], 'insufficient_evidence')
        self.assertEqual(result['decision'], 'NO_ENTRY')
        self.assertEqual(path.read_bytes(), before)

    def test_documented_synthetic_example_is_runnable(self):
        path = ROOT/'scripts/eval/fixtures/workflow_experience_contrast/experience.json'
        result = contrast.review(contrast.parse_json(path.read_bytes()), path.parent)
        self.assertEqual(result['verdict'], 'helped')
        self.assertEqual(result['experience_id'], 'synthetic_contrast_example')
        self.assertFalse(result['causal_effect_proven'])

    def test_cli_json_and_exit_codes(self):
        path = self.root/'experience.json'; path.write_text(json.dumps(self.exp))
        cmd = [sys.executable, str(ROOT/'scripts/eval/workflow_experience_contrast.py'),
               '--experience', str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'helped')
        (self.root/'before.txt').write_text('tampered')
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['decision'], 'NO_ENTRY')


if __name__ == '__main__': unittest.main()
