#!/usr/bin/env python3
"""Durable, single-use, non-actuating execution commit for ModelScope ABot."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any


PROVIDER_ID = "modelscope.studio.amap_cvlab.abot-world-0"
ATTEMPT_SCHEMA = "agent_bridge.modelscope_abot_execution_attempt.v0"
COMMIT_SCHEMA = "agent_bridge.modelscope_abot_execution_commit.v0"
_INIT_LOCK = threading.Lock()


class ExecutionCommitError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


class ExecutionCommitStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _INIT_LOCK, self._connect() as connection:
            connection.execute("pragma journal_mode = wal")
            connection.execute(
                "create table if not exists execution_commits ("
                "attempt_id text primary key, provider_id text not null, "
                "attempt_sha256 text not null unique, committed_at_unix_ms integer not null, "
                "expires_at_unix_ms integer not null)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("pragma busy_timeout = 5000")
        return connection

    def commit(
        self,
        *,
        attempt_receipt: dict[str, Any],
        now_unix_ms: int,
        fault_after_insert: bool = False,
    ) -> dict[str, Any]:
        if (
            not isinstance(attempt_receipt, dict)
            or attempt_receipt.get("schema") != ATTEMPT_SCHEMA
            or attempt_receipt.get("provider_id") != PROVIDER_ID
            or attempt_receipt.get("preflight_only") is not True
        ):
            raise ExecutionCommitError("attempt receipt invalid")
        attempt_id = attempt_receipt.get("attempt_id")
        if not isinstance(attempt_id, str) or re.fullmatch(
            r"[A-Za-z0-9._-]{16,128}", attempt_id
        ) is None:
            raise ExecutionCommitError("attempt id invalid")
        if any(
            attempt_receipt.get(field) is not False
            for field in (
                "network_request_sent",
                "subprocess_started",
                "studio_start_called",
                "execution_attempted",
                "runtime_admitted",
                "mcp_registered",
            )
        ):
            raise ExecutionCommitError("attempt boundary open")
        expires_at = attempt_receipt.get("expires_at_unix_ms")
        if (
            not isinstance(now_unix_ms, int)
            or isinstance(now_unix_ms, bool)
            or not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or now_unix_ms >= expires_at
        ):
            raise ExecutionCommitError("attempt expired")
        attempt_sha256 = _digest(attempt_receipt)
        try:
            with self._connect() as connection:
                connection.execute("begin immediate")
                connection.execute(
                    "insert into execution_commits "
                    "(attempt_id, provider_id, attempt_sha256, committed_at_unix_ms, expires_at_unix_ms) "
                    "values (?, ?, ?, ?, ?)",
                    (attempt_id, PROVIDER_ID, attempt_sha256, now_unix_ms, expires_at),
                )
                if fault_after_insert:
                    raise RuntimeError("synthetic commit interruption")
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise ExecutionCommitError("execution attempt already committed") from error
        except Exception as error:
            raise ExecutionCommitError("execution commit rejected") from error
        return {
            "schema": COMMIT_SCHEMA,
            "provider_id": PROVIDER_ID,
            "attempt_id": attempt_id,
            "attempt_sha256": attempt_sha256,
            "commit_recorded": True,
            "execution_attempted": False,
            "network_request_sent": False,
            "subprocess_started": False,
            "studio_start_called": False,
            "runtime_admitted": False,
            "mcp_registered": False,
            "next_gate": "gate7n_external_execution_dispatch",
        }

    def snapshot(self) -> dict[str, int | bool | str]:
        with self._connect() as connection:
            count = connection.execute(
                "select count(*) from execution_commits"
            ).fetchone()[0]
        return {
            "provider_id": PROVIDER_ID,
            "commit_count": count,
            "execution_attempted": False,
            "runtime_admitted": False,
        }
