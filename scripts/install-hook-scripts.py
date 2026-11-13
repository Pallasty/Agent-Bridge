#!/usr/bin/env python3
"""Install only hook scripts from this checkout, with a hash-bound rollback.
Does not run setup, change client trust/configuration, or touch databases.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

SOURCES = {
    'ab-memory-hook': 'ab-memory-hook.sh',
    'ab-precompact-hook': 'ab-precompact-hook.sh',
    'ab-session-end-hook': 'ab-session-end-hook.sh',
    'ab-instinct-observer-hook': 'ab-instinct-observer-hook.py',
}
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def replace(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.ab-hook-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin-dir', type=Path, default=Path.home()/'.local/bin')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--rollback', type=Path, help='manifest produced by --install')
    p.add_argument('--backup-dir', type=Path)
    args = p.parse_args()
    os.umask(0o077)
    if args.rollback:
        receipt = json.loads(args.rollback.read_text())
        rows = receipt['files']
        # Check all files before mutating any; never overwrite later user changes.
        for row in rows:
            if digest(Path(row['target'])) != row['installed_sha256']:
                raise SystemExit('rollback refused: installed hash changed: '+row['target'])
            if row['backup'] and digest(Path(row['backup'])) != row['previous_sha256']:
                raise SystemExit('rollback refused: backup hash changed')
        for row in rows:
            target = Path(row['target'])
            if row['backup']:
                replace(target, Path(row['backup']).read_bytes(), row['previous_mode'])
            else:
                target.unlink()
        print(json.dumps({'status': 'rolled_back', 'files': len(rows)}))
        return
    rows = []
    for name, source in SOURCES.items():
        src = ROOT/'crates/bridge/src/hooks'/source
        target = (args.bin_dir/name).resolve()
        rows.append({'name': name, 'source': str(src), 'target': str(target),
                     'installed_sha256': digest(src), 'previous_sha256': digest(target),
                     'previous_mode': target.stat().st_mode & 0o777 if target.exists() else None,
                     'in_sync': digest(src) == digest(target)})
    if args.check:
        print(json.dumps({'in_sync': all(r['in_sync'] for r in rows), 'files': rows}, indent=2))
        return
    if not args.backup_dir:
        p.error('--install requires a new --backup-dir')
    backup = args.backup_dir.resolve()
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    # Snapshot every file and write rollback receipt before installing the first.
    for row in rows:
        target = Path(row['target'])
        row['backup'] = str(backup/row['name']) if target.exists() else None
        if row['backup']:
            shutil.copy2(target, row['backup'])
            os.chmod(row['backup'], 0o600)
    receipt = {'schema': 'agent_bridge_hook_script_install.v1',
               'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope': 'scripts_only; client configuration, trust, and databases unchanged',
               'files': rows}
    manifest = backup/'manifest.json'
    manifest.write_text(json.dumps(receipt, indent=2)+'\n')
    for row in rows:
        src = Path(row['source'])
        if digest(src) != row['installed_sha256'] or digest(Path(row['target'])) != row['previous_sha256']:
            raise SystemExit('install refused: source or target changed; inspect manifest before recovery')
        replace(Path(row['target']), src.read_bytes(), 0o755)
    print(json.dumps({'status': 'installed', 'manifest': str(manifest),
                      'files': len(rows)}, indent=2))


if __name__ == '__main__':
    main()
