#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'scripts/eval/fixtures/engram_g14_wasi_g2h_local_toolchain_integrity_v0.json'

def need(value, message):
    if not value:
        raise AssertionError(message)

def main():
    contract = json.loads(FIXTURE.read_text())
    observations = contract['observations']
    authority = contract['authority']
    recovery = contract['recovery']
    need(contract['gate'] == 'G2H_LOCAL_TOOLCHAIN_INTEGRITY_AND_RECOVERY_DECISION', 'gate')
    need(contract['predecessor'] == {'g2g_fail_closed_post': 4792, 'g2h_claim_post': 4793}, 'predecessor')
    need(contract['scope'] == 'public_static_local_metadata_only', 'scope')
    need(observations['repository_selector'] == 'stable', 'repository selector')
    need(observations['partial_directory'] == {'name': '1.96.0-aarch64-apple-darwin', 'cargo_present': True, 'rustc_present': False}, 'partial toolchain observation')
    need(observations['g2f_bound_toolchain'] == '1.94-aarch64-apple-darwin' and observations['g2f_bound_toolchain_present'] is False, 'G2F toolchain absence')
    need(contract['verdict'] == 'FAIL_CLOSED_LOCAL_TOOLCHAIN_NOT_PROVEN', 'verdict')
    need(all(value is False for value in authority.values()), 'authority widened')
    need(recovery['automatic'] is False and recovery['separate_authorization_required'] is True, 'automatic recovery')
    need(recovery['required_future_bindings'] == ['exact_preinstalled_toolchain', 'outside_repository_selector_effects', 'pre_post_binary_identities', 'independent_integrity_review'], 'recovery bindings')
    print('PASS G2H: local metadata is fail-closed; recovery remains separately authorized')

if __name__ == '__main__':
    try:
        main()
    except (AssertionError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f'FAIL G2H: {error}', file=sys.stderr)
        raise SystemExit(1)
