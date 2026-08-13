#!/usr/bin/env python3
"""Non-actuating single-use authority store for ModelScope ABot-World."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
CANDIDATE_SCHEMA = "agent_bridge.modelscope_abot_preflight_candidate.v0"
AUTHORITY_SCHEMA = "agent_bridge.authority_decision.v0"
AUTHENTICITY_SCHEMA = "agent_bridge.modelscope_abot_authority_hmac.v0"
CLAIM_SCHEMA = "agent_bridge.modelscope_abot_single_use_claim.v0"


class AuthorityStoreError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: candidate.get(key)
        for key in (
            "schema",
            "provider_id",
            "authority",
            "nonce",
            "synthetic_fixture",
            "execution_authorized",
        )
    }


def candidate_digest(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(_candidate_payload(candidate))).hexdigest()


def candidate_mac(candidate: dict[str, Any], key: bytes, key_id: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise AuthorityStoreError("authority key missing")
    if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", key_id):
        raise AuthorityStoreError("authority key id invalid")
    signed = {
        "candidate": _candidate_payload(candidate),
        "authenticity": {
            "schema": AUTHENTICITY_SCHEMA,
            "algorithm": "hmac-sha256",
            "key_id": key_id,
        },
    }
    return hmac.new(key, _canonical_json(signed), hashlib.sha256).hexdigest()


def verify_candidate(candidate: Any, *, key: bytes, key_id: str, now_unix_ms: int) -> None:
    if not isinstance(now_unix_ms, int) or isinstance(now_unix_ms, bool) or now_unix_ms < 0:
        raise AuthorityStoreError("current time invalid")
    if not isinstance(candidate, dict):
        raise AuthorityStoreError("candidate not object")
    if set(candidate) != {
        "schema",
        "provider_id",
        "authority",
        "nonce",
        "synthetic_fixture",
        "execution_authorized",
        "authenticity",
    }:
        raise AuthorityStoreError("candidate fields invalid")
    if candidate.get("schema") != CANDIDATE_SCHEMA or candidate.get("provider_id") != PROVIDER_ID:
        raise AuthorityStoreError("candidate identity mismatch")
    if candidate.get("synthetic_fixture") is not False:
        raise AuthorityStoreError("synthetic candidate is not executable")
    if candidate.get("execution_authorized") is not False:
        raise AuthorityStoreError("candidate must not claim execution authority")

    authority = candidate.get("authority")
    if not isinstance(authority, dict):
        raise AuthorityStoreError("authority not object")
    if set(authority) != {
        "schema",
        "decision_id",
        "cognitive_decision_id",
        "body_id",
        "status",
        "boundary",
        "owner_confirmation",
        "lease_id",
    }:
        raise AuthorityStoreError("authority fields invalid")
    expected = {
        "schema": AUTHORITY_SCHEMA,
        "status": "approved",
        "boundary": "external_write",
        "owner_confirmation": True,
    }
    if any(authority.get(field) != value for field, value in expected.items()):
        raise AuthorityStoreError("authority boundary mismatch")
    for field in ("decision_id", "cognitive_decision_id", "body_id"):
        if not isinstance(authority.get(field), str) or not authority[field].strip():
            raise AuthorityStoreError(f"authority {field} missing")

    nonce = candidate.get("nonce")
    if not isinstance(nonce, dict):
        raise AuthorityStoreError("nonce not object")
    if set(nonce) != {"sha256", "scope", "consumed", "expires_at_unix_ms"}:
        raise AuthorityStoreError("nonce fields invalid")
    if not isinstance(nonce.get("sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", nonce["sha256"]
    ):
        raise AuthorityStoreError("nonce digest invalid")
    if nonce.get("scope") != PROVIDER_ID or nonce.get("consumed") is not False:
        raise AuthorityStoreError("nonce boundary mismatch")
    expiry = nonce.get("expires_at_unix_ms")
    if not isinstance(expiry, int) or isinstance(expiry, bool) or expiry <= now_unix_ms:
        raise AuthorityStoreError("nonce expired")

    authenticity = candidate.get("authenticity")
    if not isinstance(authenticity, dict):
        raise AuthorityStoreError("authenticity not object")
    if set(authenticity) != {"schema", "algorithm", "key_id", "mac_sha256"}:
        raise AuthorityStoreError("authenticity fields invalid")
    if (
        authenticity.get("schema") != AUTHENTICITY_SCHEMA
        or authenticity.get("algorithm") != "hmac-sha256"
        or authenticity.get("key_id") != key_id
    ):
        raise AuthorityStoreError("authenticity metadata mismatch")
    supplied = authenticity.get("mac_sha256")
    if not isinstance(supplied, str) or not hmac.compare_digest(
        supplied, candidate_mac(candidate, key, key_id)
    ):
        raise AuthorityStoreError("authority authenticity rejected")


class SingleUseAuthorityStore:
    def __init__(self, path: Path):
        self.path = path.resolve()
        if not self.path.parent.is_dir():
            raise AuthorityStoreError("authority store parent missing")

    def _connect(self) -> sqlite3.Connection:
        created = not self.path.exists()
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.execute("pragma journal_mode=WAL")
        connection.execute("pragma synchronous=FULL")
        connection.execute("pragma foreign_keys=ON")
        connection.execute(
            "create table if not exists consumed_authorities ("
            "nonce_sha256 text primary key, provider_id text not null, "
            "decision_id text not null, candidate_sha256 text not null, "
            "consumed_at_unix_ms integer not null)"
        )
        connection.execute(
            "create table if not exists provider_session_leases ("
            "provider_id text primary key, lease_id text not null unique, "
            "nonce_sha256 text not null, candidate_sha256 text not null, "
            "reserved_at_unix_ms integer not null, expires_at_unix_ms integer not null, "
            "foreign key(nonce_sha256) references consumed_authorities(nonce_sha256))"
        )
        if created:
            os.chmod(self.path, 0o600)
        return connection

    def claim(
        self,
        candidate: dict[str, Any],
        *,
        key: bytes,
        key_id: str,
        lease_id: str,
        now_unix_ms: int,
        lease_ttl_ms: int,
        fault_after_nonce_insert: bool = False,
    ) -> dict[str, Any]:
        verify_candidate(candidate, key=key, key_id=key_id, now_unix_ms=now_unix_ms)
        if not isinstance(lease_id, str) or not re.fullmatch(
            r"[A-Za-z0-9._-]{16,128}", lease_id
        ):
            raise AuthorityStoreError("lease id invalid")
        if (
            not isinstance(lease_ttl_ms, int)
            or isinstance(lease_ttl_ms, bool)
            or not 1 <= lease_ttl_ms <= 180_000
        ):
            raise AuthorityStoreError("lease ttl invalid")

        authority = candidate["authority"]
        nonce_sha256 = candidate["nonce"]["sha256"]
        digest = candidate_digest(candidate)
        expires_at = now_unix_ms + lease_ttl_ms
        with self._connect() as connection:
            try:
                connection.execute("begin immediate")
                connection.execute(
                    "delete from provider_session_leases where provider_id = ? "
                    "and expires_at_unix_ms <= ?",
                    (PROVIDER_ID, now_unix_ms),
                )
                if connection.execute(
                    "select 1 from consumed_authorities where nonce_sha256 = ?",
                    (nonce_sha256,),
                ).fetchone():
                    raise AuthorityStoreError("authority or nonce already consumed")
                if connection.execute(
                    "select 1 from provider_session_leases where provider_id = ?",
                    (PROVIDER_ID,),
                ).fetchone():
                    raise AuthorityStoreError("provider session already reserved")
                connection.execute(
                    "insert into consumed_authorities "
                    "(nonce_sha256, provider_id, decision_id, candidate_sha256, "
                    "consumed_at_unix_ms) "
                    "values (?, ?, ?, ?, ?)",
                    (nonce_sha256, PROVIDER_ID, authority["decision_id"], digest, now_unix_ms),
                )
                if fault_after_nonce_insert:
                    raise RuntimeError("synthetic transaction interruption")
                connection.execute(
                    "insert into provider_session_leases "
                    "(provider_id, lease_id, nonce_sha256, candidate_sha256, "
                    "reserved_at_unix_ms, expires_at_unix_ms) values (?, ?, ?, ?, ?, ?)",
                    (PROVIDER_ID, lease_id, nonce_sha256, digest, now_unix_ms, expires_at),
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise AuthorityStoreError("authority or nonce already consumed") from error
            except Exception:
                connection.rollback()
                raise

        return {
            "schema": CLAIM_SCHEMA,
            "provider_id": PROVIDER_ID,
            "lease_id": lease_id,
            "candidate_sha256": digest,
            "authority_consumed": True,
            "nonce_consumed": True,
            "session_reserved": True,
            "lease_expires_at_unix_ms": expires_at,
            "execution_capability_issued": False,
            "studio_start_called": False,
            "execution_authorized": False,
            "runtime_admitted": False,
            "mcp_registered": False,
            "next_gate": "gate7g_bounded_execution_capability_contract",
        }

    def release_session(self, *, lease_id: str) -> bool:
        with self._connect() as connection:
            connection.execute("begin immediate")
            cursor = connection.execute(
                "delete from provider_session_leases where provider_id = ? and lease_id = ?",
                (PROVIDER_ID, lease_id),
            )
            connection.commit()
            return cursor.rowcount == 1

    def recover_expired_sessions(self, *, now_unix_ms: int) -> int:
        with self._connect() as connection:
            connection.execute("begin immediate")
            cursor = connection.execute(
                "delete from provider_session_leases where expires_at_unix_ms <= ?",
                (now_unix_ms,),
            )
            connection.commit()
            return cursor.rowcount

    def snapshot(self) -> dict[str, Any]:
        with self._connect() as connection:
            consumed = connection.execute("select count(*) from consumed_authorities").fetchone()[0]
            leases = connection.execute(
                "select count(*) from provider_session_leases"
            ).fetchone()[0]
        return {
            "provider_id": PROVIDER_ID,
            "consumed_authority_count": consumed,
            "active_session_count": leases,
            "session_state_authoritative": True,
            "execution_capability_issued": False,
            "runtime_admitted": False,
        }
