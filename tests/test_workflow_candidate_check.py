import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/eval'))
import workflow_candidate_check as candidate


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'scripts').mkdir()
        self.skill = self.root/'SKILL.md'
        self.skill.write_text('Run `python3 scripts/check.py`.\n')
        (self.root/'scripts/check.py').write_text('print("ok")\n')

    def check(self):
        return candidate.check(self.skill, self.root)

    def test_good_package_and_bound_bytes(self):
        r = self.check()
        self.assertEqual(r['status'], 'PASS_SCOPED')
        self.assertEqual(len(r['files']), 2)
        self.assertFalse(r['runtime_verified'])
        self.assertFalse(r['executes_candidate'])

    def test_missing_reference(self):
        (self.root/'scripts/check.py').unlink()
        self.assertEqual(self.check()['status'], 'NEEDS_REVIEW')
        self.assertEqual(candidate.check(self.skill, self.root,
                         required_scripts=['scripts/check.py'])['status'], 'FAIL')

    def test_documentation_example_is_not_a_required_dependency(self):
        self.skill.write_text('Example: `scripts/rotate_pdf.py` for another skill.\n')
        result = self.check()
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        self.assertEqual(result['issues'][0]['code'], 'missing_reference')

    def test_syntax_error_even_in_unreferenced_helper(self):
        (self.root/'scripts/unused.py').write_text('def broken(:\n')
        r = self.check()
        self.assertEqual(r['status'], 'FAIL')
        self.assertTrue(any(i['code']=='python_compile' for i in r['issues']))

    def test_never_executes_or_imports_python(self):
        sentinel = self.root/'EXECUTED'
        (self.root/'scripts/check.py').write_text(
            f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("bad")\nimport missing_dependency\n')
        self.assertEqual(self.check()['status'], 'PASS_SCOPED')
        self.assertFalse(sentinel.exists())
        self.assertFalse((self.root/'scripts/__pycache__').exists())

    def test_symlink_escape_rejected(self):
        outside = self.root.parent/'outside-candidate-check.py'
        (self.root/'scripts/check.py').unlink()
        (self.root/'scripts/check.py').symlink_to(outside)
        self.assertEqual(self.check()['status'], 'FAIL')

    def test_dynamic_reference_needs_review(self):
        self.skill.write_text('Run `python3 scripts/${TASK}.py`.\n')
        self.assertEqual(self.check()['status'], 'NEEDS_REVIEW')

    def test_other_language_not_claimed_verified(self):
        self.skill.write_text('Run `bash scripts/run.sh`.\n')
        (self.root/'scripts/run.sh').write_text('not necessarily valid shell\n')
        r=self.check()
        self.assertEqual(r['status'], 'NEEDS_REVIEW')
        self.assertTrue(any(i['code']=='unchecked_language' for i in r['issues']))

    def test_no_references_not_false_full_validation(self):
        self.skill.write_text('Instructions only.\n')
        r=self.check()
        self.assertEqual(r['status'], 'NEEDS_REVIEW')

    def test_missing_skill_and_escape(self):
        with self.assertRaises(ValueError): candidate.check(self.root/'absent.md',self.root)
        with self.assertRaises(ValueError): candidate.check(self.root.parent/'SKILL.md',self.root)

    def test_cli_exit_codes_and_read_only(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        cmd=[sys.executable,str(ROOT/'scripts/eval/workflow_candidate_check.py'),'--skill',str(self.skill),
             '--required-script','scripts/check.py']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'PASS_SCOPED')
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        (self.root/'scripts/check.py').unlink()
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,1)


if __name__=='__main__': unittest.main()
