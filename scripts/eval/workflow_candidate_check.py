#!/usr/bin/env python3
"""Read-only checks of scripts/ references and Python helpers in a local skill.

No candidate is executed, imported, installed or approved. This is not AB's
security lint or a universal Markdown/shell/skill-loader validator.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import json

from workflow_experience_contrast import read_bytes, require

TOKEN = re.compile(r'(?<![\w/])(?:\.\./|\./)?scripts/[^\s`\'"<>()]+')
LITERAL = re.compile(r'(?:\.\./|\./)?scripts/[A-Za-z0-9_./-]+\.(?:py|sh|js|ts)')
MAX_FILES = 256


def check(skill, root, required_scripts=()):
    root = Path(root).resolve()
    skill = Path(skill).absolute()
    require(root.is_dir(), 'candidate root must exist')
    require(skill.resolve().is_relative_to(root), 'skill is outside candidate root')
    require(skill.is_file() and not skill.is_symlink(), 'skill must be a regular non-symlink file')
    files, issues = {}, []

    def issue(code, path, detail, severity='error'):
        issues.append({'code': code, 'path': str(path), 'detail': detail, 'severity': severity})

    def load(path):
        path = Path(path).absolute()
        resolved = path.resolve()
        require(resolved.is_relative_to(root), 'reference is outside candidate root')
        relative = path.relative_to(root)
        current = root
        for part in relative.parts:
            current = current / part
            require(not current.is_symlink(), 'symlink references are not checked')
        if not path.is_file():
            raise FileNotFoundError('referenced file is missing')
        key = str(relative)
        if key not in files:
            require(len(files) < MAX_FILES, 'candidate exceeds 256 file limit')
            data = read_bytes(path)
            files[key] = {'path': key, 'sha256': hashlib.sha256(data).hexdigest(),
                          'bytes': len(data), 'python_compiled': False}
            return key, data
        return key, None

    key, data = load(skill)
    try:
        text = data.decode('utf-8')
    except UnicodeError as exc:
        raise ValueError('skill must be UTF-8') from exc
    references = sorted({m.group(0).rstrip('.,;:') for m in TOKEN.finditer(text)})
    if not references:
        issue('no_recognized_references', key, 'No scripts/ references recognized; inspect other dependencies.', 'review')
    paths = set()
    require(len(required_scripts) <= MAX_FILES, 'too many required scripts')
    require(all(isinstance(ref, str) and LITERAL.fullmatch(ref) for ref in required_scripts),
            'required scripts must be literal scripts/ paths')
    required_paths = {skill.parent / ref for ref in required_scripts}
    paths.update(required_paths)
    for ref in references:
        if not LITERAL.fullmatch(ref):
            issue('dynamic_or_unsupported_reference', key, ref, 'review')
        else:
            paths.add(skill.parent / ref)
    directory = skill.parent / 'scripts'
    if directory.is_symlink():
        issue('symlink', 'scripts', 'Script directory must not be a symlink')
    elif directory.exists() and not directory.is_dir():
        issue('script_directory', 'scripts', 'Expected a directory')
    elif directory.is_dir():
        visited = 0
        for base, dirs, names in os.walk(directory, followlinks=False):
            visited += 1 + len(dirs) + len(names)
            require(visited <= MAX_FILES, 'candidate exceeds 256 entry scan limit')
            for name in list(dirs):
                path = Path(base) / name
                if path.is_symlink():
                    issue('symlink', path.relative_to(root), 'Directory symlink is not followed')
                    dirs.remove(name)
            for name in names:
                path = Path(base) / name
                if path.is_symlink():
                    issue('symlink', path.relative_to(root), 'File symlink is not followed')
                elif path.suffix == '.py':
                    paths.add(path)
    for path in sorted(paths):
        try:
            key, data = load(path)
            if data is None:
                continue
            if path.suffix == '.py':
                # compile(bytes) respects coding cookies without importing or writing pyc.
                compile(data, key, 'exec', dont_inherit=True)
                files[key]['python_compiled'] = True
            else:
                issue('unchecked_language', key, 'Existence checked; syntax/runtime not checked.', 'review')
        except SyntaxError as exc:
            issue('python_compile', str(path.relative_to(root)), f'{exc.msg} at line {exc.lineno}')
        except FileNotFoundError as exc:
            issue('missing_reference', str(path), str(exc),
                  'error' if path in required_paths else 'review')
        except (ValueError, OSError) as exc:
            issue('file_check', str(path), str(exc))
    status = 'FAIL' if any(i['severity'] == 'error' for i in issues) else 'NEEDS_REVIEW' if issues else 'PASS_SCOPED'
    return {'schema': 'agent_bridge.workflow_candidate_check.v1', 'status': status,
            'files': [files[k] for k in sorted(files)], 'references': references,
            'required_scripts': sorted(set(required_scripts)), 'issues': issues,
            'python_version': sys.version.split()[0], 'read_only': True,
            'executes_candidate': False, 'runtime_verified': False,
            'limits': ['Only literal scripts/ references with py/sh/js/ts suffixes are recognized.',
                       'Python helpers under the skill scripts/ directory are compiled, never run.',
                       'Other references, imports, dependencies, frontmatter and loader behavior are not validated.',
                       'No safety, useful effect, activation or deployment approval is established.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', required=True, type=Path)
    parser.add_argument('--root', type=Path, help='allowed file root; defaults to skill parent')
    parser.add_argument('--required-script', action='append', default=[],
                        help='literal script path relative to skill; repeat for required dependencies')
    args = parser.parse_args()
    try:
        result = check(args.skill, args.root or args.skill.absolute().parent, args.required_script)
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'INVALID_INPUT', 'error': str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS_SCOPED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
