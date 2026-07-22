"""Offline safety checks for the T22-A0 owner-gated tool acquirer."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_acquire_pinned_tools_v1.py"
spec = importlib.util.spec_from_file_location("t22acquire", SOURCE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

pins = json.loads(module.PINS_PATH.read_text())
module.validate_pins(pins)


def expect_rejected(candidate: dict) -> None:
    try:
        module.validate_pins(candidate)
    except (AssertionError, KeyError, TypeError, ValueError):
        return
    raise AssertionError("unsafe public-tool pin mutation admitted")


mutations = []
for mutation in (
    lambda x: x.update(schema="other"),
    lambda x: x.update(purpose="PRODUCTION"),
    lambda x: x["platform"].update(os="windows"),
    lambda x: x["network_policy"].update(default="ALLOW"),
    lambda x: x["tools"].reverse(),
    lambda x: x["tools"].pop(),
    lambda x: x["tools"][0].update(archive_format="zip"),
    lambda x: x["tools"][0].update(maximum_download_bytes=1024 * 1024 * 1024),
    lambda x: x["tools"][0].update(artifact_size_bytes=0),
    lambda x: x["tools"][0].update(maximum_download_bytes=x["tools"][0]["artifact_size_bytes"] - 1),
    lambda x: x["tools"][0].update(artifact_url="http://github.com/example"),
    lambda x: x["tools"][0].update(checksum_sha256="0"),
    lambda x: x["tools"][0]["installed_binaries"][0].update(output_name="../etcd"),
    lambda x: x["tools"][1]["installed_binaries"][0].update(output_name="etcd"),
    lambda x: x["claims"].update(owner_signature_verified=True),
):
    candidate = copy.deepcopy(pins)
    mutation(candidate)
    expect_rejected(candidate)
    mutations.append(candidate)


class NetworkForbidden:
    def __call__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network construction attempted before owner authorization")


original_build_opener = module.urllib.request.build_opener
module.urllib.request.build_opener = NetworkForbidden()
try:
    status = module.status()
    assert status["status"] == "BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED"
    assert status["network_attempted"] is False
    assert status["owner_signature_verified"] is False
    assert status["release_artifacts_downloaded"] is False
    try:
        module.acquire(Path("/missing-payload"), Path("/missing-signature"), Path("/tmp/not-authorized"))
    except (AssertionError, FileNotFoundError):
        pass
    else:
        raise AssertionError("acquire admitted without an exact owner signature")
finally:
    module.urllib.request.build_opener = original_build_opener


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    checksum = root / "checksums.txt"
    checksum.write_text("a" * 64 + "  artifact\n")
    assert module.checksum_document_entry(checksum, "artifact") == "a" * 64
    checksum.write_text("a" * 64 + "  artifact\n" + "b" * 64 + "  artifact\n")
    try:
        module.checksum_document_entry(checksum, "artifact")
    except AssertionError:
        pass
    else:
        raise AssertionError("duplicate checksum entry admitted")

    class SyntheticResponse(io.BytesIO):
        def __init__(self, content: bytes, announced: int | None):
            super().__init__(content)
            self.headers = {} if announced is None else {"Content-Length": str(announced)}

        def geturl(self) -> str:
            return "https://release-assets.githubusercontent.com/synthetic"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    class SyntheticOpener:
        def __init__(self, content: bytes, announced: int | None):
            self.content = content
            self.announced = announced

        def open(self, *_args, **_kwargs):
            return SyntheticResponse(self.content, self.announced)

    exact = root / "exact-artifact"
    module.download(
        SyntheticOpener(b"abc", 3), "https://github.com/synthetic", exact, 4, 3,
    )
    assert exact.read_bytes() == b"abc"
    for name, opener in (
        ("announced-size-drift", SyntheticOpener(b"abc", 4)),
        ("streamed-size-drift", SyntheticOpener(b"ab", None)),
    ):
        try:
            module.download(opener, "https://github.com/synthetic", root / name, 4, 3)
        except AssertionError:
            continue
        raise AssertionError("artifact byte-size drift admitted")

    archive = root / "safe.tar.gz"
    content = b"synthetic executable"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("bundle/tool")
        info.size = len(content)
        bundle.addfile(info, io.BytesIO(content))
    binary_root = root / "bin"
    binary_root.mkdir()
    installed = module.install_tar_binaries(
        archive, [{"archive_member": "tool", "output_name": "tool"}], binary_root,
    )
    assert installed[0]["sha256"] == module.hashlib.sha256(content).hexdigest()
    assert (binary_root / "tool").stat().st_mode & 0o111

    artifact_root = root / "artifact-root"
    artifact_root.mkdir()
    cache = artifact_root / ("tools.authorization-" + "a" * 12)
    cache.mkdir()
    (cache / "downloads").mkdir()
    pins_sha256 = module.hashlib.sha256(module.PINS_PATH.read_bytes()).hexdigest()
    cache_receipt = {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.pinned_tool_acquisition_receipt.v1",
        "status": "PINNED_PUBLIC_RELEASE_TOOLS_ACQUIRED",
        "owner_authorization_content_sha256": "b" * 64,
        "source_commit": "c" * 40,
        "pins_sha256": pins_sha256,
        "production_admissible": False,
    }
    receipt_path = cache / "acquisition-receipt.json"
    receipt_path.write_bytes(module.canonical(cache_receipt) + b"\n")
    assert module.validate_cache_source(cache, artifact_root, pins_sha256) == module.sha256_file(receipt_path)
    try:
        module.validate_cache_source(artifact_root / "tools", artifact_root, pins_sha256)
    except AssertionError:
        pass
    else:
        raise AssertionError("unbound cache directory name admitted")
    cache_receipt["pins_sha256"] = "0" * 64
    receipt_path.write_bytes(module.canonical(cache_receipt) + b"\n")
    try:
        module.validate_cache_source(cache, artifact_root, pins_sha256)
    except AssertionError:
        pass
    else:
        raise AssertionError("cache receipt with wrong pins admitted")
    cached = root / "cached"
    cached.write_bytes(b"exact cached release")
    copied = root / "copied"
    module.copy_exact_cached_file(
        cached, copied, cached.stat().st_size, module.sha256_file(cached),
    )
    assert copied.read_bytes() == cached.read_bytes()
    try:
        module.copy_exact_cached_file(cached, root / "wrong-copy", cached.stat().st_size, "0" * 64)
    except AssertionError:
        pass
    else:
        raise AssertionError("cache artifact with wrong hash admitted")

authorization = module.load_authorization_module()
assert authorization.ANCHOR_PATH.is_file()
authorization.validate_anchor(
    json.loads(authorization.ANCHOR_PATH.read_text()),
    json.loads(authorization.PROPOSAL_PATH.read_text()),
)
print("t22_a0_pinned_tool_acquisition_check\tpass")
print(f"directed_negative_test_count\t{len(mutations) + 9}")
print("network_attempted\tfalse")
print("release_artifacts_downloaded\tfalse")
