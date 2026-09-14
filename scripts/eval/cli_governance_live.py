#!/usr/bin/env python3
"""Fresh isolated CLI parity for the four enrolled maintenance profiles.

No installed binary, existing baseline executable, Git worktree mutation or
command supplied by a report is used. The baseline is an archived Git commit.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import cli_composition_root_governance as g

BASELINE = '4287aee34b2286ffe38c08316f1b52f1d755bc75'
SUITES = {
    'instinct': ('instinct_cli_parity', 79, 'agent_bridge.instinct_cli_parity.v1',
                 ('binaries_unchanged_during_comparison', 'script_unchanged_during_comparison')),
    'worktree': ('worktree_session_cli_parity', 34, 'agent_bridge.worktree_session_cli_parity.v1',
                 ('inputs_unchanged_during_comparison',)),
    'identity': ('dream_identity_cli_parity', 30, 'agent_bridge.dream_identity_cli_parity.v1',
                 ('inputs_unchanged_during_run',)),
}
STAGES = {'s18': 'instinct', 's20': 'instinct', 's19': 'worktree', 's21': 'identity'}


def require(condition, message):
    if not condition:
        raise g.GovernanceError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def selected_suites(stages):
    return sorted({STAGES[stage] for stage in stages})


def clean_env(env):
    return {key: value for key, value in env.items() if not key.startswith('GIT_')}


def extract_baseline(destination, env):
    resolved = subprocess.check_output(['git', 'rev-parse', BASELINE + '^{commit}'],
                                       cwd=g.ROOT, env=env, text=True).strip()
    require(resolved == BASELINE, 'pinned CLI baseline commit unavailable')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'],
                              cwd=g.ROOT, env=env, check=False)
    require(ancestor.returncode == 0, 'CLI baseline must be an ancestor of checked-out HEAD')
    archive = destination.parent / 'baseline.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar', BASELINE], cwd=g.ROOT,
                       env=env, stdout=stream, check=True)
    with tarfile.open(archive) as bundle:
        # Reject traversal/out-of-tree links in the exported source.
        bundle.extractall(destination, filter='data')
    sha = digest(archive)
    archive.unlink()
    return sha


def build(source, target, output, env, identity, log):
    settings = dict(env, CARGO_TARGET_DIR=str(target),
                    AGENT_BRIDGE_BUILD_SHA=identity, AGENT_BRIDGE_BUILD_DESCRIBE=identity)
    # The export intentionally has no .git; don't discover an enclosing repo.
    settings['GIT_CEILING_DIRECTORIES'] = str(source.parent)
    command = ['cargo', 'build', '--locked', '-p', 'ab-bridge', '--bin', 'agent-bridge']
    with log.open('wb') as stream:
        subprocess.run(command, cwd=source, env=settings, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)
    executable = target / 'debug' / ('agent-bridge.exe' if os.name == 'nt' else 'agent-bridge')
    require(executable.is_file(), 'Cargo did not produce the candidate executable')
    shutil.copy2(executable, output)
    return {'sha256': digest(output), 'build_log_sha256': digest(log), 'build_identity': identity}


def verify_report(report, suite, baseline_hash, candidate_hash, script_hash):
    script, total, schema, stable = SUITES[suite]
    require(isinstance(report, dict) and report.get('schema') == schema, f'{suite}: wrong report schema')
    require(type(report.get('passed')) is int and type(report.get('total')) is int
            and report['passed'] == report['total'] == total, f'{suite}: incomplete CLI cases')
    require(report.get('baseline_sha256') == baseline_hash
            and report.get('candidate_sha256') == candidate_hash
            and report.get('script_sha256') == script_hash, f'{suite}: report input digest mismatch')
    require(all(report.get(field) is True for field in stable), f'{suite}: unstable comparison inputs')
    rows = report.get('cases')
    require(isinstance(rows, list) and len(rows) == total, f'{suite}: missing case evidence')
    key = 'passed' if suite == 'identity' else 'equal'
    require(all(isinstance(row, dict) and row.get(key) is True for row in rows), f'{suite}: failed case evidence')
    names = [row.get('case') for row in rows]
    require(all(isinstance(name, str) and name for name in names) and len(set(names)) == total,
            f'{suite}: duplicate or unnamed cases')
    if suite == 'identity':
        require(report.get('comparison_performed') is True, 'identity: baseline-only is not CLI parity')


def run_cli_suites(stages, target, env, candidate_tree):
    suites = selected_suites(stages)
    if not suites:
        return
    env = clean_env(env)
    output_root = target / 'governance-live'
    output_root.mkdir(parents=True, exist_ok=True)
    # Unique report directory: an old successful report cannot authorize this run.
    run_dir = Path(tempfile.mkdtemp(prefix='run-', dir=output_root))
    result = {'schema': 'agent_bridge.cli_governance_live_run.v1', 'success': False,
              'baseline_commit': BASELINE, 'candidate_tree': candidate_tree,
              'started_at_unix': time.time(), 'suites': {}, 'enrolled_suites': suites}
    print(f'CLI parity artifacts: {run_dir}', flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='sources-', dir=run_dir) as temporary:
            scratch = Path(temporary)
            source = scratch / 'baseline-source'
            source.mkdir()
            result['baseline_archive_sha256'] = extract_baseline(source, env)
            baseline, candidate = scratch / 'baseline-bin', scratch / 'candidate-bin'
            print('Building pinned CLI baseline...', flush=True)
            result['baseline'] = build(source, target, baseline, env, BASELINE,
                                       run_dir / 'baseline-build.log')
            print('Building staged CLI candidate...', flush=True)
            result['candidate'] = build(g.ROOT, target, candidate, env, 'tree-' + candidate_tree,
                                        run_dir / 'candidate-build.log')
            for suite in suites:
                script = g.ROOT / f'scripts/eval/{SUITES[suite][0]}.py'
                harness_hash = digest(script)
                report_path = run_dir / f'{suite}.json'
                subprocess.run([sys.executable, str(script), '--baseline', str(baseline),
                                '--candidate', str(candidate), '--output', str(report_path)],
                               cwd=g.ROOT, env=env, check=True)
                report = json.loads(report_path.read_text())
                verify_report(report, suite, result['baseline']['sha256'],
                              result['candidate']['sha256'], harness_hash)
                require(digest(script) == harness_hash, f'{suite}: harness changed during execution')
                require(digest(baseline) == result['baseline']['sha256']
                        and digest(candidate) == result['candidate']['sha256'],
                        f'{suite}: executable changed during execution')
                result['suites'][suite] = {'passed': SUITES[suite][1], 'report_sha256': digest(report_path),
                                           'harness_sha256': harness_hash}
        result['success'] = True
        print(f'PASS: {sum(SUITES[s][1] for s in suites)} fresh isolated CLI cases', flush=True)
    finally:
        result['finished_at_unix'] = time.time()
        (run_dir / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
