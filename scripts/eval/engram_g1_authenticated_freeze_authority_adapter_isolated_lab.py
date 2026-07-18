#!/usr/bin/env python3
"""Synthetic-only G1 authenticated-freeze adapter implementation gate.

This module is an isolated laboratory, not a production adapter.  It accepts
only explicitly enabled public known-answer fixtures marked ``SYNTHETIC_KAT``.
It has no MCP/runtime registration, no network/provider path, no real trust
root, and no authority-bearing output.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import sqlite3
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, NoReturn, Optional, Sequence


MODE = "SYNTHETIC_KAT"
IMPLEMENTATION_VERSION = (
    "engram_g1_authenticated_freeze_authority_adapter_isolated_lab_v0"
)
CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "isolated_lab_contract.v0"
)
CONTRACT_ID = "engram_g1_authenticated_freeze_authority_adapter_isolated_lab_20260718"
CONTRACT_SHA256 = "f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14"
PREREGISTRATION_COMMIT = "632918db75f65030d3ac15bc991b51a9c938cba6"
PREREGISTRATION_CONTRACT_SHA256 = (
    "a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0"
)
PREREGISTRATION_VALIDATOR_SHA256 = (
    "632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde"
)
PREREGISTRATION_CHECKER_SHA256 = (
    "ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29"
)
G1_3_COMMIT = "7062869196d1a3ff8bb72572a39700e65130cde4"
G1_3_CONTRACT_SHA256 = (
    "5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504"
)
G1_3_VALIDATOR_SHA256 = (
    "0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089"
)
G1_3_CHECKER_SHA256 = "e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39"

ENVELOPE_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "synthetic_envelope.v0"
)
SIGNATURE_BUNDLE_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "synthetic_signature_bundle.v0"
)
TIME_CHECKPOINT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "synthetic_time_checkpoint.v0"
)
MANIFEST_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "synthetic_manifest_kat.v0"
)
PACKET_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "synthetic_role_packet_kat.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "isolated_lab_receipt.v0"
)
CAPABILITY_SCHEMA = (
    "agent_bridge.engram_g1_authenticated_freeze_authority_" "synthetic_capability.v0"
)

ROLES = (
    "application_owner",
    "independence_auditor",
    "freeze_reviewer_1",
    "freeze_reviewer_2",
    "sealed_evaluator_custodian",
)
ROLE_DOMAINS = {
    "application_owner": (
        "agent-bridge/engram/g1/authenticated-freeze-authority/" "application-owner/v0"
    ),
    "independence_auditor": (
        "agent-bridge/engram/g1/authenticated-freeze-authority/"
        "independence-auditor/v0"
    ),
    "freeze_reviewer_1": (
        "agent-bridge/engram/g1/authenticated-freeze-authority/" "freeze-reviewer-1/v0"
    ),
    "freeze_reviewer_2": (
        "agent-bridge/engram/g1/authenticated-freeze-authority/" "freeze-reviewer-2/v0"
    ),
    "sealed_evaluator_custodian": (
        "agent-bridge/engram/g1/authenticated-freeze-authority/"
        "sealed-evaluator-custodian/v0"
    ),
}
TIME_ROLE = "trusted_time_checkpoint_authority"
TIME_DOMAIN = (
    "agent-bridge/engram/g1/authenticated-freeze-authority/"
    "trusted-time-checkpoint/v0"
)
CAPABILITY_DOMAIN = (
    "agent-bridge/engram/g1/authenticated-freeze-authority/"
    "synthetic-capability-consumer-proof/v0"
)
PRIVATE_DIGEST_DOMAIN = (
    "agent-bridge/engram/g1/authenticated-freeze-authority/"
    "synthetic-private-input/v0"
)

PRIVATE_INPUT_NAMES = (
    "manifest.json",
    "application_owner.packet.json",
    "independence_auditor.packet.json",
    "freeze_reviewer_1.packet.json",
    "freeze_reviewer_2.packet.json",
    "sealed_evaluator_custodian.packet.json",
    "trusted_time_checkpoint.json",
    "envelope.json",
    "signatures.json",
)
BOUND_INPUT_NAMES = PRIVATE_INPUT_NAMES[:7]
MAX_JSON_BYTES = 1_048_576
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 8_192
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 512
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MIN_NONCE_BYTES = 32
MAX_ENVELOPE_AGE_SECS = 86_400
MAX_CLAIM_WINDOW_SECS = 900
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX_32_RE = re.compile(r"^[0-9a-f]{64}$")
HEX_64_RE = re.compile(r"^[0-9a-f]{128}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")

REGISTERED_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/engram_g1_authenticated_freeze_authority_adapter_"
    "isolated_lab_contract_v0.json"
)
PUBLIC_BINDINGS = {
    "preregistration_contract": PREREGISTRATION_CONTRACT_SHA256,
    "preregistration_validator": PREREGISTRATION_VALIDATOR_SHA256,
    "preregistration_checker": PREREGISTRATION_CHECKER_SHA256,
    "g1_3_contract": G1_3_CONTRACT_SHA256,
    "g1_3_validator": G1_3_VALIDATOR_SHA256,
    "g1_3_checker": G1_3_CHECKER_SHA256,
}
PUBLIC_ARTIFACTS = {
    "preregistration_contract": (
        "scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_"
        "adapter_preregistration_contract_v0.json"
    ),
    "preregistration_validator": (
        "scripts/eval/engram_g1_authenticated_freeze_authority_"
        "adapter_preregistration.py"
    ),
    "preregistration_checker": (
        "scripts/check-engram-g1-authenticated-freeze-authority-"
        "adapter-preregistration.sh"
    ),
    "g1_3_contract": (
        "scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json"
    ),
    "g1_3_validator": "scripts/eval/engram_g1_corpus_freeze_review.py",
    "g1_3_checker": "scripts/check-engram-g1-corpus-freeze-review.sh",
}


class IsolatedLabError(RuntimeError):
    """Typed fail-closed rejection from the synthetic implementation gate."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> NoReturn:
    raise IsolatedLabError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _exact_keys(
    value: Any, expected: Iterable[str], code: str, label: str
) -> Mapping[str, Any]:
    _require(type(value) is dict, code, f"{label} must be an object")
    wanted = set(expected)
    actual = set(value)
    _require(
        actual == wanted,
        code,
        f"{label} key closure drift: missing={sorted(wanted - actual)} "
        f"extra={sorted(actual - wanted)}",
    )
    return value


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _domain_sha256(domain: str, raw: bytes) -> str:
    return _sha256(domain.encode("utf-8") + b"\x00" + raw)


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("E_DUPLICATE_JSON_KEY", f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> NoReturn:
    _fail("E_JCS_FLOAT", f"floating-point JSON is outside the frozen profile: {value}")


def _reject_constant(value: str) -> NoReturn:
    _fail("E_JCS_CONSTANT", f"non-finite JSON constant is forbidden: {value}")


def _check_string(value: str, label: str) -> None:
    try:
        value.encode("utf-8")
        value.encode("utf-16-be")
    except UnicodeEncodeError as exc:
        raise IsolatedLabError(
            "E_JCS_UNICODE", f"{label} contains an unpaired surrogate"
        ) from exc


def _check_json_shape(value: Any, depth: int = 1) -> tuple[int, int]:
    _require(depth <= MAX_JSON_DEPTH, "E_JSON_DEPTH", "JSON nesting is too deep")
    if value is None or type(value) is bool:
        return 1, 0
    if type(value) is int:
        _require(
            -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER,
            "E_JCS_INTEGER",
            "integer is outside the IEEE-754 exact safe range",
        )
        return 1, 0
    if type(value) is str:
        _check_string(value, "JSON string")
        return 1, 0
    if type(value) is list:
        _require(
            len(value) <= MAX_ARRAY_ITEMS,
            "E_JSON_ARRAY",
            "JSON array is too large",
        )
        nodes = 1
        for item in value:
            child_nodes, _ = _check_json_shape(item, depth + 1)
            nodes += child_nodes
        _require(nodes <= MAX_JSON_NODES, "E_JSON_NODES", "JSON has too many nodes")
        return nodes, 0
    if type(value) is dict:
        _require(
            len(value) <= MAX_OBJECT_MEMBERS,
            "E_JSON_OBJECT",
            "JSON object has too many members",
        )
        nodes = 1
        for key, item in value.items():
            _require(type(key) is str, "E_JSON_KEY", "JSON object key is not text")
            _check_string(key, "JSON object key")
            child_nodes, _ = _check_json_shape(item, depth + 1)
            nodes += child_nodes
        _require(nodes <= MAX_JSON_NODES, "E_JSON_NODES", "JSON has too many nodes")
        return nodes, len(value)
    _fail("E_JCS_TYPE", f"unsupported JSON value type: {type(value).__name__}")


def _jcs_string(value: str) -> bytes:
    _check_string(value, "JCS string")
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def jcs_bytes(value: Any) -> bytes:
    """Render exact RFC 8785 bytes for the frozen no-float JSON domain."""

    _check_json_shape(value)
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if type(value) is str:
        return _jcs_string(value)
    if type(value) is list:
        return b"[" + b",".join(jcs_bytes(item) for item in value) + b"]"
    if type(value) is dict:
        ordered = sorted(value, key=lambda key: key.encode("utf-16-be"))
        members = (_jcs_string(key) + b":" + jcs_bytes(value[key]) for key in ordered)
        return b"{" + b",".join(members) + b"}"
    _fail("E_JCS_TYPE", "unreachable unsupported JSON type")


def decode_closed_json(raw: bytes, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes, "E_JSON_BYTES", f"{label} must be bytes")
    _require(0 < len(raw) <= MAX_JSON_BYTES, "E_JSON_SIZE", f"{label} size drift")
    _require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", f"{label} has a BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IsolatedLabError("E_JSON_UTF8", f"{label} is not UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except IsolatedLabError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise IsolatedLabError("E_JSON_PARSE", f"{label} is invalid JSON") from exc
    _require(type(value) is dict, "E_JSON_ROOT", f"{label} root must be an object")
    _check_json_shape(value)
    return value


def decode_canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    value = decode_closed_json(raw, label)
    _require(jcs_bytes(value) == raw, "E_JCS_BYTES", f"{label} is not exact RFC 8785")
    return value


def _require_registered_value(actual: Any, expected: Any, path: str) -> None:
    if type(expected) is dict:
        obj = _exact_keys(actual, expected, "E_CONTRACT_SEMANTICS", path)
        for key, expected_value in expected.items():
            _require_registered_value(obj[key], expected_value, f"{path}.{key}")
        return
    if type(expected) is list:
        _require(type(actual) is list, "E_CONTRACT_SEMANTICS", f"{path} type drift")
        _require(
            len(actual) == len(expected),
            "E_CONTRACT_SEMANTICS",
            f"{path} length drift",
        )
        for index, expected_value in enumerate(expected):
            _require_registered_value(actual[index], expected_value, f"{path}[{index}]")
        return
    _require(
        type(actual) is type(expected),
        "E_CONTRACT_SEMANTICS",
        f"{path} type drift",
    )
    _require(actual == expected, "E_CONTRACT_SEMANTICS", f"{path} value drift")


def load_registered_contract() -> tuple[dict[str, Any], bytes]:
    try:
        raw = REGISTERED_CONTRACT_PATH.read_bytes()
    except OSError as exc:
        raise IsolatedLabError(
            "E_CONTRACT_READ", "cannot read registered contract"
        ) from exc
    value = decode_closed_json(raw, "isolated-lab contract")
    _require(_sha256(raw) == CONTRACT_SHA256, "E_CONTRACT_HASH", "contract drift")
    return value, raw


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    expected, _ = load_registered_contract()
    _require_registered_value(value, expected, "contract")
    return value


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    _require(_sha256(raw) == CONTRACT_SHA256, "E_CONTRACT_HASH", "contract byte drift")
    return validate_contract_semantics(value)


# Deterministic RFC 8032 arithmetic copied from the existing Track-B offline
# known-answer double.  It is deliberately test-only and loads no key files.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(value: int) -> int:
    return pow(value, _Q - 2, _Q)


_D = (-121665 * _inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x & 1:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_B = (_xrecover(_BY), _BY)


def _edwards(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = (_D * x1 * x2 * y1 * y2) % _Q
    return (
        (x1 * y2 + x2 * y1) * _inv(1 + product) % _Q,
        (y1 * y2 + x1 * x2) * _inv(1 - product) % _Q,
    )


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    remaining = scalar
    while remaining:
        if remaining & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        remaining >>= 1
    return result


def _encodepoint(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decodepoint(raw: bytes) -> tuple[int, int]:
    _require(len(raw) == 32, "E_ED25519_KEY", "point length drift")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    _require(y < _Q, "E_ED25519_KEY", "point y is noncanonical")
    x = _xrecover(y)
    _require(not (x == 0 and sign == 1), "E_ED25519_KEY", "point sign drift")
    if (x & 1) != sign:
        x = _Q - x
    point = (x, y)
    _require(
        (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0,
        "E_ED25519_KEY",
        "point is not on curve",
    )
    return point


def _hint(raw: bytes) -> int:
    return int.from_bytes(hashlib.sha512(raw).digest(), "little")


@lru_cache(maxsize=64)
def ed25519_public_key(seed: bytes) -> bytes:
    _require(type(seed) is bytes and len(seed) == 32, "E_KAT_SEED", "seed drift")
    digest = hashlib.sha512(seed).digest()
    scalar = 2**254 + sum(
        2**index * ((digest[index // 8] >> (index & 7)) & 1) for index in range(3, 254)
    )
    return _encodepoint(_scalarmult(_B, scalar))


def ed25519_sign(message: bytes, seed: bytes) -> bytes:
    _require(type(message) is bytes, "E_ED25519_MESSAGE", "message must be bytes")
    public_key = ed25519_public_key(seed)
    digest = hashlib.sha512(seed).digest()
    scalar = 2**254 + sum(
        2**index * ((digest[index // 8] >> (index & 7)) & 1) for index in range(3, 254)
    )
    nonce = _hint(digest[32:] + message) % _L
    encoded_r = _encodepoint(_scalarmult(_B, nonce))
    challenge = _hint(encoded_r + public_key + message) % _L
    encoded_s = ((nonce + challenge * scalar) % _L).to_bytes(32, "little")
    return encoded_r + encoded_s


@lru_cache(maxsize=512)
def ed25519_verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    try:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        point_r = _decodepoint(signature[:32])
        point_a = _decodepoint(public_key)
        scalar_s = int.from_bytes(signature[32:], "little")
        if scalar_s >= _L:
            return False
        identity = (0, 1)
        if point_r == identity or point_a == identity:
            return False
        if _scalarmult(point_r, _L) != identity:
            return False
        if _scalarmult(point_a, _L) != identity:
            return False
        challenge = _hint(signature[:32] + public_key + message) % _L
        return _scalarmult(_B, scalar_s) == _edwards(
            point_r, _scalarmult(point_a, challenge)
        )
    except IsolatedLabError:
        return False


def synthetic_seed(label: str) -> bytes:
    """Return a public deterministic KAT seed; never a trust credential."""

    _require(type(label) is str and label, "E_KAT_LABEL", "KAT label drift")
    return hashlib.sha256(("public-synthetic-kat:" + label).encode("utf-8")).digest()


@dataclass(frozen=True)
class MountIdentity:
    st_dev: int
    fsid_0: int
    fsid_1: int
    filesystem_type: str
    mountpoint_sha256: str
    local: bool


class _DarwinFsid(ctypes.Structure):
    _fields_ = [("val", ctypes.c_int32 * 2)]


class _DarwinStatfs(ctypes.Structure):
    _fields_ = [
        ("f_bsize", ctypes.c_uint32),
        ("f_iosize", ctypes.c_int32),
        ("f_blocks", ctypes.c_uint64),
        ("f_bfree", ctypes.c_uint64),
        ("f_bavail", ctypes.c_uint64),
        ("f_files", ctypes.c_uint64),
        ("f_ffree", ctypes.c_uint64),
        ("f_fsid", _DarwinFsid),
        ("f_owner", ctypes.c_uint32),
        ("f_type", ctypes.c_uint32),
        ("f_flags", ctypes.c_uint32),
        ("f_fssubtype", ctypes.c_uint32),
        ("f_fstypename", ctypes.c_char * 16),
        ("f_mntonname", ctypes.c_char * 1024),
        ("f_mntfromname", ctypes.c_char * 1024),
        ("f_reserved", ctypes.c_uint32 * 8),
    ]


_MNT_LOCAL = 0x00001000
_FORBIDDEN_FILESYSTEMS = frozenset(
    {
        "afpfs",
        "autofs",
        "fusefs",
        "macfuse",
        "nfs",
        "osxfuse",
        "smbfs",
        "webdav",
    }
)


def mount_identity_from_fd(fd: int) -> MountIdentity:
    _require(platform.system() == "Darwin", "E_PLATFORM", "Darwin lab required")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.fstatfs.argtypes = [ctypes.c_int, ctypes.POINTER(_DarwinStatfs)]
    libc.fstatfs.restype = ctypes.c_int
    profile = _DarwinStatfs()
    if libc.fstatfs(fd, ctypes.byref(profile)) != 0:
        errno = ctypes.get_errno()
        _fail("E_MOUNT_PROBE", f"fstatfs failed with errno {errno}")
    fstype = bytes(profile.f_fstypename).split(b"\x00", 1)[0].decode("ascii")
    mountpoint = bytes(profile.f_mntonname).split(b"\x00", 1)[0]
    opened = os.fstat(fd)
    return MountIdentity(
        st_dev=opened.st_dev,
        fsid_0=int(profile.f_fsid.val[0]),
        fsid_1=int(profile.f_fsid.val[1]),
        filesystem_type=fstype,
        mountpoint_sha256=_sha256(mountpoint),
        local=bool(profile.f_flags & _MNT_LOCAL),
    )


def validate_mount_identity(actual: MountIdentity, expected: MountIdentity) -> None:
    _require(actual.local, "E_MOUNT_REMOTE", "filesystem is not MNT_LOCAL")
    _require(
        actual.filesystem_type.lower() not in _FORBIDDEN_FILESYSTEMS,
        "E_MOUNT_REMOTE",
        "network, FUSE, or remote filesystem is forbidden",
    )
    _require(actual == expected, "E_MOUNT_DRIFT", "mount identity drift")


def _open_absolute_directory(path: Path) -> tuple[int, os.stat_result]:
    _require(path.is_absolute(), "E_PATH", "directory path must be absolute")
    parts = path.parts[1:]
    fd = os.open(
        path.anchor,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for component in parts:
            _require(
                component not in ("", ".", "..") and "/" not in component,
                "E_PATH",
                "unsafe path component",
            )
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            os.close(fd)
            fd = next_fd
        opened = os.fstat(fd)
        _require(stat.S_ISDIR(opened.st_mode), "E_PATH", "path is not a directory")
        return fd, opened
    except BaseException:
        os.close(fd)
        raise


@dataclass(frozen=True)
class SyntheticLabConfig:
    repository_root: Path
    git_common_dir: Path
    private_input_dir_relative: str
    ledger_path: Path
    canonical_scope: str
    mode: str = MODE
    enabled: bool = False


@dataclass(frozen=True)
class CapturedFile:
    name: str
    raw: bytes
    raw_sha256: str
    domain_sha256: str
    byte_length: int
    identity_sha256: str


@dataclass
class _RetainedFile:
    name: str
    parent_fd: int
    parent_identity: os.stat_result
    fd: int
    opened: os.stat_result
    raw: bytes


PrecommitFaultHook = Optional[Callable[["RetainedCustodySession"], None]]


class RetainedCustodySession:
    """Retain no-follow repository, parent, and private file descriptors."""

    def __init__(
        self,
        config: SyntheticLabConfig,
        *,
        precommit_fault_hook: PrecommitFaultHook = None,
    ) -> None:
        _require(type(config) is SyntheticLabConfig, "E_CONFIG", "config type drift")
        _require(config.enabled is True, "E_DEFAULT_DISABLED", "gate is disabled")
        _require(config.mode == MODE, "E_MODE", "only SYNTHETIC_KAT is accepted")
        _require(platform.system() == "Darwin", "E_PLATFORM", "Darwin lab required")
        _require(
            config.repository_root.is_absolute()
            and config.git_common_dir.is_absolute()
            and config.ledger_path.is_absolute(),
            "E_CONFIG_PATH",
            "all configured roots must be absolute",
        )
        parts = Path(config.private_input_dir_relative).parts
        _require(
            parts
            and not Path(config.private_input_dir_relative).is_absolute()
            and all(part not in ("", ".", "..") for part in parts),
            "E_PRIVATE_PATH",
            "private input directory must be safe and repository-relative",
        )
        self.config = config
        self._precommit_fault_hook = precommit_fault_hook
        self._closed = False
        self._repo_fd = -1
        self._git_fd = -1
        self._private_dir_fds: list[int] = []
        self._public_fds: list[int] = []
        self._public_parent_fds: list[int] = []
        self._files: list[_RetainedFile] = []
        self._open()

    def __enter__(self) -> "RetainedCustodySession":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    @property
    def retained_fd_count(self) -> int:
        return (
            2
            + len(self._private_dir_fds)
            + len(self._public_fds)
            + len(self._public_parent_fds)
            + len(self._files)
        )

    @property
    def retained_file_fds(self) -> tuple[int, ...]:
        return tuple(item.fd for item in self._files)

    @property
    def repository_identity_sha256(self) -> str:
        self._require_open()
        return self._repository_identity_sha256

    @property
    def scope_identity_sha256(self) -> str:
        return _domain_sha256(
            "agent-bridge/engram/g1/canonical-scope/v0",
            self.config.canonical_scope.encode("utf-8"),
        )

    @property
    def mount_identity(self) -> MountIdentity:
        self._require_open()
        return self._mount_identity

    @property
    def public_bindings(self) -> dict[str, str]:
        self._require_open()
        return dict(self._public_bindings)

    def capture(self, name: str) -> CapturedFile:
        self._require_open()
        matches = [item for item in self._files if item.name == name]
        _require(len(matches) == 1, "E_INPUT_NAME", f"unknown input: {name}")
        item = matches[0]
        identity = {
            "device": item.opened.st_dev,
            "inode": item.opened.st_ino,
            "size": item.opened.st_size,
        }
        return CapturedFile(
            name=name,
            raw=item.raw,
            raw_sha256=_sha256(item.raw),
            domain_sha256=_domain_sha256(PRIVATE_DIGEST_DOMAIN + "/" + name, item.raw),
            byte_length=len(item.raw),
            identity_sha256=_sha256(jcs_bytes(identity)),
        )

    def captures(self) -> dict[str, CapturedFile]:
        return {name: self.capture(name) for name in PRIVATE_INPUT_NAMES}

    def revalidate_for_claim(self) -> None:
        self._require_open()
        if self._precommit_fault_hook is not None:
            hook = self._precommit_fault_hook
            self._precommit_fault_hook = None
            hook(self)
        validate_mount_identity(
            mount_identity_from_fd(self._repo_fd), self._mount_identity
        )
        validate_mount_identity(
            mount_identity_from_fd(self._git_fd), self._mount_identity
        )
        for fd in self._private_dir_fds:
            validate_mount_identity(mount_identity_from_fd(fd), self._mount_identity)
        for item in self._files:
            after = os.fstat(item.fd)
            relative = os.stat(item.name, dir_fd=item.parent_fd, follow_symlinks=False)
            _require(
                _same_stat(after, item.opened)
                and _same_stat(relative, item.opened)
                and stat.S_ISREG(after.st_mode)
                and after.st_uid == os.geteuid()
                and after.st_nlink == 1
                and stat.S_IMODE(after.st_mode) == 0o600,
                "E_CUSTODY_DRIFT",
                f"retained input identity drifted: {item.name}",
            )
            os.lseek(item.fd, 0, os.SEEK_SET)
            raw = _read_bounded_fd(item.fd, MAX_JSON_BYTES)
            _require(
                raw == item.raw, "E_CUSTODY_DRIFT", f"input bytes drifted: {item.name}"
            )
            validate_mount_identity(
                mount_identity_from_fd(item.fd), self._mount_identity
            )

    def close(self) -> None:
        if self._closed:
            return
        fds = (
            [item.fd for item in self._files]
            + self._public_fds
            + self._public_parent_fds
            + list(reversed(self._private_dir_fds))
            + [self._git_fd, self._repo_fd]
        )
        self._closed = True
        for fd in fds:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _require_open(self) -> None:
        _require(not self._closed, "E_CUSTODY_CLOSED", "custody session is closed")

    def _open(self) -> None:
        try:
            self._repo_fd, repo_stat = _open_absolute_directory(
                self.config.repository_root
            )
            self._git_fd, git_stat = _open_absolute_directory(
                self.config.git_common_dir
            )
            _require(
                repo_stat.st_uid == os.geteuid()
                and stat.S_IMODE(repo_stat.st_mode) & 0o022 == 0,
                "E_REPOSITORY_IDENTITY",
                "repository root must be euid-owned and not group/other writable",
            )
            _require(
                git_stat.st_uid == os.geteuid()
                and stat.S_IMODE(git_stat.st_mode) & 0o022 == 0,
                "E_REPOSITORY_IDENTITY",
                "git common dir must be euid-owned and not group/other writable",
            )
            self._mount_identity = mount_identity_from_fd(self._repo_fd)
            validate_mount_identity(self._mount_identity, self._mount_identity)
            validate_mount_identity(
                mount_identity_from_fd(self._git_fd), self._mount_identity
            )
            identity = {
                "git_common_dir_device": git_stat.st_dev,
                "git_common_dir_inode": git_stat.st_ino,
                "git_common_dir_path_sha256": _sha256(
                    os.fsencode(str(self.config.git_common_dir))
                ),
                "mount_fsid_0": self._mount_identity.fsid_0,
                "mount_fsid_1": self._mount_identity.fsid_1,
                "mountpoint_sha256": self._mount_identity.mountpoint_sha256,
                "repository_root_device": repo_stat.st_dev,
                "repository_root_inode": repo_stat.st_ino,
                "repository_root_path_sha256": _sha256(
                    os.fsencode(str(self.config.repository_root))
                ),
            }
            self._repository_identity_sha256 = _domain_sha256(
                "agent-bridge/engram/g1/repository-identity/v1", jcs_bytes(identity)
            )
            self._open_private_inputs()
            self._public_bindings = self._open_and_hash_public_bindings()
        except BaseException:
            self.close()
            raise

    def _open_private_inputs(self) -> None:
        parent_fd = self._repo_fd
        parent_identity = os.fstat(parent_fd)
        for component in Path(self.config.private_input_dir_relative).parts:
            fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            opened = os.fstat(fd)
            _require(
                stat.S_ISDIR(opened.st_mode)
                and opened.st_uid == os.geteuid()
                and stat.S_IMODE(opened.st_mode) == 0o700,
                "E_PRIVATE_DIRECTORY",
                "every private directory must be euid-owned mode 0700",
            )
            validate_mount_identity(mount_identity_from_fd(fd), self._mount_identity)
            self._private_dir_fds.append(fd)
            parent_fd = fd
            parent_identity = opened
        for name in PRIVATE_INPUT_NAMES:
            before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            _require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.geteuid()
                and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600,
                "E_PRIVATE_FILE",
                f"private input must be one euid-owned 0600 regular file: {name}",
            )
            fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            opened = os.fstat(fd)
            _require(
                _same_stat(opened, before),
                "E_PRIVATE_FILE_RACE",
                f"private input changed while opening: {name}",
            )
            validate_mount_identity(mount_identity_from_fd(fd), self._mount_identity)
            raw = _read_bounded_fd(fd, MAX_JSON_BYTES)
            after = os.fstat(fd)
            _require(
                _same_stat(after, opened) and len(raw) == opened.st_size,
                "E_PRIVATE_FILE_RACE",
                f"private input changed while reading: {name}",
            )
            self._files.append(
                _RetainedFile(
                    name=name,
                    parent_fd=parent_fd,
                    parent_identity=parent_identity,
                    fd=fd,
                    opened=opened,
                    raw=raw,
                )
            )

    def _open_and_hash_public_bindings(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for label, relative in PUBLIC_ARTIFACTS.items():
            parts = Path(relative).parts
            parent_fd = os.dup(self._repo_fd)
            self._public_parent_fds.append(parent_fd)
            for component in parts[:-1]:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=parent_fd,
                )
                self._public_parent_fds.append(next_fd)
                parent_fd = next_fd
            file_fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            opened = os.fstat(file_fd)
            _require(
                stat.S_ISREG(opened.st_mode),
                "E_PUBLIC_BINDING",
                "public artifact drift",
            )
            raw = _read_bounded_fd(file_fd, MAX_JSON_BYTES)
            after = os.fstat(file_fd)
            _require(
                _same_stat(opened, after),
                "E_PUBLIC_BINDING",
                "public artifact changed while reading",
            )
            self._public_fds.append(file_fd)
            digest = _sha256(raw)
            _require(
                digest == PUBLIC_BINDINGS[label],
                "E_PUBLIC_BINDING",
                f"public artifact hash drift: {label}",
            )
            result[label] = digest
        return result


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_uid,
        left.st_nlink,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_uid,
        right.st_nlink,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _read_bounded_fd(fd: int, limit: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(65_536, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        _require(total <= limit, "E_FILE_SIZE", "retained file exceeds limit")
    return b"".join(chunks)


def implementation_sha256() -> str:
    return _sha256(Path(__file__).resolve().read_bytes())


def process_identity_sha256(boot_epoch_hex: str) -> str:
    _require(
        type(boot_epoch_hex) is str and HEX_32_RE.fullmatch(boot_epoch_hex) is not None,
        "E_PROCESS_IDENTITY",
        "boot epoch must be 32-byte lowercase hex",
    )
    frame = {
        "boot_epoch_hex": boot_epoch_hex,
        "effective_uid": os.geteuid(),
        "implementation_sha256": implementation_sha256(),
        "parent_process_id": os.getppid(),
        "process_id": os.getpid(),
    }
    return _domain_sha256(
        "agent-bridge/engram/g1/process-identity/v0", jcs_bytes(frame)
    )


@dataclass(frozen=True)
class TrustKeyProvision:
    role: str
    key_id: str
    key_epoch: int
    public_key: bytes


@dataclass(frozen=True)
class TrustedTimeSample:
    boot_epoch_hex: str
    monotonic_ns: int


@dataclass(frozen=True)
class ClaimRecord:
    event_sha256: str
    ledger_revision: int
    ledger_chain_head_sha256: str
    state: str
    reason_code: str


@dataclass(frozen=True)
class CapabilityConsumeRecord:
    event_sha256: str
    ledger_revision: int
    ledger_chain_head_sha256: str


class ExternalRevisionAnchorDouble:
    """Packet-independent process-private rollback witness for the lab ledger."""

    __slots__ = ("_ledger_id_sha256", "_revision", "_chain_head_sha256")

    def __init__(
        self, ledger_id_sha256: str, revision: int, chain_head_sha256: str
    ) -> None:
        self._ledger_id_sha256 = ledger_id_sha256
        self._revision = revision
        self._chain_head_sha256 = chain_head_sha256

    @property
    def ledger_id_sha256(self) -> str:
        return self._ledger_id_sha256

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def chain_head_sha256(self) -> str:
        return self._chain_head_sha256

    def assert_matches(self, ledger_id: str, revision: int, chain_head: str) -> None:
        _require(
            ledger_id == self._ledger_id_sha256,
            "E_LEDGER_ANCHOR",
            "ledger identity differs from external anchor",
        )
        _require(
            revision == self._revision and chain_head == self._chain_head_sha256,
            "E_LEDGER_ROLLBACK",
            "ledger revision or chain head regressed from external anchor",
        )

    def advance(
        self,
        old_revision: int,
        old_chain_head: str,
        new_revision: int,
        new_chain_head: str,
    ) -> None:
        self.assert_matches(self._ledger_id_sha256, old_revision, old_chain_head)
        _require(
            new_revision == old_revision + 1,
            "E_LEDGER_REVISION",
            "external anchor revision is not contiguous",
        )
        self._revision = new_revision
        self._chain_head_sha256 = new_chain_head

    def __getstate__(self) -> None:
        raise TypeError("external revision anchor double is nonserializable")

    def __reduce__(self) -> None:
        raise TypeError("external revision anchor double is nonserializable")


_LEDGER_SCHEMA = r"""
CREATE TABLE ledger_meta_v0 (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    ledger_id_sha256 TEXT NOT NULL,
    repository_identity_sha256 TEXT NOT NULL,
    scope_identity_sha256 TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    chain_head_sha256 TEXT NOT NULL
) STRICT;

CREATE TABLE trust_keys_v0 (
    role TEXT NOT NULL,
    key_id TEXT NOT NULL,
    key_epoch INTEGER NOT NULL CHECK(key_epoch >= 1),
    public_key_hex TEXT NOT NULL,
    added_revision INTEGER NOT NULL,
    PRIMARY KEY(role, key_id, key_epoch),
    UNIQUE(public_key_hex)
) STRICT;

CREATE TABLE key_revocations_v0 (
    role TEXT NOT NULL,
    key_id TEXT NOT NULL,
    key_epoch INTEGER NOT NULL,
    revoked_revision INTEGER NOT NULL UNIQUE,
    reason_code TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    PRIMARY KEY(role, key_id, key_epoch),
    FOREIGN KEY(role, key_id, key_epoch)
      REFERENCES trust_keys_v0(role, key_id, key_epoch)
) STRICT;

CREATE TABLE scope_high_water_v0 (
    scope_identity_sha256 TEXT PRIMARY KEY,
    last_sequence INTEGER NOT NULL CHECK(last_sequence >= 0),
    boot_epoch_hex TEXT NOT NULL,
    last_monotonic_ns INTEGER NOT NULL CHECK(last_monotonic_ns >= 0),
    last_trusted_utc_seconds INTEGER NOT NULL,
    last_checkpoint_sequence INTEGER NOT NULL CHECK(last_checkpoint_sequence >= 0),
    trusted_time_established INTEGER NOT NULL
      CHECK(trusted_time_established IN (0, 1))
) STRICT;

CREATE TABLE claim_events_v0 (
    event_id INTEGER PRIMARY KEY,
    revision INTEGER NOT NULL UNIQUE,
    envelope_sha256 TEXT NOT NULL UNIQUE,
    repository_identity_sha256 TEXT NOT NULL,
    scope_identity_sha256 TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    nonce_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('CLAIMED', 'DENIED')),
    reason_code TEXT NOT NULL,
    consumer_public_key_sha256 TEXT NOT NULL,
    process_identity_sha256 TEXT NOT NULL,
    boot_epoch_hex TEXT NOT NULL,
    trusted_monotonic_ns INTEGER NOT NULL,
    trusted_utc_seconds INTEGER NOT NULL,
    checkpoint_sequence INTEGER NOT NULL,
    trusted_time_verified INTEGER NOT NULL
      CHECK(trusted_time_verified IN (0, 1)),
    previous_chain_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    UNIQUE(scope_identity_sha256, sequence),
    UNIQUE(scope_identity_sha256, nonce_sha256)
) STRICT;

CREATE TABLE capability_events_v0 (
    event_id INTEGER PRIMARY KEY,
    revision INTEGER NOT NULL UNIQUE,
    claim_event_sha256 TEXT NOT NULL UNIQUE,
    consumer_public_key_sha256 TEXT NOT NULL,
    process_identity_sha256 TEXT NOT NULL,
    proof_signature_sha256 TEXT NOT NULL,
    previous_chain_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE
) STRICT;

CREATE TRIGGER trust_keys_no_update_v0 BEFORE UPDATE ON trust_keys_v0
BEGIN SELECT RAISE(ABORT, 'trust_keys_v0 is append-only'); END;
CREATE TRIGGER trust_keys_no_delete_v0 BEFORE DELETE ON trust_keys_v0
BEGIN SELECT RAISE(ABORT, 'trust_keys_v0 is append-only'); END;
CREATE TRIGGER key_revocations_no_update_v0 BEFORE UPDATE ON key_revocations_v0
BEGIN SELECT RAISE(ABORT, 'key_revocations_v0 is append-only'); END;
CREATE TRIGGER key_revocations_no_delete_v0 BEFORE DELETE ON key_revocations_v0
BEGIN SELECT RAISE(ABORT, 'key_revocations_v0 is append-only'); END;
CREATE TRIGGER claim_events_no_update_v0 BEFORE UPDATE ON claim_events_v0
BEGIN SELECT RAISE(ABORT, 'claim_events_v0 is append-only'); END;
CREATE TRIGGER claim_events_no_delete_v0 BEFORE DELETE ON claim_events_v0
BEGIN SELECT RAISE(ABORT, 'claim_events_v0 is append-only'); END;
CREATE TRIGGER capability_events_no_update_v0 BEFORE UPDATE ON capability_events_v0
BEGIN SELECT RAISE(ABORT, 'capability_events_v0 is append-only'); END;
CREATE TRIGGER capability_events_no_delete_v0 BEFORE DELETE ON capability_events_v0
BEGIN SELECT RAISE(ABORT, 'capability_events_v0 is append-only'); END;
"""


def _ledger_id_from_key_rows(
    key_rows: Sequence[Mapping[str, Any]],
    repository_identity_sha256: str,
    scope_identity_sha256: str,
) -> str:
    return _domain_sha256(
        "agent-bridge/engram/g1/synthetic-trust-ledger/v0",
        jcs_bytes(
            {
                "keys": list(key_rows),
                "repository_identity_sha256": repository_identity_sha256,
                "scope_identity_sha256": scope_identity_sha256,
            }
        ),
    )


def _ledger_genesis_sha256(
    key_rows: Sequence[Mapping[str, Any]], ledger_id_sha256: str
) -> str:
    return _domain_sha256(
        "agent-bridge/engram/g1/synthetic-trust-ledger/genesis/v0",
        jcs_bytes({"keys": list(key_rows), "ledger_id_sha256": ledger_id_sha256}),
    )


def _schema_rows(connection: sqlite3.Connection) -> list[dict[str, str]]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return [
        {"name": row[1], "sql": row[3], "table": row[2], "type": row[0]} for row in rows
    ]


@lru_cache(maxsize=1)
def _expected_ledger_schema_sha256() -> str:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(_LEDGER_SCHEMA)
        return _sha256(jcs_bytes(_schema_rows(connection)))
    finally:
        connection.close()


@dataclass
class _OpenLedger:
    connection: sqlite3.Connection
    parent_fd: int
    sentinel_fd: int
    parent_stat: os.stat_result
    file_stat: os.stat_result


class PrivateTrustLedgerDouble:
    """Owner-only SQLite trust and one-shot claim ledger for synthetic KATs."""

    def __init__(
        self,
        path: Path,
        ledger_id_sha256: str,
        repository_identity_sha256: str,
        scope_identity_sha256: str,
        mount_identity: MountIdentity,
    ) -> None:
        self.path = path
        self.ledger_id_sha256 = ledger_id_sha256
        self.repository_identity_sha256 = repository_identity_sha256
        self.scope_identity_sha256 = scope_identity_sha256
        self.mount_identity = mount_identity

    @classmethod
    def initialize(
        cls,
        path: Path,
        repository_identity_sha256: str,
        scope_identity_sha256: str,
        mount_identity: MountIdentity,
        keys: Sequence[TrustKeyProvision],
    ) -> tuple["PrivateTrustLedgerDouble", ExternalRevisionAnchorDouble]:
        _require(path.is_absolute(), "E_LEDGER_PATH", "ledger path must be absolute")
        _require(len(keys) == len(ROLES) + 1, "E_LEDGER_KEYS", "key count drift")
        _require(
            tuple(key.role for key in keys) == ROLES + (TIME_ROLE,),
            "E_LEDGER_KEYS",
            "ledger key roles/order drift",
        )
        seen_ids: set[str] = set()
        seen_keys: set[bytes] = set()
        key_rows: list[dict[str, Any]] = []
        for key in keys:
            _require(type(key) is TrustKeyProvision, "E_LEDGER_KEYS", "key type drift")
            _require(
                KEY_ID_RE.fullmatch(key.key_id) is not None,
                "E_LEDGER_KEYS",
                "key id drift",
            )
            _require(
                type(key.key_epoch) is int and key.key_epoch >= 1,
                "E_LEDGER_KEYS",
                "key epoch drift",
            )
            _require(
                type(key.public_key) is bytes and len(key.public_key) == 32,
                "E_LEDGER_KEYS",
                "public key drift",
            )
            _require(
                key.key_id not in seen_ids and key.public_key not in seen_keys,
                "E_LEDGER_KEYS",
                "all ledger signers must be distinct",
            )
            seen_ids.add(key.key_id)
            seen_keys.add(key.public_key)
            key_rows.append(
                {
                    "key_epoch": key.key_epoch,
                    "key_id": key.key_id,
                    "public_key_hex": key.public_key.hex(),
                    "role": key.role,
                }
            )
        ledger_id = _ledger_id_from_key_rows(
            key_rows, repository_identity_sha256, scope_identity_sha256
        )
        initial_chain = _ledger_genesis_sha256(key_rows, ledger_id)
        parent_fd, parent_stat = _open_absolute_directory(path.parent)
        sentinel_fd = -1
        connection: sqlite3.Connection | None = None
        try:
            _require(
                parent_stat.st_uid == os.geteuid()
                and stat.S_IMODE(parent_stat.st_mode) == 0o700,
                "E_LEDGER_PARENT",
                "ledger parent must be euid-owned mode 0700",
            )
            validate_mount_identity(mount_identity_from_fd(parent_fd), mount_identity)
            sentinel_fd = os.open(
                path.name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=parent_fd,
            )
            os.fchmod(sentinel_fd, 0o600)
            connection = sqlite3.connect(
                path.as_uri(), isolation_level=None, timeout=5.0, uri=True
            )
            cls._configure_connection(connection)
            connection.executescript(_LEDGER_SCHEMA)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO ledger_meta_v0 VALUES (1, ?, ?, ?, 1, ?)",
                (
                    ledger_id,
                    repository_identity_sha256,
                    scope_identity_sha256,
                    initial_chain,
                ),
            )
            connection.executemany(
                "INSERT INTO trust_keys_v0(role, key_id, key_epoch, public_key_hex, "
                "added_revision) VALUES (?, ?, ?, ?, 1)",
                [
                    (
                        row["role"],
                        row["key_id"],
                        row["key_epoch"],
                        row["public_key_hex"],
                    )
                    for row in key_rows
                ],
            )
            connection.execute("COMMIT")
            connection.close()
            connection = None
            os.fsync(sentinel_fd)
            os.fsync(parent_fd)
        except BaseException:
            if connection is not None:
                try:
                    connection.execute("ROLLBACK")
                except BaseException:
                    pass
                connection.close()
            if sentinel_fd >= 0:
                os.close(sentinel_fd)
            os.close(parent_fd)
            raise
        os.close(sentinel_fd)
        os.close(parent_fd)
        ledger = cls(
            path,
            ledger_id,
            repository_identity_sha256,
            scope_identity_sha256,
            mount_identity,
        )
        anchor = ExternalRevisionAnchorDouble(ledger_id, 1, initial_chain)
        ledger.inspect(anchor)
        return ledger, anchor

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=EXTRA")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA read_uncommitted=OFF")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA locking_mode=NORMAL")
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(False)
        checks = {
            "journal_mode": "delete",
            "synchronous": 3,
            "foreign_keys": 1,
            "read_uncommitted": 0,
            "trusted_schema": 0,
            "locking_mode": "normal",
        }
        for name, expected in checks.items():
            row = connection.execute(f"PRAGMA {name}").fetchone()
            actual = row[0] if row else None
            if type(expected) is str and actual is not None:
                actual = str(actual).lower()
            _require(actual == expected, "E_LEDGER_PRAGMA", f"PRAGMA {name} drift")

    def inspect(self, anchor: ExternalRevisionAnchorDouble) -> dict[str, Any]:
        opened = self._open_existing()
        try:
            meta = self._read_meta(opened.connection)
            anchor.assert_matches(meta[0], meta[3], meta[4])
            return {
                "ledger_id_sha256": meta[0],
                "repository_identity_sha256": meta[1],
                "scope_identity_sha256": meta[2],
                "revision": meta[3],
                "chain_head_sha256": meta[4],
            }
        finally:
            self._close_existing(opened, durable=False)

    def revoke_key(
        self,
        anchor: ExternalRevisionAnchorDouble,
        role: str,
        key_id: str,
        key_epoch: int,
        reason_code: str = "SYNTHETIC_KAT_REVOCATION",
    ) -> None:
        opened = self._open_existing()
        old_revision = -1
        old_chain = ""
        new_revision = -1
        new_chain = ""
        try:
            connection = opened.connection
            connection.execute("BEGIN IMMEDIATE")
            meta = self._read_meta(connection)
            anchor.assert_matches(meta[0], meta[3], meta[4])
            old_revision, old_chain = meta[3], meta[4]
            self._resolve_active_key(connection, role, key_id, key_epoch)
            new_revision = old_revision + 1
            event = {
                "key_epoch": key_epoch,
                "key_id": key_id,
                "previous_chain_sha256": old_chain,
                "reason_code": reason_code,
                "revision": new_revision,
                "role": role,
            }
            event_sha = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-key-revocation/v0",
                jcs_bytes(event),
            )
            connection.execute(
                "INSERT INTO key_revocations_v0 VALUES (?, ?, ?, ?, ?, ?)",
                (role, key_id, key_epoch, new_revision, reason_code, event_sha),
            )
            new_chain = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-ledger-chain/v0",
                bytes.fromhex(old_chain) + bytes.fromhex(event_sha),
            )
            changed = connection.execute(
                "UPDATE ledger_meta_v0 SET revision=?, chain_head_sha256=? "
                "WHERE singleton=1 AND revision=? AND chain_head_sha256=?",
                (new_revision, new_chain, old_revision, old_chain),
            ).rowcount
            _require(changed == 1, "E_LEDGER_CAS", "revocation CAS lost")
            connection.execute("COMMIT")
        except BaseException:
            self._rollback_or_record(opened, "E_REVOCATION_ROLLBACK")
            raise
        finally:
            self._close_existing(opened, durable=new_revision >= 0)
        anchor.advance(old_revision, old_chain, new_revision, new_chain)

    def claim(
        self,
        anchor: ExternalRevisionAnchorDouble,
        *,
        envelope: Mapping[str, Any],
        envelope_raw: bytes,
        signatures: Sequence[Mapping[str, Any]],
        checkpoint: Mapping[str, Any],
        checkpoint_raw: bytes,
        time_sample: TrustedTimeSample,
        consumer_public_key: bytes,
        process_identity: str,
        precommit: Callable[[], None],
    ) -> ClaimRecord:
        envelope_sha = _sha256(envelope_raw)
        sequence = envelope["sequence"]
        nonce_sha = _sha256(bytes.fromhex(envelope["nonce_hex"]))
        consumer_key_sha = _sha256(consumer_public_key)
        opened = self._open_existing()
        old_revision = -1
        old_chain = ""
        new_revision = -1
        new_chain = ""
        state = "DENIED"
        reason_code = "E_INTERNAL_DENIAL"
        trusted_now = envelope["issued_at_utc_seconds"]
        try:
            connection = opened.connection
            connection.execute("BEGIN IMMEDIATE")
            meta = self._read_meta(connection)
            anchor.assert_matches(meta[0], meta[3], meta[4])
            old_revision, old_chain = meta[3], meta[4]
            _require(
                connection.execute(
                    "SELECT 1 FROM claim_events_v0 WHERE envelope_sha256=?",
                    (envelope_sha,),
                ).fetchone()
                is None,
                "E_REPLAY_ENVELOPE",
                "envelope was already claimed or denied",
            )
            _require(
                envelope["trust_ledger_id_sha256"] == meta[0]
                and envelope["trust_ledger_revision"] == old_revision,
                "E_LEDGER_REVISION_BINDING",
                "envelope trust-ledger binding is stale or foreign",
            )
            high_water = connection.execute(
                "SELECT last_sequence, boot_epoch_hex, last_monotonic_ns, "
                "last_trusted_utc_seconds, last_checkpoint_sequence "
                ", trusted_time_established "
                "FROM scope_high_water_v0 WHERE scope_identity_sha256=?",
                (self.scope_identity_sha256,),
            ).fetchone()
            expected_sequence = 1 if high_water is None else int(high_water[0]) + 1
            _require(
                sequence == expected_sequence,
                "E_SEQUENCE",
                "sequence is not the exact next per-scope value",
            )
            _require(
                connection.execute(
                    "SELECT 1 FROM claim_events_v0 WHERE scope_identity_sha256=? "
                    "AND nonce_sha256=?",
                    (self.scope_identity_sha256, nonce_sha),
                ).fetchone()
                is None,
                "E_REPLAY_NONCE",
                "nonce was already claimed or denied",
            )
            trusted_time_verified = False
            try:
                trusted_now = self._verify_time(
                    connection,
                    envelope,
                    checkpoint,
                    checkpoint_raw,
                    time_sample,
                    high_water,
                )
                trusted_time_verified = True
                self._verify_quorum(connection, envelope_raw, signatures)
                precommit()
                state = "CLAIMED"
                reason_code = "SYNTHETIC_KAT_ACCEPTED"
            except IsolatedLabError as exc:
                state = "DENIED"
                reason_code = exc.code
            new_revision = old_revision + 1
            body = checkpoint["checkpoint"]
            event = {
                "boot_epoch_hex": time_sample.boot_epoch_hex,
                "checkpoint_sequence": body["checkpoint_sequence"],
                "consumer_public_key_sha256": consumer_key_sha,
                "envelope_sha256": envelope_sha,
                "nonce_sha256": nonce_sha,
                "previous_chain_sha256": old_chain,
                "process_identity_sha256": process_identity,
                "reason_code": reason_code,
                "repository_identity_sha256": self.repository_identity_sha256,
                "revision": new_revision,
                "scope_identity_sha256": self.scope_identity_sha256,
                "sequence": sequence,
                "state": state,
                "trusted_monotonic_ns": time_sample.monotonic_ns,
                "trusted_time_verified": trusted_time_verified,
                "trusted_utc_seconds": trusted_now,
            }
            event_sha = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-claim-event/v0", jcs_bytes(event)
            )
            connection.execute(
                "INSERT INTO claim_events_v0(revision, envelope_sha256, "
                "repository_identity_sha256, scope_identity_sha256, sequence, "
                "nonce_sha256, state, reason_code, consumer_public_key_sha256, "
                "process_identity_sha256, boot_epoch_hex, trusted_monotonic_ns, "
                "trusted_utc_seconds, checkpoint_sequence, trusted_time_verified, "
                "previous_chain_sha256, event_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_revision,
                    envelope_sha,
                    self.repository_identity_sha256,
                    self.scope_identity_sha256,
                    sequence,
                    nonce_sha,
                    state,
                    reason_code,
                    consumer_key_sha,
                    process_identity,
                    time_sample.boot_epoch_hex,
                    time_sample.monotonic_ns,
                    trusted_now,
                    body["checkpoint_sequence"],
                    int(trusted_time_verified),
                    old_chain,
                    event_sha,
                ),
            )
            if high_water is None:
                connection.execute(
                    "INSERT INTO scope_high_water_v0 VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.scope_identity_sha256,
                        sequence,
                        time_sample.boot_epoch_hex if trusted_time_verified else "",
                        time_sample.monotonic_ns if trusted_time_verified else 0,
                        trusted_now if trusted_time_verified else 0,
                        body["checkpoint_sequence"] if trusted_time_verified else 0,
                        int(trusted_time_verified),
                    ),
                )
            else:
                time_established = bool(high_water[5])
                if trusted_time_verified:
                    next_monotonic_ns = time_sample.monotonic_ns
                    if time_established and time_sample.boot_epoch_hex == high_water[1]:
                        next_monotonic_ns = max(int(high_water[2]), next_monotonic_ns)
                    next_boot_epoch_hex = time_sample.boot_epoch_hex
                    next_trusted_utc = max(
                        int(high_water[3]) if time_established else 0,
                        trusted_now,
                    )
                    next_checkpoint_sequence = max(
                        int(high_water[4]) if time_established else 0,
                        body["checkpoint_sequence"],
                    )
                    next_time_established = 1
                else:
                    next_boot_epoch_hex = high_water[1]
                    next_monotonic_ns = int(high_water[2])
                    next_trusted_utc = int(high_water[3])
                    next_checkpoint_sequence = int(high_water[4])
                    next_time_established = int(high_water[5])
                connection.execute(
                    "UPDATE scope_high_water_v0 SET last_sequence=?, boot_epoch_hex=?, "
                    "last_monotonic_ns=?, last_trusted_utc_seconds=?, "
                    "last_checkpoint_sequence=?, trusted_time_established=? "
                    "WHERE scope_identity_sha256=?",
                    (
                        sequence,
                        next_boot_epoch_hex,
                        next_monotonic_ns,
                        next_trusted_utc,
                        next_checkpoint_sequence,
                        next_time_established,
                        self.scope_identity_sha256,
                    ),
                )
            new_chain = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-ledger-chain/v0",
                bytes.fromhex(old_chain) + bytes.fromhex(event_sha),
            )
            changed = connection.execute(
                "UPDATE ledger_meta_v0 SET revision=?, chain_head_sha256=? "
                "WHERE singleton=1 AND revision=? AND chain_head_sha256=?",
                (new_revision, new_chain, old_revision, old_chain),
            ).rowcount
            _require(changed == 1, "E_LEDGER_CAS", "claim CAS lost")
            connection.execute("COMMIT")
        except BaseException:
            self._rollback_or_record(opened, "E_CLAIM_ROLLBACK")
            raise
        finally:
            self._close_existing(opened, durable=new_revision >= 0)
        anchor.advance(old_revision, old_chain, new_revision, new_chain)
        record = ClaimRecord(event_sha, new_revision, new_chain, state, reason_code)
        if state == "DENIED":
            raise IsolatedLabError(
                reason_code,
                "synthetic claim was durably denied; replay is now forbidden",
            )
        return record

    def consume_capability(
        self,
        anchor: ExternalRevisionAnchorDouble,
        *,
        claim_event_sha256: str,
        consumer_public_key: bytes,
        process_identity: str,
        challenge: bytes,
        proof_signature: bytes,
    ) -> CapabilityConsumeRecord:
        _require(
            ed25519_verify(proof_signature, challenge, consumer_public_key),
            "E_CAPABILITY_PROOF",
            "consumer proof-of-possession failed",
        )
        opened = self._open_existing()
        old_revision = -1
        old_chain = ""
        new_revision = -1
        new_chain = ""
        try:
            connection = opened.connection
            connection.execute("BEGIN IMMEDIATE")
            meta = self._read_meta(connection)
            anchor.assert_matches(meta[0], meta[3], meta[4])
            old_revision, old_chain = meta[3], meta[4]
            claim = connection.execute(
                "SELECT state, consumer_public_key_sha256, process_identity_sha256 "
                "FROM claim_events_v0 WHERE event_sha256=?",
                (claim_event_sha256,),
            ).fetchone()
            _require(
                claim is not None and claim[0] == "CLAIMED",
                "E_CAPABILITY_CLAIM",
                "claim is not usable",
            )
            _require(
                claim[1] == _sha256(consumer_public_key)
                and claim[2] == process_identity,
                "E_CAPABILITY_BINDING",
                "consumer key or process identity differs from claim",
            )
            _require(
                connection.execute(
                    "SELECT 1 FROM capability_events_v0 WHERE claim_event_sha256=?",
                    (claim_event_sha256,),
                ).fetchone()
                is None,
                "E_CAPABILITY_REPLAY",
                "capability was already consumed",
            )
            new_revision = old_revision + 1
            event = {
                "claim_event_sha256": claim_event_sha256,
                "consumer_public_key_sha256": _sha256(consumer_public_key),
                "previous_chain_sha256": old_chain,
                "process_identity_sha256": process_identity,
                "proof_signature_sha256": _sha256(proof_signature),
                "revision": new_revision,
            }
            event_sha = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-capability-event/v0",
                jcs_bytes(event),
            )
            connection.execute(
                "INSERT INTO capability_events_v0(revision, claim_event_sha256, "
                "consumer_public_key_sha256, process_identity_sha256, "
                "proof_signature_sha256, previous_chain_sha256, event_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    new_revision,
                    claim_event_sha256,
                    _sha256(consumer_public_key),
                    process_identity,
                    _sha256(proof_signature),
                    old_chain,
                    event_sha,
                ),
            )
            new_chain = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-ledger-chain/v0",
                bytes.fromhex(old_chain) + bytes.fromhex(event_sha),
            )
            changed = connection.execute(
                "UPDATE ledger_meta_v0 SET revision=?, chain_head_sha256=? "
                "WHERE singleton=1 AND revision=? AND chain_head_sha256=?",
                (new_revision, new_chain, old_revision, old_chain),
            ).rowcount
            _require(changed == 1, "E_LEDGER_CAS", "capability CAS lost")
            connection.execute("COMMIT")
        except BaseException:
            self._rollback_or_record(opened, "E_CAPABILITY_ROLLBACK")
            raise
        finally:
            self._close_existing(opened, durable=new_revision >= 0)
        anchor.advance(old_revision, old_chain, new_revision, new_chain)
        return CapabilityConsumeRecord(event_sha, new_revision, new_chain)

    def _verify_quorum(
        self,
        connection: sqlite3.Connection,
        envelope_raw: bytes,
        signatures: Sequence[Mapping[str, Any]],
    ) -> None:
        _require(len(signatures) == len(ROLES), "E_QUORUM", "signature count drift")
        _require(
            tuple(signature["role"] for signature in signatures) == ROLES,
            "E_QUORUM",
            "role order or exact quorum drift",
        )
        seen_ids: set[str] = set()
        seen_keys: set[bytes] = set()
        for signature in signatures:
            role = signature["role"]
            key_id = signature["key_id"]
            key_epoch = signature["key_epoch"]
            public_key = self._resolve_active_key(connection, role, key_id, key_epoch)
            _require(
                key_id not in seen_ids and public_key not in seen_keys,
                "E_QUORUM_DISTINCT",
                "signers are not distinct",
            )
            seen_ids.add(key_id)
            seen_keys.add(public_key)
            try:
                signature_bytes = bytes.fromhex(signature["signature_hex"])
            except (TypeError, ValueError) as exc:
                raise IsolatedLabError(
                    "E_SIGNATURE_FORMAT", "signature is not hex"
                ) from exc
            message = ROLE_DOMAINS[role].encode("utf-8") + b"\x00" + envelope_raw
            _require(
                ed25519_verify(signature_bytes, message, public_key),
                "E_SIGNATURE_VERIFY",
                f"Ed25519 signature failed for {role}",
            )

    def _verify_time(
        self,
        connection: sqlite3.Connection,
        envelope: Mapping[str, Any],
        checkpoint: Mapping[str, Any],
        checkpoint_raw: bytes,
        sample: TrustedTimeSample,
        high_water: tuple[Any, ...] | None,
    ) -> int:
        body = checkpoint["checkpoint"]
        _require(
            envelope["trusted_time_checkpoint_sha256"] == _sha256(checkpoint_raw),
            "E_TIME_BINDING",
            "envelope does not bind exact checkpoint bytes",
        )
        _require(
            body["repository_identity_sha256"] == self.repository_identity_sha256
            and body["scope_identity_sha256"] == self.scope_identity_sha256,
            "E_TIME_BINDING",
            "checkpoint repository or scope drift",
        )
        public_key = self._resolve_active_key(
            connection,
            TIME_ROLE,
            checkpoint["key_id"],
            checkpoint["key_epoch"],
        )
        try:
            signature = bytes.fromhex(checkpoint["signature_hex"])
        except (TypeError, ValueError) as exc:
            raise IsolatedLabError(
                "E_TIME_SIGNATURE", "checkpoint signature is not hex"
            ) from exc
        message = TIME_DOMAIN.encode("utf-8") + b"\x00" + jcs_bytes(body)
        _require(
            ed25519_verify(signature, message, public_key),
            "E_TIME_SIGNATURE",
            "signed time checkpoint verification failed",
        )
        _require(
            sample.boot_epoch_hex
            == body["boot_epoch_hex"]
            == envelope["boot_epoch_hex"],
            "E_BOOT_EPOCH",
            "boot epoch drift",
        )
        _require(
            sample.monotonic_ns >= body["monotonic_ns"],
            "E_TIME_REGRESSION",
            "monotonic sample predates checkpoint",
        )
        elapsed = (sample.monotonic_ns - body["monotonic_ns"]) // 1_000_000_000
        trusted_now = body["checkpoint_utc_seconds"] + elapsed
        issued = envelope["issued_at_utc_seconds"]
        expires = envelope["expires_at_utc_seconds"]
        _require(
            issued <= trusted_now <= expires,
            "E_TIME_WINDOW",
            "trusted time is outside envelope validity",
        )
        _require(
            trusted_now <= body["checkpoint_expires_utc_seconds"],
            "E_TIME_CHECKPOINT_EXPIRED",
            "signed time checkpoint expired",
        )
        _require(
            trusted_now - issued <= MAX_ENVELOPE_AGE_SECS
            and expires - issued <= MAX_CLAIM_WINDOW_SECS,
            "E_TIME_WINDOW",
            "envelope age or claim window exceeds contract",
        )
        if high_water is not None and bool(high_water[5]):
            if sample.boot_epoch_hex == high_water[1]:
                _require(
                    sample.monotonic_ns >= int(high_water[2])
                    and trusted_now >= int(high_water[3])
                    and body["checkpoint_sequence"] >= int(high_water[4]),
                    "E_TIME_HIGH_WATER",
                    "same-boot time or checkpoint regressed below durable high-water",
                )
            else:
                _require(
                    trusted_now >= int(high_water[3])
                    and issued > int(high_water[3])
                    and body["checkpoint_sequence"] > int(high_water[4]),
                    "E_BOOT_EPOCH_FRESHNESS",
                    "boot change lacks a fresh signed envelope/checkpoint",
                )
        return trusted_now

    @staticmethod
    def _resolve_active_key(
        connection: sqlite3.Connection, role: str, key_id: str, key_epoch: int
    ) -> bytes:
        row = connection.execute(
            "SELECT public_key_hex FROM trust_keys_v0 WHERE role=? AND key_id=? "
            "AND key_epoch=?",
            (role, key_id, key_epoch),
        ).fetchone()
        _require(row is not None, "E_TRUST_KEY", "role/key/epoch is not provisioned")
        revoked = connection.execute(
            "SELECT 1 FROM key_revocations_v0 WHERE role=? AND key_id=? "
            "AND key_epoch=?",
            (role, key_id, key_epoch),
        ).fetchone()
        _require(revoked is None, "E_TRUST_KEY_REVOKED", "key is revoked at claim")
        return bytes.fromhex(row[0])

    def _audit_store(self, connection: sqlite3.Connection) -> None:
        _require(
            _sha256(jcs_bytes(_schema_rows(connection)))
            == _expected_ledger_schema_sha256(),
            "E_LEDGER_SCHEMA",
            "ledger schema catalog drift",
        )
        _require(
            connection.execute("SELECT COUNT(*) FROM temp.sqlite_schema").fetchone()
            == (0,),
            "E_LEDGER_SCHEMA",
            "temporary schema objects are forbidden",
        )
        _require(
            connection.execute("PRAGMA quick_check(1)").fetchone() == ("ok",)
            and not connection.execute("PRAGMA foreign_key_check").fetchall(),
            "E_LEDGER_INTEGRITY",
            "SQLite integrity check failed",
        )
        meta = self._read_meta(connection)
        key_rows_raw = connection.execute(
            "SELECT role, key_id, key_epoch, public_key_hex, added_revision "
            "FROM trust_keys_v0"
        ).fetchall()
        _require(
            len(key_rows_raw) == len(ROLES) + 1,
            "E_LEDGER_KEYS",
            "ledger key cardinality drift",
        )
        by_role = {row[0]: row for row in key_rows_raw}
        _require(
            set(by_role) == set(ROLES + (TIME_ROLE,)),
            "E_LEDGER_KEYS",
            "ledger role set drift",
        )
        key_rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_public_keys: set[str] = set()
        for role in ROLES + (TIME_ROLE,):
            row = by_role[role]
            _require(
                row[4] == 1
                and KEY_ID_RE.fullmatch(row[1]) is not None
                and type(row[2]) is int
                and row[2] >= 1
                and HEX_32_RE.fullmatch(row[3]) is not None
                and row[1] not in seen_ids
                and row[3] not in seen_public_keys,
                "E_LEDGER_KEYS",
                "ledger key row drift or duplicate",
            )
            seen_ids.add(row[1])
            seen_public_keys.add(row[3])
            key_rows.append(
                {
                    "key_epoch": row[2],
                    "key_id": row[1],
                    "public_key_hex": row[3],
                    "role": row[0],
                }
            )
        recomputed_ledger_id = _ledger_id_from_key_rows(
            key_rows, self.repository_identity_sha256, self.scope_identity_sha256
        )
        _require(
            recomputed_ledger_id == meta[0] == self.ledger_id_sha256,
            "E_LEDGER_KEYS",
            "ledger key set no longer matches ledger identity",
        )
        chain = _ledger_genesis_sha256(key_rows, recomputed_ledger_id)

        events: list[tuple[int, str, tuple[Any, ...]]] = []
        for row in connection.execute(
            "SELECT role, key_id, key_epoch, revoked_revision, reason_code, "
            "event_sha256 FROM key_revocations_v0"
        ).fetchall():
            events.append((row[3], "revocation", row))
        claim_rows = connection.execute(
            "SELECT revision, envelope_sha256, repository_identity_sha256, "
            "scope_identity_sha256, sequence, nonce_sha256, state, reason_code, "
            "consumer_public_key_sha256, process_identity_sha256, boot_epoch_hex, "
            "trusted_monotonic_ns, trusted_utc_seconds, checkpoint_sequence, "
            "trusted_time_verified, previous_chain_sha256, event_sha256 "
            "FROM claim_events_v0"
        ).fetchall()
        for row in claim_rows:
            events.append((row[0], "claim", row))
        capability_rows = connection.execute(
            "SELECT revision, claim_event_sha256, consumer_public_key_sha256, "
            "process_identity_sha256, proof_signature_sha256, "
            "previous_chain_sha256, event_sha256 FROM capability_events_v0"
        ).fetchall()
        for row in capability_rows:
            events.append((row[0], "capability", row))
        events.sort(key=lambda item: item[0])
        _require(
            [item[0] for item in events] == list(range(2, int(meta[3]) + 1)),
            "E_LEDGER_REVISION",
            "ledger event revisions are not contiguous",
        )
        claim_by_event: dict[str, tuple[Any, ...]] = {}
        for revision, kind, row in events:
            if kind == "revocation":
                payload = {
                    "key_epoch": row[2],
                    "key_id": row[1],
                    "previous_chain_sha256": chain,
                    "reason_code": row[4],
                    "revision": revision,
                    "role": row[0],
                }
                event_sha = _domain_sha256(
                    "agent-bridge/engram/g1/synthetic-key-revocation/v0",
                    jcs_bytes(payload),
                )
                stored_event_sha = row[5]
            elif kind == "claim":
                _require(
                    row[2] == self.repository_identity_sha256
                    and row[3] == self.scope_identity_sha256
                    and row[15] == chain,
                    "E_LEDGER_EVENT",
                    "claim repository, scope, or previous chain drift",
                )
                _require(
                    type(row[14]) is int and row[14] in (0, 1),
                    "E_LEDGER_EVENT",
                    "claim trusted-time verification marker drift",
                )
                payload = {
                    "boot_epoch_hex": row[10],
                    "checkpoint_sequence": row[13],
                    "consumer_public_key_sha256": row[8],
                    "envelope_sha256": row[1],
                    "nonce_sha256": row[5],
                    "previous_chain_sha256": row[15],
                    "process_identity_sha256": row[9],
                    "reason_code": row[7],
                    "repository_identity_sha256": row[2],
                    "revision": revision,
                    "scope_identity_sha256": row[3],
                    "sequence": row[4],
                    "state": row[6],
                    "trusted_monotonic_ns": row[11],
                    "trusted_time_verified": bool(row[14]),
                    "trusted_utc_seconds": row[12],
                }
                event_sha = _domain_sha256(
                    "agent-bridge/engram/g1/synthetic-claim-event/v0",
                    jcs_bytes(payload),
                )
                stored_event_sha = row[16]
                claim_by_event[stored_event_sha] = row
            else:
                _require(
                    row[5] == chain,
                    "E_LEDGER_EVENT",
                    "capability previous chain drift",
                )
                claim = claim_by_event.get(row[1])
                _require(
                    claim is not None
                    and claim[6] == "CLAIMED"
                    and claim[8] == row[2]
                    and claim[9] == row[3],
                    "E_LEDGER_EVENT",
                    "capability does not bind one successful claim",
                )
                payload = {
                    "claim_event_sha256": row[1],
                    "consumer_public_key_sha256": row[2],
                    "previous_chain_sha256": row[5],
                    "process_identity_sha256": row[3],
                    "proof_signature_sha256": row[4],
                    "revision": revision,
                }
                event_sha = _domain_sha256(
                    "agent-bridge/engram/g1/synthetic-capability-event/v0",
                    jcs_bytes(payload),
                )
                stored_event_sha = row[6]
            _require(
                event_sha == stored_event_sha,
                "E_LEDGER_EVENT",
                f"{kind} event hash drift at revision {revision}",
            )
            chain = _domain_sha256(
                "agent-bridge/engram/g1/synthetic-ledger-chain/v0",
                bytes.fromhex(chain) + bytes.fromhex(event_sha),
            )
        _require(
            chain == meta[4],
            "E_LEDGER_CHAIN",
            "recomputed event chain differs from metadata head",
        )

        high_water_rows = connection.execute(
            "SELECT scope_identity_sha256, last_sequence, boot_epoch_hex, "
            "last_monotonic_ns, last_trusted_utc_seconds, "
            "last_checkpoint_sequence, trusted_time_established "
            "FROM scope_high_water_v0"
        ).fetchall()
        if not claim_rows:
            _require(not high_water_rows, "E_TIME_HIGH_WATER", "orphan high-water row")
        else:
            _require(
                len(high_water_rows) == 1
                and high_water_rows[0][0] == self.scope_identity_sha256,
                "E_TIME_HIGH_WATER",
                "scope high-water row drift",
            )
            ordered_claims = sorted(claim_rows, key=lambda row: row[4])
            _require(
                [row[4] for row in ordered_claims]
                == list(range(1, len(ordered_claims) + 1)),
                "E_SEQUENCE",
                "stored scope sequences are not contiguous",
            )
            trusted_claims = [row for row in ordered_claims if bool(row[14])]
            if trusted_claims:
                expected_high_water = (
                    self.scope_identity_sha256,
                    ordered_claims[-1][4],
                    trusted_claims[-1][10],
                    trusted_claims[-1][11],
                    max(row[12] for row in trusted_claims),
                    max(row[13] for row in trusted_claims),
                    1,
                )
            else:
                expected_high_water = (
                    self.scope_identity_sha256,
                    ordered_claims[-1][4],
                    "",
                    0,
                    0,
                    0,
                    0,
                )
            _require(
                high_water_rows[0] == expected_high_water,
                "E_TIME_HIGH_WATER",
                "durable time/sequence high-water projection drift",
            )

    def _open_existing(self) -> _OpenLedger:
        parent_fd, parent_stat = _open_absolute_directory(self.path.parent)
        sentinel_fd = -1
        connection: sqlite3.Connection | None = None
        try:
            _require(
                parent_stat.st_uid == os.geteuid()
                and stat.S_IMODE(parent_stat.st_mode) == 0o700,
                "E_LEDGER_PARENT",
                "ledger parent must be euid-owned mode 0700",
            )
            validate_mount_identity(
                mount_identity_from_fd(parent_fd), self.mount_identity
            )
            before = os.stat(self.path.name, dir_fd=parent_fd, follow_symlinks=False)
            _require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.geteuid()
                and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600,
                "E_LEDGER_FILE",
                "ledger must be one euid-owned mode 0600 regular file",
            )
            sentinel_fd = os.open(
                self.path.name,
                os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            opened = os.fstat(sentinel_fd)
            _require(
                _same_stat(opened, before),
                "E_LEDGER_RACE",
                "ledger changed while opening",
            )
            validate_mount_identity(
                mount_identity_from_fd(sentinel_fd), self.mount_identity
            )
            connection = sqlite3.connect(
                self.path.as_uri(), isolation_level=None, timeout=5.0, uri=True
            )
            self._configure_connection(connection)
            self._audit_store(connection)
            direct = os.stat(self.path.name, dir_fd=parent_fd, follow_symlinks=False)
            _require(_same_stat(direct, opened), "E_LEDGER_RACE", "ledger path rebound")
            return _OpenLedger(connection, parent_fd, sentinel_fd, parent_stat, opened)
        except BaseException:
            if connection is not None:
                connection.close()
            if sentinel_fd >= 0:
                os.close(sentinel_fd)
            os.close(parent_fd)
            raise

    def _close_existing(self, opened: _OpenLedger, *, durable: bool) -> None:
        error: BaseException | None = None
        try:
            opened.connection.close()
            if durable:
                os.fsync(opened.sentinel_fd)
                os.fsync(opened.parent_fd)
            file_after = os.fstat(opened.sentinel_fd)
            parent_after = os.fstat(opened.parent_fd)
            direct = os.stat(
                self.path.name, dir_fd=opened.parent_fd, follow_symlinks=False
            )
            _require(
                _same_stat(file_after, direct)
                and (file_after.st_dev, file_after.st_ino)
                == (opened.file_stat.st_dev, opened.file_stat.st_ino)
                and (parent_after.st_dev, parent_after.st_ino)
                == (opened.parent_stat.st_dev, opened.parent_stat.st_ino),
                "E_LEDGER_RACE",
                "ledger or parent identity drifted during operation",
            )
        except BaseException as exc:
            error = exc
        finally:
            os.close(opened.sentinel_fd)
            os.close(opened.parent_fd)
        if error is not None:
            raise error

    def _rollback_or_record(self, opened: _OpenLedger, code: str) -> None:
        try:
            opened.connection.execute("ROLLBACK")
        except BaseException as exc:
            self._record_rollback_lesson(opened.parent_fd, code, type(exc).__name__)

    def _record_rollback_lesson(
        self, parent_fd: int, code: str, exception_type: str
    ) -> None:
        name = "synthetic-rollback-lessons.jsonl"
        fd = os.open(
            name,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            os.fchmod(fd, 0o600)
            opened = os.fstat(fd)
            _require(
                stat.S_ISREG(opened.st_mode)
                and opened.st_nlink == 1
                and opened.st_uid == os.geteuid(),
                "E_ROLLBACK_LESSON",
                "rollback lesson journal identity is unsafe",
            )
            record = {
                "code": code,
                "exception_type": exception_type,
                "lesson": "rollback_failed_stop_retry_and_preserve_evidence",
                "schema": (
                    "agent_bridge.engram_g1_authenticated_freeze_authority_"
                    "synthetic_rollback_lesson.v0"
                ),
                "synthetic_fixture": True,
            }
            os.write(fd, jcs_bytes(record) + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)

    def _read_meta(self, connection: sqlite3.Connection) -> tuple[Any, ...]:
        row = connection.execute(
            "SELECT ledger_id_sha256, repository_identity_sha256, "
            "scope_identity_sha256, revision, chain_head_sha256 "
            "FROM ledger_meta_v0 WHERE singleton=1"
        ).fetchone()
        _require(row is not None, "E_LEDGER_META", "ledger metadata missing")
        _require(
            row[0] == self.ledger_id_sha256
            and row[1] == self.repository_identity_sha256
            and row[2] == self.scope_identity_sha256,
            "E_LEDGER_META",
            "ledger identity binding drift",
        )
        return row


_ENVELOPE_KEYS = (
    "adapter_contract_sha256",
    "adapter_implementation_sha256",
    "adapter_implementation_version",
    "boot_epoch_hex",
    "consumer_public_key_sha256",
    "contract_id",
    "expires_at_utc_seconds",
    "g1_3",
    "input_bindings",
    "issued_at_utc_seconds",
    "mode",
    "nonce_hex",
    "only_permitted_successor",
    "preregistration",
    "process_identity_sha256",
    "production_admissible",
    "repository_identity_sha256",
    "schema",
    "scope_identity_sha256",
    "sequence",
    "signers",
    "synthetic_fixture",
    "trust_ledger_id_sha256",
    "trust_ledger_revision",
    "trusted_time_checkpoint_sha256",
)
_PREREGISTRATION_KEYS = (
    "checker_sha256",
    "commit",
    "contract_sha256",
    "validator_sha256",
)
_G1_3_KEYS = _PREREGISTRATION_KEYS
_INPUT_BINDING_KEYS = (
    "byte_length",
    "domain_sha256",
    "name",
    "raw_sha256",
)
_SIGNER_DESCRIPTOR_KEYS = ("key_epoch", "key_id", "role")
_SIGNATURE_BUNDLE_KEYS = (
    "envelope_sha256",
    "mode",
    "production_admissible",
    "schema",
    "signatures",
    "synthetic_fixture",
)
_SIGNATURE_KEYS = ("key_epoch", "key_id", "role", "signature_hex")
_CHECKPOINT_KEYS = (
    "checkpoint",
    "key_epoch",
    "key_id",
    "mode",
    "production_admissible",
    "schema",
    "signature_hex",
    "synthetic_fixture",
)
_CHECKPOINT_BODY_KEYS = (
    "boot_epoch_hex",
    "checkpoint_expires_utc_seconds",
    "checkpoint_sequence",
    "checkpoint_utc_seconds",
    "monotonic_ns",
    "repository_identity_sha256",
    "scope_identity_sha256",
)
_MANIFEST_KEYS = (
    "fixture_id",
    "groups",
    "mode",
    "production_admissible",
    "schema",
    "synthetic_fixture",
)
_PACKET_KEYS = (
    "commitment_sha256",
    "mode",
    "packet_id",
    "production_admissible",
    "role",
    "schema",
    "synthetic_fixture",
)


def _require_sha256(value: Any, code: str, label: str) -> str:
    _require(
        type(value) is str and SHA256_RE.fullmatch(value) is not None,
        code,
        f"{label} must be lowercase SHA-256 hex",
    )
    return value


def _require_kat_marker(value: Mapping[str, Any], label: str) -> None:
    _require(value["mode"] == MODE, "E_MODE", f"{label} mode drift")
    _require(
        value["synthetic_fixture"] is True and value["production_admissible"] is False,
        "E_SYNTHETIC_MARKER",
        f"{label} is not an explicit non-production synthetic fixture",
    )


class SyntheticAuthorityAdapter:
    """Validate one retained synthetic envelope and atomically claim it."""

    def __init__(self) -> None:
        contract, raw = load_registered_contract()
        validate_contract(contract, raw)

    def claim(
        self,
        custody: RetainedCustodySession,
        ledger: PrivateTrustLedgerDouble,
        anchor: ExternalRevisionAnchorDouble,
        time_sample: TrustedTimeSample,
        consumer_public_key: bytes,
    ) -> tuple[dict[str, Any], "SyntheticDesignReviewCapability"]:
        _require(
            type(custody) is RetainedCustodySession,
            "E_CUSTODY_TYPE",
            "claim requires a retained custody session",
        )
        _require(
            type(ledger) is PrivateTrustLedgerDouble
            and type(anchor) is ExternalRevisionAnchorDouble,
            "E_LEDGER_TYPE",
            "claim requires exact private ledger doubles",
        )
        _require(
            type(time_sample) is TrustedTimeSample,
            "E_TIME_SAMPLE",
            "time sample type drift",
        )
        _require(
            type(consumer_public_key) is bytes and len(consumer_public_key) == 32,
            "E_CONSUMER_KEY",
            "consumer public key must be 32 bytes",
        )
        _require(
            ledger.path == custody.config.ledger_path,
            "E_LEDGER_CONFIG",
            "ledger path differs from owner configuration",
        )
        _require(
            ledger.repository_identity_sha256 == custody.repository_identity_sha256
            and ledger.scope_identity_sha256 == custody.scope_identity_sha256,
            "E_LEDGER_CONFIG",
            "ledger repository or scope binding drift",
        )
        try:
            common = os.path.commonpath(
                [str(custody.config.repository_root), str(ledger.path)]
            )
        except ValueError as exc:
            raise IsolatedLabError(
                "E_LEDGER_CONFIG", "ledger path comparison failed"
            ) from exc
        _require(
            common != str(custody.config.repository_root),
            "E_LEDGER_CONFIG",
            "private trust ledger must remain outside the repository",
        )

        captures = custody.captures()
        manifest = decode_canonical_json(captures["manifest.json"].raw, "manifest")
        self._validate_manifest(manifest)
        for role in ROLES:
            packet_name = role + ".packet.json"
            packet = decode_canonical_json(captures[packet_name].raw, packet_name)
            self._validate_packet(packet, role)
        checkpoint = decode_canonical_json(
            captures["trusted_time_checkpoint.json"].raw, "trusted time checkpoint"
        )
        self._validate_checkpoint(checkpoint)
        envelope = decode_canonical_json(captures["envelope.json"].raw, "envelope")
        self._validate_envelope(
            envelope,
            custody,
            ledger,
            captures,
            time_sample,
            consumer_public_key,
        )
        signature_bundle = decode_canonical_json(
            captures["signatures.json"].raw, "signature bundle"
        )
        signatures = self._validate_signature_bundle(
            signature_bundle, envelope, captures["envelope.json"].raw
        )
        process_identity = process_identity_sha256(time_sample.boot_epoch_hex)
        record = ledger.claim(
            anchor,
            envelope=envelope,
            envelope_raw=captures["envelope.json"].raw,
            signatures=signatures,
            checkpoint=checkpoint,
            checkpoint_raw=captures["trusted_time_checkpoint.json"].raw,
            time_sample=time_sample,
            consumer_public_key=consumer_public_key,
            process_identity=process_identity,
            precommit=custody.revalidate_for_claim,
        )
        receipt = self._build_receipt(
            custody,
            ledger,
            envelope,
            captures,
            signature_bundle,
            record,
            process_identity,
            consumer_public_key,
        )
        capability = SyntheticDesignReviewCapability(
            ledger=ledger,
            anchor=anchor,
            claim_event_sha256=record.event_sha256,
            envelope_sha256=_sha256(captures["envelope.json"].raw),
            consumer_public_key=consumer_public_key,
            process_identity=process_identity,
            boot_epoch_hex=time_sample.boot_epoch_hex,
        )
        return receipt, capability

    @staticmethod
    def _validate_manifest(manifest: Mapping[str, Any]) -> None:
        _exact_keys(manifest, _MANIFEST_KEYS, "E_MANIFEST", "manifest")
        _require_kat_marker(manifest, "manifest")
        _require(
            manifest["schema"] == MANIFEST_SCHEMA, "E_MANIFEST", "manifest schema drift"
        )
        _require(
            manifest["fixture_id"] == "PUBLIC_NONSECRET_G1_MANIFEST_KAT_V0",
            "E_MANIFEST",
            "manifest fixture id drift",
        )
        _require(
            type(manifest["groups"]) is list
            and manifest["groups"] == ["synthetic-group-a", "synthetic-group-b"],
            "E_MANIFEST",
            "manifest synthetic groups drift",
        )

    @staticmethod
    def _validate_packet(packet: Mapping[str, Any], role: str) -> None:
        _exact_keys(packet, _PACKET_KEYS, "E_PACKET", f"{role} packet")
        _require_kat_marker(packet, f"{role} packet")
        _require(packet["schema"] == PACKET_SCHEMA, "E_PACKET", "packet schema drift")
        _require(packet["role"] == role, "E_PACKET", "packet role drift")
        _require(
            packet["packet_id"] == f"public-synthetic-{role}-packet-v0",
            "E_PACKET",
            "packet id drift",
        )
        _require_sha256(packet["commitment_sha256"], "E_PACKET", "packet commitment")

    @staticmethod
    def _validate_checkpoint(checkpoint: Mapping[str, Any]) -> None:
        _exact_keys(checkpoint, _CHECKPOINT_KEYS, "E_TIME_CHECKPOINT", "checkpoint")
        _require_kat_marker(checkpoint, "checkpoint")
        _require(
            checkpoint["schema"] == TIME_CHECKPOINT_SCHEMA,
            "E_TIME_CHECKPOINT",
            "checkpoint schema drift",
        )
        _require(
            checkpoint["key_id"] == "kat-trusted-time-checkpoint-authority-v1"
            and checkpoint["key_epoch"] == 1,
            "E_TIME_CHECKPOINT",
            "checkpoint key identity drift",
        )
        _require(
            type(checkpoint["signature_hex"]) is str
            and HEX_64_RE.fullmatch(checkpoint["signature_hex"]) is not None,
            "E_TIME_CHECKPOINT",
            "checkpoint signature format drift",
        )
        body = _exact_keys(
            checkpoint["checkpoint"],
            _CHECKPOINT_BODY_KEYS,
            "E_TIME_CHECKPOINT",
            "checkpoint body",
        )
        _require(
            type(body["boot_epoch_hex"]) is str
            and HEX_32_RE.fullmatch(body["boot_epoch_hex"]) is not None,
            "E_TIME_CHECKPOINT",
            "checkpoint boot epoch drift",
        )
        for field in (
            "checkpoint_expires_utc_seconds",
            "checkpoint_sequence",
            "checkpoint_utc_seconds",
            "monotonic_ns",
        ):
            _require(
                type(body[field]) is int and body[field] >= 0,
                "E_TIME_CHECKPOINT",
                f"checkpoint {field} drift",
            )
        _require(
            body["checkpoint_sequence"] >= 1
            and body["checkpoint_expires_utc_seconds"]
            >= body["checkpoint_utc_seconds"],
            "E_TIME_CHECKPOINT",
            "checkpoint sequence/window drift",
        )
        _require_sha256(
            body["repository_identity_sha256"],
            "E_TIME_CHECKPOINT",
            "checkpoint repository",
        )
        _require_sha256(
            body["scope_identity_sha256"], "E_TIME_CHECKPOINT", "checkpoint scope"
        )

    def _validate_envelope(
        self,
        envelope: Mapping[str, Any],
        custody: RetainedCustodySession,
        ledger: PrivateTrustLedgerDouble,
        captures: Mapping[str, CapturedFile],
        time_sample: TrustedTimeSample,
        consumer_public_key: bytes,
    ) -> None:
        _exact_keys(envelope, _ENVELOPE_KEYS, "E_ENVELOPE", "envelope")
        _require_kat_marker(envelope, "envelope")
        _require(
            envelope["schema"] == ENVELOPE_SCHEMA, "E_ENVELOPE", "envelope schema drift"
        )
        _require(
            envelope["contract_id"] == CONTRACT_ID, "E_ENVELOPE", "contract id drift"
        )
        _require(
            envelope["adapter_contract_sha256"] == CONTRACT_SHA256
            and envelope["adapter_implementation_version"] == IMPLEMENTATION_VERSION
            and envelope["adapter_implementation_sha256"] == implementation_sha256(),
            "E_ADAPTER_BINDING",
            "adapter contract or implementation binding drift",
        )
        prereg = _exact_keys(
            envelope["preregistration"],
            _PREREGISTRATION_KEYS,
            "E_PREREGISTRATION_BINDING",
            "preregistration",
        )
        _require(
            prereg
            == {
                "checker_sha256": PREREGISTRATION_CHECKER_SHA256,
                "commit": PREREGISTRATION_COMMIT,
                "contract_sha256": PREREGISTRATION_CONTRACT_SHA256,
                "validator_sha256": PREREGISTRATION_VALIDATOR_SHA256,
            },
            "E_PREREGISTRATION_BINDING",
            "preregistration identity drift",
        )
        g1_3 = _exact_keys(envelope["g1_3"], _G1_3_KEYS, "E_G1_3_BINDING", "g1_3")
        _require(
            g1_3
            == {
                "checker_sha256": G1_3_CHECKER_SHA256,
                "commit": G1_3_COMMIT,
                "contract_sha256": G1_3_CONTRACT_SHA256,
                "validator_sha256": G1_3_VALIDATOR_SHA256,
            },
            "E_G1_3_BINDING",
            "G1.3 identity drift",
        )
        _require(
            envelope["repository_identity_sha256"]
            == custody.repository_identity_sha256
            == ledger.repository_identity_sha256,
            "E_REPOSITORY_BINDING",
            "repository identity drift",
        )
        _require(
            envelope["scope_identity_sha256"]
            == custody.scope_identity_sha256
            == ledger.scope_identity_sha256,
            "E_SCOPE_BINDING",
            "scope identity drift",
        )
        _require(
            envelope["trust_ledger_id_sha256"] == ledger.ledger_id_sha256
            and type(envelope["trust_ledger_revision"]) is int
            and envelope["trust_ledger_revision"] >= 1,
            "E_LEDGER_BINDING",
            "trust ledger identity/revision drift",
        )
        _require(
            type(envelope["nonce_hex"]) is str
            and len(bytes.fromhex(envelope["nonce_hex"])) >= MIN_NONCE_BYTES,
            "E_NONCE",
            "nonce is shorter than 32 bytes",
        )
        _require(
            type(envelope["sequence"]) is int and envelope["sequence"] >= 1,
            "E_SEQUENCE",
            "sequence drift",
        )
        _require(
            type(envelope["issued_at_utc_seconds"]) is int
            and type(envelope["expires_at_utc_seconds"]) is int
            and envelope["expires_at_utc_seconds"] >= envelope["issued_at_utc_seconds"],
            "E_TIME_WINDOW",
            "envelope time fields drift",
        )
        _require(
            envelope["boot_epoch_hex"] == time_sample.boot_epoch_hex
            and HEX_32_RE.fullmatch(envelope["boot_epoch_hex"]) is not None,
            "E_BOOT_EPOCH",
            "envelope boot epoch drift",
        )
        _require_sha256(
            envelope["trusted_time_checkpoint_sha256"],
            "E_TIME_BINDING",
            "checkpoint digest",
        )
        expected_process = process_identity_sha256(time_sample.boot_epoch_hex)
        _require(
            envelope["consumer_public_key_sha256"] == _sha256(consumer_public_key)
            and envelope["process_identity_sha256"] == expected_process,
            "E_CONSUMER_BINDING",
            "consumer key or process identity drift",
        )
        _require(
            envelope["only_permitted_successor"]
            == "separate_g1_4_candidate_protocol_preregistration_design_review",
            "E_SUCCESSOR",
            "successor scope widened",
        )
        bindings = envelope["input_bindings"]
        _require(
            type(bindings) is list, "E_INPUT_BINDING", "input bindings must be a list"
        )
        _require(
            tuple(binding.get("name") for binding in bindings) == BOUND_INPUT_NAMES,
            "E_INPUT_BINDING",
            "input binding names/order drift",
        )
        private_digests: list[str] = []
        for binding in bindings:
            _exact_keys(
                binding, _INPUT_BINDING_KEYS, "E_INPUT_BINDING", "input binding"
            )
            captured = captures[binding["name"]]
            _require(
                binding
                == {
                    "byte_length": captured.byte_length,
                    "domain_sha256": captured.domain_sha256,
                    "name": captured.name,
                    "raw_sha256": captured.raw_sha256,
                },
                "E_INPUT_BINDING",
                f"retained input binding drift: {captured.name}",
            )
            private_digests.extend((captured.raw_sha256, captured.domain_sha256))
        _require(
            len(private_digests) == len(set(private_digests)),
            "E_PRIVATE_DIGEST_ALIAS",
            "private input digest aliases another private binding",
        )
        _require(
            set(private_digests).isdisjoint(set(PUBLIC_BINDINGS.values())),
            "E_PRIVATE_DIGEST_ALIAS",
            "private input digest aliases a public binding",
        )
        signers = envelope["signers"]
        _require(
            type(signers) is list and len(signers) == len(ROLES),
            "E_SIGNERS",
            "signer count drift",
        )
        _require(
            tuple(signer.get("role") for signer in signers) == ROLES,
            "E_SIGNERS",
            "signer role order drift",
        )
        ids: set[str] = set()
        for signer in signers:
            _exact_keys(signer, _SIGNER_DESCRIPTOR_KEYS, "E_SIGNERS", "signer")
            _require(
                KEY_ID_RE.fullmatch(signer["key_id"]) is not None
                and type(signer["key_epoch"]) is int
                and signer["key_epoch"] >= 1
                and signer["key_id"] not in ids,
                "E_SIGNERS",
                "signer key identity drift or duplicate",
            )
            ids.add(signer["key_id"])

    @staticmethod
    def _validate_signature_bundle(
        bundle: Mapping[str, Any],
        envelope: Mapping[str, Any],
        envelope_raw: bytes,
    ) -> tuple[Mapping[str, Any], ...]:
        _exact_keys(
            bundle, _SIGNATURE_BUNDLE_KEYS, "E_SIGNATURE_BUNDLE", "signature bundle"
        )
        _require_kat_marker(bundle, "signature bundle")
        _require(
            bundle["schema"] == SIGNATURE_BUNDLE_SCHEMA,
            "E_SIGNATURE_BUNDLE",
            "signature bundle schema drift",
        )
        _require(
            bundle["envelope_sha256"] == _sha256(envelope_raw),
            "E_SIGNATURE_BUNDLE",
            "signature bundle envelope digest drift",
        )
        signatures = bundle["signatures"]
        _require(
            type(signatures) is list and len(signatures) == len(ROLES),
            "E_QUORUM",
            "signature count drift",
        )
        _require(
            tuple(signature.get("role") for signature in signatures) == ROLES,
            "E_QUORUM",
            "signature role order drift",
        )
        descriptors = envelope["signers"]
        for index, signature in enumerate(signatures):
            _exact_keys(signature, _SIGNATURE_KEYS, "E_SIGNATURE_BUNDLE", "signature")
            _require(
                {key: signature[key] for key in _SIGNER_DESCRIPTOR_KEYS}
                == descriptors[index],
                "E_SIGNATURE_BINDING",
                "signature role/key/epoch differs from envelope",
            )
            _require(
                type(signature["signature_hex"]) is str
                and HEX_64_RE.fullmatch(signature["signature_hex"]) is not None,
                "E_SIGNATURE_FORMAT",
                "signature must be 64-byte lowercase hex",
            )
        return tuple(signatures)

    @staticmethod
    def _build_receipt(
        custody: RetainedCustodySession,
        ledger: PrivateTrustLedgerDouble,
        envelope: Mapping[str, Any],
        captures: Mapping[str, CapturedFile],
        signature_bundle: Mapping[str, Any],
        record: ClaimRecord,
        process_identity: str,
        consumer_public_key: bytes,
    ) -> dict[str, Any]:
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "verdict": "SYNTHETIC_IMPLEMENTATION_GATE_EXERCISED_NO_AUTHORITY",
            "mode": MODE,
            "synthetic_fixture": True,
            "production_admissible": False,
            "contract_id": CONTRACT_ID,
            "contract_sha256": CONTRACT_SHA256,
            "implementation_version": IMPLEMENTATION_VERSION,
            "implementation_sha256": implementation_sha256(),
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "g1_3_commit": G1_3_COMMIT,
            "repository_identity_sha256": custody.repository_identity_sha256,
            "scope_identity_sha256": custody.scope_identity_sha256,
            "manifest_sha256": captures["manifest.json"].raw_sha256,
            "envelope_sha256": _sha256(captures["envelope.json"].raw),
            "signature_bundle_sha256": _sha256(captures["signatures.json"].raw),
            "signature_count": len(signature_bundle["signatures"]),
            "all_required_roles_exactly_once": True,
            "trust_ledger_id_sha256": ledger.ledger_id_sha256,
            "claim_event_sha256": record.event_sha256,
            "claim_ledger_revision": record.ledger_revision,
            "claim_state": record.state,
            "trusted_time_profile": (
                "monotonic_clock_plus_durable_boot_epoch_and_"
                "signed_time_checkpoint_v1"
            ),
            "retained_repository_root_descriptor": True,
            "retained_git_common_dir_descriptor": True,
            "retained_private_file_descriptor_count": len(PRIVATE_INPUT_NAMES),
            "retained_descriptor_count_at_claim": custody.retained_fd_count,
            "mount_filesystem_type": custody.mount_identity.filesystem_type,
            "mount_identity_sha256": _sha256(
                jcs_bytes(
                    {
                        "fsid_0": custody.mount_identity.fsid_0,
                        "fsid_1": custody.mount_identity.fsid_1,
                        "filesystem_type": custody.mount_identity.filesystem_type,
                        "mountpoint_sha256": custody.mount_identity.mountpoint_sha256,
                        "st_dev": custody.mount_identity.st_dev,
                    }
                )
            ),
            "consumer_public_key_sha256": _sha256(consumer_public_key),
            "process_identity_sha256": process_identity,
            "capability_schema": CAPABILITY_SCHEMA,
            "capability_is_bearer": False,
            "capability_is_single_use": True,
            "only_permitted_successor": envelope["only_permitted_successor"],
            "manual_audit_transition_exercised": False,
            "real_authenticated_freeze_authority_verified": False,
            "real_secure_custody_verified": False,
            "real_trust_root_provisioned": False,
            "real_capability_minted": False,
            "g1_4_open": False,
            "candidate_manifest_access_authority": False,
            "candidate_fit_access_authority": False,
            "candidate_implementation_authority": False,
            "biocortex_experiment_execution_authority": False,
            "retrieval_order_mutation_authority": False,
            "live_store_write_authority": False,
            "runtime_promotion_authority": False,
        }
        return receipt


class SyntheticDesignReviewCapability:
    """Nonserializable, process/key-bound, one-use synthetic successor token."""

    __slots__ = (
        "_anchor",
        "_boot_epoch_hex",
        "_claim_event_sha256",
        "_consumer_public_key",
        "_creator_pid",
        "_envelope_sha256",
        "_ledger",
        "_process_identity",
    )

    def __init__(
        self,
        *,
        ledger: PrivateTrustLedgerDouble,
        anchor: ExternalRevisionAnchorDouble,
        claim_event_sha256: str,
        envelope_sha256: str,
        consumer_public_key: bytes,
        process_identity: str,
        boot_epoch_hex: str,
    ) -> None:
        self._ledger = ledger
        self._anchor = anchor
        self._claim_event_sha256 = claim_event_sha256
        self._envelope_sha256 = envelope_sha256
        self._consumer_public_key = bytes(consumer_public_key)
        self._process_identity = process_identity
        self._boot_epoch_hex = boot_epoch_hex
        self._creator_pid = os.getpid()

    @property
    def challenge_bytes(self) -> bytes:
        frame = {
            "claim_event_sha256": self._claim_event_sha256,
            "envelope_sha256": self._envelope_sha256,
            "process_identity_sha256": self._process_identity,
        }
        return CAPABILITY_DOMAIN.encode("utf-8") + b"\x00" + jcs_bytes(frame)

    def exercise_only_permitted_successor(
        self, proof_signature: bytes
    ) -> dict[str, Any]:
        _require(
            os.getpid() == self._creator_pid
            and process_identity_sha256(self._boot_epoch_hex) == self._process_identity,
            "E_CAPABILITY_PROCESS",
            "capability moved to another process identity",
        )
        record = self._ledger.consume_capability(
            self._anchor,
            claim_event_sha256=self._claim_event_sha256,
            consumer_public_key=self._consumer_public_key,
            process_identity=self._process_identity,
            challenge=self.challenge_bytes,
            proof_signature=proof_signature,
        )
        return {
            "schema": (
                "agent_bridge.engram_g1_authenticated_freeze_authority_"
                "synthetic_successor_exercise_receipt.v0"
            ),
            "verdict": "SYNTHETIC_SUCCESSOR_BINDING_EXERCISED_G1_4_REMAINS_CLOSED",
            "claim_event_sha256": self._claim_event_sha256,
            "capability_event_sha256": record.event_sha256,
            "ledger_revision": record.ledger_revision,
            "consumer_public_key_sha256": _sha256(self._consumer_public_key),
            "process_identity_sha256": self._process_identity,
            "only_permitted_successor": (
                "separate_g1_4_candidate_protocol_preregistration_design_review"
            ),
            "g1_4_open": False,
            "candidate_access_authority": False,
            "execution_authority": False,
            "retrieval_mutation_authority": False,
            "live_store_write_authority": False,
            "runtime_promotion_authority": False,
        }

    def __getstate__(self) -> None:
        raise TypeError("synthetic capability is nonserializable")

    def __reduce__(self) -> None:
        raise TypeError("synthetic capability is nonserializable")
