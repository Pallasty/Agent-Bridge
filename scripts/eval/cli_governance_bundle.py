#!/usr/bin/env python3
"""Read-only verification of a portable CLI run against a caller-selected commit."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import cli_governance_live as live


def file(directory, name):
    path = directory / name
    live.require(path.is_file() and not path.is_symlink(), f'missing regular bundle file: {name}')
    return path


def sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def verify_bundle(directory, candidate_tree, stages):
    """No commands, paths or expected scope are accepted from the report."""
    summary = json.loads(file(directory, 'summary.json').read_text())
    live.require(isinstance(summary, dict) and
                 summary.get('schema') == 'agent_bridge.cli_governance_live_run.v1', 'wrong run schema')
    live.require(summary.get('success') is True, 'run did not succeed')
    live.require(summary.get('baseline_commit') == live.BASELINE, 'wrong pinned baseline')
    live.require(summary.get('candidate_tree') == candidate_tree, 'candidate commit/tree mismatch')
    suites = live.selected_suites(stages)
    live.require(suites and summary.get('enrolled_suites') == suites
                 and isinstance(summary.get('suites'), dict)
                 and set(summary['suites']) == set(suites), 'bundle scope mismatch')
    start, end = summary.get('started_at_unix'), summary.get('finished_at_unix')
    live.require(all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in (start, end))
                 and end >= start, 'invalid run timestamps')
    live.require(sha(summary.get('baseline_archive_sha256')), 'invalid baseline archive digest')
    for name, identity in [('baseline', live.BASELINE), ('candidate', 'tree-' + candidate_tree)]:
        build = summary.get(name)
        live.require(isinstance(build, dict) and sha(build.get('sha256'))
                     and build.get('build_identity') == identity, f'invalid {name} build identity')
        live.require(live.digest(file(directory, name + '-build.log')) == build.get('build_log_sha256'),
                     f'{name} build log digest mismatch')
    for suite in suites:
        entry = summary['suites'][suite]
        live.require(isinstance(entry, dict) and type(entry.get('passed')) is int
                     and entry['passed'] == live.SUITES[suite][1] and sha(entry.get('harness_sha256')),
                     f'{suite}: invalid summary counters/harness digest')
        path = file(directory, suite + '.json')
        live.require(live.digest(path) == entry.get('report_sha256'), f'{suite}: report digest mismatch')
        live.verify_report(json.loads(path.read_text()), suite, summary['baseline']['sha256'],
                           summary['candidate']['sha256'], entry['harness_sha256'])
    return sum(live.SUITES[suite][1] for suite in suites)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--candidate-commit', required=True,
                        help='independently selected Git commit whose tree was tested')
    parser.add_argument('--stages', nargs='+', choices=sorted(live.STAGES), default=sorted(live.STAGES))
    args = parser.parse_args()
    try:
        # Resolve in this checkout without inheriting another hook/fixture Git context.
        commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options',
                                          args.candidate_commit + '^{commit}'], cwd=live.g.ROOT,
                                         env=live.clean_env(live.os.environ), text=True).strip()
        tree = subprocess.check_output(['git', 'rev-parse', commit + '^{tree}'], cwd=live.g.ROOT,
                                       env=live.clean_env(live.os.environ), text=True).strip()
        count = verify_bundle(args.run_dir, tree, args.stages)
        # Bind harness digests to the requested commit, not only to each other.
        summary = json.loads(file(args.run_dir, 'summary.json').read_text())
        for suite in live.selected_suites(args.stages):
            source = subprocess.check_output(['git', 'show', commit + ':scripts/eval/' + live.SUITES[suite][0] + '.py'],
                                             cwd=live.g.ROOT, env=live.clean_env(live.os.environ))
            live.require(live.hashlib.sha256(source).hexdigest() == summary['suites'][suite]['harness_sha256'],
                         f'{suite}: harness differs from candidate commit')
        print(f'PASS: portable evidence for {commit}; {count} CLI cases (no execution)')
        return 0
    except (live.g.GovernanceError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
