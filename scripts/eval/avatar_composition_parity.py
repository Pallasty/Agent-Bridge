#!/usr/bin/env python3
"""Compare pre/post-extraction CLI bytes and fixture effects without live services.

Usage: avatar_composition_parity.py --baseline BIN --candidate BIN --output JSON
Both binaries run against the same reset, isolated filesystem and fake swaymsg.
Only fixture files may be written. No live desktop, provider or audio calls.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ['sprite-asset-audit', 'sprite-asset-compile', 'sprite-asset-contract',
            'focus-follow-plan', 'focus-follow-recommend', 'focus-follow-prompt',
            'focus-follow-action', 'focus-follow-observe', 'linux-live', 'voice-observe']
TREE = {'type': 'root', 'nodes': [{'type': 'output',
    'rect': {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}, 'nodes': [
    {'type': 'workspace', 'name': '1',
     'rect': {'x': 0, 'y': 0, 'width': 1920, 'height': 1040},
     'nodes': [{'id': 41, 'type': 'con', 'app_id': 'example.editor', 'focused': True,
                'rect': {'x': 100, 'y': 80, 'width': 1200, 'height': 800}}],
     'floating_nodes': [{'id': 99, 'type': 'floating_con', 'app_id': 'agent-bridge-avatar',
                         'rect': {'x': 1700, 'y': 850, 'width': 90, 'height': 130}}]}]}]}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def setup(root, tree_mode):
    for p in root.iterdir():
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    for name in ['runtime', 'home', 'data', 'bin', 'assets']:
        (root / name).mkdir(mode=0o700)
    pets = root / 'data/agent-bridge/pet_state'
    pets.mkdir(parents=True)
    (pets / 'fixture.json').write_text(json.dumps({'schema_version': 1,
        'pet_id': 'fixture', 'mode': 'working', 'activity_state': 'verifying'}))
    (root / 'invalid.png').write_text('not a PNG')
    (root / 'tree.json').write_text(json.dumps(TREE if tree_mode == 'planned' else {}))
    (root / 'bin/swaymsg').write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$FIXTURE_ROOT/sway-calls"
if [ "$*" != '-t get_tree -r' ]; then exit 91; fi
case "$FIXTURE_TREE_MODE" in
  failed) echo fixture-sway-failure >&2; exit 2;;
  malformed) echo not-json;;
  *) cat "$FIXTURE_ROOT/tree.json";;
esac
''')
    (root / 'bin/swaymsg').chmod(0o700)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AB_', 'AGENT_BRIDGE_', 'QWEN', 'XDG_', 'WAYLAND', 'SWAY', 'HYPRLAND'))}
    env.update(HOME=str(root / 'home'), XDG_RUNTIME_DIR=str(root / 'runtime'),
               XDG_DATA_HOME=str(root / 'data'), XDG_CONFIG_HOME=str(root / 'home'),
               AGENT_BRIDGE_STATE_DIR=str(root / 'data/agent-bridge'),
               PATH=str(root / 'bin') + ':/usr/bin:/bin',
               FIXTURE_ROOT=str(root), FIXTURE_TREE_MODE=tree_mode,
               XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='sway',
               SWAYSOCK=str(root / 'runtime/fake.sock'), WAYLAND_DISPLAY='wayland-fixture',
               NO_COLOR='1', RUST_LOG='off')
    return env


def snapshot(root):
    return {str(p.relative_to(root)): digest(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def cases(root):
    yield 'root-help', ['--help'], 'planned'
    yield 'avatar-help', ['avatar', '--help'], 'planned'
    for cmd in COMMANDS:
        yield cmd + '-help', ['avatar', cmd, '--help'], 'planned'
    for cmd in ['focus-follow-plan', 'focus-follow-recommend', 'focus-follow-prompt',
                'focus-follow-action', 'focus-follow-observe']:
        for mode in ['planned', 'empty', 'malformed', 'failed']:
            for fmt in [[], ['--json']]:
                yield cmd + '-' + mode + ('-json' if fmt else '-text'), ['avatar', cmd] + fmt, mode
    atlas = ROOT / 'crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-atlas.png'
    for fmt in [[], ['--json']]:
        suffix = '-json' if fmt else '-text'
        for name, args in [
            ('asset-audit', ['sprite-asset-audit', '--path', str(atlas)]),
            ('asset-audit-rejected', ['sprite-asset-audit', '--path', str(atlas), '--cell-width', '1']),
            ('asset-audit-malformed', ['sprite-asset-audit', '--path', str(root / 'invalid.png')]),
            ('asset-audit-missing', ['sprite-asset-audit', '--path', str(root / 'missing.png')]),
            ('asset-contract-missing', ['sprite-asset-contract', '--asset-root', str(root / 'assets')]),
            ('asset-contract', ['sprite-asset-contract', '--asset-root', str(atlas.parent)]),
            ('asset-compile-preview', ['sprite-asset-compile', '--input', str(atlas), '--output', str(root / 'out.png')]),
            ('asset-compile-write', ['sprite-asset-compile', '--input', str(atlas), '--output', str(root / 'out.png'), '--execute', '--confirm']),
            ('asset-compile-unconfirmed', ['sprite-asset-compile', '--input', str(root / 'missing.png'), '--output', str(root / 'out.png'), '--execute']),
            ('asset-compile-missing', ['sprite-asset-compile', '--input', str(root / 'missing.png'), '--output', str(root / 'out.png')]),
        ]:
            yield name + suffix, ['avatar'] + args + fmt, 'planned'
        for cmd in ['linux-live', 'voice-observe']:
            for pet in ['fixture', 'missing']:
                yield cmd + '-' + pet + suffix, ['avatar', cmd, '--pet-id', pet,
                    '--duration-ms', '1', '--state-poll-ms', '1', '--dry-run'] + fmt, 'planned'
    yield 'action-confirm-without-execute', ['avatar', 'focus-follow-action', '--confirm'], 'planned'
    yield 'prompt-confirm-without-show', ['avatar', 'focus-follow-prompt', '--confirm'], 'planned'


def compare(baseline, candidate):
    records = []
    with tempfile.TemporaryDirectory(prefix='avatar-parity-') as temp:
        root = Path(temp)
        for name, args, mode in cases(root):
            outputs = []
            for binary in [baseline, candidate]:
                env = setup(root, mode)
                before = snapshot(root)
                run = subprocess.run(["agent-bridge", *args], executable=binary, cwd=ROOT, env=env,
                                     capture_output=True, timeout=20)
                after = snapshot(root)
                effects = {p: after.get(p) for p in before.keys() | after.keys()
                           if before.get(p) != after.get(p)}
                outputs.append((run.returncode, run.stdout, run.stderr, effects))
            same = outputs[0] == outputs[1]
            records.append({'case': name, 'equal': same, 'exit_code': outputs[0][0],
                            'stdout_sha256': digest(outputs[0][1]),
                            'stderr_sha256': digest(outputs[0][2]),
                            'effects': outputs[0][3]})
            if not same:
                print(name, 'DIFF: exit/stdout/stderr/effects equality',
                      [a == b for a, b in zip(outputs[0], outputs[1])])
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = compare(str(Path(args.baseline).resolve()), str(Path(args.candidate).resolve()))
    report = {'baseline_sha256': digest(Path(args.baseline).read_bytes()),
              'candidate_sha256': digest(Path(args.candidate).read_bytes()), 'cases': records,
              'passed': sum(r['equal'] for r in records), 'total': len(records)}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"{report['passed']}/{report['total']} exact CLI/effect parity cases passed")
    return 0 if report['passed'] == report['total'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
