#!/usr/bin/env python3
"""Exact-result regression tests for the formal Majorana P3 replay."""

from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest import mock


BASE = Path(__file__).resolve().parent

RESULT_SHA256 = "1b795f11e76fca543028ce6b82d26b76711598efee61da12de0177a9d577af33"
CERTIFICATE_SHA256 = "cd861b06721ea945d312c60dac309dd5d350848f3daec42d8eab5892f92ea1bc"
PRECOMMIT_SHA256 = "036da84f1c8aa681c5526db06def058da1ae5044a9fad0e25d2cae02061800f6"
CHECKER_SHA256 = "06a106db25536bddd5e1b910fe12736ef827b37128d61b227dd549a4e08c4997"
RUNNER_SHA256 = "958de8886bb8e56cda26eb6c45029c7016e886caae26c598c7e6b5c595257fe2"
FIXTURE_SHA256 = "a478b783ae4005f7ef79572a4b34eee72299da262e439bdc35eca13496bdc236"
POLICY_SHA256 = "a72ef3796de65f08941cb1e82df0fbcf3f6218d678ac5ddfdefc4d05d63b0b66"
RUNTIME_LOCK_SHA256 = "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17"
PARENT_RESULT_SHA256 = "36071d1648d35f831436623b2b36d30b5f72dd9dafcddb991ea6083e7e4f1813"
PARENT_CERTIFICATE_SHA256 = "2b700d70c75392777d3f756d06199d6e416351f894a8a58bdb0e2a181ff10e09"

PRECOMMIT_COMMIT = "5c1d009165716e6b8a935cad57c556a7ba966bbf"
REPLAY_PACKAGE_SHA256 = "c5a83972635501e6bbf254f59a682bc0c09620f52d410eab5507909a249e2583"
WITNESS_SHA256 = "6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5"
TRANSCRIPT_SHA256 = "f102a1aab1bfc4f05b38d98df6371cf1aee2c3087a9960ba1b2c346b6c6dba43"
OUTER_CUSTODY_SHA256 = "dc3db8f0a4058bda29d30063f6d5054c1447aeb92ffb0e0e06ab062a0748b526"
RUNNER_STAGING_SHA256 = "e13c8a1fe1a5909a85b34ffb3082d0433db9a8351fc61f2ecea5940058ddf454"
RUNNER_STAGING_TREE_SHA256 = "9d402f9f6bb61e11bded044cf6edb441330f18021ecf977438bffe49d7986a89"
ENVIRONMENT_SHA256 = "07860c1eac760479a92059c00dd573f5de571bc13928e6bcde6cd31d22470d3f"

RUNTIME_SHA256 = "5161103e46ab4b2b647b1a4215faa75e094a7c182c05a4e1ad413cf4f0a58c54"
UPSTREAM_SHA256 = "8926d042a9f1dd2ad3e3bd09ca338f0e14f8a7528103a43f434a5f2e4b75e149"
INITIAL_SHA256 = "862dd596ff43a349e9735e049acae39b9d5697e81ea16313c86095411fea63ae"
SCHEDULE_SHA256 = "30b8715d2bd878bf1868d0c18c35c85c18b30ee9ac68fbd9be9948cb42a06007"
TRIG_TABLE_SHA256 = "e9debed19b33f2fb497b2a576c8b0509bcf4547551dc8a6fb9bbaf688061b649"
TRIG_ENTRIES_SHA256 = "2cf79510f1f76728e9cbe22cd168d220845b0be328833d04f0da322da331ee0a"
EXECUTION_SHA256 = "0ce9fa3907257064d784ced229641f68e8761cb4b304630444b8db65a5624394"
TRANSITION_RECORDS_SHA256 = "f7e8e0e262a78b165a64d2014a7b5cad08014be8a3f2dab38d20d39dfe12d357"
BOUNDARY_RECORDS_SHA256 = "82a4e39d22faf87a15aad083b9c57b245187de82ac97d4e6796ba2f66d601d9f"
STAGE_RECORDS_SHA256 = "e43d24de27a615209bfbb50ea364246bc3c185647e5dd0e1a5d56d9ed91f8c70"
ACCURACY_LEDGER_SHA256 = "19774d946e85f04fbe1d3f97d85d62644adb9ff3e253546ead1e1ddd31abddd3"
FINAL_STATE_SHA256 = "1aba5cd54742310cd6fa54f90654eb7cafde9a28e12850a93f2ea0c5cc0514d3"
DECLARED_INTERVAL_SHA256 = "29cc4eced5b5717b9a7ae9f0b7771adecbdef026aa5e6c9ddee6ec40e432b760"
SCOPE_SHA256 = "d074ff5a2466bd21949f0d48f6cef2854d246d29aaeada11f8d0eeee422060b2"
DEPOT_CUSTODY_SHA256 = "ce59b3c6d22e4894f8c93034ef30b5de52a925159c9fe8b492d39ae79a8172a5"
HOST_RESOURCE_SHA256 = "6b2eba9cc852dd0460b66a43b8e8ccec66583dc0dd1076d25f118b9d6561c091"

