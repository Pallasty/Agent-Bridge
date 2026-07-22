import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "fh_l8_packed_consumer_forensic_d16_checker.py"
CONTRACT = HERE / "fh_l8_packed_consumer_forensic_d16_contract.json"
RESULT = HERE / "fh_l8_packed_consumer_forensic_d16_result.json"

BASE_COMMIT = "e6cc31c6987cc33d7fbb8890cc172a7ba817cf56"
CHECKER_FREEZE_COMMIT = "ad20d45f14016bbc34bd61a3685c581c9727ef20"
CHECKER_FREEZE_TREE = "5b0d550d937c9df30a00cacb4dfa956917e4f8f6"
CONTRACT_FREEZE_COMMIT = "f7d9fdf2d24e22973d0409737c2182fc9266e6e9"
CONTRACT_FREEZE_TREE = "c42aff2c32e8241f94a52281f7812ab586482c1f"
OUTCOME_COMMIT = "6e3230f55ddc68e7ea39e6513f28c2cfb5c0ce6e"
OUTCOME_TREE = "08f341569a9290ef21d00564bb98a957776fe82e"

FROZEN_FILES = {
    CHECKER: (
        134523,
        "4b784cced6ccd47fb91e3d7639a46800c6310c8dfaac8fd424ba9f4afdfe30b5",
    ),
    CONTRACT: (
        19487,
        "e42029f7090da444a9f464d53221da6009db0d6eff2fe3f1631306a7b6053768",
    ),
    RESULT: (
        138356,
        "686043604180a195a2924c72215b1d23ef80b7765f0d7ddd51eba7fcef604501",
    ),
}

SPEC = importlib.util.spec_from_file_location("fh_l8_d16_test_subject", CHECKER)
D16 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(D16)


