"""Real Git histories: admission must bind content, ancestry and staged state."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/eval/cli_composition_root_governance.py'
spec = importlib.util.spec_from_file_location('governance', SCRIPT)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class RepositoryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        old_root = g.ROOT
        self.addCleanup(setattr, g, 'ROOT', old_root)
        g.ROOT = self.root
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.write(g.MAIN_RS, 'fn main() {}\n')
        self.base = self.commit('base')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True).strip()

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, message):
        self.git('add', '.')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def change(self, source, text, name='change'):
        r = g.valid_synthetic_receipt()
        r.update(change_id=name, source_base=source,
                 main_rs_before_sha256=g.sha256(g.git_blob(source, g.MAIN_RS)),
                 main_rs_after_sha256=g.sha256(text.encode()))
        self.write(g.MAIN_RS, text)
        path = g.RECEIPT_PREFIX + name + '.json'
        self.write(path, json.dumps(r))
        return path

    def test_exact_transition(self):
        self.change(self.base, 'fn main() { one(); }\n')
        g.validate_repository(self.base, self.commit('one'))

    def test_comparison_base_can_advance_without_main_change(self):
        self.write('README.md', 'docs')
        compare = self.commit('docs')
        self.change(self.base, 'fn main() { one(); }\n')
        g.validate_repository(compare, self.commit('one'))

    def test_multiple_receipts_cover_push(self):
        self.change(self.base, 'fn main() { one(); }\n', 'one')
        one = self.commit('one')
        self.change(one, 'fn main() { two(); }\n', 'two')
        g.validate_repository(self.base, self.commit('two'))

    def test_missing_receipt_rejected(self):
        self.write(g.MAIN_RS, 'uncovered')
        with self.assertRaisesRegex(g.GovernanceError, 'found 0'):
            g.validate_repository(self.base, self.commit('uncovered'))

    def test_missing_intermediate_transition_rejected(self):
        self.write(g.MAIN_RS, 'uncovered')
        gap = self.commit('gap')
        self.change(gap, 'covered end', 'end')
        with self.assertRaisesRegex(g.GovernanceError, 'do not cover'):
            g.validate_repository(self.base, self.commit('end'))

    def test_stale_after_digest_rejected(self):
        self.change(self.base, 'reviewed')
        self.write(g.MAIN_RS, 'different')
        with self.assertRaisesRegex(g.GovernanceError, 'do not cover'):
            g.validate_repository(self.base, self.commit('different'))

    def test_wrong_before_digest_rejected(self):
        path = self.change(self.base, 'new')
        r = json.loads((self.root / path).read_text())
        r['main_rs_before_sha256'] = '0' * 64
        self.write(path, json.dumps(r))
        with self.assertRaisesRegex(g.GovernanceError, 'does not bind the base'):
            g.validate_repository(self.base, self.commit('wrong before'))

    def test_nonancestor_receipt_rejected(self):
        self.write('other', 'sibling')
        sibling = self.commit('sibling')
        self.git('checkout', '-qb', 'candidate', self.base)
        self.change(sibling, 'new')
        with self.assertRaisesRegex(g.GovernanceError, 'ancestor'):
            g.validate_repository(self.base, self.commit('new'))

    def test_staged_file_cannot_borrow_unstaged_receipt(self):
        self.change(self.base, 'new')
        self.git('add', g.MAIN_RS)
        with self.assertRaisesRegex(g.GovernanceError, 'found 0'):
            g.validate_repository('HEAD', 'INDEX')

    def test_staged_validation_ignores_unstaged_file(self):
        self.change(self.base, 'reviewed')
        self.git('add', '.')
        self.write(g.MAIN_RS, 'unstaged')
        g.validate_repository('HEAD', 'INDEX')

    def test_dangling_receipt_rejected(self):
        self.change(self.base, 'fabricated', 'dangling')
        self.change(self.base, 'actual', 'actual')
        with self.assertRaisesRegex(g.GovernanceError, 'unrelated or incomplete'):
            g.validate_repository(self.base, self.commit('dangling'))

    def test_receipt_only_corruption_is_checked(self):
        path = self.change(self.base, 'new')
        prior = self.commit('new')
        self.write(path, '{}')
        with self.assertRaises(g.GovernanceError):
            g.validate_repository(prior, self.commit('corrupt receipt'))

    def test_short_source_sha_is_not_a_canonical_receipt(self):
        path = self.change(self.base, 'new')
        r = json.loads((self.root / path).read_text())
        r['source_base'] = self.base[:12]
        self.write(path, json.dumps(r))
        with self.assertRaisesRegex(g.GovernanceError, 'resolved governance base'):
            g.validate_repository(self.base, self.commit('short source'))

    def test_unclassified_change_remains_rejected_in_repository_mode(self):
        path = self.change(self.base, 'new')
        r = json.loads((self.root / path).read_text())
        r['changes'][0]['category'] = 'pure_logic'
        self.write(path, json.dumps(r))
        with self.assertRaisesRegex(g.GovernanceError, 'pure logic cannot remain'):
            g.validate_repository(self.base, self.commit('pure in root'))

    def test_retrospective_chain_can_prepend_current_transition(self):
        self.write(g.MAIN_RS, 'historically uncovered')
        current = self.commit('historical gap')
        self.change(self.base, 'historically uncovered', 'retrospective')
        self.change(current, 'current reviewed', 'current')
        head = self.commit('audit and current change')
        g.validate_repository(current, head)
        g.validate_repository(self.base, head)

    def test_retrospective_receipt_alone_cannot_authorize_current_change(self):
        self.write(g.MAIN_RS, 'historically uncovered')
        current = self.commit('historical gap')
        self.change(self.base, 'historically uncovered', 'retrospective')
        self.write(g.MAIN_RS, 'new uncovered')
        with self.assertRaisesRegex(g.GovernanceError, 'do not cover'):
            g.validate_repository(current, self.commit('uncovered with historical receipt'))

    def test_receipt_only_retrospective_audit_binds_current_file(self):
        self.write(g.MAIN_RS, 'historically uncovered')
        current = self.commit('historical gap')
        self.change(self.base, 'historically uncovered', 'retrospective')
        g.validate_repository(current, self.commit('audit only'))

    def test_retrospective_dangling_output_remains_rejected(self):
        self.write(g.MAIN_RS, 'historically uncovered')
        current = self.commit('historical gap')
        self.change(self.base, 'fabricated', 'retrospective')
        self.change(current, 'current reviewed', 'current')
        with self.assertRaisesRegex(g.GovernanceError, 'unrelated or incomplete'):
            g.validate_repository(current, self.commit('dangling audit'))

    def install_hook_fixture(self):
        script = self.root / 'scripts/eval/cli_composition_root_governance.py'
        script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, script)
        hook = self.root / '.githooks/pre-commit'
        hook.parent.mkdir()
        shutil.copyfile(SCRIPT.parents[2] / '.githooks/pre-commit', hook)
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', '.githooks')
        fake = self.root / 'bin/cargo'
        fake.parent.mkdir()
        fake.write_text('#!/bin/sh\necho called >> cargo-calls\n')
        fake.chmod(0o755)
        return {**os.environ, 'PATH': str(fake.parent) + os.pathsep + os.environ['PATH']}

    def test_actual_precommit_blocks_before_cargo_without_receipt(self):
        env = self.install_hook_fixture()
        self.write(g.MAIN_RS, 'unreviewed')
        self.git('add', g.MAIN_RS)
        result = subprocess.run(['git', 'commit', '-qm', 'must fail'], cwd=self.root,
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('found 0', result.stderr)
        self.assertFalse((self.root / 'cargo-calls').exists())
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.base)

    def test_actual_precommit_allows_bound_staged_change_then_checks_rust(self):
        env = self.install_hook_fixture()
        self.change(self.base, 'reviewed')
        self.git('add', g.MAIN_RS, g.RECEIPT_PREFIX)
        result = subprocess.run(['git', 'commit', '-qm', 'reviewed'], cwd=self.root,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'cargo-calls').read_text(), 'called\n')


if __name__ == '__main__':
    unittest.main()
