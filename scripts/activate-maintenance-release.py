#!/usr/bin/env python3
"""Adopt an admitted private maintenance release through existing local aliases.

The default action only checks and prints a plan. Services and SQLite backups
belong to the calling deployment procedure. Alias adoption is not atomic:
rename-to-backup briefly removes each path before creating its replacement.
Caught failures restore completed moves in reverse.
"""

import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import uuid


class ActivationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ActivationError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def absolute(path):
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)), "path must be absolute and normalized")
    require(not any(ord(c) < 32 for c in str(path)), "control character in path")
    return path


def physical(path):
    for part in [*reversed(path.parents), path]:
        require(not part.is_symlink(), f"symlink path component: {part}")
    require(path.exists(), f"missing path: {path}")


def private(path, root, mode, directory=False):
    require(path == root or root in path.parents, f"private path escapes root: {path}")
    physical(path)
    info = root.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, "deployment root must be owned and exactly 0700")
    for part in path.parents if path != root else []:
        if part == root:
            break
        info = part.stat()
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, f"private directory must be owned and 0700: {part}")
    info = path.stat()
    correct_kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    require(correct_kind and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == mode, f"invalid private owner/type/mode: {path}")
    return info


def snapshot(path):
    """Content and object kinds, never FUSE owner/mode as integrity evidence."""
    physical(path.parent)
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if not path.exists():
        return {"kind": "absent"}
    physical(path)
    if path.is_file():
        return {"kind": "file", "size": path.stat().st_size, "sha256": digest(path)}
    require(path.is_dir(), f"unsupported legacy object: {path}")
    children = {}
    for child in sorted(path.rglob("*")):
        require(not child.is_symlink(), f"legacy tree contains symlink: {child}")
        if child.is_dir():
            children[str(child.relative_to(path))] = {"kind": "directory"}
        elif child.is_file():
            children[str(child.relative_to(path))] = {"kind": "file", "size": child.stat().st_size, "sha256": digest(child)}
        else:
            raise ActivationError(f"legacy tree contains special file: {child}")
    return {"kind": "directory", "children": children}


def publisher_assets():
    # Read the fixed literal publisher arrays; never source or execute shell.
    source = Path(__file__).with_name("deploy_from_master.sh").read_text()
    arrays = {}
    for name in ["AUDIO_ADAPTER_COMPANIONS", "AUDIO_POLICY_ASSETS", "RUNTIME_ASSETS"]:
        match = re.search(rf"^{name}=\(\n(.*?)^\)", source, re.M | re.S)
        require(match is not None, f"missing publisher asset array: {name}")
        entries = match.group(1).split()
        require(entries and all(re.fullmatch(r"[A-Za-z0-9_./-]+", value) and ".." not in Path(value).parts and not value.startswith("/") for value in entries), "publisher assets must be literal relative paths")
        arrays[name] = entries
    return arrays


def parse_asset_inventory(root, records):
    release = root / "maintenance"
    require(isinstance(records, list) and 2 <= len(records) <= 256, "invalid frozen asset list")
    result = []
    seen = set()
    ranks = []
    for item in records:
        require(isinstance(item, dict) and set(item) == {"label", "source", "mode"}, "invalid frozen asset entry")
        label, source, mode = item["label"], absolute(item["source"]), item["mode"]
        require(label in {"wrapper", "adapter", "companion", "policy", "runtime"}, "invalid frozen asset category")
        prefixes = {"companion": release / "share/ab-tts", "policy": release / "share", "runtime": release / "lib/agent-bridge/scripts"}
        if label == "wrapper":
            require(source == root / "bin/agent-bridge", "invalid frozen wrapper path")
        elif label == "adapter":
            require(source == release / "share/ab-tts/audio_embody.py", "invalid frozen adapter path")
        else:
            require(prefixes[label] in source.parents and ".." not in source.parts, "frozen asset path escapes its category")
        require(mode == (0o644 if label == "policy" else 0o755) and source not in seen, "invalid frozen asset mode or duplicate")
        seen.add(source)
        ranks.append(["wrapper", "adapter", "companion", "policy", "runtime"].index(label))
        result.append((label, source, mode))
    require(ranks == sorted(ranks) and ranks.count(0) == 1 and ranks.count(1) == 1, "invalid frozen asset order")
    return result


