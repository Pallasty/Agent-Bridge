#!/usr/bin/env python3
"""Bounded WorktreeSession CLI comparison using isolated fake and real Git.

List/help/error cases compare exact CLI bytes and fixture effects. New cases
validate the one generated slug timestamp within each invocation, then replace
only that exact slug in CLI/argv/path evidence. Real Git evidence compares refs,
worktree metadata and fixture contents, not volatile Git index/database bytes.
No real repository, configuration, hooks, credentials, or network is used.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time


# The fixture interpreter must not add Apple Python caches to the observed
# filesystem. Keep effect assertions strict; suppress only fixture bytecode.
FAKE_GIT = '''#!/usr/bin/python3 -B
import json, os, sys
from pathlib import Path
root = Path(os.environ["FIXTURE_ROOT"])
cfg = json.loads((root / "fake-git.json").read_text())
args = sys.argv[1:]
with (root / "git-calls.jsonl").open("a") as log:
    log.write(json.dumps({"argv": args, "cwd": os.getcwd(),
        "parent_exists": (root / "repo/.worktrees").is_dir()}) + "\\n")
if args == ["rev-parse", "--show-toplevel"]:
    if cfg["discovery_fail"]:
        sys.stderr.buffer.write(b"fixture discovery failure\\xff \\n")
        sys.exit(7)
    sys.stdout.buffer.write(("  " + str(root / "repo") + "\\n").encode())
elif args[:4] == ["-C", str(root / "repo"), "worktree", "list"]:
    if cfg["git_fail"]:
        sys.stderr.buffer.write(b"fixture list failure\\xff \\n")
        sys.exit(8)
    sys.stdout.buffer.write((root / "porcelain").read_bytes())
    sys.stderr.buffer.write(b"suppressed successful git stderr\\n")
elif args[:4] == ["-C", str(root / "repo"), "worktree", "add"]:
    if cfg["git_fail"]:
        sys.stdout.buffer.write(b"failed git stdout must not escape\\n")
        sys.stderr.buffer.write(b"fixture add failure\\xff \\n")
        sys.exit(9)
    sys.stdout.buffer.write(b"fixture git stdout\\xff\\n")
    sys.stderr.buffer.write(b"suppressed successful git stderr\\n")
else:
    sys.stderr.buffer.write(b"unexpected fixture git arguments\\n")
    sys.exit(98)
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def git(root, env, *args):
    result = subprocess.run(["/usr/bin/git", "-C", str(root / "repo"), *args],
                            env=env, capture_output=True, timeout=20)
    require(result.returncode == 0, "fixture Git failed: " + result.stderr.decode(errors="replace"))
    return result.stdout


def setup(root, case):
    for path in root.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name in ["home", "config", "data", "cache", "state", "runtime", "tmp", "hooks",
                 "empty-template", "repo", "outside", "bin"]:
        (root / name).mkdir(mode=0o700)
    (root / "empty-creds").write_bytes(b"")
    (root / "empty-git-config").write_bytes(b"")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC", "RUST_LOG": "off",
           "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
           "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
           "XDG_CACHE_HOME": str(root / "cache"), "XDG_STATE_HOME": str(root / "state"),
           "XDG_RUNTIME_DIR": str(root / "runtime"),
           "AGENT_BRIDGE_STATE_DIR": str(root / "state"),
           "AGENT_BRIDGE_CREDS_FILE": str(root / "empty-creds"),
           "AGENT_BRIDGE_EMBED_BACKEND": "hash", "AGENT_BRIDGE_REPO": str(root / "repo"),
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": str(root / "empty-git-config"),
           "GIT_CONFIG_GLOBAL": str(root / "empty-git-config"), "GIT_ATTR_NOSYSTEM": "1",
           "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.hooksPath",
           "GIT_CONFIG_VALUE_0": str(root / "hooks"), "GIT_CONFIG_KEY_1": "commit.gpgSign",
           "GIT_CONFIG_VALUE_1": "false", "GIT_CONFIG_KEY_2": "core.autocrlf",
           "GIT_CONFIG_VALUE_2": "false", "GIT_TERMINAL_PROMPT": "0",
           "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GIT_AUTHOR_DATE": "2001-01-01T00:00:00 +0000",
           "GIT_COMMITTER_DATE": "2001-01-01T00:00:00 +0000"}
    if case["backend"] == "real":
        git(root, env, "init", "-q", "--initial-branch=fixture-main", "--template=" + str(root / "empty-template"))
        (root / "repo/fixture.txt").write_bytes(b"one\n")
        git(root, env, "add", "fixture.txt")
        git(root, env, "commit", "-qm", "fixture one [skip ci]")
        git(root, env, "branch", "fixture-base")
        (root / "repo/fixture.txt").write_bytes(b"two\n")
        git(root, env, "commit", "-qam", "fixture two [skip ci]")
        if case.get("seed_list"):
            git(root, env, "worktree", "add", "-q", "-b", "session/seed",
                str(root / "repo/.worktrees/session-seed"), "fixture-base")
            git(root, env, "worktree", "add", "-q", "--detach",
                str(root / "repo/.worktrees/session-detached"), "HEAD")
            git(root, env, "worktree", "add", "-q", "--detach",
                str(root / "repo/ordinary"), "HEAD")
    else:
        env.update(PATH=str(root / "bin") + ":/usr/bin:/bin", FIXTURE_ROOT=str(root))
        (root / "bin/git").write_text(FAKE_GIT, encoding="utf-8")
        (root / "bin/git").chmod(0o700)
        (root / "fake-git.json").write_text(json.dumps({
            "discovery_fail": case.get("discovery_fail", False),
            "git_fail": case.get("git_fail", False)}), encoding="utf-8")
        (root / "porcelain").write_bytes(case.get("porcelain", b""))
    if case.get("mkdir_blocked"):
        (root / "repo/.worktrees").write_bytes(b"fixture obstruction\n")
    if case.get("discover"):
        del env["AGENT_BRIDGE_REPO"]
    return env


def cases(root):
    def case(name, args, **kwargs):
        return {"name": name, "args": args, "backend": "fake", "exit": 0, **kwargs}

    for name, args in [("root-help", ["--help"]), ("group-help", ["worktree-session", "--help"]),
                       ("new-help", ["worktree-session", "new", "--help"]),
                       ("list-help", ["worktree-session", "list", "--help"])]:
        yield case(name, args, no_git=True)
    for command in ["new", "list"]:
        yield case(command + "-invalid-option", ["worktree-session", command, "--fixture-invalid"],
                   exit=2, no_git=True)
    for name, porcelain, expected in [
        ("empty", b"", b""),
        ("unrelated", b"worktree /fixture/ordinary\nHEAD abcdef123456\nbranch refs/heads/main\n\n", b""),
        ("normal", b"worktree /fixture/.worktrees/session-a\nHEAD abcdef123456\nbranch refs/heads/session/a\n\n",
         b"/fixture/.worktrees/session-a  refs/heads/session/a  abcdef12\n"),
        ("no-trailing-blank", b"worktree /fixture/.worktrees/session-a\nHEAD abcdef123456\nbranch refs/heads/session/a",
         b"/fixture/.worktrees/session-a  refs/heads/session/a  abcdef12\n"),
        ("detached", b"worktree /fixture/.worktrees/session-a\nHEAD 1234567890\ndetached\n\n",
         b"/fixture/.worktrees/session-a    12345678\n"),
        ("missing-head", b"worktree /fixture/.worktrees/session-a\nbranch refs/heads/session/a\n\n",
         b"/fixture/.worktrees/session-a  refs/heads/session/a  \n"),
        ("lossy", b"worktree /fixture/.worktrees/session-\xff\nHEAD \xff1234567890\nbranch refs/heads/\xff\n\n",
         "/fixture/.worktrees/session-�  refs/heads/�  �1234567\n".encode()),
        ("order-and-reset", b"worktree /fixture/.worktrees/session-z\nHEAD 0123456789\nbranch refs/heads/z\n\n"
         b"worktree /fixture/ordinary\nHEAD ffffffffff\nbranch refs/heads/ignored\n\n"
         b"worktree /fixture/.worktrees/session-a\nHEAD aaaaaaaaaa\n\n",
         b"/fixture/.worktrees/session-z  refs/heads/z  01234567\n/fixture/.worktrees/session-a    aaaaaaaa\n"),
    ]:
        yield case("fake-list-" + name, ["worktree-session", "list"], porcelain=porcelain, expected_stdout=expected)
    yield case("fake-list-discovery", ["worktree-session", "list"], discover=True, expected_stdout=b"")
    yield case("fake-list-discovery-failure", ["worktree-session", "list"], discover=True, discovery_fail=True, exit=1)
    yield case("fake-list-git-failure", ["worktree-session", "list"], git_fail=True, exit=1)
    for name, args, name_part in [("named", ["--name", "Fix-2_x"], "Fix-2_x"),
                                  ("anonymous", [], "anon"), ("empty-name", ["--name", ""], "anon"),
                                  ("sanitized", ["--name", "Fix /中文_2"], "Fix----_2"),
                                  ("explicit-base", ["--base", "fixture-base"], "anon")]:
        yield case("fake-new-" + name, ["worktree-session", "new", *args], name_part=name_part)
    yield case("fake-new-discovery", ["worktree-session", "new", "--name", "discovered"],
               name_part="discovered", discover=True)
    yield case("fake-new-override-priority", ["worktree-session", "new"], name_part="anon", discovery_fail=True)
    yield case("fake-new-git-failure", ["worktree-session", "new"], name_part="anon", git_fail=True, exit=1)
    yield case("fake-new-mkdir-failure", ["worktree-session", "new"], mkdir_blocked=True, exit=1)
    yield case("fake-new-discovery-failure", ["worktree-session", "new"], discover=True, discovery_fail=True, exit=1)
    for name, args, options in [
        ("head", ["new", "--name", "real"], {"name_part": "real"}),
        ("base", ["new", "--base", "fixture-base"], {"name_part": "anon", "base": "fixture-base"}),
        ("discovery", ["new"], {"name_part": "anon", "discover": True}),
        ("invalid-base", ["new", "--base", "fixture-does-not-exist"],
         {"name_part": "anon", "exit": 1, "base": "fixture-does-not-exist"}),
        ("mkdir-failure", ["new"], {"mkdir_blocked": True, "exit": 1}),
        ("list-empty", ["list"], {}),
        ("list-seeded", ["list"], {"seed_list": True}),
    ]:
        yield case("real-" + name, ["worktree-session", *args], backend="real", **options)


def snapshot(root, normalize, real):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if real and len(relative.parts) > 1 and relative.parts[:2] == ("repo", ".git"):
            continue
        if relative == Path("git-calls.jsonl"):
            continue  # Compared separately as ordered structured argv records.
        key = normalize(str(relative))
        entry = {"mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_dir():
            entry["kind"] = "directory"
        else:
            data = path.read_bytes()
            # The new worktree's .git pointer contains the same validated slug.
            if path.name == ".git":
                data = normalize(data.decode()).encode()
            entry.update(kind="file", sha256=digest(data))
        result[key] = entry
    return result


def refs(root, env):
    return dict(line.split(" ", 1) for line in git(
        root, env, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines())


def execute(binary, root, case):
    env = setup(root, case)
    real = case["backend"] == "real"
    before = snapshot(root, lambda value: value, real)
    old_refs = refs(root, env) if real else None
    cwd = root / ("repo" if case.get("discover") and real else "outside")
    start = time.time()
    run = subprocess.run(["agent-bridge", *case["args"]], executable=str(binary),
                         cwd=cwd, env=env, capture_output=True, timeout=30)
    end = time.time()
    require(run.returncode == case["exit"], f"exit {run.returncode}, expected {case['exit']}: {run.stderr!r}")
    if case["exit"] != 0:
        require(run.stdout == b"" and b"worktree created" not in run.stderr, "failure printed success")
    normalize = lambda value: value
    timestamp = None
    new_path = None
    branch = None
    if "name_part" in case:
        match = re.search(rb"  branch : session/([^\n]+)\n", run.stderr)
        require(match is not None, "new plan branch missing")
        slug = match[1].decode()
        prefix = case["name_part"] + "-"
        require(slug.startswith(prefix) and slug[len(prefix):].isdigit(), "unexpected sanitized slug")
        timestamp = int(slug[len(prefix):])
        require(int(start) <= timestamp <= int(end), "slug timestamp outside invocation")
        normalize = lambda value: value.replace(slug, prefix + "<validated-unix>")
        branch = "session/" + slug
        new_path = root / "repo/.worktrees" / ("session-" + slug)
        require(("  path   : " + str(new_path) + "\n").encode() in run.stderr, "path/branch slug mismatch")
        require(run.stderr.startswith(("# ε-5 worktree-session new\n  repo   : " + str(root / "repo") + "\n").encode()),
                "plan stderr ordering changed")
        if case["exit"] == 0:
            require(run.stdout == (str(new_path) + "\n").encode(), "success stdout is not precisely final path")
            require(b"worktree created\n" in run.stderr, "success status absent")
        else:
            require(run.stdout == b"" and b"worktree created" not in run.stderr, "failure printed success")
    if case.get("mkdir_blocked"):
        require(run.stdout == b"" and run.stderr.startswith(b"Error: mkdir "), "mkdir error/empty stdout changed")
        require(b"# " not in run.stderr, "plan emitted before mkdir failed")
    calls = []
    if (root / "git-calls.jsonl").exists():
        calls = [json.loads(line) for line in (root / "git-calls.jsonl").read_text().splitlines()]
    if not real:
        expected_calls = []
        if case.get("discover") and not case.get("no_git"):
            expected_calls.append(["rev-parse", "--show-toplevel"])
        terminal_before_git = case.get("no_git") or case.get("mkdir_blocked") or (
            case.get("discover") and case.get("discovery_fail"))
        if not terminal_before_git:
            if case["args"][1] == "list":
                expected_calls.append(["-C", str(root / "repo"), "worktree", "list", "--porcelain"])
            else:
                base = case["args"][case["args"].index("--base") + 1] if "--base" in case["args"] else "HEAD"
                expected_calls.append(["-C", str(root / "repo"), "worktree", "add", "-b", branch, str(new_path), base])
        require([call["argv"] for call in calls] == expected_calls, "Git argv/ordering changed")
        for call in calls:
            require(call["cwd"] == str(cwd), "Git invocation cwd changed")
            if "add" in call["argv"]:
                require(call["parent_exists"], "Git add executed before parent mkdir")
        require(b"suppressed successful git stderr" not in run.stderr, "successful Git stderr leaked")
        if "name_part" in case and case["exit"] == 0:
            require(b"fixture git stdout\xef\xbf\xbd\n" in run.stderr, "Git stdout not lossy-forwarded to stderr")
            require(run.stderr.index(b"  path   :") < run.stderr.index(b"fixture git stdout") <
                    run.stderr.index("  ✓ worktree created".encode()), "new diagnostic ordering changed")
        if "expected_stdout" in case:
            require(run.stdout == case["expected_stdout"], "list expected bytes changed")
            expected_stderr = b"" if run.stdout else (
                "(no session worktrees under " + str(root / "repo/.worktrees") + ")\n").encode()
            require(run.stderr == expected_stderr, "empty/nonempty list stderr changed")
    business = None
    if real:
        after_refs = refs(root, env)
        expected_refs = dict(old_refs)
        if new_path is not None and case["exit"] == 0:
            base = case.get("base", "HEAD")
            expected_head = git(root, env, "rev-parse", base).decode().strip()
            expected_refs["refs/heads/" + branch] = expected_head
            require(new_path.is_dir(), "new worktree directory missing")
            actual_head = git(root, env, "-C", str(new_path), "rev-parse", "HEAD").decode().strip()
            require(actual_head == expected_head, "new worktree uses wrong base")
            require((new_path / "fixture.txt").read_bytes() == (b"one\n" if base == "fixture-base" else b"two\n"),
                    "new worktree checkout contents changed")
        require(after_refs == expected_refs, "unexpected missing/additional Git refs")
        porcelain = git(root, env, "worktree", "list", "--porcelain").decode()
        if case["exit"] != 0:
            require("/.worktrees/session-" not in porcelain, "failure registered a worktree")
        if case.get("seed_list"):
            require(len(run.stdout.splitlines()) == 2 and b"ordinary" not in run.stdout,
                    "real list filter/count changed")
            require(b"refs/heads/session/seed" in run.stdout and b"session-detached    " in run.stdout,
                    "real list branch/detached handling changed")
        business = {"refs": {normalize(key): value for key, value in after_refs.items()},
                    "worktree_porcelain": normalize(porcelain)}
    after = snapshot(root, normalize, real)
    effects = {key: after.get(key) for key in sorted(before.keys() | after.keys())
               if before.get(key) != after.get(key)}
    if new_path is None:
        require(not effects, f"read-only/early error caused filesystem changes: {effects}")
    elif not real:
        require(set(effects) == {"repo/.worktrees"}, f"fake new caused unexpected effects: {effects}")
    elif case["exit"] != 0:
        require(set(effects) == {"repo/.worktrees"}, f"failed real new caused unexpected effects: {effects}")
    else:
        relative_path = normalize(str(new_path.relative_to(root)))
        require(set(effects) == {"repo/.worktrees", relative_path,
                                relative_path + "/.git", relative_path + "/fixture.txt"},
                f"real new caused unexpected checkout effects: {effects}")
    normalized_calls = json.loads(normalize(json.dumps(calls)))
    stdout = run.stdout.replace(slug.encode(), (prefix + "<validated-unix>").encode()) if timestamp is not None else run.stdout
    stderr = run.stderr.replace(slug.encode(), (prefix + "<validated-unix>").encode()) if timestamp is not None else run.stderr
    comparable = (run.returncode, stdout, stderr, effects, normalized_calls, business)
    return comparable, {"exit_code": run.returncode, "stdout_sha256": digest(run.stdout),
                        "stderr_sha256": digest(run.stderr), "compared_stdout_sha256": digest(stdout),
                        "compared_stderr_sha256": digest(stderr), "effects": effects,
                        "git_calls": normalized_calls, "git_business_state": business,
                        "invocation_start_unix": start, "invocation_end_unix": end,
                        "validated_slug_timestamp": timestamp}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    binaries = [args.baseline.resolve(), args.candidate.resolve()]
    guarded_files = [*binaries, Path(__file__)]
    hashes_before = [digest(path.read_bytes()) for path in guarded_files]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix="worktree-session-parity-", dir=args.output.parent) as temp:
        root = Path(temp).resolve()
        for case in cases(root):
            record = {"case": case["name"], "backend": case["backend"], "argv": ["agent-bridge", *case["args"]],
                      "evidence_type": "validated_slug_cli_and_git_effect" if "name_part" in case else "exact_cli_and_fixture_effect"}
            try:
                baseline, baseline_evidence = execute(binaries[0], root, case)
                candidate, candidate_evidence = execute(binaries[1], root, case)
                record.update(equal=baseline == candidate, baseline=baseline_evidence, candidate=candidate_evidence)
                if not record["equal"]:
                    record["component_equal"] = [a == b for a, b in zip(baseline, candidate)]
            except (AssertionError, OSError, subprocess.TimeoutExpired, ValueError) as error:
                record.update(equal=False, error=str(error))
            records.append(record)
            if not record["equal"]:
                print(case["name"], "FAIL", record.get("error", record.get("component_equal")))
    hashes_after = [digest(path.read_bytes()) for path in guarded_files]
    report = {"schema": "agent_bridge.worktree_session_cli_parity.v1",
              "baseline_sha256": hashes_before[0], "candidate_sha256": hashes_before[1],
              "script_sha256": hashes_before[2], "inputs_unchanged_during_comparison": hashes_before == hashes_after,
              "passed": sum(record["equal"] for record in records), "total": len(records),
              "scope": "CLI bytes; only validated new slug normalized; fake Git argv/effects and real Git refs/worktrees/contents",
              "excluded": ["real user repositories/configuration/hooks", "Git index/database byte equivalence",
                           "same-second real Git collision timing", "cross-stream wall-clock ordering"], "cases": records}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{report['total']} WorktreeSession CLI parity cases passed")
    return 0 if report["passed"] == report["total"] and report["inputs_unchanged_during_comparison"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
