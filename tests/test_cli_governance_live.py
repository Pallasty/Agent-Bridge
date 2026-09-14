"""Fresh CLI runner: pinned builds, strict reports, deduplication and failures."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts/eval'
sys.path.insert(0, str(SCRIPTS))
import cli_governance_live as live


def report(suite):
    script, total, schema, stable = live.SUITES[suite]
    key = 'passed' if suite == 'identity' else 'equal'
    return {'schema': schema, 'total': total, 'passed': total,
            'baseline_sha256': 'baseline', 'candidate_sha256': 'candidate', 'script_sha256': 'script',
            **{field: True for field in stable}, 'comparison_performed': True,
            'cases': [{'case': f'case-{i}', key: True} for i in range(total)]}


class LiveTests(unittest.TestCase):
    def setUp(self):
        clean = patch.dict(os.environ, live.clean_env(os.environ), clear=True)
        clean.start(); self.addCleanup(clean.stop)

    def verify(self, value, suite='identity'):
        live.verify_report(value, suite, 'baseline', 'candidate', 'script')

    def test_instinct_deduplicated(self):
        self.assertEqual(live.selected_suites(['s18', 's20']), ['instinct'])
        self.assertEqual(live.selected_suites(['s18', 's19', 's20', 's21']), ['identity', 'instinct', 'worktree'])
        self.assertEqual(live.selected_suites([]), [])

    def test_valid_actual_report_shapes(self):
        for suite in live.SUITES:
            self.verify(report(suite), suite)

    def test_wrong_schema_rejected(self):
        r = report('identity'); r['schema'] = 'other'
        with self.assertRaisesRegex(live.g.GovernanceError, 'schema'):
            self.verify(r)

    def test_zero_or_missing_cases_rejected(self):
        for value in [0, None, True]:
            r = report('identity'); r['total'] = value
            with self.assertRaisesRegex(live.g.GovernanceError, 'incomplete'):
                self.verify(r)

    def test_wrong_input_hashes_rejected(self):
        for field in ['baseline_sha256', 'candidate_sha256', 'script_sha256']:
            r = report('identity'); r[field] = 'stale'
            with self.assertRaisesRegex(live.g.GovernanceError, 'digest'):
                self.verify(r)

    def test_false_stability_rejected(self):
        for suite, (_, _, _, fields) in live.SUITES.items():
            for field in fields:
                r = report(suite); r[field] = False
                with self.assertRaisesRegex(live.g.GovernanceError, 'unstable'):
                    self.verify(r, suite)

    def test_missing_rows_rejected(self):
        r = report('identity'); r['cases'].pop()
        with self.assertRaisesRegex(live.g.GovernanceError, 'missing case'):
            self.verify(r)

    def test_failed_row_rejected_despite_success_counter(self):
        r = report('identity'); r['cases'][0]['passed'] = False
        with self.assertRaisesRegex(live.g.GovernanceError, 'failed case'):
            self.verify(r)

    def test_duplicate_case_rejected(self):
        r = report('identity'); r['cases'][1] = r['cases'][0]
        with self.assertRaisesRegex(live.g.GovernanceError, 'duplicate'):
            self.verify(r)

    def test_baseline_only_cannot_authorize_candidate(self):
        r = report('identity'); r['comparison_performed'] = False
        with self.assertRaisesRegex(live.g.GovernanceError, 'baseline-only'):
            self.verify(r)

    def test_git_environment_removed(self):
        self.assertEqual(live.clean_env({'GIT_DIR': 'parent', 'GIT_INDEX_FILE': 'index', 'GIT_CONFIG_COUNT': '1', 'PATH': 'bin'}), {'PATH': 'bin'})

    def test_build_requires_success_and_copies_distinct_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root / 'target'; (target / 'debug').mkdir(parents=True)
            produced = target / 'debug/agent-bridge'; produced.write_bytes(b'fresh executable')
            output = root / 'snapshot'
            with patch.object(live.subprocess, 'run') as run:
                result = live.build(root, target, output, {}, 'source-id', root / 'build.log')
                self.assertEqual(result['sha256'], live.digest(produced))
                self.assertEqual(run.call_args.args[0], ['cargo', 'build', '--locked', '-p', 'ab-bridge', '--bin', 'agent-bridge'])
                self.assertEqual(run.call_args.kwargs['env']['AGENT_BRIDGE_BUILD_SHA'], 'source-id')
            produced.write_bytes(b'later build')
            self.assertEqual(output.read_bytes(), b'fresh executable')

    def test_failed_build_does_not_copy_old_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'debug').mkdir(); (root / 'debug/agent-bridge').write_bytes(b'stale')
            with patch.object(live.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['cargo'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    live.build(root, root, root / 'output', {}, 'id', root / 'log')
            self.assertFalse((root / 'output').exists())

    def test_failing_run_keeps_failure_summary_and_fresh_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(live, 'extract_baseline', side_effect=RuntimeError('fail')):
                for _ in range(2):
                    with self.assertRaises(RuntimeError):
                        live.run_cli_suites(['s21'], root, {}, 'tree')
            summaries = list(root.glob('governance-live/run-*/summary.json'))
            self.assertEqual(len(summaries), 2)
            self.assertTrue(all(json.loads(p.read_text())['success'] is False for p in summaries))

    def test_export_preserves_parent_git_metadata_and_pinned_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'repo'; source.mkdir()
            env = live.clean_env(os.environ)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=source, env=env, text=True).strip()
            git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
            (source / 'tracked').write_text('pinned')
            git('add', '.'); git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'base')
            commit = git('rev-parse', 'HEAD')
            watched = [source / '.git/config', source / '.git/index']
            before = [p.read_bytes() for p in watched]
            (source / 'tracked').write_text('unstaged')
            export = root / 'export'; export.mkdir()
            with patch.object(live.g, 'ROOT', source), patch.object(live, 'BASELINE', commit):
                sha = live.extract_baseline(export, env)
            self.assertEqual(len(sha), 64)
            self.assertEqual((export / 'tracked').read_text(), 'pinned')
            self.assertFalse((export / '.git').exists())
            self.assertEqual(git('rev-parse', 'HEAD'), commit)
            self.assertEqual([p.read_bytes() for p in watched], before)


if __name__ == '__main__':
    unittest.main()
