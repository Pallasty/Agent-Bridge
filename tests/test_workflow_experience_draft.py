import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/eval'))
import workflow_experience_contrast as contrast


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.root=ROOT/'scripts/eval/fixtures/workflow_experience_contrast'
        self.exp=json.loads((self.root/'experience.json').read_text())
        self.lesson={'cue':'When retrieving a project-specific commitment',
                     'lesson':'Keep the explicitly named project in the query.',
                     'counterexample':'Do not invent a project name when the request omits one.',
                     'unknowns':['Synthetic fixture; transfer to natural tasks untested.']}

    def draft(self):
        return contrast.propose_draft(self.exp,self.root,self.lesson)

    def test_evidence_bound_proposal_and_replay(self):
        out=self.draft();draft=out['draft']
        self.assertEqual(out['decision'],'DRAFT_PROPOSED')
        self.assertEqual(draft['schema'],'agent_bridge.experience.v0')
        self.assertEqual(draft['outcome']['status'],'proposed')
        self.assertEqual(draft['reflection']['claim_status'],'caller_proposed')
        self.assertEqual(draft['reflection']['falsifier'],self.lesson['counterexample'])
        self.assertEqual(draft['outcome']['cost'],out['review']['cost'])
        self.assertEqual(contrast.review(draft,self.root)['verdict'],'helped')
        self.assertEqual(draft['source_anchors']['evidence_root'],str(self.root.resolve()))

    def test_old_success_and_authority_are_not_inherited(self):
        self.exp.update(outcome={'status':'success','task_acceptance_verified':True},
                        promotion={'runtime_influence_allowed':True},
                        safety={'fixture_writes_memory':True})
        before=copy.deepcopy(self.exp)
        d=self.draft()['draft']
        self.assertFalse(d['outcome']['task_acceptance_verified'])
        self.assertFalse(d['promotion']['runtime_influence_allowed'])
        self.assertTrue(d['promotion']['owner_gate_required'])
        self.assertTrue(all(v is False for v in d['safety'].values()))
        self.assertEqual(self.exp,before)

    def test_no_evidence_no_draft(self):
        self.exp.pop('execution_contrast')
        r=self.draft()
        self.assertEqual(r['decision'],'NO_ENTRY');self.assertIsNone(r['draft'])

    def test_single_pair_stays_confounded(self):
        self.exp['execution_contrast']['pairs'].pop()
        self.assertIsNone(self.draft()['draft'])

    def test_negative_evidence_can_propose_a_caution(self):
        self.exp['execution_contrast']['metrics'][0]['direction']='lower'
        r=self.draft()
        self.assertEqual(r['review']['verdict'],'hurt')
        self.assertEqual(r['draft']['outcome']['observed_verdict'],'hurt')

    def test_missing_context_and_unknowns_rejected(self):
        for key in self.lesson:
            saved=self.lesson[key];self.lesson[key]=[] if key=='unknowns' else ''
            with self.assertRaises(ValueError):self.draft()
            self.lesson[key]=saved

    def test_draft_does_not_alias_input(self):
        d=self.draft()['draft'];d['execution_contrast']['pairs'].clear()
        self.assertEqual(len(self.exp['execution_contrast']['pairs']),2)

    def test_cli_is_opt_in_and_legacy_shape_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            lesson=Path(tmp)/'lesson.json';lesson.write_text(json.dumps(self.lesson))
            cmd=[sys.executable,str(ROOT/'scripts/eval/workflow_experience_contrast.py'),
                 '--experience',str(self.root/'experience.json')]
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(r.returncode,0);self.assertNotIn('draft',json.loads(r.stdout))
            r=subprocess.run(cmd+['--lesson',str(lesson)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['decision'],'DRAFT_PROPOSED')


if __name__=='__main__':unittest.main()
