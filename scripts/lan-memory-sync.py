#!/usr/bin/env python3
"""Bounded LAN orchestration around the installed AB sync engine.

No database writes, merge implementation, binary installation or HTTP listener.
The existing AB engine owns import/export and the shared memory-sync lock.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time


class Busy(RuntimeError):
    pass


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    with open(tmp, "x", encoding="utf-8") as f:
        os.chmod(tmp, 0o600)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def command(argv, env=None, timeout=30, check=True):
    """Bound the child and its own process group, including Git/SSH children."""
    p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
        raise RuntimeError("command timed out: " + Path(argv[0]).name)
    if check and p.returncode:
        # Do not emit remote URLs or arbitrary credential-bearing stderr.
        raise RuntimeError("command failed: " + Path(argv[0]).name + " exit=" + str(p.returncode))
    return p.returncode, out, err


def sync_env(config, channel):
    env = dict(os.environ)
    env.update({
        "AGENT_BRIDGE_DB": config["db"],
        "AGENT_BRIDGE_MEMORY_REPO": channel["repo"],
        "AB_LOCKS_DIR": config["locks_dir"],
        "AGENT_BRIDGE_MEMORY_IMPORT_SKIP_EMBEDDINGS": "1",
        "AGENT_BRIDGE_SYNC_REMOTE_REINDEX_BATCH_SIZE": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2",
    })
    return env


def git(repo, args, env, timeout=20, check=True):
    return command(["git", "-C", str(repo), *args], env, timeout, check)


@contextlib.contextmanager
def sync_lock(config):
    """Share AB's exact JSON lock for short Git/config work; never steal it.

    Do not call AB sync while holding this: its lock acquisition would skip.
    Dead-owner cleanup belongs to the existing AB lock implementation.
    """
    path = Path(config["locks_dir"]) / "memory-sync.lock"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = {"resource": "memory-sync", "owner_pid": os.getpid(),
            "owner_cmd": "lan-memory-sync git reconciliation", "acquired_at": int(time.time()),
            "ttl_secs": 600}
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Busy("existing AB sync owns the shared lock")
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        yield
    finally:
        try:
            current = path.stat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                path.unlink()
        except FileNotFoundError:
            pass


def check_repo(config, channel, env):
    repo = Path(channel["repo"])
    if not (repo / ".git").is_dir():
        raise RuntimeError("sync checkout is missing")
    expected = channel["origin"]
    for args in [["remote", "get-url", "origin"],
                 ["remote", "get-url", "--push", "--all", "origin"]]:
        urls = git(repo, args, env)[1].splitlines()
        if not urls or any(url != expected for url in urls):
            raise RuntimeError("origin fetch/push configuration drift")
    branch = git(repo, ["branch", "--show-current"], env)[1].strip()
    upstream = git(repo, ["rev-parse", "--abbrev-ref", "@{u}"], env)[1].strip()
    if branch != channel["branch"] or upstream != "origin/" + branch:
        raise RuntimeError("branch/upstream configuration drift")
    if not Path(config["db"]).is_file():
        raise RuntimeError("configured live database is missing")
    return repo, branch


def reconcile_push(config, channel, env):
    """Retry committed-but-unsent work even when AB's export did not change."""
    with sync_lock(config):
        repo, branch = check_repo(config, channel, env)
        git(repo, ["fetch", "origin"], env)
        ahead, behind = map(int, git(repo, ["rev-list", "--left-right", "--count",
                                              "HEAD...origin/" + branch], env)[1].split())
        if behind:
            # Next AB import/export owns semantic merge. Never force/reset here.
            return {"transport_state": "peer_advanced_retry", "ahead": ahead, "behind": behind}
        head = git(repo, ["rev-parse", "HEAD"], env)[1].strip()
        if ahead:
            git(repo, ["push", "origin", branch + ":refs/heads/" + branch], env)
        remote = git(repo, ["ls-remote", "origin", "refs/heads/" + branch], env)[1].split()
        if not remote:
            raise RuntimeError("remote branch missing after reconciliation")
        remote_tip = remote[0]
        if remote_tip != head:
            # A second writer may have advanced it after our push.
            git(repo, ["fetch", "origin"], env)
            rc = git(repo, ["merge-base", "--is-ancestor", head, "origin/" + branch], env,
                     check=False)[0]
            if rc != 0:
                raise RuntimeError("published commit not confirmed on remote")
        return {"transport_state": "published", "published_commit": head,
                "observed_remote_tip": remote_tip, "retried_ahead_commits": ahead,
                "target_database_import": "not_claimed; use verify on receiving node"}


