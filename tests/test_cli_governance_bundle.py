"""Portable evidence rejects corruption, incomplete scope and false custody."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/eval'))
import cli_governance_bundle as bundle
from test_cli_governance_live import report


class BundleTests(unittest.TestCase):
    def setUp(self):
        clean = patch.dict(os.environ, bundle.live.clean_env(os.environ), clear=True)
        clean.start(); self.addCleanup(clean.stop)
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.run = self.root / 'bundle'; self.run.mkdir()
        self.tree = 'a' * 40
        self.summary = {'schema': 'agent_bridge.cli_governance_live_run.v1', 'success': True,
                        'baseline_commit': bundle.live.BASELINE, 'candidate_tree': self.tree,
                        'baseline_archive_sha256': 'a' * 64, 'started_at_unix': 1, 'finished_at_unix': 2,
                        'enrolled_suites': ['identity', 'instinct', 'worktree'], 'suites': {}}
        for name, identity in [('baseline', bundle.live.BASELINE), ('candidate', 'tree-' + self.tree)]:
            log = self.run / (name + '-build.log'); log.write_text('fixture build log')
            self.summary[name] = {'sha256': 'b' * 64, 'build_identity': identity,
                                  'build_log_sha256': bundle.live.digest(log)}
        for suite in bundle.live.SUITES:
            r = report(suite); r.update(baseline_sha256='b' * 64, candidate_sha256='b' * 64, script_sha256='c' * 64)
            path = self.run / (suite + '.json'); path.write_text(json.dumps(r))
            self.summary['suites'][suite] = {'passed': r['passed'], 'report_sha256': bundle.live.digest(path),
                                            'harness_sha256': 'c' * 64}
        self.save()

    def save(self):
        (self.run / 'summary.json').write_text(json.dumps(self.summary))

    def verify(self):
        return bundle.verify_bundle(self.run, self.tree, sorted(bundle.live.STAGES))

    def test_complete_bundle_and_relocation(self):
        self.assertEqual(self.verify(), 143)
        moved = self.root / 'moved'; shutil.copytree(self.run, moved)
        self.assertEqual(bundle.verify_bundle(moved, self.tree, sorted(bundle.live.STAGES)), 143)

    def test_wrong_candidate_tree(self):
        with self.assertRaisesRegex(bundle.live.g.GovernanceError, 'candidate'):
            bundle.verify_bundle(self.run, 'd' * 40, sorted(bundle.live.STAGES))

    def test_invalid_summary_fields(self):
        for field, value in [('success', False), ('success', 1), ('schema', 'unknown'),
                             ('baseline_commit', 'd' * 40), ('enrolled_suites', ['identity']),
                             ('baseline_archive_sha256', '../archive'), ('finished_at_unix', 0),
                             ('started_at_unix', float('nan'))]:
            with self.subTest(field=field, value=value):
                old = self.summary[field]; self.summary[field] = value; self.save()
                with self.assertRaises(bundle.live.g.GovernanceError): self.verify()
                self.summary[field] = old
        self.save()

    def test_missing_files(self):
        for path in list(self.run.iterdir()):
            content = path.read_bytes(); path.unlink()
            with self.subTest(name=path.name), self.assertRaises(bundle.live.g.GovernanceError): self.verify()
            path.write_bytes(content)

    def test_changed_report_or_log(self):
        for name in ['identity.json', 'candidate-build.log', 'baseline-build.log']:
            path = self.run / name; content = path.read_bytes(); path.write_bytes(content + b' ')
            with self.subTest(name=name), self.assertRaisesRegex(bundle.live.g.GovernanceError, 'digest'): self.verify()
            path.write_bytes(content)

    def test_failed_case_even_with_updated_report_digest(self):
        path = self.run / 'identity.json'; value = json.loads(path.read_text())
        value['cases'][0]['passed'] = False; path.write_text(json.dumps(value))
        self.summary['suites']['identity']['report_sha256'] = bundle.live.digest(path); self.save()
        with self.assertRaisesRegex(bundle.live.g.GovernanceError, 'failed case'): self.verify()

    def test_wrong_build_identity(self):
        self.summary['candidate']['build_identity'] = bundle.live.BASELINE; self.save()
        with self.assertRaisesRegex(bundle.live.g.GovernanceError, 'build identity'): self.verify()

    def test_incomplete_scope_cannot_choose_own_expectation(self):
        self.summary['suites'].pop('instinct'); self.save()
        with self.assertRaisesRegex(bundle.live.g.GovernanceError, 'scope'): self.verify()

    def test_symlink_not_portable_file(self):
        path = self.run / 'identity.json'; outside = self.root / 'external.json'
        path.rename(outside); path.symlink_to(outside)
        with self.assertRaisesRegex(bundle.live.g.GovernanceError, 'regular bundle file'): self.verify()

    def test_cli_resolves_commit_and_checks_harness_source(self):
        repo = self.root / 'repo'; repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'test@example.invalid')
        scripts = repo / 'scripts/eval'; scripts.mkdir(parents=True)
        for suite, entry in self.summary['suites'].items():
            source = scripts / (bundle.live.SUITES[suite][0] + '.py'); source.write_text('# fixture\n')
            entry['harness_sha256'] = bundle.live.digest(source)
            path = self.run / (suite + '.json'); r = json.loads(path.read_text()); r['script_sha256'] = entry['harness_sha256']
            path.write_text(json.dumps(r)); entry['report_sha256'] = bundle.live.digest(path)
        git('add', '.'); git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')
        self.summary['candidate_tree'] = git('rev-parse', 'HEAD^{tree}')
        self.summary['candidate']['build_identity'] = 'tree-' + self.summary['candidate_tree']; self.save()
        args = ['verify', '--run-dir', str(self.run), '--candidate-commit', 'HEAD']
        with patch.object(bundle.live.g, 'ROOT', repo), patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bundle.main(), 0)
            # Internally consistent report forgery still differs from selected commit's harness.
            self.summary['suites']['identity']['harness_sha256'] = 'd' * 64
            path = self.run / 'identity.json'; r = json.loads(path.read_text()); r['script_sha256'] = 'd' * 64
            path.write_text(json.dumps(r)); self.summary['suites']['identity']['report_sha256'] = bundle.live.digest(path); self.save()
            self.assertEqual(bundle.main(), 1)


if __name__ == '__main__':
    unittest.main()
