import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).parents[1] / "scripts" / "qwen3_lan_remote_synth.py"
SPEC = importlib.util.spec_from_file_location("qwen3_lan_remote_synth", SCRIPT)
REMOTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REMOTE)


def make_args(tmp_path):
    return SimpleNamespace(text="你好; $(unsafe)", output=tmp_path / "speech.wav",
                           speaker="serena", instruct="自然")


def configure(monkeypatch, tmp_path):
    monkeypatch.setenv("AB_QWEN3_LAN_REMOTE_HOST", "pallasting@192.168.1.2")
    monkeypatch.setenv("AB_QWEN3_LAN_REMOTE_PYTHON", "/venv/bin/python")
    monkeypatch.setenv("AB_QWEN3_LAN_WORKER_SOCKET", "/tmp/worker.sock")
    monkeypatch.setenv("AB_QWEN3_LAN_HOST_KEY_ALIAS", "192.168.1.2")
    monkeypatch.setenv("AB_QWEN3_LAN_LOCK", str(tmp_path / "lock"))


def test_dispatch_sends_text_in_stdin_and_cleans_remote(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "ssh" and "-c" not in command[-2:]:
            request = json.loads(kwargs["input"])
            assert request["text"] == "你好; $(unsafe)"
            assert request["text"] not in " ".join(command)
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "ok": True, "backend": "qwen3", "output": request["output"],
                "device": "mps", "dtype": "float16",
            }), stderr="")
        if command[0] == "scp":
            Path(command[-1]).write_bytes(b"RIFFfake")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(REMOTE.subprocess, "run", fake_run)
    receipt = REMOTE.dispatch(make_args(tmp_path))
    assert make_args(tmp_path).output.read_bytes() == b"RIFFfake"
    assert receipt["backend"] == "qwen3-lan"
    assert receipt["execution_transport"] == "ssh"
    assert receipt["remote_cleanup_attempted"] is True
    assert len(calls) == 3


def test_dispatch_rejects_unexpected_remote_output(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)

    def fake_run(command, **kwargs):
        if command[0] == "ssh" and "-c" not in command[-2:]:
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "ok": True, "output": "/tmp/other.wav",
            }), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(REMOTE.subprocess, "run", fake_run)
    try:
        REMOTE.dispatch(make_args(tmp_path))
    except RuntimeError as exc:
        assert "unexpected output path" in str(exc)
    else:
        raise AssertionError("unexpected remote output was accepted")


def test_dispatch_fails_fast_when_busy(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setattr(REMOTE.fcntl, "flock",
                        lambda *unused: (_ for _ in ()).throw(BlockingIOError()))
    try:
        REMOTE.dispatch(make_args(tmp_path))
    except RuntimeError as exc:
        assert "busy" in str(exc)
    else:
        raise AssertionError("busy remote lock was accepted")


def test_health_uses_explicit_host_key_alias(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        request = json.loads(kwargs["input"])
        assert request["op"] == "health"
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "ok": True, "protocol": "ab.tts.worker.v1", "device": "mps",
        }), stderr="")

    monkeypatch.setattr(REMOTE.subprocess, "run", fake_run)
    receipt = REMOTE.health(make_args(tmp_path))
    assert receipt["device"] == "mps"
    assert "HostKeyAlias=192.168.1.2" in calls[0][0]


def test_rejects_unsafe_host(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("AB_QWEN3_LAN_REMOTE_HOST", "-oProxyCommand=unsafe")
    try:
        REMOTE.dispatch(make_args(tmp_path))
    except ValueError as exc:
        assert "safe SSH destination" in str(exc)
    else:
        raise AssertionError("unsafe host was accepted")
