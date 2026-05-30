"""Shared two-phase host-confirm store for the Linux Computer Use lane (thread 79).

Both desktop_invoke.py (semantic AT-SPI) and desktop_action.py (coordinate input)
stage a host-targeted action here in phase 1 (--request-host-confirm) and execute it
in phase 2 (--confirm-token) only after a human approved. The record carries a `kind`
("invoke" | "action") so a single desktop_confirm MCP tool can dispatch to the right
backend, and an opaque per-kind `payload` (the selector or the action spec).

Tokens are single-use and TTL-bounded; a token is marked consumed BEFORE execution so
it can never be replayed. See docs/design/HOST_CONFIRM_PATH.md.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "desktop_confirm/v0"
_CACHE_ROOT = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "agent-bridge"
PENDING_DIR = _CACHE_ROOT / "desktop_pending"
DEFAULT_CONFIRM_TTL = 120  # seconds a pending host-action token stays valid


def mint_token() -> str:
    return secrets.token_hex(16)


def _pending_path(token: str) -> Path:
    # token is hex (validated by mint); strip anything else so the path can't escape.
    safe = "".join(c for c in (token or "") if c in "0123456789abcdef")
    return PENDING_DIR / f"{safe}.json"


def write_pending(token: str, kind: str, payload: dict[str, Any],
                  summary: str, expires_at: int) -> None:
    """Persist a pending host action. `payload` is kind-specific and re-resolved fresh
    at confirm time (a selector for invoke, an action spec for action)."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "schema": SCHEMA_VERSION, "kind": kind, "ts": int(time.time()),
        "token": token, "payload": payload, "summary": summary,
        "expires_at": expires_at, "status": "pending",
    }
    _pending_path(token).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def load_and_consume_pending(token: str, expect_kind: str | None = None
                             ) -> tuple[dict[str, Any] | None, str]:
    """Load + validate (exists, unconsumed, unexpired, right kind) + mark consumed
    (single-use). Returns (record, reason); record is None on any failure. Consumption
    happens BEFORE the caller executes, so a token can never be replayed."""
    path = _pending_path(token)
    if not token or not path.exists():
        return None, "no such pending token (expired, already used, or never issued)"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"unreadable pending record: {exc}"
    if rec.get("status") != "pending":
        return None, f"token already {rec.get('status', 'consumed')} (single-use)"
    if int(time.time()) > int(rec.get("expires_at", 0)):
        return None, "token expired"
    if expect_kind and rec.get("kind") != expect_kind:
        return None, f"token is for {rec.get('kind')!r}, not {expect_kind!r}"
    rec["status"] = "consumed"
    rec["consumed_at"] = int(time.time())
    try:  # mark consumed BEFORE the caller executes
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        return None, f"could not mark token consumed: {exc}"
    return rec, "ok"


def peek_kind(token: str) -> str | None:
    """Read a pending record's kind WITHOUT consuming it (for the confirm dispatcher)."""
    try:
        return json.loads(_pending_path(token).read_text(encoding="utf-8")).get("kind")
    except (OSError, ValueError):
        return None


def notify_pending(summary: str, token: str) -> None:
    """Best-effort: mirror a pending host action onto the human's screen. Non-critical —
    the primary approval channel is the agent surfacing the summary to the user."""
    try:
        subprocess.run(
            ["notify-send", "-u", "critical",
             "Agent-Bridge: host desktop action pending approval",
             f"{summary}\nconfirm token: {token}"],
            timeout=3, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


# ===========================================================================
# Pre-authorized capability grants (host-confirm path C). A human mints a
# time-boxed, scope-limited grant via scripts/desktop_grant.py; within the
# window a COVERED host action executes without a per-action pending token.
# Grants are minted ONLY by the human CLI (never exposed via MCP) — the MCP
# tools only CHECK them. Honest threat model (same as path A): on a shell-
# accessible box this is not agent-proof; it prevents silent/accidental
# escalation and bounds blast radius (ttl + max_uses + scope + revocable +
# audited), requiring a deliberate human pre-authorization step.
# ===========================================================================
GRANTS_DIR = _CACHE_ROOT / "desktop_grants"


def mint_grant_id() -> str:
    return secrets.token_hex(8)


def _grant_path(grant_id: str) -> Path:
    safe = "".join(c for c in (grant_id or "") if c in "0123456789abcdef")
    return GRANTS_DIR / f"{safe}.json"


def write_grant(grant_id: str, kind: str, scope: dict[str, Any],
                expires_at: int, max_uses: int | None, note: str = "") -> dict[str, Any]:
    """Persist a human-minted capability grant. `scope` is {app?, name?, action?} where
    a missing/'*' field matches anything. max_uses None = unlimited within the ttl."""
    GRANTS_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "schema": SCHEMA_VERSION, "grant_id": grant_id, "kind": kind, "scope": scope,
        "created_at": int(time.time()), "expires_at": expires_at,
        "max_uses": max_uses, "uses": 0, "status": "active", "note": note,
    }
    _grant_path(grant_id).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def _iter_grants():
    if not GRANTS_DIR.exists():
        return
    for p in sorted(GRANTS_DIR.glob("*.json")):
        try:
            yield json.loads(p.read_text(encoding="utf-8")), p
        except (OSError, ValueError):
            continue


def _grant_live(rec: dict[str, Any], now: int) -> bool:
    if rec.get("status") != "active" or now > int(rec.get("expires_at", 0)):
        return False
    mu = rec.get("max_uses")
    return not (mu is not None and int(rec.get("uses", 0)) >= int(mu))


def list_grants(active_only: bool = True) -> list[dict[str, Any]]:
    now = int(time.time())
    return [rec for rec, _ in _iter_grants() if (not active_only) or _grant_live(rec, now)]


def revoke_grant(grant_id: str) -> bool:
    path = _grant_path(grant_id)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    rec["status"] = "revoked"
    rec["revoked_at"] = int(time.time())
    try:
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False


def revoke_all_grants() -> int:
    n = 0
    for rec, _ in list((r, p) for r, p in _iter_grants()):
        if rec.get("status") == "active" and revoke_grant(rec.get("grant_id", "")):
            n += 1
    return n


def _scope_covers(scope_val, req_val, exact: bool = False) -> bool:
    if scope_val in (None, "*", ""):
        return True
    if req_val is None:
        return False
    if exact:
        return str(scope_val).lower() == str(req_val).lower()
    return str(scope_val).lower() in str(req_val).lower()


def find_matching_grant(kind: str, app=None, name=None, action=None) -> dict[str, Any] | None:
    """First live grant of `kind` whose scope covers the request. app/name match by
    substring, action matches exactly. Returns None if nothing covers it."""
    now = int(time.time())
    for rec, _ in _iter_grants():
        if rec.get("kind") != kind or not _grant_live(rec, now):
            continue
        scope = rec.get("scope", {}) or {}
        if (_scope_covers(scope.get("app", "*"), app)
                and _scope_covers(scope.get("name", "*"), name)
                and _scope_covers(scope.get("action", "*"), action, exact=True)):
            return rec
    return None


def record_grant_use(grant_id: str) -> None:
    path = _grant_path(grant_id)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    rec["uses"] = int(rec.get("uses", 0)) + 1
    rec["last_used_at"] = int(time.time())
    try:
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
