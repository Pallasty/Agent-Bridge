#!/usr/bin/env python3
"""Exact-result regression tests for the formal Majorana P5 S0 replay."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest


BASE = Path(__file__).resolve().parent
FILE_HASHES = {
    "majorana_certificate_p5_contract.json": "8177c2ebe24ef9da5d796ea61fac1ea035b9d1460d9708df0271edd988bd6c32",
    "majorana_certificate_p5_certificate.json": "e99e6d5b9f4f037132d337c203ac5baf4527065f3a2ba2ee2f27565ab935c516",
    "majorana_certificate_p5_precommit_contract.json": "ad5980e74370a732456a1729665702fcaab4751d322145c0ea9775b329f06b01",
    "majorana_certificate_p5_checker.py": "b60cc0ab58316630f5fb15532c0d70c5dabaea1828fef19a2f570dae8f9f26d7",
    "majorana_certificate_p5/majorana_p5_runner.jl": "3f91ae3a6886c930cd482a13809cad5e772b8c5db0188bfa6dcbf3a7067721ea",
    "majorana_certificate_p5_fixture.json": "fd8b46c8761f548d615042b24f8ec85b32891e4f42dbafdd9bd70d58379a8afb",
    "majorana_certificate_p5_policy.json": "5fb96c16dcae4cdef807491a65ccddb051e9451d0dc7d652f2971b1d0323185e",
    "majorana_certificate_p0_runtime_lock.json": "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17",
    "majorana_certificate_p3_contract.json": "1b795f11e76fca543028ce6b82d26b76711598efee61da12de0177a9d577af33",
    "majorana_certificate_p3_certificate.json": "cd861b06721ea945d312c60dac309dd5d350848f3daec42d8eab5892f92ea1bc",
    "majorana_certificate_p4_contract.json": "7d71cf5f71f8efc15f5cb4b9f1cac27f23d3a6ef05ab6925cc2e54772fa3be60",
    "majorana_certificate_p4_certificate.json": "70aa96ff57cf2021099f79786d8f3f14a5d23f0459023603d65f475a463563a0",
    "majorana_certificate_p5_design_probe_policy.json": "e47ad24291f217b0b5d54ba6aa120c479d522bd23c74faf41b5bde6da2413aa2",
    "majorana_certificate_p5_design_probe_report.json": "602c4eddea30c20ddb793e2641b1e8b55e4767a62366b946892a19c3802dffc5",
}
PRECOMMIT_COMMIT = "85173e5982f526258563fc00e326d7f3f39b0a7a"
REPLAY_PACKAGE_SHA256 = "d58edc020c6611ac90c060007dea8fe96f28c9038381182ace4f632fc29331b3"
WITNESS_SHA256 = "de70c1ac987906f6e800e7207bbc6fb9a07d8219002ba1c25ac51d2669139d7f"
RAW_WITNESS_SHA256 = {
    "K36": "d7e176ec1ca6963ad85605bc8d7142ec5ec21f5db568b9bd3a24fa5e4a8f6ee7",
    "K37": "484de796a2b47572db9b8f4dbc6130c3172d55a976973fb8e5c9131124edc901",
}
RAW_TRANSCRIPT_SHA256 = {
    "K36": "f59e72b48f78c404710f939a494e0085a093fa392dc3e96bf557747c252c612f",
    "K37": "82480f77321a880f3925bf8cfc172247045ff911a57b18e05e9fd859d83c2bdd",
}
GRID = 340282366920938463463374607431768211456
PARENT_E1_TICKS = 296986546391593866116533250955376
P4_E12_TICKS = 4729678739637900685775256738670681

COMMON_HASHES = {
    "scope": "34b49322153472cb4a795554e182a3fcf7ec68babec083298e6b468911b38d73",
    "design_parent_D0": "498f293a36496f9bce30aa46811158797db8004e1d1688f43c369debf0cfb367",
    "parent_P4": "f25acfda297387440093243c7bb668d99de64dd2d9abeb535de039b854e656c6",
    "parent_P3": "fb301c386abee99d003787ebd0c8d4dbe4459d4186edc3e3a579ac52bf70e90b",
    "candidate_results": "1c6ea2a2e3e69c69217a3b0c7153987c64300fe42d6532307d87ce34f52091fd",
    "process_bindings": "4b5d47e1df1a9c184d5c3ca361d24aa2647c200575df493230a4f5a8c824f12b",
    "runtime": "5161103e46ab4b2b647b1a4215faa75e094a7c182c05a4e1ad413cf4f0a58c54",
    "upstream": "8926d042a9f1dd2ad3e3bd09ca338f0e14f8a7528103a43f434a5f2e4b75e149",
    "initial": "862dd596ff43a349e9735e049acae39b9d5697e81ea16313c86095411fea63ae",
    "schedule": "30b8715d2bd878bf1868d0c18c35c85c18b30ee9ac68fbd9be9948cb42a06007",
    "trig_table": "e9debed19b33f2fb497b2a576c8b0509bcf4547551dc8a6fb9bbaf688061b649",
    "step_boundary_link": "e1f89a571357ebd2499c28476a357c0829c60a1c473dfcb402283785144d3e8f",
    "step1": "5e590bc8f296b14f853c2e601454759ccb336972f1537b547b0db526c3b80cc6",
    "step1_execution": "0ce9fa3907257064d784ced229641f68e8761cb4b304630444b8db65a5624394",
    "step1_ledger": "19774d946e85f04fbe1d3f97d85d62644adb9ff3e253546ead1e1ddd31abddd3",
    "step1_transitions": "f7e8e0e262a78b165a64d2014a7b5cad08014be8a3f2dab38d20d39dfe12d357",
    "step1_boundaries": "82a4e39d22faf87a15aad083b9c57b245187de82ac97d4e6796ba2f66d601d9f",
    "step1_stages": "e43d24de27a615209bfbb50ea364246bc3c185647e5dd0e1a5d56d9ed91f8c70",
    "step1_final": "1aba5cd54742310cd6fa54f90654eb7cafde9a28e12850a93f2ea0c5cc0514d3",
}

CANDIDATE_HASHES = {
    "K36": {
        "candidate_result": "0bcf90bbe7a10012499dff81e3e80420eaa5b38f279ba094694d02facb9e166f",
        "candidate": "b4f93ad3e42e0a4b0a740fe94a0af2ef998012bb8acbe4a6ebc3bc4f6a909b3f",
        "step2": "61c22fec9545ee7964b17045a138071e4ebe81958ab886f4cb4258783a1b4930",
        "step2_execution": "8b24e1c4e62b74e1bc84f450ece7e9c1608f2f0d9176478b10f6333ef10ba95f",
        "step2_ledger": "3be2a40349a6d9bdcad98573064e3c69aa9af084a9354d027d2437e24e63a8be",
        "step2_transitions": "e03b27b614d48b4baff66897881107dd0d2f9b8a493e1880466a6847841ebb13",
        "step2_boundaries": "b0317b674439f1febb7f4fe226ef63b0d6c33e45b111e02e54cf3f75d1e0a5b1",
        "step2_stages": "434ebc00923f0e869ee3863f6fe283b1d6113f4e78057cda51b5cfb94cc1eb92",
        "step2_local_final": "a9f84f984c3c2241b64727b37b5ba81c792a7b700175bacdd3d403aeb11c23f8",
        "telescoping": "40ef6e88fd8e470a64417b6d878e1d1d7bd661fae35c44c87146cf69ba75c381",
        "authoritative_final": "d4b03f2b5f4d8588a8a310469a887b4641f67e719a476d104093289c77dc1de8",
        "authoritative_interval": "d7236921dd48522b945507eaae2fc318ced57805efe315807af6454b8a85fadb",
    },
    "K37": {
        "candidate_result": "c79e206a31393aae5c65b028649919c61cae6ef824f672f2e96cad5af1c2e176",
        "candidate": "1d8d19d601d1b6507857820285e9324b3e174e5234e3c9695bf357f1a8bd3252",
        "step2": "7b2ed2539c674134fa0ebb83062018913181deecf5c91028276ec5ab87dabc2e",
        "step2_execution": "e34e44d14ef95ddd4a96d6f741ebff8a7763f7290ad8739f3617e0194e47b110",
        "step2_ledger": "bb4bf479cd11806d23ead17a46d99c9c161dcf84c7a391ac207148eeaa4d0829",
        "step2_transitions": "1b0f6026b0a86677804a838f81395da48cddf989c455662f339046f5d080754c",
        "step2_boundaries": "b07b96c67374fec8de99f14c1542e58421114be065d74497e86064cfeba6bbf9",
        "step2_stages": "eace0739f674b8b0410fa6b816c2d66e4045486f822f19ffc76b8a0796078236",
        "step2_local_final": "16ace8a4ea3a3762733cc2a59556428616e117603777eb7fe7925c91dc982093",
        "telescoping": "dfcdeb13b1373940d6ee3a46d2ed6ee0eab83445db9585b7367f856324a39c76",
        "authoritative_final": "c71a5353ff0a9d128ad96495a5714c9ef0ffdd99fc29908c90e254e37e72d4ef",
        "authoritative_interval": "198d1b8664b8468781895a74ae9579dc43c1b37e8aaa59443a820f0fa452a95e",
    },
}

LEDGERS = {
    "K36": {
        "product": 147855427294375606587484,
        "merge": 145445157209360875778048,
        "drop": 2070126857683522430189962843389952,
        "local": 2070126857976823014693699325755484,
        "cumulative": 2367113404368416880810232576710860,
        "events": (3916152, 7832304, 1029824, 2754752, 11616880),
    },
    "K37": {
        "product": 147828058732567715525057,
        "merge": 143978275273708240105472,
        "drop": 1113735320916988663593322980311040,
        "local": 1113735321208794997599598935941569,
        "cumulative": 1410721867600388863716132186896945,
        "events": (5372752, 10745504, 1492112, 3682224, 15919840),
    },
}

RESOURCES = {
    "K36": {
        "peak_premerge_contribution_count": 186102,
        "peak_postmerge_unique_term_count": 183704,
        "threshold_dropped_term_count": 2754752,
        "exact_zero_dropped_term_count": 16349,
        "P2_resource_counters": {
            "cap_scan_term_visits": 103922274,
            "final_evaluation_term_visits": 174280,
            "propagation_term_visits": 103922274,
            "total_charged_term_visits": 279133312,
            "truncation_term_visits": 71114484,
        },
        "total_P2_plus_accuracy_charged_event_count": 290750192,
    },
    "K37": {
        "peak_premerge_contribution_count": 257558,
        "peak_postmerge_unique_term_count": 253710,
        "threshold_dropped_term_count": 3682224,
        "exact_zero_dropped_term_count": 23061,
        "P2_resource_counters": {
            "cap_scan_term_visits": 138923424,
            "final_evaluation_term_visits": 241120,
            "propagation_term_visits": 138923424,
            "total_charged_term_visits": 372980288,
            "truncation_term_visits": 94892320,
        },
        "total_P2_plus_accuracy_charged_event_count": 388900128,
    },
}

RECORD_DIGESTS = {
    "K36": {
        "P2_transition_records_sha256": "43c3f0c0024ed3111d4c1d9bb9e4c7bbd110eb3f091fd035dbf480dbead38094",
        "P2_boundary_records_sha256": "862c5a1996868b51c3f68803c7afa59ae45e7bd1e46d96afb3fe1b934778ea87",
        "P2_stage_records_sha256": "a3dcb5003b43d031c6ab1b01e14b08c2004a92406c9a5e890d9154bfa6ea5723",
        "transition_records_sha256": "e03b27b614d48b4baff66897881107dd0d2f9b8a493e1880466a6847841ebb13",
        "boundary_records_sha256": "b0317b674439f1febb7f4fe226ef63b0d6c33e45b111e02e54cf3f75d1e0a5b1",
        "stage_records_sha256": "434ebc00923f0e869ee3863f6fe283b1d6113f4e78057cda51b5cfb94cc1eb92",
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": "3ed9842b288cdf4a",
    },
    "K37": {
        "P2_transition_records_sha256": "ed871924d70f7b9f592f090a0b220e8c572de83d96f8219bbd7a3a6802086f06",
        "P2_boundary_records_sha256": "ad5bc19127b6ae46cfd36a41b6f4305c2cd9cec914fc74221868468768d6f351",
        "P2_stage_records_sha256": "e8e0e4b67d1cc80d30d4b32583bc4458bd10245d2065be71daf0a5c28d1f24f5",
        "transition_records_sha256": "1b0f6026b0a86677804a838f81395da48cddf989c455662f339046f5d080754c",
        "boundary_records_sha256": "b07b96c67374fec8de99f14c1542e58421114be065d74497e86064cfeba6bbf9",
        "stage_records_sha256": "eace0739f674b8b0410fa6b816c2d66e4045486f822f19ffc76b8a0796078236",
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": "3ecb74a8747d30fd",
    },
}

NEEL = {
    "K36": {
        "center": 339332875056044976948375139469750173696,
        "lower": 339330507942640608531494329237173462836,
        "upper": 339335242169449345365255949702326884556,
        "center_rational": "602776273439156144015483/604462909807314587353088",
        "interval": {
            "lower": "84832626985660152132873582309293365709/85070591730234615865843651857942052864",
            "upper": "84833810542362336341313987425581721139/85070591730234615865843651857942052864",
        },
        "retained": 174280,
        "term": "efd5195b1509eb54c29a6009c1bd1fa08391a68cc98b21e9cd6c926bff3d0409",
        "contribution": "fcca094a6852e57eca1f5ca645ca0b4ad2a46314f637b517f35416f8b3a86433",
        "rows": "23535e1465963f4cc1d7989e71ab329e1720ac48d04adf6af29c008e7eb9f98b",
        "float_bits": "3fefe9244df9d5f2",
    },
    "K37": {
        "center": 339332874981661087840305106126662270976,
        "lower": 339331464259793487451441389994475374031,
        "upper": 339334285703528688229168822258849167921,
        "center_rational": "602776273307023813857173/604462909807314587353088",
        "interval": {
            "lower": "339331464259793487451441389994475374031/340282366920938463463374607431768211456",
            "upper": "339334285703528688229168822258849167921/340282366920938463463374607431768211456",
        },
        "retained": 241120,
        "term": "30cf8e1a423253a0b5a02ed4c299aed157c7a6e29d21c4624f58dc6a103e288a",
        "contribution": "e1d5fbe127c220e80713f3584af97e84db02d8b409d4de6c07b08f5cf0cc53b8",
        "rows": "08f264280157deba23a0e377ee69422673a9e80bb937b021c1b455f1b5258bc6",
        "float_bits": "3fefe9244ddbcac6",
    },
}


def _load_checker():
    path = BASE / "majorana_certificate_p5_checker.py"
    spec = importlib.util.spec_from_file_location(
        "majorana_p5_checker_for_result_tests", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P5 = _load_checker()


class MajoranaP5ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The persisted P5 contract is intentionally larger than P3's old
        # stdout cap; use P5's duplicate-key/float-rejecting persisted loader.
        cls.result = P5._load_persisted_json(BASE / P5.RESULT_CONTRACT_NAME, BASE)
        cls.certificate = P5.load_json(BASE / P5.CERTIFICATE_NAME)
        cls.precommit = P5.load_json(BASE / P5.PRECOMMIT_CONTRACT_NAME)
        cls.fixture = P5.validate_fixture(P5.load_json(BASE / P5.FIXTURE_NAME), BASE)
        cls.runtime = P5.P0.validate_runtime_lock(P5.load_json(BASE / P5.RUNTIME_LOCK_NAME))
        cls.policy = P5.validate_policy(
            P5.load_json(BASE / P5.POLICY_NAME), cls.fixture, cls.runtime,
        )
        cls.package = P5._package_from_result(cls.result, cls.precommit, BASE)
        cls.witness = cls.result["witness"]
        cls.raws = cls.witness["raw_witnesses_by_candidate"]
        cls.candidates = {
            row["candidate_id"]: row for row in cls.witness["candidate_results"]
        }

    def test_exact_artifact_hashes_canonical_bytes_and_v1_identities(self) -> None:
        for relative, expected in FILE_HASHES.items():
            with self.subTest(relative=relative):
                self.assertEqual(P5.file_sha256(BASE / relative), expected)
        self.assertEqual(
            (BASE / P5.RESULT_CONTRACT_NAME).read_bytes(),
            P5.canonical_bytes(self.result) + b"\n",
        )
        self.assertEqual(
            (BASE / P5.CERTIFICATE_NAME).read_bytes(),
            P5.canonical_bytes(self.certificate) + b"\n",
        )
        self.assertEqual(self.result["contract_type"], P5.RESULT_CONTRACT_TYPE)
        self.assertEqual(self.certificate["certificate_type"], P5.CERTIFICATE_TYPE)
        self.assertEqual(self.fixture["fixture_id"], P5.FIXTURE_ID)

    def test_final_verifier_accepts_the_formal_result_once(self) -> None:
        self.assertEqual(
            P5.verify_final(BASE),
            {
                "status": P5.NO_CANDIDATE_STATUS,
                "terminal_branch": (
                    "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE"
                ),
                "selected_candidate_id": None,
                "precommit_commit_sha": PRECOMMIT_COMMIT,
                "raw_witness_sha256_by_candidate": RAW_WITNESS_SHA256,
                "canonical_witness_sha256": WITNESS_SHA256,
                "result_contract_sha256": FILE_HASHES[P5.RESULT_CONTRACT_NAME],
                "certificate_sha256": FILE_HASHES[P5.CERTIFICATE_NAME],
                "policy_id": (
                    "MAJORANA-P5-S0-CONDITIONAL-STEP2-THRESHOLD-HARDENING-V1"
                ),
            },
        )

    def test_replay_package_hashes_freshness_and_isolation_are_exact(self) -> None:
        self.assertEqual(self.result["precommit_commit_sha"], PRECOMMIT_COMMIT)
        self.assertEqual(
            self.result["precommit_contract_sha256"],
            FILE_HASHES[P5.PRECOMMIT_CONTRACT_NAME],
        )
        self.assertEqual(self.result["replay_package_sha256"], REPLAY_PACKAGE_SHA256)
        self.assertEqual(
            hashlib.sha256(P5.canonical_bytes(self.package) + b"\n").hexdigest(),
            REPLAY_PACKAGE_SHA256,
        )
        custody = {
            "outer": (self.package["outer_custody_manifest"], "ee2ce13258417ab419a13dd82b428cc49556309f7aa219f3a2a569ef962f7521"),
            "runner": (self.package["runner_staging_manifest"], "ff737178a4186ea5a82b59959ad701676ea2397a987e9b8fc27f3b549e69cc50"),
            "environment": (self.result["host_abi_and_locale_custody"], "07860c1eac760479a92059c00dd573f5de571bc13928e6bcde6cd31d22470d3f"),
            "depot": (self.result["depot_custody"], "ce59b3c6d22e4894f8c93034ef30b5de52a925159c9fe8b492d39ae79a8172a5"),
            "host": (self.result["host_resource_enforcement"], "ba2205270e24df4aa08c2ac1e6363923da111684f83ffe38060e13987ed11542"),
            "bindings": (self.result["candidate_process_bindings"], COMMON_HASHES["process_bindings"]),
        }
        for label, (value, expected) in custody.items():
            with self.subTest(label=label):
                self.assertEqual(P5.canonical_sha256(value), expected)
        self.assertEqual(self.result["fresh_process_count"], 4)
        self.assertEqual(self.result["candidate_process_order"], ["K36", "K37"])
        self.assertTrue(self.result["two_fresh_processes_per_candidate"])
        self.assertTrue(
            self.result[
                "each_process_executes_step1_then_its_candidate_step2_same_process"
            ]
        )
        self.assertFalse(
            self.result[
                "cross_candidate_state_cache_checkpoint_or_writable_scratch_shared"
            ]
        )
        self.assertEqual(
            self.result["pair_stdout_byte_identical_by_candidate"],
            {"K36": True, "K37": True},
        )
        self.assertEqual(
            self.result["raw_transcript_sha256_in_order_by_candidate"],
            {key: [value, value] for key, value in RAW_TRANSCRIPT_SHA256.items()},
        )

    def test_raw_transcript_witness_and_parent_component_hashes_are_exact(self) -> None:
        self.assertEqual(P5.canonical_sha256(self.witness), WITNESS_SHA256)
        self.assertEqual(self.result["canonical_witness_sha256"], WITNESS_SHA256)
        self.assertEqual(
            self.result["raw_witness_sha256_by_candidate"], RAW_WITNESS_SHA256,
        )
        self.assertEqual(
            self.witness["raw_witnesses_sha256_by_candidate"], RAW_WITNESS_SHA256,
        )
        objects = {
            "scope": self.witness["scope"],
            "design_parent_D0": self.witness["design_parent_D0"],
            "parent_P4": self.witness["parent_P4_lineage"],
            "parent_P3": self.witness["parent_P3_authority"],
            "candidate_results": self.witness["candidate_results"],
        }
        for label, value in objects.items():
            with self.subTest(label=label):
                self.assertEqual(P5.canonical_sha256(value), COMMON_HASHES[label])
        for candidate_id, raw in self.raws.items():
            self.assertEqual(P5.canonical_sha256(raw), RAW_WITNESS_SHA256[candidate_id])
            for label, value in (
                ("runtime", raw["runtime"]),
                ("upstream", raw["upstream"]),
                ("initial", raw["initial_observable"]),
                ("schedule", raw["schedule"]),
                ("trig_table", raw["trig_table"]),
                ("step_boundary_link", raw["step_boundary_link"]),
            ):
                with self.subTest(candidate=candidate_id, label=label):
                    self.assertEqual(P5.canonical_sha256(value), COMMON_HASHES[label])

    def test_step1_is_identical_P3_prefix_and_E1_is_inherited_once(self) -> None:
        step1_k36 = self.raws["K36"]["step1"]
        step1_k37 = self.raws["K37"]["step1"]
        self.assertEqual(step1_k36, step1_k37)
        objects = {
            "step1": step1_k36,
            "step1_execution": step1_k36["execution"],
            "step1_ledger": step1_k36["accuracy_ledger"],
            "step1_transitions": step1_k36["execution"]["transition_records"],
            "step1_boundaries": step1_k36["execution"]["boundary_records"],
            "step1_stages": step1_k36["execution"]["stage_records"],
            "step1_final": step1_k36["final_state"],
        }
        for label, value in objects.items():
            self.assertEqual(P5.canonical_sha256(value), COMMON_HASHES[label])
        self.assertEqual(step1_k36["final_state"]["retained_term_count"], 42704)
        self.assertEqual(
            int(step1_k36["accuracy_ledger"]["total_operator_error_ticks"]),
            PARENT_E1_TICKS,
        )
        parent = self.witness["parent_P3_authority"]
        self.assertEqual(parent["E1_charge_multiplicity_per_completed_candidate"], 1)
        self.assertEqual(
            parent["canonical_witness_sha256"],
            "6b4354b7f26db198427a74cfc7eac08c1895fda8d397918a9733fe7e32e8d7f5",
        )
        for candidate_id, row in self.candidates.items():
            tel = row["telescoping_ledger"]
            self.assertTrue(row["step1_P3_fieldwise_conformance"])
            self.assertTrue(row["parent_P3_E1_inherited"])
            self.assertEqual(
                row["step1_P3_projection_sha256"], parent["canonical_witness_sha256"],
            )
            self.assertEqual(int(tel["parent_P3_operator_error_ticks"]), PARENT_E1_TICKS)
            self.assertEqual(tel["parent_step1_error_charge_multiplicity"], 1)
            self.assertEqual(
                int(tel["candidate_cumulative_two_step_operator_error_ticks"]),
                PARENT_E1_TICKS + LEDGERS[candidate_id]["local"],
            )
            self.assertNotEqual(
                int(tel["candidate_cumulative_two_step_operator_error_ticks"]),
                P4_E12_TICKS + LEDGERS[candidate_id]["local"],
            )
            self.assertFalse(tel["P4_E12_or_step2_error_inherited"])
        self.assertFalse(
            self.witness["parent_P4_lineage"]["numeric_E12_or_step2_error_inherited"]
        )
        self.assertFalse(self.certificate["P4_numeric_E12_or_step2_error_inherited"])

    def test_candidate_step2_component_hashes_ledgers_and_resources_are_exact(self) -> None:
        for candidate_id in ("K36", "K37"):
            raw = self.raws[candidate_id]
            step2 = raw["step2"]
            execution = step2["execution"]
            ledger = step2["accuracy_ledger"]
            row = self.candidates[candidate_id]
            hashes = {
                "candidate_result": row,
                "candidate": raw["candidate"],
                "step2": step2,
                "step2_execution": execution,
                "step2_ledger": ledger,
                "step2_transitions": execution["transition_records"],
                "step2_boundaries": execution["boundary_records"],
                "step2_stages": execution["stage_records"],
                "step2_local_final": step2["final_state"],
                "telescoping": row["telescoping_ledger"],
                "authoritative_final": row["authoritative_two_step_final_state"],
                "authoritative_interval": row[
                    "authoritative_two_step_final_state"
                ]["declared_expectation_interval"],
            }
            for label, value in hashes.items():
                with self.subTest(candidate=candidate_id, label=label):
                    self.assertEqual(
                        P5.canonical_sha256(value), CANDIDATE_HASHES[candidate_id][label]
                    )
            expected = LEDGERS[candidate_id]
            self.assertEqual(int(ledger["product_defect_ticks"]), expected["product"])
            self.assertEqual(int(ledger["merge_defect_ticks"]), expected["merge"])
            self.assertEqual(int(ledger["drop_defect_ticks"]), expected["drop"])
            self.assertEqual(int(ledger["total_operator_error_ticks"]), expected["local"])
            self.assertEqual(
                expected["local"], expected["product"] + expected["merge"] + expected["drop"],
            )
            events = expected["events"]
            self.assertEqual(
                (
                    ledger["anticommuting_event_count"],
                    ledger["product_defect_event_count"],
                    ledger["merge_defect_event_count"],
                    ledger["drop_defect_event_count"],
                    ledger["accuracy_charged_event_count"],
                ),
                events,
            )
            self.assertIsNone(execution["cap_event"])
            self.assertEqual(
                (
                    execution["completed_composite_count"],
                    execution["completed_constituent_count"],
                    execution["completed_truncation_boundary_count"],
                ),
                (512, 1152, 768),
            )
            for key, value in RESOURCES[candidate_id].items():
                self.assertEqual(execution[key], value)
            for key, value in RECORD_DIGESTS[candidate_id].items():
                self.assertEqual(execution[key], value)

    def test_strict_allocations_produce_K36_double_fail_K37_mixed_fail(self) -> None:
        k36 = self.candidates["K36"]["telescoping_ledger"]
        k37 = self.candidates["K37"]["telescoping_ledger"]
        self.assertFalse(k36["candidate_step2_strictly_within_allocation"])
        self.assertFalse(k36["candidate_cumulative_strictly_within_allocation"])
        self.assertFalse(k37["candidate_step2_strictly_within_allocation"])
        self.assertTrue(k37["candidate_cumulative_strictly_within_allocation"])
        self.assertGreaterEqual(LEDGERS["K36"]["local"] * 400000, GRID)
        self.assertGreaterEqual(LEDGERS["K36"]["cumulative"] * 200000, GRID)
        self.assertGreaterEqual(LEDGERS["K37"]["local"] * 400000, GRID)
        self.assertLess(LEDGERS["K37"]["cumulative"] * 200000, GRID)
        for candidate_id in ("K36", "K37"):
            self.assertFalse(
                self.candidates[candidate_id]["telescoping_ledger"][
                    "candidate_positive_iff_both_strict_comparisons"
                ]
            )
            self.assertFalse(self.raws[candidate_id]["candidate_local_allocation_pass"])
        self.assertTrue(self.witness["all_candidates_completed_before_selection"])
        self.assertEqual(self.witness["selection_order"], ["K36", "K37"])
        self.assertIsNone(self.witness["selected_candidate_id"])
        self.assertIsNone(self.witness["selected_authoritative_two_step_final_state"])
        self.assertEqual(
            self.result["terminal_branch"],
            "NO_CANDIDATE_WITHIN_BOTH_ALLOCATIONS_AFTER_ALL_CANDIDATES_COMPLETE",
        )
        self.assertEqual(self.result["status"], P5.NO_CANDIDATE_STATUS)

    def test_candidate_Neel_centers_digests_and_intervals_are_exact(self) -> None:
        for candidate_id, expected in NEEL.items():
            final = self.candidates[candidate_id]["authoritative_two_step_final_state"]
            self.assertEqual(final["center_lower_ticks"], str(expected["center"]))
            self.assertEqual(final["center_upper_ticks"], str(expected["center"]))
            self.assertEqual(final["declared_expectation_lower_ticks"], str(expected["lower"]))
            self.assertEqual(final["declared_expectation_upper_ticks"], str(expected["upper"]))
            self.assertEqual(
                expected["lower"], expected["center"] - LEDGERS[candidate_id]["cumulative"],
            )
            self.assertEqual(
                expected["upper"], expected["center"] + LEDGERS[candidate_id]["cumulative"],
            )
            self.assertEqual(
                final["checkerboard_Neel_exact_dyadic_center"], expected["center_rational"],
            )
            self.assertEqual(final["declared_expectation_interval"], expected["interval"])
            self.assertEqual(final["retained_term_count"], expected["retained"])
            self.assertEqual(final["term_stream_sha256"], expected["term"])
            self.assertEqual(
                final["checkerboard_Neel_contribution_stream_sha256"],
                expected["contribution"],
            )
            self.assertEqual(
                final["checkerboard_Neel_expectation_rows_sha256"], expected["rows"],
            )
            self.assertEqual(
                final["checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"],
                expected["float_bits"],
            )
            self.assertEqual(
                Fraction(final["checkerboard_Neel_exact_dyadic_center"]),
                Fraction(expected["center"], GRID),
            )
            self.assertTrue(
                final["declared_interval_uses_parent_E1_once_plus_step2_local_increment"]
            )
            self.assertTrue(final["exact_dyadic_center_and_declared_interval_are_authoritative"])
            self.assertNotIn("local_only_interval_is_not_two_step_authority", final)

    def test_certificate_no_selection_authority_claims_exclusions_and_scope(self) -> None:
        self.assertEqual(
            self.certificate["result_contract_sha256"],
            FILE_HASHES[P5.RESULT_CONTRACT_NAME],
        )
        self.assertEqual(self.certificate["selected_candidate_id"], None)
        self.assertEqual(self.certificate["status"], P5.NO_CANDIDATE_STATUS)
        self.assertEqual(
            self.certificate["authority"],
            (
                "completed_fixed_K36_and_K37_conditional_bounds_and_no_"
                "selection_only_not_a_general_threshold_or_simulation_no_go"
            ),
        )
        expected_claims = (
            *P5.COMMON_CERTIFICATE_CLAIMS,
            *P5.COMPLETED_CANDIDATE_CLAIMS,
            *P5.NO_SELECTION_CLAIMS,
        )
        self.assertEqual(tuple(self.certificate["claims"]), expected_claims)
        self.assertNotIn(
            "selected_candidate_passes_both_strict_allocations",
            self.certificate["claims"],
        )
        self.assertEqual(
            tuple(self.certificate["explicit_exclusions"]), P5.CERTIFICATE_EXCLUSIONS,
        )
        self.assertFalse(self.certificate["ready_gate_eligible"])
        self.assertFalse(self.certificate["D0_has_scientific_or_selection_authority"])
        expected_scope = {"maximum_positive_status": P5.MAXIMUM_STATUS, **self.policy["scope_boundary"]}
        self.assertEqual(self.result["scope"], expected_scope)
        self.assertEqual(self.result["scope"], self.witness["scope"])
        self.assertEqual(
            self.result["scope"]["uniform_2^-36_or_2^-37_threshold_across_both_steps"],
            "NOT_ASSESSED",
        )
        self.assertEqual(self.result["scope"]["budget_constrained_drop"], "NOT_ASSESSED")
        self.assertEqual(
            self.result["scope"]["remaining_98_mapped_steps_or_full_R100"],
            "NOT_ASSESSED",
        )
        self.assertFalse(self.result["scope"]["physical_reference_qualified"])
        self.assertFalse(self.result["scope"]["ready_gate_eligible"])

    def test_result_artifacts_were_absent_at_the_precommit_commit(self) -> None:
        repo = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=BASE, check=True, stdout=subprocess.PIPE,
            ).stdout.decode().strip()
        ).resolve()
        self.assertEqual(
            subprocess.run(
                ["git", "rev-parse", f"{PRECOMMIT_COMMIT}^"],
                cwd=repo, check=True, stdout=subprocess.PIPE,
            ).stdout.decode().strip(),
            P5.REQUIRED_PARENT_COMMIT,
        )
        tree = set(
            subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", PRECOMMIT_COMMIT],
                cwd=repo, check=True, stdout=subprocess.PIPE,
            ).stdout.decode().splitlines()
        )
        prefix = str(BASE.relative_to(repo))
        self.assertEqual(
            tuple(self.precommit["result_artifacts_required_absent"]),
            (P5.RESULT_CONTRACT_NAME, P5.CERTIFICATE_NAME, P5.RESULT_TEST_NAME),
        )
        for name in self.precommit["result_artifacts_required_absent"]:
            self.assertNotIn(f"{prefix}/{name}", tree)
        self.assertNotIn(P5.RESULT_TEST_NAME, P5.PRECOMMIT_SOURCE_PATHS)


if __name__ == "__main__":
    unittest.main()
