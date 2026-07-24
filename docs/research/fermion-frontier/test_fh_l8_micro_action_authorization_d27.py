#!/usr/bin/env python3
import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fh_l8_micro_action_authorization_d27 as d27


def approval():
    req = d27.request()
    return {"schema_version": 1, "request_id": req["request_id"], "approving_authority": "independent-reviewer", "approval_certificate_sha256": "b" * 64, "approved_kernel_sha256": req["kernel"]["sha256"], "approved_action_limit": req["action_limit"], "approved_resource_ceiling": req["resource_ceiling"]}


class D27Tests(unittest.TestCase):
    def test_absence_is_no_go_without_action(self):
        result = d27.absent_approval_decision()
        self.assertFalse(result["independent_approval_present"])
        self.assertEqual(result["scientific_action_calls"], 0)

    def test_independent_exact_scope_is_only_admissible(self):
        result = d27.validate_approval(d27.request(), approval())
        self.assertTrue(result["approval_admissible"])
        self.assertFalse(result["full_53_scientific_execution_authorized"])

    def test_self_approval_rejected(self):
        value = approval(); value["approving_authority"] = d27.request()["requesting_authority"]
        with self.assertRaisesRegex(d27.AuthorizationError, "independent"):
            d27.validate_approval(d27.request(), value)

    def test_scope_escalation_rejected(self):
        value = approval(); value["approved_action_limit"] = copy.deepcopy(value["approved_action_limit"]); value["approved_action_limit"]["kernel_calls"] = 2
        with self.assertRaisesRegex(d27.AuthorizationError, "scope"):
            d27.validate_approval(d27.request(), value)


if __name__ == "__main__": unittest.main()
