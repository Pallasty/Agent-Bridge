import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_packed_q3_checkpoint_d11_checker.py"
RUNNER = HERE / "fh_l8_packed_q3_checkpoint_d11_runner.py"
CONTRACT = HERE / "fh_l8_packed_q3_checkpoint_d11_contract.json"
BUNDLE = HERE / "fh_l8_packed_q3_checkpoint_d11_bundle"
CHECKPOINT = BUNDLE / "checkpoint.bin"
RESULT = BUNDLE / "result.json"
TERMINAL_RECEIPT = HERE / "fh_l8_packed_q3_checkpoint_d11_terminal_receipt.json"
BASE_SOURCE_RECEIPT = HERE / "fh_l8_checkpointed_quotient_h_d11_receipt.json"

BASE_COMMIT = "b620f02ff53ed84472d0f38c775bdeb584fdf736"
SOURCE_FREEZE_COMMIT = "49ac8a25faf80c85fab9acaa7390fda7b4c0d7f2"
SOURCE_FREEZE_TREE = "75f8034aec9c95d02b4647c5908aea17c1835115"
CONTRACT_FREEZE_COMMIT = "429f31d0b82284f07860b3eb460102816fae1e17"
CONTRACT_FREEZE_TREE = "3d0ce731c6ae6c3697eb691823e95e527ae4918f"
OUTCOME_COMMIT = "784f01b8e3c589b7c6ab25773f93937d5a1344f8"
OUTCOME_TREE = "801d335d7edf39de22a24f969c1a81396c065095"

FROZEN_FILES = {
    CHECKER: (
        109796,
        "d7b4f1853f99f80f1a1241d078049d254d414ec0a3f99906d7b0801fe764a74e",
    ),
    RUNNER: (
        97061,
        "4a6a138ae56b9e308ef22ebad667982e5cbf488dfed76a7914f5ab4d03bef0ba",
    ),
    CONTRACT: (
        21439,
        "a9171c10c3fb66408b97c45fd8f2b81d2b4a8f64855e197f0e178cccedd18b41",
    ),
    CHECKPOINT: (
        6819168,
        "db2ce0a338a378aef6e4a043e02388c4268addc951d0ae590c2ae1d65f840231",
    ),
    RESULT: (
        8608,
        "f372a2eedabfc57d049d6a8c6d0609c1b7bcf25aae760353699916a6f1bc4bf5",
    ),
    TERMINAL_RECEIPT: (
        2470,
        "deafacbcbb77885353254306200137c7248321641b0eb197494d5cbd0d3a9ab2",
    ),
}

SPEC = importlib.util.spec_from_file_location("fh_l8_d11_test_subject", CHECKER)
D11 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D11)


def _canonical_receipt(receipt):
    return D11._canonical_json(receipt) + b"\n"


