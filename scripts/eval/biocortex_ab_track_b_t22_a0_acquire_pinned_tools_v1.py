"""Acquire T22-A0 lab binaries only after exact owner authorization.

The status path is intentionally offline. The acquire path verifies the owner
SSHSIG, expiry, source commit, repository cleanliness, manifest pins, release
checksum documents, archive members, and the exact artifact-root destination
before any installed binary becomes visible.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PINS_PATH = ROOT / "docs/design/fixtures/biocortex-ab-track-b-t22-a0-public-tool-pins-v1.json"
AUTH_SOURCE = ROOT / "scripts/eval/biocortex_ab_track_b_t22_a0_owner_authorization_v1.py"
ALLOWED_INITIAL_HOSTS = frozenset({"github.com"})
ALLOWED_REDIRECT_HOSTS = frozenset({"github.com", "release-assets.githubusercontent.com"})
CHECKSUM_MAXIMUM_BYTES = 2 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


def load_authorization_module():
    spec = importlib.util.spec_from_file_location("t22_a0_owner_authorization", AUTH_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_https_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urllib.parse.urlsplit(url)
    assert parsed.scheme == "https"
    assert parsed.hostname in allowed_hosts
    assert parsed.username is None and parsed.password is None and parsed.port in (None, 443)
    assert not parsed.fragment


def validate_pins(pins: dict) -> None:
    assert pins["schema"] == "agent_bridge.biocortex.track_b.t22_a0.public_tool_pins.v1"
    assert pins["purpose"] == "OWNER_AUTHORIZED_SINGLE_HOST_REAL_PROCESS_PILOT_ONLY"
    assert pins["platform"] == {"os": "linux", "architecture": "amd64"}
    assert pins["network_policy"] == {
        "default": "DENY",
        "authorization_required": "VERIFIED_UNEXPIRED_T22_A0_OWNER_SSHSIG",
        "allowed_release_host": "github.com",
        "allowed_redirect_host": "release-assets.githubusercontent.com",
    }
    assert [tool["name"] for tool in pins["tools"]] == ["etcd", "openbao", "toxiproxy"]
    output_names: list[str] = []
    for tool in pins["tools"]:
        assert tool["archive_format"] in {"tar.gz", "raw"}
        assert 0 < tool["maximum_download_bytes"] <= 128 * 1024 * 1024
        assert len(tool["artifact_sha256"]) == len(tool["checksum_sha256"]) == 64
        assert all(character in "0123456789abcdef" for character in tool["artifact_sha256"] + tool["checksum_sha256"])
        validate_https_url(tool["release_url"], ALLOWED_INITIAL_HOSTS)
        validate_https_url(tool["checksum_url"], ALLOWED_INITIAL_HOSTS)
        validate_https_url(tool["artifact_url"], ALLOWED_INITIAL_HOSTS)
        assert PurePosixPath(tool["artifact_name"]).name == tool["artifact_name"]
        assert PurePosixPath(urllib.parse.urlsplit(tool["artifact_url"]).path).name == tool["artifact_name"]
        for binary in tool["installed_binaries"]:
            assert PurePosixPath(binary["archive_member"]).is_absolute() is False
            assert ".." not in PurePosixPath(binary["archive_member"]).parts
            assert PurePosixPath(binary["output_name"]).name == binary["output_name"]
            output_names.append(binary["output_name"])
    assert len(output_names) == len(set(output_names))
    assert set(output_names) == {"etcd", "etcdctl", "bao", "toxiproxy-server"}
    assert pins["claims"] == {
        "release_artifacts_downloaded": False,
        "owner_signature_verified": False,
        "real_process_execution_authorized": False,
        "production_admissible": False,
    }


def current_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def require_clean_tracked_tree() -> None:
    subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=True)


def verify_authorization(payload_path: Path, signature_path: Path) -> tuple[dict, object]:
    authorization = load_authorization_module()
    proposal = json.loads(authorization.PROPOSAL_PATH.read_text())
    anchor = json.loads(authorization.ANCHOR_PATH.read_text())
    payload = json.loads(payload_path.read_text())
    public_key = authorization.validate_payload(payload, anchor, proposal, datetime.now(timezone.utc))
    authorization.verify_signature(payload_path, signature_path, public_key)
    assert payload["source_commit"] == current_commit()
    assert payload["artifact_root"] == proposal["scope"]["artifact_root"]
    assert "HASH_PINNED_PUBLIC_RELEASE_DOWNLOAD" in payload["allowed_after_signature"]
    require_clean_tracked_tree()
    return payload, authorization


class RestrictedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validate_https_url(newurl, ALLOWED_REDIRECT_HOSTS)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(opener, url: str, output: Path, maximum_bytes: int) -> None:  # noqa: ANN001
    validate_https_url(url, ALLOWED_INITIAL_HOSTS)
    request = urllib.request.Request(url, headers={"User-Agent": "agent-bridge-t22-a0/1"})
    written = 0
    with opener.open(request, timeout=30) as response, output.open("xb") as handle:
        validate_https_url(response.geturl(), ALLOWED_REDIRECT_HOSTS)
        length = response.headers.get("Content-Length")
        if length is not None:
            assert 0 <= int(length) <= maximum_bytes
        while True:
            chunk = response.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            written += len(chunk)
            assert written <= maximum_bytes
            handle.write(chunk)
    assert written > 0


def checksum_document_entry(document: Path, artifact_name: str) -> str:
    matches: list[str] = []
    for raw_line in document.read_text().splitlines():
        fields = raw_line.strip().split()
        if len(fields) == 2 and fields[1].lstrip("*") == artifact_name:
            matches.append(fields[0])
    assert len(matches) == 1
    assert len(matches[0]) == 64 and all(character in "0123456789abcdef" for character in matches[0])
    return matches[0]


def write_executable(source, output: Path) -> str:  # noqa: ANN001
    digest = hashlib.sha256()
    with output.open("xb") as handle:
        while True:
            chunk = source.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            handle.write(chunk)
    assert output.stat().st_size > 0
    output.chmod(0o755)
    return digest.hexdigest()


def install_tar_binaries(archive: Path, specifications: list[dict], binary_root: Path) -> list[dict]:
    installed: list[dict] = []
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        for specification in specifications:
            requested = specification["archive_member"]
            candidates = [member for member in members if member.name == requested and member.isfile()]
            if not candidates and "/" not in requested:
                candidates = [
                    member for member in members
                    if PurePosixPath(member.name).name == requested and member.isfile()
                ]
            assert len(candidates) == 1
            member = candidates[0]
            assert not member.issym() and not member.islnk() and not member.isdev()
            source = bundle.extractfile(member)
            assert source is not None
            output = binary_root / specification["output_name"]
            binary_hash = write_executable(source, output)
            installed.append({"name": output.name, "sha256": binary_hash, "bytes": output.stat().st_size})
    return installed


def install_tool(tool: dict, artifact: Path, binary_root: Path) -> list[dict]:
    if tool["archive_format"] == "tar.gz":
        return install_tar_binaries(artifact, tool["installed_binaries"], binary_root)
    assert tool["archive_format"] == "raw" and len(tool["installed_binaries"]) == 1
    specification = tool["installed_binaries"][0]
    assert specification["archive_member"] == tool["artifact_name"]
    output = binary_root / specification["output_name"]
    with artifact.open("rb") as source:
        binary_hash = write_executable(source, output)
    return [{"name": output.name, "sha256": binary_hash, "bytes": output.stat().st_size}]


def validate_exact_destination(destination: Path, payload: dict) -> tuple[Path, Path]:
    artifact_root = Path(payload["artifact_root"])
    expected = artifact_root / "tools"
    assert destination == expected and destination.is_absolute()
    assert not destination.exists()
    for parent in reversed(destination.parents):
        if parent.exists():
            assert not parent.is_symlink()
    return artifact_root, expected


def acquire(payload_path: Path, signature_path: Path, destination: Path) -> dict:
    # This is the sole transition from offline validation to network access.
    payload, _authorization = verify_authorization(payload_path, signature_path)
    pins = json.loads(PINS_PATH.read_text())
    validate_pins(pins)
    artifact_root, destination = validate_exact_destination(destination, payload)
    artifact_root.mkdir(parents=True, exist_ok=True)
    assert not artifact_root.is_symlink()
    stage = Path(tempfile.mkdtemp(prefix=".t22-a0-tools-", dir=artifact_root))
    try:
        downloads = stage / "downloads"
        binaries = stage / "bin"
        downloads.mkdir(mode=0o700)
        binaries.mkdir(mode=0o700)
        opener = urllib.request.build_opener(RestrictedRedirectHandler())
        evidence: list[dict] = []
        installed: list[dict] = []
        for tool in pins["tools"]:
            checksum = downloads / f"{tool['name']}-checksums.txt"
            artifact = downloads / tool["artifact_name"]
            download(opener, tool["checksum_url"], checksum, CHECKSUM_MAXIMUM_BYTES)
            assert sha256_file(checksum) == tool["checksum_sha256"]
            assert checksum_document_entry(checksum, tool["artifact_name"]) == tool["artifact_sha256"]
            download(opener, tool["artifact_url"], artifact, tool["maximum_download_bytes"])
            assert sha256_file(artifact) == tool["artifact_sha256"]
            tool_binaries = install_tool(tool, artifact, binaries)
            installed.extend(tool_binaries)
            evidence.append({
                "name": tool["name"], "version": tool["version"],
                "checksum_sha256": tool["checksum_sha256"],
                "artifact_name": tool["artifact_name"],
                "artifact_sha256": tool["artifact_sha256"],
                "artifact_bytes": artifact.stat().st_size,
            })
        receipt = {
            "schema": "agent_bridge.biocortex.track_b.t22_a0.pinned_tool_acquisition_receipt.v1",
            "status": "PINNED_PUBLIC_RELEASE_TOOLS_ACQUIRED",
            "owner_authorization_content_sha256": payload["content_sha256"],
            "source_commit": payload["source_commit"],
            "pins_sha256": hashlib.sha256(PINS_PATH.read_bytes()).hexdigest(),
            "acquired_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tools": evidence,
            "installed_binaries": installed,
            "production_admissible": False,
        }
        (stage / "acquisition-receipt.json").write_bytes(canonical(receipt) + b"\n")
        stage.rename(destination)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def status() -> dict:
    pins = json.loads(PINS_PATH.read_text())
    validate_pins(pins)
    authorization_status = load_authorization_module().status()
    authorized = authorization_status["real_process_execution_authorized"] is True
    return {
        "schema": "agent_bridge.biocortex.track_b.t22_a0.pinned_tool_acquisition_status.v1",
        "status": "READY_FOR_EXACT_SIGNED_RECEIPT" if authorized else "BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED",
        "pins_sha256": hashlib.sha256(PINS_PATH.read_bytes()).hexdigest(),
        "tool_versions": {tool["name"]: tool["version"] for tool in pins["tools"]},
        "network_attempted": False,
        "owner_signature_verified": False,
        "release_artifacts_downloaded": False,
        "real_process_execution_authorized": False,
        "production_admissible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    acquire_parser = subcommands.add_parser("acquire")
    acquire_parser.add_argument("--payload", type=Path, required=True)
    acquire_parser.add_argument("--signature", type=Path, required=True)
    acquire_parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "status":
        print(json.dumps(status(), sort_keys=True, separators=(",", ":")))
        return
    receipt = acquire(arguments.payload, arguments.signature, arguments.destination)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