class PackedConsumerForensicD16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_contract = CONTRACT.read_bytes()
        cls.contract = D16._load_json_bytes(cls.raw_contract)
        cls.raw_result = RESULT.read_bytes()
        cls.result = D16._load_json_bytes(cls.raw_result)
        packed_result = cls.result["packed_source_audit"]
        cls.packed = {
            "checkpoint": packed_result["checkpoint"],
            "source_shard_manifest_sha256": packed_result[
                "source_shard_manifest_sha256"
            ],
            "source_shards": packed_result["source_shards"],
            "packed_result_and_terminal_receipt_bound": packed_result[
                "packed_result_and_terminal_receipt_bound"
            ],
        }

        # The static verifier scans only committed repository evidence.  Make any
        # accidental access to the retained external spool fail this test loudly.
        with mock.patch.object(
            D16,
            "audit_external_custody",
            side_effect=AssertionError("static verification touched external custody"),
        ):
            cls.static_evidence = D16.verify_outcome(
                cls.contract, CONTRACT_FREEZE_COMMIT, OUTCOME_COMMIT
            )

    def _validate_result(self, result):
        raw = D16._canonical_json(result)
        return D16.validate_result(
            result,
            raw,
            result["forensic_manifest"],
            self.result["protocol"],
            self.result["source_git_audit"],
            self.packed,
            self.result["downstream_D12_disposition"],
            self.contract,
        )

    def _run_main(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            returncode = D16.main(argv)
        return returncode, json.loads(stream.getvalue())

    def test_static_happy_path_is_exact_and_never_external(self):
        self.assertEqual(
            D16._commit_record(CHECKER_FREEZE_COMMIT),
            {
                "commit": CHECKER_FREEZE_COMMIT,
                "tree": CHECKER_FREEZE_TREE,
                "parents": [BASE_COMMIT],
            },
        )
        self.assertEqual(
            D16._commit_record(CONTRACT_FREEZE_COMMIT),
            {
                "commit": CONTRACT_FREEZE_COMMIT,
                "tree": CONTRACT_FREEZE_TREE,
                "parents": [CHECKER_FREEZE_COMMIT],
            },
        )
        self.assertEqual(
            D16._commit_record(OUTCOME_COMMIT),
            {
                "commit": OUTCOME_COMMIT,
                "tree": OUTCOME_TREE,
                "parents": [CONTRACT_FREEZE_COMMIT],
            },
        )
        self.assertEqual(
            D16._diff_entries(OUTCOME_COMMIT), {("A", D16.RESULT_PATH)}
        )
        self.assertEqual(self.static_evidence["status"], D16.STATUS)
        self.assertTrue(self.static_evidence["verified"])
        self.assertTrue(self.static_evidence["packed_source_admissible"])
        self.assertTrue(self.static_evidence["legacy_target_quarantined"])
        self.assertEqual(self.static_evidence["outcome_commit"], OUTCOME_COMMIT)
        self.assertEqual(self.static_evidence["outcome_tree"], OUTCOME_TREE)
        self.assertEqual(
            self.static_evidence["result_artifact"]["sha256"],
            FROZEN_FILES[RESULT][1],
        )
        self.assertFalse(
            self.result["authority"]["fresh_bounded_4096_preflight_execution_authorized"]
        )

    def test_frozen_file_bytes_and_hashes(self):
        for path, (expected_bytes, expected_sha256) in FROZEN_FILES.items():
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                self.assertEqual(len(raw), expected_bytes)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha256)

    def test_duplicate_nonfinite_float_and_extra_key_fail_closed(self):
        malformed = (
            b'{"value":1,"value":2}',
            b'{"value":NaN}',
            b'{"value":1.25}',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                with self.assertRaises(D16.VerificationError):
                    D16._load_json_bytes(raw)

        mutation = copy.deepcopy(self.result)
        mutation["unexpected"] = True
        with self.assertRaisesRegex(D16.VerificationError, "schema drift"):
            self._validate_result(mutation)

    def test_bool_as_int_mutations_fail_closed(self):
        result_mutation = copy.deepcopy(self.result)
        result_mutation["schema_version"] = True
        with self.assertRaises(D16.VerificationError):
            self._validate_result(result_mutation)

        contract_mutation = copy.deepcopy(self.contract)
        contract_mutation["resource_limits"]["scientific_action_call_budget"] = False
        with self.assertRaises(D16.VerificationError):
            D16.validate_contract(contract_mutation)

    def test_manifest_and_digest_mutations_fail_closed(self):
        manifest_mutation = copy.deepcopy(self.result)
        manifest_mutation["forensic_manifest"]["target_to_spool_provenance_proven"] = True
        manifest_mutation["forensic_manifest_sha256"] = D16._hash_bytes(
            D16._canonical_value(manifest_mutation["forensic_manifest"])
        )
        with self.assertRaises(D16.VerificationError):
            self._validate_result(manifest_mutation)

        digest_mutation = copy.deepcopy(self.result)
        digest_mutation["forensic_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(D16.VerificationError, "manifest binding"):
            self._validate_result(digest_mutation)

    def test_authority_resource_and_publication_scope_mutations_fail_closed(self):
        authority = copy.deepcopy(self.result)
        authority["authority"]["fresh_bounded_4096_preflight_execution_authorized"] = True
        with self.assertRaises(D16.VerificationError):
            self._validate_result(authority)

        resource_mutation = copy.deepcopy(self.result)
        resource_mutation["forensic_read_resource_observations"][
            "memory_peak_at_snapshot_bytes"
        ] = self.contract["resource_limits"]["max_cgroup_peak_bytes"] + 1
        with self.assertRaises(D16.ResourceIndeterminate):
            self._validate_result(resource_mutation)

        publication = copy.deepcopy(self.result)
        publication["publication_scope"]["publication_resource_usage_attested"] = True
        with self.assertRaises(D16.VerificationError):
            self._validate_result(publication)

    def test_unknown_cli_and_external_roots_in_static_modes_are_rejected(self):
        returncode, output = self._run_main(
            ["--mode", "protocol", "--contract-commit", CONTRACT_FREEZE_COMMIT, "--unknown"]
        )
        self.assertEqual(returncode, 1)
        self.assertEqual(output["status"], "VERIFICATION_FAILED")

        cases = (
            [
                "--mode",
                "protocol",
                "--contract-commit",
                CONTRACT_FREEZE_COMMIT,
                "--source-root",
                "/tmp/not-contract-bound",
            ],
            [
                "--mode",
                "static",
                "--contract-commit",
                CONTRACT_FREEZE_COMMIT,
                "--outcome-commit",
                OUTCOME_COMMIT,
                "--run-root",
                "/tmp/not-contract-bound",
            ],
        )
        for argv in cases:
            with self.subTest(mode=argv[1]):
                returncode, output = self._run_main(argv)
                self.assertEqual(returncode, 1)
                self.assertEqual(output["status"], "VERIFICATION_FAILED")
                self.assertIn("forbids external root arguments", output["error"])

    def test_oversize_git_blob_is_rejected_before_local_read(self):
        maximum = 64
        oversize = maximum + 1
        with mock.patch.object(
            D16, "_blob_metadata", return_value=("100644", "0" * 40, oversize)
        ):
            with mock.patch.object(D16, "_open_directory_nofollow") as open_directory:
                with self.assertRaisesRegex(
                    D16.VerificationError, "Git artifact byte preflight"
                ):
                    D16._read_git_bound_repo_artifact(
                        "never-read.json",
                        OUTCOME_COMMIT,
                        oversize,
                        "0" * 64,
                        maximum,
                    )
                open_directory.assert_not_called()

    def test_publication_oserror_is_resource_indeterminate_without_writing(self):
        with mock.patch.object(
            D16,
            "_publish_forensic_result_impl",
            side_effect=FileExistsError("concurrent publication"),
        ):
            with self.assertRaises(D16.ResourceIndeterminate):
                D16._publish_forensic_result(b"{}\n", 64)


if __name__ == "__main__":
    unittest.main()
