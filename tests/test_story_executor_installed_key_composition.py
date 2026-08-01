import importlib.util
import inspect
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/story_executor_installed_key_composition.py"
BASE_TEST = ROOT / "tests/test_story_executor_secure_runtime_composition.py"
BINDING = ROOT / "scripts/story_executor_posix_runtime_binding.py"


def load(path: Path, name: str):
    assert path.exists(), f"missing module:{path}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    base_test = load(BASE_TEST, "s613_base_fixture")
    _base, contract, envelope, key, request = base_test.fixture()
    return contract, envelope, key, request


def test_public_entrypoint_has_no_key_or_path_override_parameters():
    module = load(MODULE, "s613")
    signature = inspect.signature(module.prepare_installed_secure_bounded_render)
    assert list(signature.parameters) == ["execution_contract", "envelope", "request"]
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY
               for parameter in signature.parameters.values())


def test_public_entrypoint_loads_envelope_key_id_and_clears_context(monkeypatch):
    module = load(MODULE, "s613")
    binding = load(BINDING, "s613_binding")
    contract, envelope, key, request = fixture()
    loaded = binding.LoadedAuthorityKey(envelope["key_id"], key)
    requested = []

    class FakeBinding:
        @staticmethod
        def load_installed_authority_key(key_id):
            requested.append(key_id)
            return loaded

        @staticmethod
        def secure_nonce_store_path():
            return Path(
                "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")

    monkeypatch.setattr(module, "_load_binding", lambda: FakeBinding)
    prepared = module.prepare_installed_secure_bounded_render(
        execution_contract=contract, envelope=envelope, request=request)
    assert requested == [envelope["key_id"]]
    assert loaded.cleared is True
    assert prepared["authority_verifier"](prepared["authorization"]) is True
    assert prepared["nonce_store_path"] == Path(
        "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")


def test_public_entrypoint_rejects_missing_key_id_before_loading(monkeypatch):
    module = load(MODULE, "s613")
    contract, envelope, _key, request = fixture()
    envelope.pop("key_id")
    called = []
    monkeypatch.setattr(module, "_load_binding", lambda: called.append(True))
    with pytest.raises(ValueError, match="key_id"):
        module.prepare_installed_secure_bounded_render(
            execution_contract=contract, envelope=envelope, request=request)
    assert called == []


def test_public_entrypoint_rejects_malformed_envelope_before_loading(monkeypatch):
    module = load(MODULE, "s613")
    contract, envelope, _key, request = fixture()
    envelope["mac_sha256"] = "not-hex"
    called = []
    monkeypatch.setattr(module, "_load_binding", lambda: called.append(True))
    with pytest.raises(ValueError, match="envelope"):
        module.prepare_installed_secure_bounded_render(
            execution_contract=contract, envelope=envelope, request=request)
    assert called == []


def test_loaded_key_context_clears_when_preparation_rejects_request(monkeypatch):
    module = load(MODULE, "s613")
    binding = load(BINDING, "s613_binding_failure")
    contract, envelope, key, request = fixture()
    loaded = binding.LoadedAuthorityKey(envelope["key_id"], key)

    class FakeBinding:
        @staticmethod
        def load_installed_authority_key(_key_id):
            return loaded

    monkeypatch.setattr(module, "_load_binding", lambda: FakeBinding)
    with pytest.raises(ValueError, match="effects"):
        module.prepare_installed_secure_bounded_render(
            execution_contract=contract, envelope=envelope,
            request=dict(request, playback=True))
    assert loaded.cleared is True


def test_loaded_key_context_clears_when_mac_is_rejected(monkeypatch):
    module = load(MODULE, "s613_mac_failure")
    binding = load(BINDING, "s613_binding_mac_failure")
    contract, envelope, key, request = fixture()
    loaded = binding.LoadedAuthorityKey(envelope["key_id"], key)
    envelope["mac_sha256"] = "0" * 64

    class FakeBinding:
        @staticmethod
        def load_installed_authority_key(_key_id):
            return loaded

    monkeypatch.setattr(module, "_load_binding", lambda: FakeBinding)
    with pytest.raises(ValueError, match="MAC"):
        module.prepare_installed_secure_bounded_render(
            execution_contract=contract, envelope=envelope, request=request)
    assert loaded.cleared is True


def test_key_is_cleared_before_non_secret_preparation(monkeypatch):
    module = load(MODULE, "s613_clear_order")
    binding = load(BINDING, "s613_binding_clear_order")
    contract, envelope, key, request = fixture()
    loaded = binding.LoadedAuthorityKey(envelope["key_id"], key)
    observed = []
    context = object()
    nonce_path = Path(
        "/home/pallasting/.agent-bridge-secure/story-render/story-render-nonces.sqlite3")

    class FakeBinding:
        @staticmethod
        def load_installed_authority_key(_key_id):
            return loaded

        @staticmethod
        def secure_nonce_store_path():
            return nonce_path

    class FakeComposition:
        @staticmethod
        def _build_authority_verifier_context_with_key(**_kwargs):
            observed.append(("build", loaded.cleared))
            return context

        @staticmethod
        def _prepare_secure_bounded_render_with_authority_verifier_context(
                *, authority_verifier_context, **_kwargs):
            observed.append(("finish", loaded.cleared,
                             authority_verifier_context is context))
            return {"nonce_store_path": nonce_path}

    monkeypatch.setattr(module, "_load_binding", lambda: FakeBinding)
    monkeypatch.setattr(module, "_load_composition", lambda: FakeComposition)
    module.prepare_installed_secure_bounded_render(
        execution_contract=contract, envelope=envelope, request=request)
    assert observed == [("build", False), ("finish", True, True)]


def test_fixed_installed_key_is_present_after_authorized_installation():
    key_path = Path(
        "/home/pallasting/.agent-bridge-secure/story-render/authority-keys.v1.json")
    assert key_path.is_file()


def test_source_has_no_executor_invocation_cli_or_key_path_override():
    source = MODULE.read_text()
    assert "execute_bounded_render" not in source
    assert "os.environ" not in source
    assert "sqlite3" not in source
    assert 'if __name__ == "__main__"' not in source
    assert "key_path" not in source
