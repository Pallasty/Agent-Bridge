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

authorization = module.load_authorization_module()
assert authorization.ANCHOR_PATH.is_file()
authorization.validate_anchor(
    json.loads(authorization.ANCHOR_PATH.read_text()),
    json.loads(authorization.PROPOSAL_PATH.read_text()),
)
print("t22_a0_pinned_tool_acquisition_check\tpass")
print(f"directed_negative_test_count\t{len(mutations) + 3}")
print("network_attempted\tfalse")
print("release_artifacts_downloaded\tfalse")