def _rebind_terminal_stdout(receipt):
    terminal_stdout = (
        json.dumps(
            receipt["runner_terminal_evidence"],
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    receipt["runner_stdout_bytes"] = len(terminal_stdout)
    receipt["runner_stdout_sha256"] = hashlib.sha256(terminal_stdout).hexdigest()


class PackedQ3CheckpointD11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_contract = CONTRACT.read_bytes()
        cls.contract = D11._load_json_bytes(cls.raw_contract)
        cls.raw_checkpoint = CHECKPOINT.read_bytes()
        cls.raw_result = RESULT.read_bytes()
        cls.result = D11._load_json_bytes(cls.raw_result)
        cls.raw_receipt = TERMINAL_RECEIPT.read_bytes()
        cls.receipt = D11._load_json_bytes(cls.raw_receipt)

        # These checks are Git/JSON/receipt-only.  The default unit suite must
        # not perform the 213,099-record audit or any scientific replay.
        cls.protocol = D11.verify_protocol(cls.contract, CONTRACT_FREEZE_COMMIT)
        cls.terminal_summary = D11._validate_execution_receipt(
            cls.raw_receipt,
            cls.contract,
            CONTRACT_FREEZE_COMMIT,
            cls.protocol,
            cls.result,
            cls.result["checkpoint"],
            cls.raw_result,
        )

    def test_frozen_identities_chronology_and_exact_outcome_diff(self):
        self.assertEqual(
            D11._commit_record(SOURCE_FREEZE_COMMIT),
            {
                "commit": SOURCE_FREEZE_COMMIT,
                "tree": SOURCE_FREEZE_TREE,
                "parents": [BASE_COMMIT],
            },
        )
        self.assertEqual(
            D11._commit_record(CONTRACT_FREEZE_COMMIT),
            {
                "commit": CONTRACT_FREEZE_COMMIT,
                "tree": CONTRACT_FREEZE_TREE,
                "parents": [SOURCE_FREEZE_COMMIT],
            },
        )
        self.assertEqual(
            D11._commit_record(OUTCOME_COMMIT),
            {
                "commit": OUTCOME_COMMIT,
                "tree": OUTCOME_TREE,
                "parents": [CONTRACT_FREEZE_COMMIT],
            },
        )
        self.assertEqual(
            D11._diff_entries(OUTCOME_COMMIT),
            {
                ("A", D11.CHECKPOINT_PATH),
                ("A", D11.RESULT_PATH),
                ("A", D11.TERMINAL_RECEIPT_PATH),
            },
        )
        for path in (
            D11.CHECKPOINT_PATH,
            D11.RESULT_PATH,
            D11.TERMINAL_RECEIPT_PATH,
        ):
            D11._require_mode(OUTCOME_COMMIT, path)
        self.assertEqual(
            self.protocol,
            {
                "protocol_source_freeze_commit": SOURCE_FREEZE_COMMIT,
                "protocol_source_freeze_tree": SOURCE_FREEZE_TREE,
                "contract_freeze_commit": CONTRACT_FREEZE_COMMIT,
                "contract_freeze_tree": CONTRACT_FREEZE_TREE,
                "outputs_absent_before_official_replay": True,
                "terminal_receipt_path": D11.TERMINAL_RECEIPT_PATH,
                "terminal_receipt_required_for_outcome": True,
            },
        )

    def test_frozen_file_hashes_and_scientific_boundary(self):
        for path, (expected_bytes, expected_sha256) in FROZEN_FILES.items():
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                self.assertEqual(len(raw), expected_bytes)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha256)

        checkpoint = self.result["checkpoint"]
        self.assertEqual(checkpoint["record_bytes"], 32)
        self.assertEqual(checkpoint["record_count"], 213099)
        self.assertEqual(checkpoint["file_bytes"], 6819168)
        self.assertEqual(
            checkpoint["legacy_d5b_insertion_json_sha256"],
            "7230d8bd0e726535cb5da01bc191313b25e38b83a6b809a7e6e39823a418757e",
        )
        self.assertEqual(
            checkpoint["d6_sorted_support_orbit_sha256"],
            "7e4f0d2526b49c786b124a8b45dc82cc8892a7798e7c4c362cd4aa15db74ca26",
        )
        depth = self.result["depth_replay"]
        self.assertEqual(depth["acted_source_depths"], [0, 1, 2])
        self.assertEqual(depth["hamiltonian_actions_executed"], 3)
        self.assertTrue(depth["fourth_call_rejected_before_backend"])
        self.assertEqual(depth["depth3_source_rows_visited"], 0)
        self.assertEqual(depth["q4_records_emitted"], 0)
        authority = self.result["authority"]
        self.assertTrue(authority["packed_q3_checkpoint_materialized"])
        self.assertTrue(authority["packed_q3_checkpoint_certified"])
        self.assertFalse(authority["depth3_to_depth4_execution_authorized"])
        self.assertFalse(authority["depth3_to_depth4_quotient_hamiltonian_action_executed"])
        self.assertEqual(
            self.result["next_gate"],
            "CHECKPOINTED_FULL_QUOTIENT_H_RUNNER_IMPLEMENTATION_AND_AUTHORIZATION",
        )
        self.assertEqual(
            self.terminal_summary["checkpoint_sha256"],
            FROZEN_FILES[CHECKPOINT][1],
        )
        self.assertEqual(
            self.terminal_summary["result_sha256"], FROZEN_FILES[RESULT][1]
        )

    def test_rank_extension_projects_to_independent_base_checkpoint_identity(self):
        base_receipt = json.loads(BASE_SOURCE_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(base_receipt["payload_bytes"], len(self.raw_checkpoint))
        self.assertFalse(base_receipt["fourth_action_executed"])

        projected = hashlib.sha256()
        nonzero_ranks = 0
        for offset in range(0, len(self.raw_checkpoint), 32):
            record = self.raw_checkpoint[offset : offset + 32]
            projected.update(record[:25])
            projected.update(b"\x00" * 7)
            nonzero_ranks += int.from_bytes(record[28:32], "big") != 0

        self.assertEqual(nonzero_ranks, 213098)
        self.assertEqual(
            projected.hexdigest(),
            "09758478e63d21014bdd704e157b1969498fdd4068b6ab4f78c2720324477017",
        )
        self.assertEqual(projected.hexdigest(), base_receipt["payload_sha256"])

    def test_terminal_receipt_exit_schema_and_hash_mutations_fail_closed(self):
        mutations = []

        nonzero_exit = copy.deepcopy(self.receipt)
        nonzero_exit["runner_exit_code"] = 1
        mutations.append(nonzero_exit)

        extra_key = copy.deepcopy(self.receipt)
        extra_key["unexpected"] = True
        mutations.append(extra_key)

        bad_stdout_hash = copy.deepcopy(self.receipt)
        bad_stdout_hash["runner_stdout_sha256"] = "0" * 64
        mutations.append(bad_stdout_hash)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(D11.VerificationError):
                    D11._validate_execution_receipt(
                        _canonical_receipt(mutation),
                        self.contract,
                        CONTRACT_FREEZE_COMMIT,
                        self.protocol,
                        self.result,
                        self.result["checkpoint"],
                        self.raw_result,
                    )

    def test_terminal_resource_cap_mutation_is_indeterminate(self):
        mutation = copy.deepcopy(self.receipt)
        terminal_resource = mutation["runner_terminal_evidence"][
            "terminal_resource_receipt"
        ]
        terminal_resource["memory_peak_bytes"] = (
            self.contract["resource_limits"]["max_cgroup_peak_bytes"] + 1
        )
        _rebind_terminal_stdout(mutation)
        with self.assertRaises(D11.ResourceIndeterminate):
            D11._validate_execution_receipt(
                _canonical_receipt(mutation),
                self.contract,
                CONTRACT_FREEZE_COMMIT,
                self.protocol,
                self.result,
                self.result["checkpoint"],
                self.raw_result,
            )

    def test_checkpoint_flag_mutation_rejected_before_full_record_audit(self):
        mutation = bytearray(self.raw_checkpoint)
        mutation[25] = 1
        dummy_science_cache = {
            "d5b_module": None,
            "symmetries": None,
            "d6_module": None,
            "d6_tables": None,
        }
        with mock.patch.object(D11, "verify_sources", return_value={}):
            with mock.patch.object(D11, "_SCIENCE_CACHE", dummy_science_cache):
                with self.assertRaisesRegex(
                    D11.VerificationError, "flags/reserved bytes"
                ):
                    D11.parse_checkpoint(bytes(mutation), self.contract)

    def test_result_authority_uplift_mutation_fails_closed_without_replay(self):
        mutation = copy.deepcopy(self.result)
        mutation["authority"]["depth3_to_depth4_execution_authorized"] = True
        with mock.patch.object(
            D11, "verify_sources", return_value=mutation["source_evidence"]
        ):
            with mock.patch.object(
                D11,
                "verify_byte_tables",
                return_value=mutation["byte_table_full_domain_validation"],
            ):
                with self.assertRaisesRegex(D11.VerificationError, "authority uplift"):
                    D11._validate_result(
                        self.contract,
                        mutation,
                        mutation["checkpoint"],
                        mutation["protocol"],
                        len(self.raw_result),
                    )

    def test_missing_receipt_and_extra_outcome_path_have_distinct_classification(self):
        missing_receipt_diff = {
            ("A", D11.CHECKPOINT_PATH),
            ("A", D11.RESULT_PATH),
        }
        extra_path_diff = {
            ("A", D11.CHECKPOINT_PATH),
            ("A", D11.RESULT_PATH),
            ("A", D11.TERMINAL_RECEIPT_PATH),
            ("A", f"{D11.PREFIX}/unexpected.txt"),
        }

        def assert_classification(diff, exception):
            with mock.patch.object(D11, "verify_protocol", return_value=self.protocol):
                with mock.patch.object(D11, "verify_sources", return_value={}):
                    with mock.patch.object(
                        D11,
                        "_commit_record",
                        return_value={"parents": [CONTRACT_FREEZE_COMMIT]},
                    ):
                        with mock.patch.object(D11, "_diff_entries", return_value=diff):
                            with self.assertRaises(exception):
                                D11.verify_outcome(
                                    self.contract,
                                    CONTRACT_FREEZE_COMMIT,
                                    OUTCOME_COMMIT,
                                )

        assert_classification(missing_receipt_diff, D11.ResourceIndeterminate)
        assert_classification(extra_path_diff, D11.VerificationError)


if __name__ == "__main__":
    unittest.main()