def assets(root, payload=None):
    release = root / "maintenance"
    if payload is not None:
        inventory = payload / "asset-list.json"
        private(inventory, root, 0o600)
        require(inventory.stat().st_size <= 65536, "frozen asset list is too large")
        records = json.loads(inventory.read_text())
        return parse_asset_inventory(root, records)
    listed = publisher_assets()
    return [
        ("wrapper", root / "bin/agent-bridge", 0o755),
        ("adapter", release / "share/ab-tts/audio_embody.py", 0o755),
        *[("companion", release / "share/ab-tts" / value, 0o755) for value in listed["AUDIO_ADAPTER_COMPANIONS"]],
        *[("policy", release / "share" / value, 0o644) for value in listed["AUDIO_POLICY_ASSETS"]],
        *[("runtime", release / "lib/agent-bridge/scripts" / value, 0o755) for value in listed["RUNTIME_ASSETS"]],
    ]


def assets_digest(root, payload=None):
    lines = []
    for label, source, mode in assets(root, payload):
        path = payload_path(root, payload, source) if payload else source
        private(path, root, mode)
        lines.append(f"{label}\t{source}\t{digest(path)}\t{mode:o}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


RECEIPT_KEYS = ("schema,pending_lease_id,pending_challenge,candidate_commit,real_path,shared_targets,installed_binary_sha256,installed_binary_inode,installed_binary_mode,installed_assets_sha256,pending_installed_at,admission_lease_id,admission_challenge,fresh_mcp,probe_schema,probe_nonce,probe_started_at,probe_finished_at,probe_server_name,probe_server_version,probe_protocol_version,probe_build_git_sha,probe_toolset,probe_tool_count,probe_capabilities_tool_present,probe_method,probe_copied_binary_sha256,probe_evidence_sha256,admission_binding_sha256,receipt_binding_sha256").split(",")


def validate_release(root, receipt, payload=None):
    private(root, root, 0o700, directory=True)
    release = root / "maintenance"
    source_binary = release / "bin/agent-bridge.real"
    binary = payload / "bin/agent-bridge.real" if payload else source_binary
    info = private(binary, root, 0o755)
    receipt_dir = root / "publisher-state/maintenance/receipts"
    allowed_receipt = receipt.parent == receipt_dir and receipt.name.endswith(".fresh-mcp-admitted.meta")
    if payload is not None:
        allowed_receipt = receipt == payload / "fresh-mcp-admitted.meta"
    require(allowed_receipt, "receipt must be a fixed maintenance admission receipt")
    private(receipt, root, 0o600)
    raw = receipt.read_bytes()
    lines = raw.decode("ascii").splitlines(keepends=True)
    require(len(lines) == len(RECEIPT_KEYS) and all(line.endswith("\n") and "\r" not in line for line in lines), "invalid admission receipt framing")
    pairs = [line[:-1].split("=", 1) for line in lines]
    require(all(len(pair) == 2 for pair in pairs) and [pair[0] for pair in pairs] == RECEIPT_KEYS, "invalid admission receipt fields")
    record = dict(pairs)
    bound = hashlib.sha256(b"domain=agent_bridge.publisher_fresh_mcp_admission_receipt.v1\n" + "".join(lines[:29]).encode()).hexdigest()
    require(record["receipt_binding_sha256"] == bound, "admission receipt digest mismatch")
    expected = {
        "schema": "agent_bridge.publisher_fresh_mcp_admission.v1",
        "real_path": str(source_binary),
        "shared_targets": "|".join(map(str, [source_binary, release / "share/ab-tts/audio_embody.py", release / "lib/agent-bridge/scripts", root / "bin/agent-bridge"])),
        "installed_binary_sha256": digest(binary),
        "installed_binary_mode": "755",
        "installed_assets_sha256": assets_digest(root, payload),
        "fresh_mcp": "verified",
        "probe_schema": "agent_bridge.publisher_fresh_mcp_probe.v1",
        "probe_server_name": "agent-bridge",
        "probe_protocol_version": "2024-11-05",
        "probe_toolset": "codex-essential",
        "probe_capabilities_tool_present": "true",
        "probe_method": "independent_stdio_private_exact_binary_copy",
        "probe_copied_binary_sha256": digest(binary),
    }
    if payload is None:
        expected["installed_binary_inode"] = str(info.st_ino)
    for key, value in expected.items():
        require(record[key] == value, f"admission receipt mismatch: {key}")
    require(re.fullmatch(r"[0-9a-f]{40}", record["candidate_commit"]) and record["probe_build_git_sha"] == record["candidate_commit"][:12], "admission commit mismatch")
    require(record["probe_tool_count"].isdigit() and int(record["probe_tool_count"]) > 0, "fresh MCP returned no tools")
    with binary.open("rb") as stream:
        require(stream.read(4) == b"\x7fELF", "maintenance adoption requires a native Linux ELF binary")
        stream.seek(0)
        marker = b"agent_bridge.runtime_profile.maintenance.v1"
        overlap = b""
        found = False
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            found |= marker in overlap + chunk
            overlap = chunk[-len(marker):]
        require(found, "binary has no maintenance runtime profile marker")
    return record


def payload_path(root, payload, source):
    if source == root / "bin/agent-bridge":
        return payload / "bin/agent-bridge"
    return payload / source.relative_to(root / "maintenance")


def release_path(root, admitted):
    identity = admitted["installed_binary_sha256"] + "-" + admitted["installed_assets_sha256"]
    require(re.fullmatch(r"[0-9a-f]{64}-[0-9a-f]{64}", identity), "invalid immutable release identity")
    return root / "maintenance/releases" / identity


def validate_frozen(root, payload):
    require(payload.parent == root / "maintenance/releases" and re.fullmatch(r"[0-9a-f]{64}-[0-9a-f]{64}", payload.name), "invalid immutable release path")
    private(payload, root, 0o700, directory=True)
    admitted = validate_release(root, payload / "fresh-mcp-admitted.meta", payload)
    require(release_path(root, admitted) == payload, "frozen payload does not match its identity")
    return admitted


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_mkdir(path, root):
    require(path == root or root in path.parents, "directory escapes deployment root")
    if not path.exists():
        private_mkdir(path.parent, root)
        path.mkdir(mode=0o700)
        sync_directory(path.parent)
    private(path, root, 0o700, directory=True)


def rename_without_replace(source, destination):
    # This helper already requires Linux/ELF. renameat2 prevents replacing even
    # an empty existing directory if another actor creates the final name.
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def clean_interrupted_staging(root, final, declared):
    # Only this identity's reserved staging names, while holding the publisher
    # mutex. Reject links, foreign ownership and unexpected content instead of
    # traversing or deleting an unknown directory.
    allowed = {Path("asset-list.json"), Path("fresh-mcp-admitted.meta"), Path("bin/agent-bridge.real")}
    allowed.update(payload_path(root, final, source).relative_to(final) for _, source, _ in declared)
    directories = {parent for path in allowed for parent in path.parents if str(parent) != "."}
    pattern = re.compile(r"\.staging-" + re.escape(final.name) + r"-[0-9a-f]{32}")
    for stage in final.parent.iterdir():
        if not pattern.fullmatch(stage.name):
            continue
        private(stage, root, 0o700, directory=True)
        for child in stage.rglob("*"):
            relative = child.relative_to(stage)
            require(not child.is_symlink(), "interrupted staging contains a symlink")
            if child.is_dir():
                require(relative in directories, "interrupted staging contains an unexpected directory")
                private(child, root, 0o700, directory=True)
            else:
                manifest_temp = len(relative.parts) == 1 and re.fullmatch(r"asset-list\.json\.tmp-[0-9a-f]{32}", relative.name)
                require((relative in allowed or manifest_temp) and child.is_file(), "interrupted staging contains an unexpected file")
                require(child.stat().st_uid == os.getuid() and not stat.S_IMODE(child.stat().st_mode) & 0o022, "interrupted staging file is not private publisher content")
        shutil.rmtree(stage)
    sync_directory(final.parent)


def freeze_release(root, receipt, admitted):
    final = release_path(root, admitted)
    if os.path.lexists(final):
        validate_frozen(root, final)
        return final
    private_mkdir(final.parent, root)
    declared = assets(root)
    clean_interrupted_staging(root, final, declared)
    stage = final.with_name(".staging-" + final.name + "-" + uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    sync_directory(stage.parent)
    try:
        save_manifest(stage / "asset-list.json", [{"label": label, "source": str(source), "mode": mode} for label, source, mode in declared])
        copies = [(root / "maintenance/bin/agent-bridge.real", stage / "bin/agent-bridge.real", 0o755)]
        copies += [(source, payload_path(root, stage, source), mode) for _, source, mode in declared]
        copies.append((receipt, stage / "fresh-mcp-admitted.meta", 0o600))
        for source, destination, mode in copies:
            private_mkdir(destination.parent, root)
            source_hash = digest(source)
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            with source.open("rb") as src, os.fdopen(fd, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fchmod(dst.fileno(), mode)
                os.fsync(dst.fileno())
            require(digest(destination) == source_hash, "frozen payload copy differs from admitted source")
            sync_directory(destination.parent)
        staged_admission = validate_release(root, stage / "fresh-mcp-admitted.meta", stage)
        require(release_path(root, staged_admission) == final, "staged payload does not match final identity")
        sync_directory(stage)
        try:
            rename_without_replace(stage, final)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
            validate_frozen(root, final)
            shutil.rmtree(stage)
        sync_directory(final.parent)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return final


def fixed_aliases(root, wrapper, payload=None, declared=None):
    home = Path.home()
    require(wrapper == home / ".local/bin/agent-bridge", "legacy wrapper must be the existing HOME/.local/bin/agent-bridge")
    physical(wrapper)
    require(wrapper.is_file(), "legacy wrapper must be a regular file")
    release = root / "maintenance"
    # Keep the audio directory and its local models. Only publisher-owned files
    # are switched, including the two policy paths resolved through legacy HOME.
    aliases = [(wrapper.with_name("agent-bridge.real"), release / "bin/agent-bridge.real")]
    aliases.append((home / ".local/lib/agent-bridge/scripts", release / "lib/agent-bridge/scripts"))
    for label, target, _mode in declared if declared is not None else assets(root):
        if label in {"adapter", "companion", "policy"}:
            aliases.append((home / ".local/share" / target.relative_to(release / "share"), target))
    if payload:
        aliases = [(alias, payload_path(root, payload, target)) for alias, target in aliases]
    return aliases


def frozen_target_payload(root, target, source):
    target = absolute(target)
    base = root / "maintenance/releases"
    require(base in target.parents, "legacy alias must point into a fixed maintenance release")
    relative = target.relative_to(base)
    require(len(relative.parts) > 1, "legacy alias cannot target a release root")
    payload = base / relative.parts[0]
    require(re.fullmatch(r"[0-9a-f]{64}-[0-9a-f]{64}", payload.name), "legacy alias has an invalid release identity")
    require(target == payload_path(root, payload, source), "legacy alias targets the wrong release artifact")
    return payload


def validate_existing_aliases(root, source_aliases):
    previous = set()
    link_count = 0
    absent = []
    for alias, source in source_aliases:
        physical(alias.parent)
        if alias.is_symlink():
            previous.add(frozen_target_payload(root, os.readlink(alias), source))
            link_count += 1
        elif alias.exists():
            physical(alias)
        else:
            absent.append(source)
    if previous:
        require(len(previous) == 1 and link_count + len(absent) == len(source_aliases), "legacy aliases are a mixed generation; recover the interrupted activation first")
        payload = next(iter(previous))
        validate_frozen(root, payload)
        old_sources = {source for _label, source, _mode in assets(root, payload)}
        old_sources.update({root / "maintenance/bin/agent-bridge.real", root / "maintenance/lib/agent-bridge/scripts"})
        require(all(source not in old_sources for source in absent), "a previously declared alias is missing; recover it before updating")
    else:
        require(not absent and link_count == 0, "initial adoption requires existing legacy files")


@contextlib.contextmanager
def publisher_lock(root):
    lock = root / "publisher-state/deploy/publisher.kernel.lock"
    info = private(lock, root, 0o600)
    fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        current = os.fstat(fd)
        require((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino), "publisher lock changed")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def save_manifest(path, data):
    tmp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    sync_directory(path.parent)


def restore(entries):
    for entry in reversed(entries):
        alias, backup = Path(entry["alias"]), Path(entry["backup"])
        if entry["before"]["kind"] == "absent":
            require(not os.path.lexists(backup), "unexpected backup for a newly declared alias")
            if alias.is_symlink():
                require(os.readlink(alias) == entry["target"], f"new alias was changed after activation: {alias}")
                alias.unlink()
            else:
                require(not alias.exists(), f"new alias was replaced after activation: {alias}")
            continue
        require(snapshot(backup) == entry["before"], f"backup content changed: {backup}")
        if alias.is_symlink():
            require(os.readlink(alias) == entry["target"], f"alias was changed after activation: {alias}")
            alias.unlink()
        else:
            require(not alias.exists(), f"alias was replaced after activation: {alias}")
        os.rename(backup, alias)


def run(args):
    root, wrapper = absolute(args.deploy_root), absolute(args.legacy_wrapper)
    require(re.fullmatch(r"[0-9a-f]{64}", args.expected_binary_sha256) and re.fullmatch(r"[0-9a-f]{64}", args.expected_wrapper_sha256), "expected hashes must be lowercase SHA-256")
    with publisher_lock(root):
        aliases = fixed_aliases(root, wrapper)
        require(digest(wrapper) == args.expected_wrapper_sha256, "legacy wrapper changed")
        if args.action == "rollback":
            manifest = absolute(args.manifest)
            require(manifest.parent == root / "publisher-state/maintenance/receipts" and re.fullmatch(r"[0-9a-f]{32}\.maintenance-activation\.json", manifest.name), "invalid activation manifest location")
            private(manifest, root, 0o600)
            data = json.loads(manifest.read_text())
            require(data["status"] in {"prepared", "activated", "rollback_started", "recovery_required"} and data["deploy_root"] == str(root) and data["legacy_wrapper"] == str(wrapper), "manifest does not describe an active matching adoption")
            require(data["expected_binary_sha256"] == args.expected_binary_sha256 and data["expected_wrapper_sha256"] == args.expected_wrapper_sha256, "manifest baseline mismatch")
            payload = absolute(data["release_root"])
            require(payload.parent == root / "maintenance/releases" and re.fullmatch(r"[0-9a-f]{64}-[0-9a-f]{64}", payload.name), "invalid rollback release path")
            # The outgoing payload may be damaged or absent. Its protected
            # activation manifest supplies the exact adopted paths; only the
            # backups and previous frozen recovery target must still be healthy.
            frozen_assets = parse_asset_inventory(root, data["asset_list"])
            aliases = fixed_aliases(root, wrapper, payload, frozen_assets)
            require([(entry["alias"], entry["target"]) for entry in data["entries"]] == [(str(a), str(t)) for a, t in aliases], "manifest alias set changed")
            # A synced prepared manifest precedes every rename. Process
            # interruption can be recovered after checking current contents;
            # this does not promise power-loss atomicity on the legacy mount.
            restore_entries = []
            previous_payloads = set()
            source_by_alias = dict(fixed_aliases(root, wrapper, declared=frozen_assets))
            for entry in data["entries"]:
                alias, backup = Path(entry["alias"]), Path(entry["backup"])
                require(backup == alias.with_name(alias.name + ".bak-maintenance-" + data["id"]), "manifest backup path escapes the fixed sibling")
                if entry["before"]["kind"] == "symlink":
                    previous_payloads.add(frozen_target_payload(root, entry["before"]["target"], source_by_alias[alias]))
                if entry["before"]["kind"] == "absent":
                    require(not os.path.lexists(backup), "unexpected backup for newly declared alias")
                    require((alias.is_symlink() and os.readlink(alias) == entry["target"]) or not os.path.lexists(alias), f"new alias was changed after activation: {alias}")
                    restore_entries.append(entry)
                elif os.path.lexists(backup):
                    require((alias.is_symlink() and os.readlink(alias) == entry["target"]) or not os.path.lexists(alias), f"alias was changed after activation: {alias}")
                    require(snapshot(backup) == entry["before"], f"backup content changed: {backup}")
                    restore_entries.append(entry)
                else:
                    require(snapshot(alias) == entry["before"], f"alias was changed after activation: {alias}")
            for previous in previous_payloads:
                validate_frozen(root, previous)
            data["status"] = "rollback_started"
            save_manifest(manifest, data)
            restore(restore_entries)
            data["status"] = "rolled_back"
            save_manifest(manifest, data)
            return {"status": "rolled_back", "manifest": str(manifest)}
        require(args.admission_receipt, "admission receipt is required")
        receipt = absolute(args.admission_receipt)
        admitted = validate_release(root, receipt)
        payload = release_path(root, admitted)
        aliases = fixed_aliases(root, wrapper, payload)
        validate_existing_aliases(root, fixed_aliases(root, wrapper))
        require(digest(aliases[0][0]) == args.expected_binary_sha256, "legacy binary changed")
        entries = [{"alias": str(alias), "target": str(target), "before": snapshot(alias)} for alias, target in aliases]
        if args.action == "plan":
            return {"status": "ready", "action": "plan", "candidate_commit": admitted["candidate_commit"], "aliases": entries, "atomicity": "not atomic: each path is briefly absent between backup rename and symlink creation; services and SQLite backup are caller responsibilities"}
        freeze_release(root, receipt, admitted)
        identity = uuid.uuid4().hex
        manifest = root / "publisher-state/maintenance/receipts" / (identity + ".maintenance-activation.json")
        for entry in entries:
            alias = Path(entry["alias"])
            entry["backup"] = str(alias.with_name(alias.name + ".bak-maintenance-" + identity))
            require(not os.path.lexists(entry["backup"]), "backup path already exists")
        data = {"id": identity, "status": "prepared", "deploy_root": str(root), "legacy_wrapper": str(wrapper), "expected_binary_sha256": args.expected_binary_sha256, "expected_wrapper_sha256": args.expected_wrapper_sha256, "admission_receipt": str(receipt), "release_root": str(payload), "asset_list": [{"label": label, "source": str(source), "mode": mode} for label, source, mode in assets(root)], "entries": entries}
        save_manifest(manifest, data)
        moved = []
        try:
            for entry in entries:
                alias, backup = Path(entry["alias"]), Path(entry["backup"])
                require(digest(wrapper) == args.expected_wrapper_sha256, "legacy wrapper changed during activation")
                require(snapshot(alias) == entry["before"], f"legacy target changed during activation: {alias}")
                if entry["before"]["kind"] != "absent":
                    os.rename(alias, backup)
                moved.append(entry)
                os.symlink(entry["target"], alias)
            data["status"] = "activated"
            save_manifest(manifest, data)
        except BaseException:
            try:
                restore(moved)
            except BaseException:
                data["status"] = "recovery_required"
                save_manifest(manifest, data)
                raise
            data["status"] = "automatically_restored"
            save_manifest(manifest, data)
            raise
        return {"status": "activated", "manifest": str(manifest), "candidate_commit": admitted["candidate_commit"], "existing_mcp_sessions_refreshed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "activate", "rollback"], nargs="?", default="plan")
    parser.add_argument("--deploy-root", required=True)
    parser.add_argument("--legacy-wrapper", required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument("--expected-wrapper-sha256", required=True)
    parser.add_argument("--admission-receipt")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    try:
        require(args.action != "rollback" or args.manifest, "rollback requires --manifest")
        print(json.dumps(run(args), sort_keys=True, indent=2))
    except (ActivationError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
