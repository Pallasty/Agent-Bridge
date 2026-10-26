import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/eval'))
import workflow_artifact_compare as compare


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'review'
        def ref(name,text):
            data=text.encode();(self.root/name).write_bytes(data)
            return {'path':name,'sha256':hashlib.sha256(data).hexdigest()}
        self.spec={'task':ref('task.txt','Return the saved commitment.'),
                   'baseline':ref('baseline-secret.txt','First answer.'),
                   'candidates':[{'label':'new-secret','artifact':ref('candidate-secret.txt','Second answer.')}]}
        self.path=self.root/'spec.json';self.path.write_text(json.dumps(self.spec))

    def prepare(self):
        compare.prepare(self.path,self.out)
        return json.loads((self.out/'packet.json').read_text()),json.loads((self.out/'mapping.json').read_text())

    def decide(self,mapping,choice):
        return {'packet_sha256':mapping['packet_sha256'],'choice':choice,'rationale':'Fits the requested result.'}

    def test_packet_omits_provenance_preserves_exact_text(self):
        packet,mapping=self.prepare();public=json.dumps(packet)
        self.assertNotIn('secret',public);self.assertNotIn('baseline',public)
        self.assertEqual(set(packet),{'schema','task','candidates'})
        self.assertEqual({c['text'] for c in packet['candidates']},{'First answer.','Second answer.'})
        self.assertEqual(len(mapping['id_to_label']),2)
        self.assertEqual(self.out.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.out/'mapping.json').stat().st_mode & 0o777,0o600)

    def test_baseline_can_win_and_choice_is_not_task_acceptance(self):
        _,mapping=self.prepare()
        choice=next(k for k,v in mapping['id_to_label'].items() if v=='baseline')
        result=compare.resolve(self.out,self.decide(mapping,choice))
        self.assertEqual(result['selected_label'],'baseline')
        self.assertFalse(result['task_acceptance_verified'])
        self.assertFalse(result['runtime_influence_allowed'])

    def test_abstain(self):
        _,mapping=self.prepare()
        r=compare.resolve(self.out,self.decide(mapping,None))
        self.assertEqual(r['status'],'ABSTAINED');self.assertIsNone(r['selected_label'])

    def test_unknown_choice_or_stale_packet_binding_rejected(self):
        _,mapping=self.prepare()
        with self.assertRaises(ValueError):compare.resolve(self.out,self.decide(mapping,'Z'))
        d=self.decide(mapping,'A');d['packet_sha256']='0'*64
        with self.assertRaises(ValueError):compare.resolve(self.out,d)

    def test_changed_packet_or_source_rejected(self):
        _,mapping=self.prepare();d=self.decide(mapping,'A')
        (self.root/'candidate-secret.txt').write_text('Changed after review')
        with self.assertRaises(ValueError):compare.resolve(self.out,d)
        self.setUp();_,mapping=self.prepare();d=self.decide(mapping,'A')
        (self.out/'packet.json').write_text('{}')
        with self.assertRaises(ValueError):compare.resolve(self.out,d)

    def test_bad_mapping_bijection_rejected(self):
        _,mapping=self.prepare();mapping['id_to_label']['B']=mapping['id_to_label']['A']
        (self.out/'mapping.json').write_text(json.dumps(mapping))
        with self.assertRaises(ValueError):compare.resolve(self.out,self.decide(mapping,'A'))

    def test_swapped_mapping_cannot_relabel_distinct_answers(self):
        _,mapping=self.prepare()
        m=mapping['id_to_label'];m['A'],m['B']=m['B'],m['A']
        (self.out/'mapping.json').write_text(json.dumps(mapping))
        with self.assertRaises(ValueError):compare.resolve(self.out,self.decide(mapping,'A'))

    def test_spec_changes_invalidate_prior_packet(self):
        _,mapping=self.prepare()
        self.spec['candidates'][0]['label']='renamed-after-review'
        self.path.write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):compare.resolve(self.out,self.decide(mapping,'A'))

    def test_no_overwrite(self):
        self.prepare();before=(self.out/'packet.json').read_bytes()
        with self.assertRaises((ValueError,FileExistsError)):compare.prepare(self.path,self.out)
        self.assertEqual((self.out/'packet.json').read_bytes(),before)

    def test_invalid_specs_never_create_output(self):
        for change in [lambda s:s.update(candidates=[]),
                       lambda s:s.pop('baseline'),
                       lambda s:s['candidates'][0].update(label='baseline'),
                       lambda s:s['baseline'].update(path='../outside')]:
            s=json.loads(json.dumps(self.spec));change(s);self.path.write_text(json.dumps(s))
            with self.assertRaises(ValueError):compare.prepare(self.path,self.out)
            self.assertFalse(self.out.exists())

    def test_binary_or_empty_output_not_silently_removed(self):
        for data in [b'\xff',b'']:
            p=self.root/'baseline-secret.txt';p.write_bytes(data)
            self.spec['baseline']['sha256']=hashlib.sha256(data).hexdigest()
            self.path.write_text(json.dumps(self.spec))
            with self.assertRaises(ValueError):compare.prepare(self.path,self.out)
            self.assertFalse(self.out.exists())

    def test_cli_round_trip(self):
        cmd=[sys.executable,str(ROOT/'scripts/eval/workflow_artifact_compare.py')]
        r=subprocess.run(cmd+['prepare','--spec',str(self.path),'--output-dir',str(self.out)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotIn('new-secret',r.stdout)
        m=json.loads((self.out/'mapping.json').read_text())
        decision=self.root/'decision.json';decision.write_text(json.dumps(self.decide(m,'A')))
        r=subprocess.run(cmd+['resolve','--review-dir',str(self.out),'--decision',str(decision)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'],'SELECTED_FOR_REVIEW')


if __name__=='__main__':unittest.main()
