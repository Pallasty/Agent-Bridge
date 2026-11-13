import os,json,subprocess,tempfile,hashlib,argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--output-dir',type=Path,required=True)
out=parser.parse_args().output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
root=Path(tempfile.mkdtemp(prefix='env-paths-',dir=out))
repo=Path(__file__).resolve().parents[2];hooks=repo/'crates/bridge/src/hooks'
home=root/'home';envfile=home/'.config/agent-bridge/machine.env';envfile.parent.mkdir(parents=True)
state=root/'private-data';log=root/'private-observer/log.jsonl'
envfile.write_text('export XDG_DATA_HOME="${XDG_DATA_HOME:-'+str(state)+'}"\nexport AGENT_BRIDGE_DB="${AGENT_BRIDGE_DB:-'+str(root/'missing.db')+'}"\nexport AB_INSTINCT_OBSERVER_LOG="${AB_INSTINCT_OBSERVER_LOG:-'+str(log)+'}"\nprintf "do-not-leak-config-output\\n"\n')
env={'HOME':str(home),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','AB_PET_STATE_DISABLE':'1'}
results=[]
for script,event in [('ab-memory-hook.sh','beforeSubmitPrompt'),('ab-precompact-hook.sh','preCompact'),('ab-session-end-hook.sh','stop')]:
 p=subprocess.run(['bash',str(hooks/script)],input='{}',text=True,capture_output=True,env=env,timeout=5)
 assert p.returncode==0 and 'do-not-leak' not in p.stdout and not p.stderr,(script,p)
 rows=[json.loads(l) for l in (state/'agent-bridge/hook-runs.jsonl').read_text().splitlines()]
 assert rows[-1]['event']==event
 results.append({'case':'machine_env_'+event,'status':'PASS'})
for script,event in [('ab-memory-hook.sh','beforeSubmitPrompt'),('ab-precompact-hook.sh','preCompact'),('ab-session-end-hook.sh','stop')]:
 override=root/('override-'+event)
 p=subprocess.run(['bash',str(hooks/script)],input='{}',text=True,capture_output=True,env={**env,'XDG_DATA_HOME':str(override)},timeout=5)
 assert (override/'agent-bridge/hook-runs.jsonl').exists()
 results.append({'case':'explicit_env_'+event,'status':'PASS'})
payload=json.dumps({'hook_event_name':'UserPromptSubmit','session_id':'synthetic-only','prompt':'fixture'})
for case,extra in [('configured',{}),('override',{'AB_INSTINCT_OBSERVER_LOG':str(root/'override-observer/log.jsonl')})]:
 p=subprocess.run(['python3',str(hooks/'ab-instinct-observer-hook.py')],input=payload,text=True,capture_output=True,env={**env,**extra},timeout=5)
 target=Path(extra.get('AB_INSTINCT_OBSERVER_LOG',str(log)))
 assert target.exists() and p.returncode==0 and not p.stdout and not p.stderr
 results.append({'case':'observer_'+case,'status':'PASS'})
log.write_bytes(b'X'*(8*1024*1024));before=hashlib.sha256(log.read_bytes()).hexdigest()
p=subprocess.run(['python3',str(hooks/'ab-instinct-observer-hook.py')],input=payload,text=True,capture_output=True,env=env,timeout=5)
assert hashlib.sha256(log.read_bytes()).hexdigest()==before and p.returncode==0
results.append({'case':'observer_cap_preserved','status':'PASS'})
envfile.write_text('return 1\n')
new=root/'failure/log.jsonl'
p=subprocess.run(['python3',str(hooks/'ab-instinct-observer-hook.py')],input=payload,text=True,capture_output=True,env={**env,'AB_INSTINCT_OBSERVER_LOG':str(new)},timeout=5)
assert p.returncode==0 and not p.stdout and not new.exists()
results.append({'case':'observer_config_failure_no_collection','status':'PASS'})
# Installer round trip preserves preexisting scripts and never writes configs/DB.
inst=repo/'scripts/install-hook-scripts.py';bindir=root/'bin';bindir.mkdir()
old=bindir/'ab-memory-hook';old.write_text('old-fixture\n');old.chmod(0o700);original_mode=old.stat().st_mode&0o777
backup=root/'install-backup'
subprocess.run(['python3',str(inst),'--bin-dir',str(bindir),'--install','--backup-dir',str(backup)],check=True,capture_output=True)
check=json.loads(subprocess.check_output(['python3',str(inst),'--bin-dir',str(bindir),'--check']))
assert check['in_sync']
subprocess.run(['python3',str(inst),'--rollback',str(backup/'manifest.json')],check=True,capture_output=True)
assert old.read_text()=='old-fixture\n' and old.stat().st_mode&0o777==original_mode and len(list(bindir.iterdir()))==1
results.append({'case':'installer_roundtrip','status':'PASS'})
(out/'path-tests.json').write_text(json.dumps({'status':'PASS','cases':len(results),'results':results},indent=2)+'\n')
print('PASS',len(results),'path and rollback cases')