P2_TRANSITION_SHA256 = "9e9ee353993acf25b668cd22ccf20a9c221f805a63d384db715094cee30d25fd"
P2_BOUNDARY_SHA256 = "20dfca26afcc4d41851e69deae7cabb3a2588212c5ed61235b454db5f4fd66d5"
P2_STAGE_SHA256 = "76a55ef2aec9dc6fad74373bd9e94d9d55fd2aa5652bac54619ddac2624b1a1e"
FINAL_TERM_STREAM_SHA256 = "067f02a72d50f8061c746896d9eb02e3b60f7e5d6b42f21f0191b8e5887a9c9e"
NEEL_CONTRIBUTION_SHA256 = "3090eba64aeb84ff133ea556a57ee77eb5b96ba16911bcf28d90abfe1c99c1d3"
NEEL_ROWS_SHA256 = "ff9618084e141d3933b745f60681ae2255df3a56009ec29c397a21b6b9e716b0"

ENVIRONMENT_ROWS = (
    ("ELF_DYNAMIC_LOADER", "/lib64/ld-linux-x86-64.so.2", 493, 254864, "223b94a42758f2434da331cc0aa62db1af5b456481762c5caceefa1a2d1eb8fb"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_ADDRESS", 420, 127, "26e2800affab801cb36d4ff9625a95c3abceeda2b6553a7aecd0cfcf34c98099"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_COLLATE", 420, 1406, "47a5f5359a8f324abc39d69a7f6241a2ac0e2fbbeae5b9c3a756e682b75d087b"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_CTYPE", 420, 369120, "40680545df4f92443c15e7c6f51a7fdc9154ebedd9eff1ed5c48437039add365"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_IDENTIFICATION", 420, 258, "38a1d8e5271c86f48910d9c684f64271955335736e71cec35eeac942f90eb091"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MEASUREMENT", 420, 23, "bb14a6f2cbd5092a755e8f272079822d3e842620dd4542a8dfa1e5e72fc6115b"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MESSAGES/SYS_LC_MESSAGES", 420, 48, "f9ad02f1d8eba721d4cbd50c365b5c681c39aec008f90bfc2be2dc80bfbaddcb"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_MONETARY", 420, 270, "bfd9e9975443b834582493fe9a8d7aefcd989376789c17470a1e548aee76fd55"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_NAME", 420, 62, "14507aad9f806112e464b9ca94c93b2e4d759ddc612b5f87922d7cac7170697d"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_NUMERIC", 420, 50, "f5976e6b3e6b24dfe03caad6a5b98d894d8110d8bd15507e690fd60fd3e04ab2"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_PAPER", 420, 34, "cde048b81e2a026517cc707c906aebbd50f5ee3957b6f0c1c04699dffcb7c015"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_TELEPHONE", 420, 47, "f4caf0d12844219b65ba42edc7ec2f5ac1b2fc36a3c88c28887457275daca1ee"),
    ("C_UTF_8_LOCALE", "/usr/lib/locale/C.utf8/LC_TIME", 420, 3360, "0910b595d1d5d4e52cc0f415bbb1ff07c015d6860d34aae02505dd9973a63154"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libc.so.6", 493, 2186512, "d763925433ff9b757390549e1b20c085f5e6de27ae700fe89194178d96a8a2b0"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libdl.so.2", 420, 14408, "d822d2db61dfc44ba839ebd6d3552dcd2030e1b762f13f35b25702017e5fe707"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libm.so.6", 420, 1198376, "670fb59bd462ee2f833e2ed7c0a1814e0dcdbec0b8bfa048bec46e2e6fd66334"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/libpthread.so.0", 420, 14408, "c57a9c92bbd4dc724654c5e4cea774a28f772ba83b7c1804ccc8d9d364c1576b"),
    ("GLIBC_ABI", "/usr/lib/x86_64-linux-gnu/librt.so.1", 420, 14624, "882fb78b405f88b1280b3d8d1936abd30beb1d419bdc972b7cb62a621b003653"),
)


def _load_checker():
    path = BASE / "majorana_certificate_p3_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_p3_checker_for_result_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P3 = _load_checker()


class MajoranaP3ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = P3.load_json(BASE / P3.RESULT_CONTRACT_NAME)
        cls.certificate = P3.load_json(BASE / P3.CERTIFICATE_NAME)
        cls.precommit = P3.load_json(BASE / P3.PRECOMMIT_CONTRACT_NAME)
        cls.fixture = P3.validate_fixture(P3.load_json(BASE / P3.FIXTURE_NAME))
        cls.runtime = P3.P0.validate_runtime_lock(
            P3.load_json(BASE / P3.RUNTIME_LOCK_NAME)
        )
        cls.policy = P3.validate_policy(
            P3.load_json(BASE / P3.POLICY_NAME), cls.runtime
        )
        cls.p2_fixture = P3.P2.validate_fixture(
            P3.load_json(BASE / "majorana_certificate_p2_fixture.json")
        )
        cls.witness = cls.result["witness"]
        cls.execution = cls.witness["execution"]
        cls.ledger = cls.witness["accuracy_ledger"]
        cls.final_state = cls.witness["final_state"]
        cls.package = P3._package_from_result(cls.result, cls.precommit, BASE)

    def test_exact_artifact_and_precommit_hashes(self) -> None:
        expected = {
            P3.RESULT_CONTRACT_NAME: RESULT_SHA256,
            P3.CERTIFICATE_NAME: CERTIFICATE_SHA256,
            P3.PRECOMMIT_CONTRACT_NAME: PRECOMMIT_SHA256,
            P3.CHECKER_NAME: CHECKER_SHA256,
            P3.RUNNER_RELATIVE_PATH: RUNNER_SHA256,
            P3.FIXTURE_NAME: FIXTURE_SHA256,
            P3.POLICY_NAME: POLICY_SHA256,
            P3.RUNTIME_LOCK_NAME: RUNTIME_LOCK_SHA256,
            "majorana_certificate_p2_contract.json": PARENT_RESULT_SHA256,
            "majorana_certificate_p2_certificate.json": PARENT_CERTIFICATE_SHA256,
        }
        for relative, digest in expected.items():
            self.assertEqual(P3.file_sha256(BASE / relative), digest, relative)
        self.assertEqual(
            (BASE / P3.RESULT_CONTRACT_NAME).read_bytes(),
            P3.canonical_bytes(self.result) + b"\n",
        )
        self.assertEqual(
            (BASE / P3.CERTIFICATE_NAME).read_bytes(),
            P3.canonical_bytes(self.certificate) + b"\n",
        )

    def test_final_verifier_accepts_the_formal_result_once(self) -> None:
        summary = P3.verify_final()
        self.assertEqual(summary["status"], P3.MAXIMUM_STATUS)
        self.assertEqual(summary["terminal_branch"], "BOUND_WITHIN_PREFIX_ALLOCATION")
        self.assertEqual(summary["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(summary["result_contract_sha256"], RESULT_SHA256)
        self.assertEqual(summary["certificate_sha256"], CERTIFICATE_SHA256)

    def test_exact_witness_and_aggregate_hashes(self) -> None:
        objects = {
            "witness": (self.witness, WITNESS_SHA256),
            "runtime": (self.witness["runtime"], RUNTIME_SHA256),
            "upstream": (self.witness["upstream"], UPSTREAM_SHA256),
            "initial": (self.witness["initial_observable"], INITIAL_SHA256),
            "schedule": (self.witness["schedule"], SCHEDULE_SHA256),
            "trig_table": (self.witness["trig_table"], TRIG_TABLE_SHA256),
            "trig_entries": (
                self.witness["trig_table"]["entries"],
                TRIG_ENTRIES_SHA256,
            ),
            "execution": (self.execution, EXECUTION_SHA256),
            "transition_records": (
                self.execution["transition_records"],
                TRANSITION_RECORDS_SHA256,
            ),
            "boundary_records": (
                self.execution["boundary_records"],
                BOUNDARY_RECORDS_SHA256,
            ),
            "stage_records": (
                self.execution["stage_records"],
                STAGE_RECORDS_SHA256,
            ),
            "accuracy_ledger": (self.ledger, ACCURACY_LEDGER_SHA256),
            "final_state": (self.final_state, FINAL_STATE_SHA256),
            "declared_interval": (
                self.final_state["declared_expectation_interval"],
                DECLARED_INTERVAL_SHA256,
            ),
            "scope": (self.witness["scope"], SCOPE_SHA256),
            "depot_custody": (self.result["depot_custody"], DEPOT_CUSTODY_SHA256),
            "environment": (
                self.result["host_abi_and_locale_custody"],
                ENVIRONMENT_SHA256,
            ),
            "host_resource": (
                self.result["host_resource_enforcement"],
                HOST_RESOURCE_SHA256,
            ),
        }
        for label, (value, expected) in objects.items():
            with self.subTest(label=label):
                self.assertEqual(P3.canonical_sha256(value), expected)
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(self.certificate["accuracy_ledger_sha256"], ACCURACY_LEDGER_SHA256)

    def test_replay_isolation_and_provenance_are_exact(self) -> None:
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(self.result["precommit_contract_sha256"], PRECOMMIT_SHA256)
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(
            hashlib.sha256(P3.canonical_bytes(self.package) + b"\n").hexdigest(),
            REPLAY_PACKAGE_SHA256,
        )
        self.assertEqual(self.result["outer_custody_manifest_sha256"], OUTER_CUSTODY_SHA256)
        self.assertEqual(self.result["runner_staging_manifest_sha256"], RUNNER_STAGING_SHA256)
        self.assertEqual(self.result["runner_staging_tree_sha256"], RUNNER_STAGING_TREE_SHA256)
        self.assertEqual(self.result["host_abi_and_locale_custody_sha256"], ENVIRONMENT_SHA256)
        self.assertEqual(self.result["transcript_sha256_in_order"], [TRANSCRIPT_SHA256] * 2)
        self.assertEqual(self.result["fresh_process_count"], 2)
        self.assertTrue(self.result["stdout_byte_identical"])
        self.assertEqual(
            self.result["network_isolation"],
            "bubblewrap_unshared_network_namespace",
        )
        self.assertEqual(
            self.result["PID_isolation"], "bubblewrap_unshared_PID_namespace"
        )
        self.assertEqual(
            self.result["mount_isolation"],
            "six_file_runner_stage_plus_runtime_depot_scratch_18_file_host_environment_and_private_proc_dev_only",
        )
        self.assertEqual(
            self.result["host_resource_enforcement"],
            {
                "MemoryMax_bytes": 2**32,
                "RuntimeMaxSec": "300s",
                "cgroup_version": 2,
                "observed_runtime_or_memory_peak_in_canonical_package": False,
                "supervisor": "systemd_user_scope",
            },
        )

    def test_exact_18_file_environment_manifest(self) -> None:
        observed = tuple(
            (
                row["role"],
                row["sandbox_path"],
                row["mode"],
                row["size_bytes"],
                row["sha256"],
            )
            for row in self.result["host_abi_and_locale_custody"]
        )
        self.assertEqual(observed, ENVIRONMENT_ROWS)
        self.assertEqual(
            [row[1] for row in observed], sorted(row[1] for row in observed)
        )
        self.assertEqual(len(observed), 18)
        for row in self.result["host_abi_and_locale_custody"]:
            self.assertEqual(
                set(row), {"role", "sandbox_path", "mode", "size_bytes", "sha256"}
            )
        self.assertEqual(
            P3.canonical_sha256(self.result["host_abi_and_locale_custody"]),
            ENVIRONMENT_SHA256,
        )

    def test_exact_schedule_and_event_ledgers(self) -> None:
        schedule = self.witness["schedule"]
        self.assertEqual(
            (
                schedule["stage_count"],
                schedule["composite_count"],
                schedule["constituent_count"],
                schedule["truncation_boundary_count"],
            ),
            (9, 512, 1152, 768),
        )
        self.assertEqual(len(self.execution["transition_records"]), 1152)
        self.assertEqual(len(self.execution["boundary_records"]), 768)
        self.assertEqual(len(self.execution["stage_records"]), 9)
        self.assertEqual(self.execution["transition_records_sha256"], TRANSITION_RECORDS_SHA256)
        self.assertEqual(self.execution["boundary_records_sha256"], BOUNDARY_RECORDS_SHA256)
        self.assertEqual(self.execution["stage_records_sha256"], STAGE_RECORDS_SHA256)
        self.assertEqual(self.execution["P2_transition_records_sha256"], P2_TRANSITION_SHA256)
        self.assertEqual(self.execution["P2_boundary_records_sha256"], P2_BOUNDARY_SHA256)
        self.assertEqual(self.execution["P2_stage_records_sha256"], P2_STAGE_SHA256)
        self.assertEqual(
            self.execution["P2_resource_counters"],
            {
                "cap_scan_term_visits": 15_113_342,
                "final_evaluation_term_visits": 42_704,
                "propagation_term_visits": 15_113_342,
                "total_charged_term_visits": 40_259_148,
                "truncation_term_visits": 9_989_760,
            },
        )
        self.assertEqual(
            self.execution["accuracy_counters"],
            {
                "accuracy_charged_event_count": 1_426_644,
                "anticommuting_event_count": 489_740,
                "drop_defect_event_count": 328_956,
                "merge_defect_event_count": 118_208,
                "product_defect_event_count": 979_480,
            },
        )
        self.assertEqual(self.execution["total_P2_plus_accuracy_charged_event_count"], 41_685_792)
        self.assertEqual(self.execution["peak_premerge_contribution_count"], 44_222)
        self.assertEqual(self.execution["peak_postmerge_unique_term_count"], 43_848)
        self.assertIsNone(self.execution["cap_event"])

    def test_accuracy_ledger_and_strict_allocation_are_exact(self) -> None:
        expected = {
            "accuracy_charged_event_count": 1_426_644,
            "allocation_grid_ceiling_ticks_diagnostic_only": "850705917302346158658436518579421",
            "allocation_rational": "1/400000",
            "anticommuting_event_count": 489_740,
            "coefficient_L1_bounds_operator_norm": True,
            "drop_defect_event_count": 328_956,
            "drop_defect_ticks": "296986546186107059275602367348736",
            "grid_denominator": str(2**128),
            "merge_defect_event_count": 118_208,
            "merge_defect_ticks": "90064161277934613561344",
            "no_future_L1_amplification_from_exact_unitary_conjugation": True,
            "outward_widening_is_absorbed_in_each_local_upper_not_added_again": True,
            "product_defect_event_count": 979_480,
            "product_defect_ticks": "115422645562996270045296",
            "strict_comparison": "total_operator_error_ticks_times_400000_strictly_less_than_2_pow_128",
            "strictly_within_allocation": True,
            "total_operator_error_ticks": "296986546391593866116533250955376",
        }
        self.assertEqual(self.ledger, expected)
        total = int(self.ledger["total_operator_error_ticks"])
        components = sum(
            int(self.ledger[field])
            for field in ("product_defect_ticks", "merge_defect_ticks", "drop_defect_ticks")
        )
        self.assertEqual(total, components)
        self.assertLess(total * 400_000, 2**128)
        self.assertEqual(
            self.ledger["accuracy_charged_event_count"],
            self.ledger["product_defect_event_count"]
            + self.ledger["merge_defect_event_count"]
            + self.ledger["drop_defect_event_count"],
        )
        self.assertEqual(
            self.ledger["product_defect_event_count"],
            2 * self.ledger["anticommuting_event_count"],
        )

    def test_declared_Neel_interval_is_exact_and_outward(self) -> None:
        total = int(self.ledger["total_operator_error_ticks"])
        center_lower = int(self.final_state["center_lower_ticks"])
        center_upper = int(self.final_state["center_upper_ticks"])
        declared_lower = int(self.final_state["declared_expectation_lower_ticks"])
        declared_upper = int(self.final_state["declared_expectation_upper_ticks"])
        self.assertEqual(center_lower, 340044424554109064623036652659786383360)
        self.assertEqual(center_upper, center_lower)
        self.assertEqual(declared_lower, 340044127567562673029170536126535427984)
        self.assertEqual(declared_upper, 340044721540655456216902769193037338736)
        self.assertEqual(declared_lower, center_lower - total)
        self.assertEqual(declared_upper, center_upper + total)
        interval = self.final_state["declared_expectation_interval"]
        self.assertEqual(
            interval,
            {
                "lower": "21252757972972667064323158507908464249/21267647932558653966460912964485513216",
                "upper": "21252795096290966013556423074564833671/21267647932558653966460912964485513216",
            },
        )
        self.assertEqual(Fraction(interval["lower"]), Fraction(declared_lower, 2**128))
        self.assertEqual(Fraction(interval["upper"]), Fraction(declared_upper, 2**128))
        self.assertEqual(
            Fraction(self.final_state["checkerboard_Neel_exact_dyadic_center"]),
            Fraction(center_lower, 2**128),
        )
        self.assertEqual(self.final_state["retained_term_count"], 42_704)
        self.assertEqual(self.final_state["term_stream_sha256"], FINAL_TERM_STREAM_SHA256)
        self.assertEqual(
            self.final_state["checkerboard_Neel_contribution_stream_sha256"],
            NEEL_CONTRIBUTION_SHA256,
        )
        self.assertEqual(
            self.final_state["checkerboard_Neel_expectation_rows_sha256"],
            NEEL_ROWS_SHA256,
        )
        self.assertEqual(
            self.final_state["checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"],
            "3feffa45912362b7",
        )
        self.assertTrue(self.final_state["exact_dyadic_center_and_declared_interval_are_authoritative"])
        self.assertTrue(self.final_state["Float64_reduction_is_diagnostic_only"])

    def test_trig_table_is_exact_and_mutations_fail_closed(self) -> None:
        trig = self.witness["trig_table"]
        self.assertEqual(trig["entry_count"], 6)
        self.assertEqual(trig["entries_sha256"], TRIG_ENTRIES_SHA256)
        self.assertEqual(trig["grid_denominator"], str(2**128))
        self.assertEqual(trig["taylor_order"], 7)
        self.assertEqual(
            trig["entries"][0],
            {
                "angle": "-1/50",
                "angle_Float64_bits_hex": "bf947ae147ae147b",
                "cosine_Float64_bits_hex": "3feffe5c95658d96",
                "cosine_lower_ticks": "340214312716073141471485608408691179914",
                "cosine_upper_ticks": "340214312716073141471485608408691179915",
                "sine_Float64_bits_hex": "bf947a87cda55867",
                "sine_lower_ticks": "-6805193637670318048769431381177191021",
                "sine_upper_ticks": "-6805193637670318048769431381177191020",
            },
        )
        P3._validate_trig_table(trig)
        stale_digest = copy.deepcopy(trig)
        stale_digest["entries"][0]["sine_lower_ticks"] = str(
            int(stale_digest["entries"][0]["sine_lower_ticks"]) + 1
        )
        exact_but_inward = copy.deepcopy(stale_digest)
        exact_but_inward["entries_sha256"] = P3.canonical_sha256(
            exact_but_inward["entries"]
        )
        for candidate in (stale_digest, exact_but_inward):
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3._validate_trig_table(candidate)

    def test_certificate_authority_and_provenance_are_exact(self) -> None:
        certificate = self.certificate
        self.assertEqual(certificate["status"], P3.MAXIMUM_STATUS)
        self.assertEqual(certificate["terminal_branch"], "BOUND_WITHIN_PREFIX_ALLOCATION")
        self.assertEqual(
            certificate["authority"],
            "fixed_L8_first_fused_mapped_step_exact_prefix_local_defect_operator_and_Neel_expectation_enclosure_only",
        )
        self.assertEqual(certificate["result_contract_sha256"], RESULT_SHA256)
        self.assertEqual(certificate["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(certificate["policy_sha256"], POLICY_SHA256)
        self.assertEqual(certificate["runtime_lock_sha256"], RUNTIME_LOCK_SHA256)
        self.assertEqual(certificate["fixture_sha256"], FIXTURE_SHA256)
        self.assertEqual(certificate["runner_sha256"], RUNNER_SHA256)
        self.assertEqual(certificate["checker_sha256"], CHECKER_SHA256)
        self.assertEqual(certificate["parent_P2_result_contract_sha256"], PARENT_RESULT_SHA256)
        self.assertEqual(certificate["parent_P2_certificate_sha256"], PARENT_CERTIFICATE_SHA256)
        self.assertEqual(certificate["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(certificate["accuracy_ledger_sha256"], ACCURACY_LEDGER_SHA256)
        self.assertFalse(certificate["ready_gate_eligible"])
        exclusions = " ".join(certificate["explicit_exclusions"])
        for token in (
            "global_coefficientwise",
            "raw_1280",
            "double_occupancy",
            "remaining_99",
            "exact_Hubbard",
            "READY",
            "host_runtime_RSS",
        ):
            self.assertIn(token, exclusions)

    def test_scope_cannot_promote_beyond_the_fixed_prefix(self) -> None:
        self.assertEqual(self.result["scope"], self.witness["scope"])
        scope = self.witness["scope"]
        self.assertTrue(scope["fixed_L8_first_fused_mapped_step_exact_prefix_only"])
        self.assertEqual(scope["operator_norm_error_enclosure"], "ASSESSED")
        self.assertEqual(scope["checkerboard_Neel_expectation_enclosure"], "ASSESSED")
        self.assertEqual(scope["remaining_99_mapped_steps_or_full_R100"], "NOT_ASSESSED")
        self.assertEqual(scope["product_formula_to_exact_Hubbard_error"], "NOT_ASSESSED")
        self.assertEqual(scope["double_occupancy"], "NOT_ASSESSED")
        self.assertFalse(scope["physical_reference_qualified"])
        self.assertFalse(scope["ready_gate_eligible"])

    def test_witness_mutations_fail_closed_without_replaying_the_full_oracle(self) -> None:
        replay_projection = {
            field: copy.deepcopy(self.witness[field])
            for field in (
                "initial_observable",
                "schedule",
                "execution",
                "accuracy_ledger",
                "final_state",
            )
        }
        mutants = []
        candidate = copy.deepcopy(self.witness)
        candidate["accuracy_ledger"]["total_operator_error_ticks"] = str(
            int(candidate["accuracy_ledger"]["total_operator_error_ticks"]) - 1
        )
        mutants.append(candidate)
        candidate = copy.deepcopy(self.witness)
        candidate["execution"]["accuracy_counters"]["merge_defect_event_count"] += 1
        mutants.append(candidate)
        candidate = copy.deepcopy(self.witness)
        candidate["final_state"]["declared_expectation_lower_ticks"] = str(
            int(candidate["final_state"]["declared_expectation_lower_ticks"]) + 1
        )
        mutants.append(candidate)
        candidate = copy.deepcopy(self.witness)
        candidate["execution"]["P2_transition_records_sha256"] = "0" * 64
        mutants.append(candidate)
        candidate = copy.deepcopy(self.witness)
        candidate["scope"]["ready_gate_eligible"] = True
        mutants.append(candidate)
        candidate = copy.deepcopy(self.witness)
        candidate["terminal_branch"] = "BOUND_EXCEEDS_PREFIX_ALLOCATION"
        mutants.append(candidate)
        with mock.patch.object(
            P3, "replay_accuracy_oracle", return_value=replay_projection
        ):
            for candidate in mutants:
                with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                    P3.validate_witness(
                        candidate, self.fixture, self.runtime, self.p2_fixture
                    )

    def test_environment_and_package_mutations_fail_closed_lightweight(self) -> None:
        environment = self.result["host_abi_and_locale_custody"]
        manifest_mutants = []
        candidate = copy.deepcopy(environment)
        candidate[0:2] = reversed(candidate[0:2])
        manifest_mutants.append(candidate)
        candidate = copy.deepcopy(environment)
        candidate[0]["source_realpath"] = "/host/loader"
        manifest_mutants.append(candidate)
        candidate = copy.deepcopy(environment)
        candidate[0]["role"] = "UNDECLARED_ROLE"
        manifest_mutants.append(candidate)
        for candidate in manifest_mutants:
            with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                P3._validate_environment_manifest(candidate)

        outer = self.package["outer_custody_manifest"]
        runner = self.package["runner_staging_manifest"]
        tree = self.package["runner_staging_tree_sha256"]
        package_mutants = []
        candidate = copy.deepcopy(self.package)
        candidate["canonical_witness_sha256"] = "0" * 64
        package_mutants.append(candidate)
        candidate = copy.deepcopy(self.package)
        candidate["transcript_sha256_in_order"][0] = "0" * 64
        package_mutants.append(candidate)
        candidate = copy.deepcopy(self.package)
        candidate["PID_isolation"] = "host_PID_namespace"
        package_mutants.append(candidate)
        candidate = copy.deepcopy(self.package)
        candidate["host_abi_and_locale_custody"][0]["sha256"] = "0" * 64
        package_mutants.append(candidate)
        candidate = copy.deepcopy(self.package)
        candidate["runner_staging_tree_sha256"] = "0" * 64
        package_mutants.append(candidate)
        with (
            mock.patch.object(P3, "validate_fixture", return_value=self.fixture),
            mock.patch.object(P3.P0, "validate_runtime_lock", return_value=self.runtime),
            mock.patch.object(P3, "validate_policy", return_value=self.policy),
            mock.patch.object(P3, "validate_precommit_contract", return_value=self.precommit),
            mock.patch.object(P3.P2, "verify_final", return_value={"status": P3.PARENT_STATUS}),
            mock.patch.object(P3, "validate_witness", return_value=self.witness),
            mock.patch.object(P3.P2, "_validate_recorded_depot_custody", return_value=None),
            mock.patch.object(
                P3,
                "_committed_replay_evidence",
                return_value=(outer, runner, tree),
            ),
        ):
            self.assertEqual(P3._validate_replay_package(self.package), self.package)
            for candidate in package_mutants:
                with self.assertRaises((P3.SchemaError, P3.VerificationError)):
                    P3._validate_replay_package(candidate)


if __name__ == "__main__":
    unittest.main()
