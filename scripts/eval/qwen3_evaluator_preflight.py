#!/usr/bin/env python3
"""Fail-closed preflight for the isolated Qwen3-TTS evaluator environment."""
import argparse
import json
import subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--python',required=True,type=Path); ap.add_argument('--output',required=True,type=Path); a=ap.parse_args()
    if not a.python.is_file():
        ap.error(f'python runtime does not exist: {a.python}')
    probe = subprocess.run(
        [str(a.python), '-c', 'from funasr import AutoModel; print("ok")'],
        text=True, capture_output=True, check=False,
    )
    installed = probe.returncode == 0 and probe.stdout.strip().endswith('ok')
    report={'schema':'agent_bridge.qwen3_tts.evaluator_preflight.v0','status':'READY_FOR_MODEL_PINNING' if installed else 'BLOCKED_FUNASR_AUTOMODEL_IMPORT','runtime_python':str(a.python),'funasr_automodel_importable':installed,'funasr_probe_stderr':probe.stderr.strip()[-1000:],'required_models':['iic/emotion2vec_plus_large','damo/speech_campplus_sv_zh-cn_16k-common'],'allows_candidate_generation':False,'allows_promotion':False}
    if a.output.exists(): ap.error('refusing to overwrite output')
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(report,ensure_ascii=False)); return 0
if __name__=='__main__': main()