def run_round(config, name):
    channel = config["channels"][name]
    env = sync_env(config, channel)
    receipt = {"schema": "ab.lan-sync.round.v1", "node": config["node"],
               "channel": name, "started_at": time.time()}
    state = Path(config["state_dir"])
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(state / (name + ".runner.lock"), "a") as runner:
        try:
            fcntl.flock(runner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"state": "busy", "channel": name}))
            return 3
        try:
            repo, branch = check_repo(config, channel, env)
            # Unlike the legacy best-effort pull, failed reachability is visible.
            if not git(repo, ["ls-remote", "origin", "refs/heads/" + branch], env)[1].strip():
                raise RuntimeError("remote branch unavailable")
            rc, out, err = command([config["wrapper"], "sync", "-v"], env,
                                   channel.get("timeout_seconds", 180), check=False)
            # Keep only bounded routine diagnostic text; never dump raw memory.
            log = out + err
            (state / (name + ".last-sync.log")).write_text(log, encoding="utf-8")
            os.chmod(state / (name + ".last-sync.log"), 0o600)
            receipt["sync_exit_code"] = rc
            if rc:
                raise RuntimeError("AB sync failed with exit=" + str(rc))
            actual_repo = re.search(r"\[sync\] repo: ([^\n]+)", log)
            if actual_repo and Path(actual_repo.group(1)).resolve() != repo.resolve():
                raise RuntimeError("wrapper changed the selected sync checkout")
            match = re.search(r"\[sync\] memory import: ([^\n]+)", log)
            if match is None:
                raise Busy("AB sync did not report a completed import")
            counters = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", match.group(1))}
            receipt["local_import_counters"] = counters
            if counters.get("malformed", 0) or counters.get("edges_malformed", 0):
                raise RuntimeError("malformed imported records need review")
            receipt.update(reconcile_push(config, channel, env))
            receipt["state"] = "complete" if receipt["transport_state"] == "published" else "retry"
            code = 0 if receipt["state"] == "complete" else 3
        except Busy as e:
            receipt.update(state="busy", reason=str(e))
            code = 3
        except Exception as e:
            receipt.update(state="failed", reason=str(e))
            code = 1
        receipt["finished_at"] = time.time()
        receipt["duration_seconds"] = round(receipt["finished_at"] - receipt["started_at"], 3)
        atomic_json(state / (name + ".last-round.json"), receipt)
        if code == 0:
            atomic_json(state / (name + ".last-success.json"), receipt)
        print(json.dumps(receipt, ensure_ascii=False))
        return code


def memory_proof(config, key, expected=None):
    """Read one exact durable row. This does not depend on retrieval ranking."""
    db = Path(config["db"]).resolve(strict=True)
    with contextlib.closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5)) as con:
        row = con.execute("SELECT content, updated_at, status, version_vector FROM memories WHERE key=?", (key,)).fetchone()
    proof = {"schema": "ab.lan-sync.memory-proof.v1", "node": config["node"],
             "key": key, "checked_at": time.time(),
             "db_path_sha256": hashlib.sha256(str(db).encode()).hexdigest(), "exists": row is not None}
    if row:
        proof.update(content_sha256=hashlib.sha256(row[0].encode()).hexdigest(),
                     updated_at=row[1], status=row[2], version_vector=json.loads(row[3] or "{}"))
    if expected is not None:
        fields = ["key", "content_sha256", "updated_at", "status", "version_vector"]
        proof["matches_expected"] = row is not None and all(proof.get(k) == expected.get(k) for k in fields)
    return proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    sub = p.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--channel", default="lan")
    verify = sub.add_parser("verify")
    verify.add_argument("--key", required=True)
    verify.add_argument("--expected", type=Path)
    sub.add_parser("status")
    a = p.parse_args()
    config = json.loads(a.config.read_text())
    if config.get("version") != 1:
        raise RuntimeError("unsupported config version")
    if a.action == "run":
        return run_round(config, a.channel)
    if a.action == "verify":
        proof = memory_proof(config, a.key, json.loads(a.expected.read_text()) if a.expected else None)
        print(json.dumps(proof, ensure_ascii=False, indent=2))
        return 0 if proof.get("matches_expected", proof["exists"]) else 1
    receipts = {}
    for name in config["channels"]:
        receipts[name] = {}
        for label in ["last-round", "last-success"]:
            path = Path(config["state_dir"]) / (name + "." + label + ".json")
            receipts[name][label] = json.loads(path.read_text()) if path.exists() else None
    print(json.dumps(receipts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
