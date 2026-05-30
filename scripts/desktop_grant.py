#!/usr/bin/env python3
"""desktop_grant — human-minted capability grants for Linux Computer Use (thread 79).

Host-confirm path C. A grant pre-authorizes a *time-boxed, scope-limited* window in
which covered host desktop actions execute WITHOUT a per-action two-phase confirm
(path A). It trades per-action review for a bounded, revocable, audited window —
opt-in convenience for trusted repetition.

THIS CLI IS FOR THE HUMAN. It is deliberately NOT exposed via MCP: the MCP desktop_*
tools only *check* grants (use_grant:true), they never mint them. Honest threat model
(same as path A): on a box where the agent has a shell this is not agent-proof — its
job is to require a deliberate human pre-authorization and to bound blast radius
(ttl + max_uses + scope + revoke), not to sandbox an adversarial agent.

Usage:
  desktop_grant.py grant --kind invoke --app firefox --action click --ttl 300 [--max-uses 5] [--name Save] [--note "..."]
  desktop_grant.py grant --kind action --action click --ttl 120
  desktop_grant.py list [--all]
  desktop_grant.py revoke <grant_id> | desktop_grant.py revoke --all
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_confirm_store import (  # noqa: E402
    find_matching_grant,
    list_grants,
    mint_grant_id,
    revoke_all_grants,
    revoke_grant,
    write_grant,
)


def cmd_grant(args: argparse.Namespace) -> int:
    scope = {"app": args.app or "*", "name": args.name or "*", "action": args.action or "*"}
    expires_at = int(time.time()) + max(1, args.ttl)
    rec = write_grant(mint_grant_id(), args.kind, scope, expires_at, args.max_uses, args.note or "")
    print(json.dumps({"granted": True, **rec}, ensure_ascii=False))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    grants = list_grants(active_only=not args.all)
    print(json.dumps({"count": len(grants), "grants": grants}, ensure_ascii=False, indent=2))
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    if args.all:
        n = revoke_all_grants()
        print(json.dumps({"revoked_all": True, "count": n}, ensure_ascii=False))
        return 0
    if not args.grant_id:
        print(json.dumps({"error": "pass a grant_id or --all"}, ensure_ascii=False))
        return 2
    ok = revoke_grant(args.grant_id)
    print(json.dumps({"revoked": ok, "grant_id": args.grant_id}, ensure_ascii=False))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="human-minted desktop capability grants (path C)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grant", help="mint a time-boxed capability grant")
    g.add_argument("--kind", required=True, choices=["invoke", "action"],
                   help="which tool family this grant covers")
    g.add_argument("--app", default=None, help="invoke: app-name substring to cover (default any)")
    g.add_argument("--name", default=None, help="invoke: accessible-name substring to cover (default any)")
    g.add_argument("--action", default=None, help="action verb / AT-SPI action to cover (default any)")
    g.add_argument("--ttl", type=int, required=True, help="seconds the grant stays valid")
    g.add_argument("--max-uses", dest="max_uses", type=int, default=None,
                   help="cap the number of actions (default: unlimited within ttl)")
    g.add_argument("--note", default=None, help="free-text note (why this was granted)")
    g.set_defaults(func=cmd_grant)

    li = sub.add_parser("list", help="list grants")
    li.add_argument("--all", action="store_true", help="include expired/revoked/exhausted")
    li.set_defaults(func=cmd_list)

    rv = sub.add_parser("revoke", help="revoke a grant by id, or --all")
    rv.add_argument("grant_id", nargs="?", default=None)
    rv.add_argument("--all", action="store_true", help="revoke every active grant")
    rv.set_defaults(func=cmd_revoke)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
