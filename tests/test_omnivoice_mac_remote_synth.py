import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).parents[1] / "scripts" / "omnivoice_mac_remote_synth.py"
SPEC = importlib.util.spec_from_file_location("omnivoice_mac_remote_synth", SCRIPT)
REMOTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REMOTE)


def args(tmp_path):
    return SimpleNamespace(text="你好; $(unsafe)", output=tmp_path / "speech.wav",
                           manifest=Path("/remote/manifest.json"))


def test_dispatch_requires_explicit_remote_configuration(monkeypatch, tmp_path):
    for name in ("AB_OMNIVOICE_MAC_REMOTE_HOST", "AB_OMNIVOICE_MAC_REMOTE_PYTHON",
                 "AB_OMNIVOICE_MAC_REMOTE_ADAPTER"):
        monkeypatch.delenv(name, raising=False)
    try:
        REMOTE.dispatch(args(tmp_path))
    except ValueError as exc:
        assert "AB_OMNIVOICE_MAC_REMOTE_HOST" in str(exc)
    else:
        raise AssertionError("missing remote configuration was accepted")


def test_dispatch_sends_text_only_in_stdin_json(monkeypatch, tmp_path):
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_HOST", "mac.example")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_PYTHON", "/venv/bin/python")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_ADAPTER", "/repo/scripts/remote.py")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_LOCK", str(tmp_path / "lock"))
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "ssh" and "--worker" in command[-1]:
            request = json.loads(kwargs["input"])
            assert request["text"] == "你好; $(unsafe)"
            assert request["text"] not in " ".join(command)
            remote_output = str(REMOTE.checked_job_dir(request["job_id"]) / "speech.wav")
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "ok": True, "backend": "omnivoice", "remote_output": remote_output,
                "remote_job_id": request["job_id"], "hashes_verified": True,
            }), stderr="")
        if command[0] == "scp":
            Path(command[-1]).write_bytes(b"RIFFfake")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(REMOTE.subprocess, "run", fake_run)
    receipt = REMOTE.dispatch(args(tmp_path))
    assert args(tmp_path).output.read_bytes() == b"RIFFfake"
    assert receipt["execution_transport"] == "ssh"
    assert receipt["remote_cleanup_attempted"] is True
    assert len(calls) == 3


def test_dispatch_fails_fast_when_mac_lock_is_busy(monkeypatch, tmp_path):
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_HOST", "mac.example")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_PYTHON", "/venv/bin/python")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_ADAPTER", "/repo/scripts/remote.py")
    monkeypatch.setenv("AB_OMNIVOICE_MAC_REMOTE_LOCK", str(tmp_path / "lock"))
    monkeypatch.setattr(REMOTE.fcntl, "flock", lambda *unused: (_ for _ in ()).throw(BlockingIOError()))
    try:
        REMOTE.dispatch(args(tmp_path))
    except RuntimeError as exc:
        assert "Mac is busy" in str(exc)
    else:
        raise AssertionError("busy remote lock was accepted")


def test_cleanup_rejects_non_job_paths():
    try:
        REMOTE.cleanup("../../danger")
    except ValueError as exc:
        assert "invalid remote job id" in str(exc)
    else:
        raise AssertionError("unsafe cleanup path was accepted")
