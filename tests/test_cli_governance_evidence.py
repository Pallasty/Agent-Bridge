"""Negative controls in real Git indexes for evidence binding and execution custody."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts/eval'
sys.path.insert(0, str(SCRIPTS))
import cli_governance_evidence as e


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        isolated = patch.dict(os.environ, {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}, clear=True)
        isolated.start()
        self.addCleanup(isolated.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cli = patch.object(e, 'run_cli_suites')
        cli.start()
        self.addCleanup(cli.stop)
        old = e.g.ROOT
        e.g.ROOT = self.root
        self.addCleanup(setattr, e.g, 'ROOT', old)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.write(e.g.MAIN_RS, 'fn main() {}\n')
        for stage in e.PROFILES:
            for file in e.bindings(stage):
                self.write(file, file + '\n')
            self.write(f'crates/bridge/tests/{e.PROFILES[stage][2]}.rs', '// boundary\n')
        self.registry = {'schema': e.SCHEMA, 'stages': {}}
        for stage in e.PROFILES:
            self.report(stage)
        self.save_registry()
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True).strip()

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)

    def report(self, stage):
        section = e.PROFILES[stage][1]
        value = {section: {'passed': 2, 'total': 2, 'success': True}, 'cli_parity': {'passed': 1, 'total': 1}}
        for file, (key, field) in e.bindings(stage).items():
            value.setdefault(key, {})[field] = hashlib.sha256((self.root / file).read_bytes()).hexdigest()
        name = f'docs/reports/main-rs-governance/{stage}.json'
        self.write(name, json.dumps(value))
        self.registry['stages'][stage] = {'report': name, 'sha256': hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def save_registry(self):
        self.write(e.REGISTRY, json.dumps(self.registry))

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def validate(self):
        return e.validate('HEAD', 'INDEX')

    def test_unchanged_evidence_selects_no_execution(self):
        self.assertEqual(self.validate(), [])

    def test_module_only_change_requires_fresh_report(self):
        self.write('crates/bridge/src/cli/dream_identity_view.rs', '// changed\n')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'stale evidence'):
            self.validate()

    def test_unstaged_report_cannot_authorize_staged_module(self):
        file = 'crates/bridge/src/cli/dream_identity_view.rs'
        self.write(file, '// changed\n')
        self.git('add', file)
        self.report('s21')
        self.save_registry()
        with self.assertRaisesRegex(e.g.GovernanceError, 'stale evidence'):
            self.validate()

    def test_data_validation_reads_index_not_worktree(self):
        self.write('crates/bridge/src/cli/dream_identity_view.rs', '// unstaged\n')
        self.assertEqual(self.validate(), [])
        with self.assertRaisesRegex(e.g.GovernanceError, 'worktree equal'):
            e.ensure_checkout('INDEX')

    def test_new_bound_report_selects_execution(self):
        self.write('crates/bridge/src/cli/dream_identity_view.rs', '// changed\n')
        self.report('s21')
        self.save_registry()
        self.git('add', '.')
        # Registry amendments conservatively rerun every enrolled suite.
        self.assertEqual(self.validate(), sorted(e.PROFILES))

    def test_single_test_change_selects_only_its_suite(self):
        self.write('crates/bridge/tests/cli_dream_identity_s21_extraction.rs', '// changed\n')
        self.git('add', '.')
        self.assertEqual(self.validate(), ['s21'])

    def test_root_and_shared_dependency_changes_select_all(self):
        for file in [e.g.MAIN_RS, 'crates/store/src/sqlite.rs', 'Cargo.lock']:
            self.write(file, '// changed\n')
            self.git('add', '.')
            self.assertEqual(self.validate(), sorted(e.PROFILES))

    def test_report_tamper_is_rejected(self):
        self.write(self.registry['stages']['s21']['report'], '{}')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'report digest'):
            self.validate()

    def test_failed_report_cannot_pass_after_rehash(self):
        p = self.root / self.registry['stages']['s21']['report']
        d = json.loads(p.read_text()); d['view_parity']['passed'] = 1
        p.write_text(json.dumps(d))
        self.registry['stages']['s21']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        self.save_registry(); self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'fully passed'):
            self.validate()

    def test_empty_report_cannot_pass(self):
        p = self.root / self.registry['stages']['s21']['report']
        d = json.loads(p.read_text()); d['view_parity'].update(passed=0, total=0)
        p.write_text(json.dumps(d))
        self.registry['stages']['s21']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        self.save_registry(); self.git('add', '.')
        with self.assertRaises(e.g.GovernanceError):
            self.validate()

    def test_harness_change_rejected(self):
        self.write('scripts/eval/dream_identity_view_parity.py', '# changed')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'stale evidence'):
            self.validate()

    def test_bound_dependency_change_rejected(self):
        self.write('crates/store/src/lib.rs', '// changed')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'stale evidence'):
            self.validate()

    def test_registry_deletion_rejected(self):
        (self.root / e.REGISTRY).unlink(); self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'removal cannot disable'):
            self.validate()

    def test_stage_removal_rejected(self):
        del self.registry['stages']['s21']; self.save_registry(); self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'four enrolled stages'):
            self.validate()

    def test_external_report_path_rejected(self):
        self.registry['stages']['s21']['report'] = 'docs/reports/main-rs-governance/../../secret.json'
        self.save_registry(); self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'repository-local'):
            self.validate()

    def test_missing_boundary_test_rejected(self):
        (self.root / 'crates/bridge/tests/cli_dream_identity_s21_extraction.rs').unlink()
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'boundary test missing'):
            self.validate()

    def test_symlink_cannot_supply_evidence(self):
        file = 'crates/bridge/src/cli/dream_identity_view.rs'
        p = self.root / file
        p.unlink()
        p.symlink_to('/outside-source')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'regular Git file'):
            self.validate()

    def test_symlink_cannot_replace_boundary_test(self):
        p = self.root / 'crates/bridge/tests/cli_dream_identity_s21_extraction.rs'
        p.unlink()
        p.symlink_to('/outside-test')
        self.git('add', '.')
        with self.assertRaisesRegex(e.g.GovernanceError, 'regular Git file'):
            self.validate()

    def test_actual_hook_blocks_module_only_change_before_cargo(self):
        for script in ('cli_governance_evidence.py', 'cli_composition_root_governance.py', 'cli_governance_live.py'):
            dest = self.root / 'scripts/eval' / script
            shutil.copyfile(SCRIPTS / script, dest)
        hook = self.root / '.githooks/pre-commit'
        hook.parent.mkdir()
        shutil.copyfile(SCRIPTS.parents[1] / '.githooks/pre-commit', hook)
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', '.githooks')
        self.write('crates/bridge/src/cli/dream_identity_view.rs', '// unreviewed')
        self.git('add', '.')
        run = subprocess.run(['git', 'commit', '-qm', 'must fail'], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('stale evidence', run.stderr)
        self.assertNotIn('Running', run.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)

    def test_historical_head_cannot_execute_current_checkout(self):
        self.write('README.md', 'later'); self.commit()
        with self.assertRaisesRegex(e.g.GovernanceError, 'checked-out HEAD'):
            e.ensure_checkout(self.base)

    def test_untracked_source_cannot_enter_execution(self):
        self.write('crates/bridge/tests/surprise.rs', '// untracked')
        with self.assertRaisesRegex(e.g.GovernanceError, 'untracked inputs'):
            e.ensure_checkout('INDEX')

    def test_runner_propagates_failure(self):
        with patch.object(e, 'ensure_checkout', return_value='tree'), patch.object(e.subprocess, 'check_output', return_value='ext4'), patch.object(e.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['cargo'])):
            with self.assertRaises(subprocess.CalledProcessError):
                e.run_selected(['s21'], 'INDEX')

    def test_gate_changes_execute_self_tests_before_domain_tests(self):
        with patch.object(e, 'ensure_checkout', return_value='tree'), patch.object(e.subprocess, 'check_output', return_value='ext4'), patch.object(e.subprocess, 'run') as run:
            e.run_selected(['s21'], 'INDEX', check_gate=True)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0][-1], 'test_cli_governance_evidence.py')
            self.assertEqual(commands[1][-1], 'test_cli_composition_root_governance.py')
            self.assertEqual(commands[2][-1], 'test_cli_governance_live.py')
            self.assertEqual(commands[3][-1], 'test_cli_governance_bundle.py')
            self.assertEqual(commands[4][-1], 'self-test')
            self.assertEqual(commands[5][0], 'cargo')

    def test_runner_does_not_export_parent_git_context(self):
        with patch.dict(os.environ, {'GIT_DIR': '/parent', 'GIT_INDEX_FILE': '/parent/index', 'GIT_CONFIG_COUNT': '1'}), patch.object(e, 'ensure_checkout', return_value='tree'), patch.object(e.subprocess, 'check_output', return_value='ext4'), patch.object(e.subprocess, 'run') as run:
            e.run_selected(['s21'], 'INDEX')
            for call in run.call_args_list:
                self.assertFalse(any(k.startswith('GIT_') for k in call.kwargs['env']))

    def test_fixture_suites_cannot_mutate_inherited_parent_repository(self):
        watched = [self.root / '.git/config', self.root / '.git/index']
        before = [p.read_bytes() for p in watched]
        head = self.git('rev-parse', 'HEAD')
        environment = dict(os.environ, GIT_DIR=str(self.root / '.git'),
                           GIT_WORK_TREE=str(self.root), GIT_INDEX_FILE=str(self.root / '.git/index'))
        for file, test in [
            ('test_cli_governance_evidence.py', 'EvidenceTests.test_unchanged_evidence_selects_no_execution'),
            ('test_cli_composition_root_governance.py', 'RepositoryAdmissionTests.test_exact_transition'),
        ]:
            run = subprocess.run([sys.executable, str(SCRIPTS.parents[1] / 'tests' / file), test],
                                 cwd=self.root, env=environment, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(self.git('rev-parse', 'HEAD'), head)
            self.assertEqual([p.read_bytes() for p in watched], before)

    def test_fixed_runner_and_post_run_index_guard(self):
        with patch.object(e, 'ensure_checkout', side_effect=['before', 'after']), patch.object(e.subprocess, 'check_output', return_value='ext4'), patch.object(e.subprocess, 'run') as run:
            with self.assertRaisesRegex(e.g.GovernanceError, 'index changed'):
                e.run_selected(['s21'], 'INDEX')
            self.assertEqual(run.call_args_list[0].args[0], ['cargo', 'test', '-p', 'ab-bridge', '--test', 'cli_dream_identity_s21_extraction'])
            self.assertIn('scripts/eval/dream_identity_view_parity.py', run.call_args_list[1].args[0])


if __name__ == '__main__':
    unittest.main()
