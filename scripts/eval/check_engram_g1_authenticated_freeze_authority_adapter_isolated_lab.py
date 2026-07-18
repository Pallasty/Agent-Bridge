#!/usr/bin/env python3
"""Adversarial checker for the G1 authenticated-freeze isolated lab gate."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import os
import pickle
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


EXPECTED_CONTRACT_SHA256 = (
    "f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14"
)
EXPECTED_IMPLEMENTATION_SHA256 = (
    "50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94"
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def expect_error(action: Callable[[], Any], code: str) -> str:
    try:
        action()
    except module.IsolatedLabError as exc:
        require(exc.code == code, f"expected {code}, got {exc.code}: {exc}")
        return str(exc)
    raise CheckFailure(f"expected rejection {code}")


def git_common_dir(repo: Path) -> Path:
    dotgit = repo / ".git"
    if dotgit.is_dir():
        return dotgit
    text = dotgit.read_text(encoding="utf-8").strip()
    require(text.startswith("gitdir: "), "worktree .git file drift")
    git_dir = Path(text.removeprefix("gitdir: "))
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    return (git_dir / common).resolve()


def write_private(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            require(written > 0, f"short write: {path.name}")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path: Path, value: Any) -> None:
    write_private(path, module.jcs_bytes(value))


class Harness:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.ledger_dir = Path(
            tempfile.mkdtemp(prefix="ab-g1-ledger-kat-", dir="/private/tmp")
        )
        self.private_dir = Path(tempfile.mkdtemp(prefix=".ab-g1-freeze-kat-", dir=repo))
        os.chmod(self.ledger_dir, 0o700)
        os.chmod(self.private_dir, 0o700)
        try:
            self._initialize(repo)
        except BaseException:
            self.close()
            raise

    def _initialize(self, repo: Path) -> None:
        self.ledger_path = self.ledger_dir / "private-trust-ledger.sqlite3"
        self.boot_epoch_hex = hashlib.sha256(b"public-synthetic-boot-epoch").hexdigest()
        self.checkpoint_utc = 1_800_000_000
        self.checkpoint_monotonic_ns = 10_000_000_000
        self.consumer_seed = module.synthetic_seed("authorized-consumer")
        self.consumer_public_key = module.ed25519_public_key(self.consumer_seed)
        self.role_seeds = {role: module.synthetic_seed(role) for role in module.ROLES}
        self.time_seed = module.synthetic_seed(module.TIME_ROLE)
        self.key_ids = {
            role: "kat-" + role.replace("_", "-") + "-v1" for role in module.ROLES
        }
        self.time_key_id = "kat-trusted-time-checkpoint-authority-v1"
        self.config = module.SyntheticLabConfig(
            repository_root=repo,
            git_common_dir=git_common_dir(repo),
            private_input_dir_relative=self.private_dir.name,
            ledger_path=self.ledger_path,
            canonical_scope=f"project:{repo}",
            mode=module.MODE,
            enabled=True,
        )
        self._write_initial_inputs()
        with module.RetainedCustodySession(self.config) as setup:
            repository_identity = setup.repository_identity_sha256
            scope_identity = setup.scope_identity_sha256
            mount_identity = setup.mount_identity
        keys = [
            module.TrustKeyProvision(
                role=role,
                key_id=self.key_ids[role],
                key_epoch=1,
                public_key=module.ed25519_public_key(self.role_seeds[role]),
            )
            for role in module.ROLES
        ]
        keys.append(
            module.TrustKeyProvision(
                role=module.TIME_ROLE,
                key_id=self.time_key_id,
                key_epoch=1,
                public_key=module.ed25519_public_key(self.time_seed),
            )
        )
        self.ledger, self.anchor = module.PrivateTrustLedgerDouble.initialize(
            self.ledger_path,
            repository_identity,
            scope_identity,
            mount_identity,
            keys,
        )
        self._write_checkpoint(checkpoint_sequence=1)
        self.refresh_envelope(sequence=1, nonce_label="claim-1")

    def close(self) -> None:
        for path in (self.private_dir, self.ledger_dir):
            if path.exists():
                shutil.rmtree(path)

    def __enter__(self) -> "Harness":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    @property
    def default_time_sample(self) -> module.TrustedTimeSample:
        return module.TrustedTimeSample(
            boot_epoch_hex=self.boot_epoch_hex,
            monotonic_ns=self.checkpoint_monotonic_ns + 60_000_000_000,
        )

    def _write_initial_inputs(self) -> None:
        manifest = {
            "fixture_id": "PUBLIC_NONSECRET_G1_MANIFEST_KAT_V0",
            "groups": ["synthetic-group-a", "synthetic-group-b"],
            "mode": module.MODE,
            "production_admissible": False,
            "schema": module.MANIFEST_SCHEMA,
            "synthetic_fixture": True,
        }
        write_json(self.private_dir / "manifest.json", manifest)
        for role in module.ROLES:
            packet = {
                "commitment_sha256": hashlib.sha256(
                    ("public-synthetic-commitment:" + role).encode("utf-8")
                ).hexdigest(),
                "mode": module.MODE,
                "packet_id": f"public-synthetic-{role}-packet-v0",
                "production_admissible": False,
                "role": role,
                "schema": module.PACKET_SCHEMA,
                "synthetic_fixture": True,
            }
            write_json(self.private_dir / f"{role}.packet.json", packet)
        for name in (
            "trusted_time_checkpoint.json",
            "envelope.json",
            "signatures.json",
        ):
            write_json(self.private_dir / name, {})

    def _write_checkpoint(self, checkpoint_sequence: int) -> None:
        body = {
            "boot_epoch_hex": self.boot_epoch_hex,
            "checkpoint_expires_utc_seconds": self.checkpoint_utc + 3_600,
            "checkpoint_sequence": checkpoint_sequence,
            "checkpoint_utc_seconds": self.checkpoint_utc,
            "monotonic_ns": self.checkpoint_monotonic_ns,
            "repository_identity_sha256": self.ledger.repository_identity_sha256,
            "scope_identity_sha256": self.ledger.scope_identity_sha256,
        }
        message = module.TIME_DOMAIN.encode("utf-8") + b"\x00" + module.jcs_bytes(body)
        checkpoint = {
            "checkpoint": body,
            "key_epoch": 1,
            "key_id": self.time_key_id,
            "mode": module.MODE,
            "production_admissible": False,
            "schema": module.TIME_CHECKPOINT_SCHEMA,
            "signature_hex": module.ed25519_sign(message, self.time_seed).hex(),
            "synthetic_fixture": True,
        }
        write_json(self.private_dir / "trusted_time_checkpoint.json", checkpoint)

    def refresh_envelope(
        self,
        *,
        sequence: int,
        nonce_label: str,
        trust_revision: int | None = None,
        issued_at: int | None = None,
        expires_at: int | None = None,
        mutate: Callable[[dict[str, Any]], None] | None = None,
        signature_mutator: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        with module.RetainedCustodySession(self.config) as custody:
            captures = custody.captures()
            repository_identity = custody.repository_identity_sha256
            scope_identity = custody.scope_identity_sha256
        input_bindings = [
            {
                "byte_length": captures[name].byte_length,
                "domain_sha256": captures[name].domain_sha256,
                "name": name,
                "raw_sha256": captures[name].raw_sha256,
            }
            for name in module.BOUND_INPUT_NAMES
        ]
        signers = [
            {"key_epoch": 1, "key_id": self.key_ids[role], "role": role}
            for role in module.ROLES
        ]
        envelope = {
            "adapter_contract_sha256": module.CONTRACT_SHA256,
            "adapter_implementation_sha256": module.implementation_sha256(),
            "adapter_implementation_version": module.IMPLEMENTATION_VERSION,
            "boot_epoch_hex": self.boot_epoch_hex,
            "consumer_public_key_sha256": hashlib.sha256(
                self.consumer_public_key
            ).hexdigest(),
            "contract_id": module.CONTRACT_ID,
            "expires_at_utc_seconds": (
                self.checkpoint_utc + 300 if expires_at is None else expires_at
            ),
            "g1_3": {
                "checker_sha256": module.G1_3_CHECKER_SHA256,
                "commit": module.G1_3_COMMIT,
                "contract_sha256": module.G1_3_CONTRACT_SHA256,
                "validator_sha256": module.G1_3_VALIDATOR_SHA256,
            },
            "input_bindings": input_bindings,
            "issued_at_utc_seconds": (
                self.checkpoint_utc if issued_at is None else issued_at
            ),
            "mode": module.MODE,
            "nonce_hex": hashlib.sha256(
                ("public-synthetic-nonce:" + nonce_label).encode("utf-8")
            ).hexdigest(),
            "only_permitted_successor": (
                "separate_g1_4_candidate_protocol_preregistration_design_review"
            ),
            "preregistration": {
                "checker_sha256": module.PREREGISTRATION_CHECKER_SHA256,
                "commit": module.PREREGISTRATION_COMMIT,
                "contract_sha256": module.PREREGISTRATION_CONTRACT_SHA256,
                "validator_sha256": module.PREREGISTRATION_VALIDATOR_SHA256,
            },
            "process_identity_sha256": module.process_identity_sha256(
                self.boot_epoch_hex
            ),
            "production_admissible": False,
            "repository_identity_sha256": repository_identity,
            "schema": module.ENVELOPE_SCHEMA,
            "scope_identity_sha256": scope_identity,
            "sequence": sequence,
            "signers": signers,
            "synthetic_fixture": True,
            "trust_ledger_id_sha256": self.ledger.ledger_id_sha256,
            "trust_ledger_revision": (
                self.anchor.revision if trust_revision is None else trust_revision
            ),
            "trusted_time_checkpoint_sha256": captures[
                "trusted_time_checkpoint.json"
            ].raw_sha256,
        }
        if mutate is not None:
            mutate(envelope)
        envelope_raw = module.jcs_bytes(envelope)
        write_private(self.private_dir / "envelope.json", envelope_raw)
        signatures = []
        for role in module.ROLES:
            message = module.ROLE_DOMAINS[role].encode("utf-8") + b"\x00" + envelope_raw
            signatures.append(
                {
                    "key_epoch": 1,
                    "key_id": self.key_ids[role],
                    "role": role,
                    "signature_hex": module.ed25519_sign(
                        message, self.role_seeds[role]
                    ).hex(),
                }
            )
        bundle = {
            "envelope_sha256": hashlib.sha256(envelope_raw).hexdigest(),
            "mode": module.MODE,
            "production_admissible": False,
            "schema": module.SIGNATURE_BUNDLE_SCHEMA,
            "signatures": signatures,
            "synthetic_fixture": True,
        }
        if signature_mutator is not None:
            signature_mutator(bundle)
        write_json(self.private_dir / "signatures.json", bundle)

    def claim(
        self,
        *,
        time_sample: module.TrustedTimeSample | None = None,
        hook: Callable[[module.RetainedCustodySession], None] | None = None,
        consumer_public_key: bytes | None = None,
    ) -> tuple[dict[str, Any], module.SyntheticDesignReviewCapability]:
        with module.RetainedCustodySession(
            self.config, precommit_fault_hook=hook
        ) as custody:
            return module.SyntheticAuthorityAdapter().claim(
                custody,
                self.ledger,
                self.anchor,
                self.default_time_sample if time_sample is None else time_sample,
                (
                    self.consumer_public_key
                    if consumer_public_key is None
                    else consumer_public_key
                ),
            )

    def database_bytes(self) -> bytes:
        return self.ledger_path.read_bytes()

    def high_water(self) -> tuple[Any, ...]:
        connection = sqlite3.connect(self.ledger_path)
        try:
            row = connection.execute(
                "SELECT last_sequence, boot_epoch_hex, last_monotonic_ns, "
                "last_trusted_utc_seconds, last_checkpoint_sequence, "
                "trusted_time_established FROM scope_high_water_v0"
            ).fetchone()
            require(row is not None, "missing scope high-water row")
            return row
        finally:
            connection.close()

    def restore_database_bytes(self, raw: bytes) -> None:
        write_private(self.ledger_path, raw)


def iter_scalar_paths(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if type(value) is dict:
        paths: list[tuple[Any, ...]] = []
        for key, child in value.items():
            paths.extend(iter_scalar_paths(child, path + (key,)))
        return paths
    if type(value) is list:
        paths = []
        for index, child in enumerate(value):
            paths.extend(iter_scalar_paths(child, path + (index,)))
        return paths
    return [path]


def path_text(path: tuple[Any, ...]) -> str:
    result = "contract"
    for part in path:
        result += f"[{part}]" if type(part) is int else f".{part}"
    return result


def replace_at_path(value: Any, path: tuple[Any, ...]) -> None:
    cursor = value
    for part in path[:-1]:
        cursor = cursor[part]
    key = path[-1]
    old = cursor[key]
    if type(old) is bool:
        replacement = not old
    elif type(old) is int:
        replacement = old + 1
    elif type(old) is str:
        replacement = old + "-drift"
    elif old is None:
        replacement = "not-null"
    else:
        raise CheckFailure(f"unhandled scalar type: {type(old).__name__}")
    cursor[key] = replacement


def test_contract_semantics_and_raw_pin() -> int:
    contract, raw = module.load_registered_contract()
    require(
        hashlib.sha256(raw).hexdigest() == EXPECTED_CONTRACT_SHA256,
        "contract pin drift",
    )
    module.validate_contract(copy.deepcopy(contract), raw)
    cases = 0
    for path in iter_scalar_paths(contract):
        candidate = copy.deepcopy(contract)
        replace_at_path(candidate, path)
        detail = expect_error(
            lambda candidate=candidate: module.validate_contract_semantics(candidate),
            "E_CONTRACT_SEMANTICS",
        )
        require(
            path_text(path) in detail, f"mutation did not fail at {path_text(path)}"
        )
        cases += 1
    extra = copy.deepcopy(contract)
    extra["unexpected"] = False
    expect_error(
        lambda: module.validate_contract_semantics(extra), "E_CONTRACT_SEMANTICS"
    )
    missing = copy.deepcopy(contract)
    del missing["boundaries"]
    expect_error(
        lambda: module.validate_contract_semantics(missing), "E_CONTRACT_SEMANTICS"
    )
    reordered = copy.deepcopy(contract)
    reordered["signature_policy"]["required_roles_in_order"] = list(
        reversed(reordered["signature_policy"]["required_roles_in_order"])
    )
    expect_error(
        lambda: module.validate_contract_semantics(reordered), "E_CONTRACT_SEMANTICS"
    )
    expect_error(
        lambda: module.validate_contract(contract, raw + b"\n"), "E_CONTRACT_HASH"
    )
    duplicate = b'{"schema":"a","schema":"b"}'
    expect_error(
        lambda: module.decode_closed_json(duplicate, "duplicate"),
        "E_DUPLICATE_JSON_KEY",
    )
    return cases + 5


def test_jcs_and_ed25519_known_answers() -> int:
    ordering = {
        "\u20ac": "euro",
        "\r": "cr",
        "\ufb33": "hebrew",
        "1": "one",
        "😀": "emoji",
        "\u0080": "control",
        "ö": "o-diaeresis",
    }
    expected = (
        b'{"\\r":"cr","1":"one","\xc2\x80":"control","\xc3\xb6":"o-diaeresis",'
        b'"\xe2\x82\xac":"euro","\xf0\x9f\x98\x80":"emoji","\xef\xac\xb3":"hebrew"}'
    )
    require(module.jcs_bytes(ordering) == expected, "RFC 8785 UTF-16 ordering drift")
    expect_error(lambda: module.jcs_bytes({"float": 1.5}), "E_JCS_TYPE")
    expect_error(
        lambda: module.jcs_bytes({"unsafe": module.MAX_SAFE_INTEGER + 1}),
        "E_JCS_INTEGER",
    )
    expect_error(lambda: module.jcs_bytes({"surrogate": "\ud800"}), "E_JCS_UNICODE")

    seed = bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    )
    public_key = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    )
    signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    require(module.ed25519_public_key(seed) == public_key, "RFC 8032 public key drift")
    require(module.ed25519_sign(b"", seed) == signature, "RFC 8032 signature drift")
    require(module.ed25519_verify(signature, b"", public_key), "RFC 8032 verify drift")
    changed = bytearray(signature)
    changed[0] ^= 1
    require(
        not module.ed25519_verify(bytes(changed), b"", public_key),
        "tampered signature accepted",
    )
    noncanonical = (1 << 255).to_bytes(32, "little") + signature[32:]
    require(
        not module.ed25519_verify(noncanonical, b"", public_key),
        "noncanonical point accepted",
    )
    return 10


def test_default_off(repo: Path) -> int:
    config = module.SyntheticLabConfig(
        repository_root=repo,
        git_common_dir=git_common_dir(repo),
        private_input_dir_relative="does-not-matter",
        ledger_path=Path("/private/tmp/does-not-matter.sqlite3"),
        canonical_scope=f"project:{repo}",
    )
    expect_error(lambda: module.RetainedCustodySession(config), "E_DEFAULT_DISABLED")
    wrong_mode = copy.copy(config)
    object.__setattr__(wrong_mode, "enabled", True)
    object.__setattr__(wrong_mode, "mode", "PRODUCTION")
    expect_error(lambda: module.RetainedCustodySession(wrong_mode), "E_MODE")
    return 2


def assert_zero_authority(receipt: dict[str, Any]) -> None:
    require(receipt["production_admissible"] is False, "production flag widened")
    require(
        receipt["verdict"] == "SYNTHETIC_IMPLEMENTATION_GATE_EXERCISED_NO_AUTHORITY",
        "verdict drift",
    )
    for key, value in receipt.items():
        if key.startswith("real_") or key.endswith("_authority") or key == "g1_4_open":
            require(value is False, f"authority field widened: {key}")
    rendered = json.dumps(receipt, sort_keys=True)
    require(
        "manifest.json" not in rendered and "/Users/" not in rendered,
        "receipt leaked raw path/input",
    )


def test_happy_path_and_capability(repo: Path) -> int:
    with Harness(repo) as harness:
        receipt, capability = harness.claim()
        assert_zero_authority(receipt)
        require(receipt["signature_count"] == 5, "quorum count drift")
        require(
            receipt["retained_private_file_descriptor_count"] == 9,
            "custody fd count drift",
        )
        require(receipt["claim_state"] == "CLAIMED", "claim state drift")
        try:
            pickle.dumps(capability)
        except TypeError:
            pass
        else:
            raise CheckFailure("capability was serializable")
        wrong_seed = module.synthetic_seed("wrong-consumer")
        wrong_proof = module.ed25519_sign(capability.challenge_bytes, wrong_seed)
        expect_error(
            lambda: capability.exercise_only_permitted_successor(wrong_proof),
            "E_CAPABILITY_PROOF",
        )
        proof = module.ed25519_sign(capability.challenge_bytes, harness.consumer_seed)
        successor = capability.exercise_only_permitted_successor(proof)
        require(successor["g1_4_open"] is False, "successor opened G1.4")
        require(
            successor["verdict"]
            == "SYNTHETIC_SUCCESSOR_BINDING_EXERCISED_G1_4_REMAINS_CLOSED",
            "successor verdict drift",
        )
        expect_error(
            lambda: capability.exercise_only_permitted_successor(proof),
            "E_CAPABILITY_REPLAY",
        )
    return 11


def test_quorum_revocation_and_denial_replay(repo: Path) -> int:
    with Harness(repo) as harness:

        def tamper(bundle: dict[str, Any]) -> None:
            signature = bundle["signatures"][2]["signature_hex"]
            bundle["signatures"][2]["signature_hex"] = (
                "0" if signature[0] != "0" else "1"
            ) + signature[1:]

        harness.refresh_envelope(
            sequence=1, nonce_label="bad-signature", signature_mutator=tamper
        )
        expect_error(harness.claim, "E_SIGNATURE_VERIFY")
        require(harness.anchor.revision == 2, "denial did not advance ledger")
        expect_error(harness.claim, "E_REPLAY_ENVELOPE")

    with Harness(repo) as harness:

        def partial(bundle: dict[str, Any]) -> None:
            bundle["signatures"] = bundle["signatures"][:-1]

        harness.refresh_envelope(
            sequence=1, nonce_label="partial", signature_mutator=partial
        )
        expect_error(harness.claim, "E_QUORUM")

    with Harness(repo) as harness:

        def inject(bundle: dict[str, Any]) -> None:
            bundle["signatures"][0]["public_key_hex"] = "00" * 32

        harness.refresh_envelope(
            sequence=1, nonce_label="injection", signature_mutator=inject
        )
        expect_error(harness.claim, "E_SIGNATURE_BUNDLE")

    with Harness(repo) as harness:
        harness.ledger.revoke_key(
            harness.anchor,
            module.ROLES[0],
            harness.key_ids[module.ROLES[0]],
            1,
        )
        harness.refresh_envelope(sequence=1, nonce_label="revoked")
        expect_error(harness.claim, "E_TRUST_KEY_REVOKED")
        require(harness.anchor.revision == 3, "revoked-key denial was not recorded")
    return 9


def test_custody_fail_closed(repo: Path) -> int:
    with Harness(repo) as harness:
        alias = harness.private_dir / "manifest.alias"
        os.link(harness.private_dir / "manifest.json", alias)
        expect_error(
            lambda: module.RetainedCustodySession(harness.config), "E_PRIVATE_FILE"
        )

    with Harness(repo) as harness:
        target = harness.private_dir / "signatures.json"
        target.unlink()
        target.symlink_to("manifest.json")
        expect_error(
            lambda: module.RetainedCustodySession(harness.config), "E_PRIVATE_FILE"
        )

    with Harness(repo) as harness:
        os.chmod(harness.private_dir / "manifest.json", 0o640)
        expect_error(
            lambda: module.RetainedCustodySession(harness.config), "E_PRIVATE_FILE"
        )

    with Harness(repo) as harness:
        os.chmod(harness.private_dir, 0o750)
        expect_error(
            lambda: module.RetainedCustodySession(harness.config),
            "E_PRIVATE_DIRECTORY",
        )

    with Harness(repo) as harness:

        def swap(_custody: module.RetainedCustodySession) -> None:
            path = harness.private_dir / "envelope.json"
            path.rename(harness.private_dir / "envelope.opened")
            write_json(path, {"replacement": True})

        expect_error(lambda: harness.claim(hook=swap), "E_CUSTODY_DRIFT")
        (harness.private_dir / "envelope.json").unlink()
        (harness.private_dir / "envelope.opened").rename(
            harness.private_dir / "envelope.json"
        )
        expect_error(harness.claim, "E_REPLAY_ENVELOPE")

    with Harness(repo) as harness:

        def mutate(_custody: module.RetainedCustodySession) -> None:
            path = harness.private_dir / "manifest.json"
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            try:
                os.write(fd, b" ")
                os.fsync(fd)
            finally:
                os.close(fd)

        expect_error(lambda: harness.claim(hook=mutate), "E_CUSTODY_DRIFT")

    remote = module.MountIdentity(1, 1, 2, "nfs", "0" * 64, False)
    expect_error(
        lambda: module.validate_mount_identity(remote, remote), "E_MOUNT_REMOTE"
    )
    return 8


def test_binding_and_canonical_failures(repo: Path) -> int:
    mutations = [
        (
            "scope",
            lambda value: value.__setitem__("scope_identity_sha256", "0" * 64),
            "E_SCOPE_BINDING",
        ),
        (
            "repo",
            lambda value: value.__setitem__("repository_identity_sha256", "1" * 64),
            "E_REPOSITORY_BINDING",
        ),
        (
            "g13",
            lambda value: value["g1_3"].__setitem__("commit", "0" * 40),
            "E_G1_3_BINDING",
        ),
        (
            "successor",
            lambda value: value.__setitem__("only_permitted_successor", "runtime"),
            "E_SUCCESSOR",
        ),
    ]
    for label, mutation, code in mutations:
        with Harness(repo) as harness:
            harness.refresh_envelope(sequence=1, nonce_label=label, mutate=mutation)
            expect_error(harness.claim, code)

    with Harness(repo) as harness:
        manifest_path = harness.private_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["groups"][0] = "synthetic-group-drift"
        write_json(manifest_path, manifest)
        expect_error(harness.claim, "E_MANIFEST")

    with Harness(repo) as harness:
        envelope = (harness.private_dir / "envelope.json").read_bytes()
        write_private(harness.private_dir / "envelope.json", envelope + b"\n")
        expect_error(harness.claim, "E_JCS_BYTES")

    with Harness(repo) as harness:
        raw = (harness.private_dir / "envelope.json").read_text(encoding="utf-8")
        duplicate = raw[:-1] + ',"schema":"duplicate"}'
        write_private(harness.private_dir / "envelope.json", duplicate.encode("utf-8"))
        expect_error(harness.claim, "E_DUPLICATE_JSON_KEY")
    return 7


def test_time_sequence_and_rollback_anchor(repo: Path) -> int:
    with Harness(repo) as harness:
        snapshot = harness.database_bytes()
        receipt, _capability = harness.claim()
        assert_zero_authority(receipt)
        expect_error(harness.claim, "E_REPLAY_ENVELOPE")
        harness.restore_database_bytes(snapshot)
        expect_error(
            lambda: harness.ledger.inspect(harness.anchor), "E_LEDGER_ROLLBACK"
        )

    with Harness(repo) as harness:
        expired = module.TrustedTimeSample(
            boot_epoch_hex=harness.boot_epoch_hex,
            monotonic_ns=harness.checkpoint_monotonic_ns + 400_000_000_000,
        )
        expect_error(lambda: harness.claim(time_sample=expired), "E_TIME_WINDOW")
        expect_error(lambda: harness.claim(time_sample=expired), "E_REPLAY_ENVELOPE")
        require(
            harness.high_water() == (1, "", 0, 0, 0, 0),
            "unverified time denial poisoned durable high-water",
        )
        harness.refresh_envelope(
            sequence=2,
            nonce_label="claim-2-after-invalid-time-denial",
            trust_revision=harness.anchor.revision,
        )
        receipt, _capability = harness.claim()
        assert_zero_authority(receipt)
        require(
            harness.high_water()
            == (
                2,
                harness.boot_epoch_hex,
                harness.default_time_sample.monotonic_ns,
                harness.checkpoint_utc + 60,
                1,
                1,
            ),
            "first verified time did not establish the durable high-water",
        )

    with Harness(repo) as harness:
        harness.claim()
        harness.refresh_envelope(
            sequence=2,
            nonce_label="claim-2-regressed-time",
            trust_revision=harness.anchor.revision,
        )
        regressed = module.TrustedTimeSample(
            boot_epoch_hex=harness.boot_epoch_hex,
            monotonic_ns=harness.checkpoint_monotonic_ns + 30_000_000_000,
        )
        expect_error(lambda: harness.claim(time_sample=regressed), "E_TIME_HIGH_WATER")

    with Harness(repo) as harness:
        wrong_boot = module.TrustedTimeSample(
            boot_epoch_hex="f" * 64,
            monotonic_ns=harness.default_time_sample.monotonic_ns,
        )
        expect_error(lambda: harness.claim(time_sample=wrong_boot), "E_BOOT_EPOCH")

    with Harness(repo) as harness:
        harness.claim()
        old_monotonic_ns = harness.default_time_sample.monotonic_ns
        harness.boot_epoch_hex = hashlib.sha256(
            b"public-synthetic-fresh-boot-epoch"
        ).hexdigest()
        harness.checkpoint_utc += 120
        harness.checkpoint_monotonic_ns = 1_000_000_000
        harness._write_checkpoint(checkpoint_sequence=2)
        harness.refresh_envelope(
            sequence=2,
            nonce_label="claim-2-fresh-boot",
            trust_revision=harness.anchor.revision,
        )
        require(
            harness.default_time_sample.monotonic_ns < old_monotonic_ns,
            "fresh-boot fixture did not reset the monotonic domain",
        )
        receipt, _capability = harness.claim()
        assert_zero_authority(receipt)
        require(
            harness.high_water()
            == (
                2,
                harness.boot_epoch_hex,
                harness.default_time_sample.monotonic_ns,
                harness.checkpoint_utc + 60,
                2,
                1,
            ),
            "fresh boot did not replace the prior monotonic-domain high-water",
        )

    with Harness(repo) as harness:
        harness.claim()
        harness.boot_epoch_hex = hashlib.sha256(
            b"public-synthetic-stale-checkpoint-new-boot"
        ).hexdigest()
        harness.checkpoint_utc += 120
        harness.checkpoint_monotonic_ns = 1_000_000_000
        harness._write_checkpoint(checkpoint_sequence=1)
        harness.refresh_envelope(
            sequence=2,
            nonce_label="claim-2-new-boot-stale-checkpoint",
            trust_revision=harness.anchor.revision,
        )
        expect_error(harness.claim, "E_BOOT_EPOCH_FRESHNESS")

    with Harness(repo) as harness:
        harness._write_checkpoint(checkpoint_sequence=2)
        harness.refresh_envelope(sequence=1, nonce_label="checkpoint-2-first")
        harness.claim()
        harness._write_checkpoint(checkpoint_sequence=1)
        harness.refresh_envelope(
            sequence=2,
            nonce_label="claim-2-checkpoint-regression",
            trust_revision=harness.anchor.revision,
        )
        expect_error(harness.claim, "E_TIME_HIGH_WATER")

    with Harness(repo) as harness:
        harness.refresh_envelope(sequence=2, nonce_label="sequence-gap")
        expect_error(harness.claim, "E_SEQUENCE")
    return 18


def rewrite_behind_append_only_trigger(
    database: Path, trigger_name: str, update_sql: str
) -> None:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type='trigger' AND name=?",
            (trigger_name,),
        ).fetchone()
        require(
            row is not None and type(row[0]) is str, f"missing trigger {trigger_name}"
        )
        trigger_sql = row[0]
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.execute(update_sql)
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()


def test_ledger_tamper_audit(repo: Path) -> int:
    with Harness(repo) as harness:
        rewrite_behind_append_only_trigger(
            harness.ledger_path,
            "trust_keys_no_update_v0",
            "UPDATE trust_keys_v0 SET public_key_hex='" + ("ab" * 32) + "' "
            "WHERE role='application_owner'",
        )
        expect_error(lambda: harness.ledger.inspect(harness.anchor), "E_LEDGER_KEYS")

    with Harness(repo) as harness:
        harness.claim()
        connection = sqlite3.connect(harness.ledger_path)
        try:
            connection.execute("UPDATE scope_high_water_v0 SET last_monotonic_ns=0")
            connection.commit()
        finally:
            connection.close()
        expect_error(
            lambda: harness.ledger.inspect(harness.anchor), "E_TIME_HIGH_WATER"
        )

    with Harness(repo) as harness:
        harness.claim()
        rewrite_behind_append_only_trigger(
            harness.ledger_path,
            "claim_events_no_update_v0",
            "UPDATE claim_events_v0 SET reason_code='TAMPERED'",
        )
        expect_error(lambda: harness.ledger.inspect(harness.anchor), "E_LEDGER_EVENT")

    with Harness(repo) as harness:
        connection = sqlite3.connect(harness.ledger_path)
        try:
            connection.execute("DROP TRIGGER capability_events_no_delete_v0")
            connection.commit()
        finally:
            connection.close()
        expect_error(lambda: harness.ledger.inspect(harness.anchor), "E_LEDGER_SCHEMA")
    return 4


def test_fixture_constructor_failure_cleanup(repo: Path) -> int:
    before_private = set(repo.glob(".ab-g1-freeze-kat-*"))
    before_ledger = set(Path("/private/tmp").glob("ab-g1-ledger-kat-*"))
    original = Harness._write_initial_inputs

    def fail_before_enter(_self: Harness) -> None:
        raise CheckFailure("synthetic constructor failure")

    Harness._write_initial_inputs = fail_before_enter
    try:
        try:
            Harness(repo)
        except CheckFailure as exc:
            require(
                str(exc) == "synthetic constructor failure", "wrong injected failure"
            )
        else:
            raise CheckFailure("injected constructor failure did not fire")
    finally:
        Harness._write_initial_inputs = original
    require(
        set(repo.glob(".ab-g1-freeze-kat-*")) == before_private,
        "constructor failure left a private fixture directory",
    )
    require(
        set(Path("/private/tmp").glob("ab-g1-ledger-kat-*")) == before_ledger,
        "constructor failure left a ledger fixture directory",
    )
    return 2


def test_static_boundary(repo: Path) -> int:
    source_path = (
        repo
        / "scripts/eval/engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    forbidden = {"asyncio", "http", "requests", "socket", "subprocess", "urllib"}
    require(
        imports.isdisjoint(forbidden),
        f"forbidden implementation import: {imports & forbidden}",
    )
    for token in (
        "mcp_tools",
        "memory_search",
        "PRODUCTION_MODE",
        "os.system(",
        "os.popen(",
    ):
        require(
            token not in source,
            f"runtime/production surface leaked into implementation: {token}",
        )
    require(
        module.implementation_sha256() == EXPECTED_IMPLEMENTATION_SHA256,
        "implementation pin drift",
    )
    contract, _ = module.load_registered_contract()
    require(contract["scope"]["enabled_by_default"] is False, "default gate opened")
    require(
        contract["scope"]["production_mode_representable"] is False,
        "production mode represented",
    )
    require(
        contract["state_machine"]["production_authority_state_representable"] is False,
        "authority state represented",
    )
    require(
        contract["state_machine"]["g1_4_state_representable"] is False,
        "G1.4 state represented",
    )
    return 10


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "scripts/eval"))
    global module
    module = importlib.import_module(
        "engram_g1_authenticated_freeze_authority_adapter_isolated_lab"
    )
    total = 0
    total += test_contract_semantics_and_raw_pin()
    total += test_jcs_and_ed25519_known_answers()
    total += test_default_off(repo)
    total += test_happy_path_and_capability(repo)
    total += test_quorum_revocation_and_denial_replay(repo)
    total += test_custody_fail_closed(repo)
    total += test_binding_and_canonical_failures(repo)
    total += test_time_sequence_and_rollback_anchor(repo)
    total += test_ledger_tamper_audit(repo)
    total += test_fixture_constructor_failure_cleanup(repo)
    total += test_static_boundary(repo)
    print(
        json.dumps(
            {
                "schema": (
                    "agent_bridge.engram_g1_authenticated_freeze_authority_"
                    "adapter_isolated_lab_check_receipt.v0"
                ),
                "verdict": "PASS_SYNTHETIC_ISOLATED_LAB_NO_AUTHORITY",
                "checks": total,
                "contract_sha256": EXPECTED_CONTRACT_SHA256,
                "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
                "production_admissible": False,
                "g1_4_open": False,
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
