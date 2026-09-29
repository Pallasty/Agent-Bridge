#!/usr/bin/env python3
"""Bind enrolled CLI evidence to Git blobs and run fixed, local regression suites."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import cli_composition_root_governance as g
from cli_governance_live import run_cli_suites

REGISTRY = 'docs/design/evidence/cli-governance-registry.json'
SCHEMA = 'agent_bridge.cli_governance_evidence_registry.v1'
SELF = 'scripts/eval/cli_governance_evidence.py'
GATE_INPUTS = {REGISTRY, SELF, '.githooks/pre-commit',
               'scripts/eval/dream_diff_plan_cli_check.py',
               'crates/bridge/tests/fixtures/dream_diff_cli_baseline.json',
               'scripts/eval/dream_weekly_snapshot_check.py',
               'scripts/eval/cli_governance_bundle.py', 'tests/test_cli_governance_bundle.py',
               'scripts/eval/cli_governance_live.py',
               'tests/test_cli_governance_live.py',
               'scripts/check-cli-composition-root-governance.sh',
               'scripts/eval/cli_composition_root_governance.py',
               'tests/test_cli_governance_evidence.py',
               'tests/test_cli_composition_root_governance.py'}
PROFILES = {
    's18': ('instinct_presentation', 'presentation_parity', 'cli_instinct_s18_extraction', 'instinct_cli_parity'),
    's19': ('worktree_session_view', 'view_parity', 'cli_worktree_session_s19_extraction', 'worktree_session_cli_parity'),
    's20': ('instinct_memory', 'record_parity', 'cli_instinct_s20_extraction', 'instinct_cli_parity'),
    's21': ('dream_identity_view', 'view_parity', 'cli_dream_identity_s21_extraction', 'dream_identity_cli_parity'),
}
PROBES = {k: ('instinct_memory_record' if k == 's20' else v[0]) + '_parity' for k, v in PROFILES.items()}


def require(value, message):
    if not value:
        raise g.GovernanceError(message)


def paths(revision):
    args = ('ls-files', '-z') if revision == 'INDEX' else ('ls-tree', '-rz', '--name-only', revision)
    return set(g.git(*args).split('\0')) - {''}


def regular_blob(revision, path):
    entry = g.git('ls-files', '--stage', '--', path) if revision == 'INDEX' else g.git('ls-tree', revision, '--', path)
    require(entry.split(' ', 1)[0] in ('100644', '100755'), f'bound path must be a regular Git file: {path}')
    return g.git_blob(revision, path)


def document(revision, path):
    try:
        return json.loads(regular_blob(revision, path))
    except (ValueError, UnicodeDecodeError) as error:
        raise g.GovernanceError(f'{path}: invalid JSON: {error}') from error


def safe_report(path):
    require(isinstance(path, str) and path.startswith('docs/reports/main-rs-governance/')
            and path.endswith('.json') and '..' not in PurePosixPath(path).parts,
            'report must be a repository-local governance JSON path')
    return path


def bindings(stage):
    module, section, test, cli = PROFILES[stage]
    result = {
        f'crates/bridge/src/cli/{module}.rs': (section, 'candidate_module_sha256'),
        f'scripts/eval/{PROBES[stage]}.py': (section, 'harness_sha256'),
        f'scripts/eval/{cli}.py': ('cli_parity', 'script_sha256'),
    }
    if stage in ('s20', 's21'):
        result['crates/store/src/lib.rs'] = (section, 'store_source_sha256')
    if stage == 's21':
        result['crates/bridge/src/cli/dream.rs'] = (section, 'candidate_dream_sha256')
        result['scripts/eval/cli_fixture_paths.py'] = ('cli_parity', 'path_helper_sha256')
    return result


def validate(base, head):
    available = paths(head)
    previous = paths(base)
    enrolled = {f'crates/bridge/src/cli/{v[0]}.rs' for v in PROFILES.values()}
    if REGISTRY not in available:
        require(REGISTRY not in previous and not (enrolled & (available | previous)),
                'governance evidence registry is required; removal cannot disable admission')
        return []  # Historical/minimal repositories with no enrolled source.
    registry = document(head, REGISTRY)
    require(isinstance(registry, dict) and registry.get('schema') == SCHEMA, 'invalid registry schema')
    entries = registry.get('stages')
    require(isinstance(entries, dict) and set(entries) == set(PROFILES),
            'registry must retain exactly the four enrolled stages s18–s21')
    touched = set(g.changed_paths(base, head))
    selected = set()
    for stage, entry in entries.items():
        require(isinstance(entry, dict), f'{stage}: invalid registry entry')
        report_path = safe_report(entry.get('report'))
        raw = regular_blob(head, report_path)
        require(entry.get('sha256') == g.sha256(raw), f'{stage}: report digest mismatch')
        report = document(head, report_path)
        require(isinstance(report, dict), f'{stage}: report must be an object')
        section = PROFILES[stage][1]
        for key in (section, 'cli_parity'):
            stats = report.get(key, {})
            require(isinstance(stats, dict) and type(stats.get('total')) is int and stats['total'] > 0
                    and type(stats.get('passed')) is int and stats['passed'] == stats['total'],
                    f'{stage}: {key} must have nonempty fully passed cases')
        require(report[section].get('success') is True, f'{stage}: probe report must record success')
        for file, (key, field) in bindings(stage).items():
            require(file in available, f'{stage}: bound file missing: {file}')
            require(report.get(key, {}).get(field) == g.sha256(regular_blob(head, file)),
                    f'{stage}: stale evidence for {file}')
        # Old main.rs hashes remain historical, never compared to current root.
        # Current root custody is covered by the separate transition gate.
        test = f'crates/bridge/tests/{PROFILES[stage][2]}.rs'
        require(test in available, f'{stage}: required boundary test missing')
        regular_blob(head, test)
        if touched & (set(bindings(stage)) | {report_path, test}):
            selected.add(stage)
    own_modules = {f'crates/bridge/src/cli/{v[0]}.rs' for v in PROFILES.values()}
    own_tests = {f'crates/bridge/tests/{v[2]}.rs' for v in PROFILES.values()}
    shared_rust = any((p.endswith('.rs') and p not in own_modules | own_tests)
                      or Path(p).name in ('Cargo.toml', 'Cargo.lock')
                      or p.startswith('.cargo/') for p in touched)
    if touched & GATE_INPUTS or shared_rust:
        selected.update(PROFILES)
    return sorted(selected)


def ensure_checkout(head):
    require(head == 'INDEX' or g.git('rev-parse', head) == g.git('rev-parse', 'HEAD'),
            'execution requires INDEX or the checked-out HEAD')
    if head != 'INDEX':
        require(not g.git('diff', '--cached', '--name-only'), 'execution requires index equal to HEAD')
    # diff/status honor these index hints and can hide changed tracked files.
    # Reject them before trusting the worktree comparison, including sparse
    # checkouts. NUL delimiters preserve paths containing whitespace/newlines.
    entries = g.git('ls-files', '-v', '-z').split('\0')
    hidden = [entry[2:] for entry in entries if entry and
              (entry[0].islower() or entry[0] == 'S')]
    require(not hidden, 'execution requires no assume-unchanged/skip-worktree flags; '
            f'inspect index entries: {hidden!r}')
    require(not g.git('diff', '--name-only'), 'execution requires tracked worktree equal to index')
    untracked = g.git('ls-files', '--others', '--exclude-standard').splitlines()
    require(not any(p.endswith(('.rs', '.py')) or Path(p).name in ('Cargo.toml', 'Cargo.lock')
                    or p.startswith('.cargo/') for p in untracked),
            'execution requires source/scripts staged; untracked inputs could affect tests')
    return g.git('write-tree')


def run_selected(stages, head, check_gate=False):
    if not stages:
        return
    initial = ensure_checkout(head)
    target = Path(os.environ.get('CARGO_TARGET_DIR', '/Data/ab-main-rs-governance-target')).resolve()
    # Project instructions prohibit Cargo on tmpfs, including symlinked targets.
    target.mkdir(parents=True, exist_ok=True)
    require(not target.is_relative_to(Path('/tmp')), 'Cargo target must be outside /tmp')
    if sys.platform.startswith('linux'):
        fs = subprocess.check_output(['stat', '-f', '-c', '%T', str(target)], text=True).strip()
        require(fs not in ('tmpfs', 'ramfs'), 'Cargo target must be on real disk')
    # Git hooks export repository/index variables. Never pass those to tests
    # creating fixture repositories, Cargo build scripts, or local Git probes.
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['CARGO_TARGET_DIR'] = str(target)
    env.setdefault('CARGO_BUILD_JOBS', '4')
    if check_gate:
        for test in ('test_cli_governance_evidence.py', 'test_cli_composition_root_governance.py', 'test_cli_governance_live.py', 'test_cli_governance_bundle.py'):
            subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', test],
                           cwd=g.ROOT, env=env, check=True)
        subprocess.run([sys.executable, 'scripts/eval/cli_composition_root_governance.py', 'self-test'],
                       cwd=g.ROOT, env=env, check=True)
    command = ['cargo', 'test', '-p', 'ab-bridge']
    for stage in stages:
        command += ['--test', PROFILES[stage][2]]
    # This real CLI regression covers the retained weekly/snapshot adapter.
    command += ['--test', 'cli_dream_weekly_snapshot', '--test', 'cli_civil_date', '--test', 'cli_dream_diff_plan']
    # These source-bound tests must not be mistaken for behavior probes.
    subprocess.run(command, cwd=g.ROOT, env=env, check=True)
    for stage in stages:
        command = [sys.executable, f'scripts/eval/{PROBES[stage]}.py',
                   '--deps-dir', str(target / 'debug/deps'),
                   '--output-dir', str(target / 'governance-evidence' / stage)]
        subprocess.run(command, cwd=g.ROOT, env=env, check=True)
    require(ensure_checkout(head) == initial, 'index changed before CLI execution')
    run_cli_suites(stages, target, env, initial)
    require(ensure_checkout(head) == initial, 'index changed during regression execution')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='HEAD')
    parser.add_argument('--head', default='INDEX')
    parser.add_argument('--run', action='store_true', help='run fixed boundary, pure behavior and fresh CLI suites')
    args = parser.parse_args()
    try:
        stages = validate(args.base, args.head)
        print(f'PASS: evidence bindings; selected suites: {", ".join(stages) or "none"}', flush=True)
        if args.run:
            run_selected(stages, args.head, bool(set(g.changed_paths(args.base, args.head)) & GATE_INPUTS))
            # Guard evidence as well as source against changes during execution.
            require(validate(args.base, args.head) == stages, 'selection changed during execution')
        return 0
    except (g.GovernanceError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
