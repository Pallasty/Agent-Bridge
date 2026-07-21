#!/usr/bin/env python3
"""Durable contract tests for the K=589824/C=34 arithmetic capability."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import pathlib
import sys
import types
import unittest


HERE = pathlib.Path(__file__).resolve().parent
WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k589824_c34.py"
BASE_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
ROUTE_PREDECESSOR_NAME = "hubbard_l8_adaptive_k_arithmetic_k573440_c33.py"

EXPECTED_WRAPPER_SHA256 = (
    "7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254"
)
EXPECTED_BASE_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_ROUTE_PREDECESSOR_SHA256 = (
    "811a16b6a47bca60281fb4afe8280783146e6f4ee28955dde7907b47fc65bb49"
)
EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256 = (
    "c2787b105553b80ee9a1e5e1d925d6cac2ab819b0cdfab305484bf89bbba32c5"
)
EXPECTED_MANIFEST_SHA256 = (
    "36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a"
)
EXPECTED_SOURCE_LAYERS_SHA256 = (
    "bc20e41796609490cb9c3f8c96b16882ab97f95d1d50da936eb454989531cc5c"
)
EXPECTED_ROUTE_REFERENCE_SHA256 = (
    "b8dc6798ebde60ca0200f0375d9cf894bcbb570fecd520f3990e0fb2a02d5d9a"
)
EXPECTED_BEFORE_LIMITS_SHA256 = (
    "22067237fe211d42123b03a969b2484306a59be46e4c844d10f148dc0c5bc00b"
)
EXPECTED_ROUTE_LIMITS_SHA256 = (
    "a812f96c2207c06795e93c78f34055a981803baf088ce779ccccb7f20145c1ed"
)
EXPECTED_AFTER_LIMITS_SHA256 = (
    "db2e0ae039c65760093ab4ef9718fb850009aabbecf7598ec387a7ae90595ebe"
)
EXPECTED_DIRECT_DELTA_SHA256 = (
    "66172a913145333ee751a5c494cdc71c0f49997ad5d9b5839967d6cb3b86fdad"
)
EXPECTED_ROUTE_DELTA_SHA256 = (
    "c621fcd80da1bcb8f0719b31cf76d73193e87ef8fce404c9af0cdb347caf1be6"
)

D_CANDIDATES_33 = (
    73_728, 81_920, 90_112, 98_304, 106_496, 114_688, 122_880,
    131_072, 147_456, 163_840, 180_224, 196_608, 212_992, 229_376,
    245_760, 262_144, 278_528, 294_912, 311_296, 327_680, 344_064,
    360_448, 376_832, 393_216, 409_600, 425_984, 442_368, 458_752,
    475_136, 507_904, 524_288, 540_672, 573_440,
)
EXPECTED_D_CANDIDATES_33_SHA256 = (
    "461517a4e7d5f6ffbb610b53240f01071cc7f7a9ac1b2dfdbc6e4b0addd59a27"
)
D_CANDIDATES_34 = D_CANDIDATES_33 + (589_824,)
EXPECTED_D_CANDIDATES_34_SHA256 = (
    "a15306f3ca1f770baeac58bd8d3d48e64bb677e9fb10b6177c30be60bc735774"
)
D_CANDIDATES_35 = (65_536,) + D_CANDIDATES_34
EXPECTED_D_CANDIDATES_35_SHA256 = (
    "a428cf54a735c4d8bbc0c3cd1d4c7d99f6603de8879160bfa6e779ce0559927b"
)


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


WRAPPER = load_module("k589824_c34_wrapper_for_tests", WRAPPER_NAME)
DIRECT_V2 = load_module("direct_v2_for_k589824_c34_tests", BASE_NAME)


class K589824C34ArithmeticTests(unittest.TestCase):
    def test_01_exact_wrapper_base_and_route_predecessor_pins(self):
        wrapper_payload = (HERE / WRAPPER_NAME).read_bytes()
        base_payload = (HERE / BASE_NAME).read_bytes()
        predecessor_payload = (HERE / ROUTE_PREDECESSOR_NAME).read_bytes()
        self.assertEqual(sha256(wrapper_payload), EXPECTED_WRAPPER_SHA256)
        self.assertEqual(sha256(base_payload), EXPECTED_BASE_SHA256)
        self.assertEqual(
            sha256(predecessor_payload), EXPECTED_ROUTE_PREDECESSOR_SHA256
        )
        self.assertEqual(WRAPPER.SELF_NAME, WRAPPER_NAME)
        self.assertEqual(WRAPPER.BASE_KERNEL_NAME, BASE_NAME)
        self.assertEqual(WRAPPER.ROUTE_PREDECESSOR_NAME, ROUTE_PREDECESSOR_NAME)
        self.assertEqual(WRAPPER.EXPECTED_BASE_KERNEL_SHA256, EXPECTED_BASE_SHA256)
        self.assertEqual(
            WRAPPER.EXPECTED_ROUTE_PREDECESSOR_SHA256,
            EXPECTED_ROUTE_PREDECESSOR_SHA256,
        )
        self.assertEqual(
            WRAPPER.EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256,
            EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256,
        )
        self.assertEqual(WRAPPER.WRAPPER_SOURCE_SHA256, EXPECTED_WRAPPER_SHA256)
        self.assertEqual(
            WRAPPER._VERIFIED_SELF_SOURCE_BYTES, wrapper_payload
        )
        self.assertEqual(
            WRAPPER._VERIFIED_BASE_KERNEL_SOURCE_BYTES, base_payload
        )

    def test_02_fresh_same_byte_isolation_and_fail_closed_loading(self):
        wrapper_payload = (HERE / WRAPPER_NAME).read_bytes()
        base_payload = (HERE / BASE_NAME).read_bytes()
        first = WRAPPER.fresh_self_module()
        second = WRAPPER.fresh_self_module()
        pinned = WRAPPER.load_pinned_capability(EXPECTED_WRAPPER_SHA256)
        self.assertIsNot(first, WRAPPER)
        self.assertIsNot(first, second)
        self.assertIsNot(first._BASE_KERNEL_MODULE, second._BASE_KERNEL_MODULE)
        self.assertIsNot(first._BASE_KERNEL_MODULE, DIRECT_V2)
        for capability in (first, second, pinned):
            self.assertEqual(capability._VERIFIED_SELF_SOURCE_BYTES, wrapper_payload)
            self.assertEqual(
                capability._VERIFIED_BASE_KERNEL_SOURCE_BYTES, base_payload
            )
            self.assertEqual(
                capability.WRAPPER_SOURCE_SHA256, EXPECTED_WRAPPER_SHA256
            )

        with self.assertRaisesRegex(RuntimeError, "wrapper source pin drift"):
            WRAPPER.load_pinned_capability("0" * 64)
        for invalid in ("A" * 64, "a" * 63, 7, None):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(RuntimeError, "not canonical lowercase"):
                    WRAPPER.load_pinned_capability(invalid)
        with self.assertRaisesRegex(TypeError, "exact bytes"):
            WRAPPER.exact_source_sha256(bytearray(wrapper_payload))

        def execute_with(bindings):
            module = types.ModuleType("injected_k589824_c34_for_test")
            module.__file__ = str(HERE / WRAPPER_NAME)
            module.__package__ = ""
            module.__dict__.update(bindings)
            exec(compile(wrapper_payload, module.__file__, "exec"), module.__dict__)
            return module

        with self.assertRaisesRegex(RuntimeError, "requires exact self and"):
            execute_with({"_VERIFIED_SELF_SOURCE_BYTES": wrapper_payload})
        with self.assertRaisesRegex(RuntimeError, "requires exact self and"):
            execute_with({"_VERIFIED_BASE_KERNEL_SOURCE_BYTES": base_payload})
        tampered_base = base_payload[:-1] + bytes([base_payload[-1] ^ 1])
        with self.assertRaisesRegex(RuntimeError, "arithmetic-v2 source pin drift"):
            execute_with({
                "_VERIFIED_SELF_SOURCE_BYTES": wrapper_payload,
                "_VERIFIED_BASE_KERNEL_SOURCE_BYTES": tampered_base,
            })

    def test_03_direct_v2_is_the_only_execution_layer(self):
        observed_reads = []
        observed_compiles = []
        observed_imports = []
        original_reader = WRAPPER._read_bounded_source
        original_compile = builtins.compile
        original_import = builtins.__import__

        def tracked_reader(path, maximum):
            observed_reads.append(path.name)
            return original_reader(path, maximum)

        def tracked_compile(source, filename, mode, *args, **kwargs):
            observed_compiles.append(pathlib.Path(filename).name)
            return original_compile(source, filename, mode, *args, **kwargs)

        def tracked_import(name, globals=None, locals=None, fromlist=(), level=0):
            observed_imports.append(name)
            return original_import(name, globals, locals, fromlist, level)

        try:
            WRAPPER._read_bounded_source = tracked_reader
            builtins.compile = tracked_compile
            builtins.__import__ = tracked_import
            fresh = WRAPPER.fresh_self_module()
        finally:
            WRAPPER._read_bounded_source = original_reader
            builtins.compile = original_compile
            builtins.__import__ = original_import
        self.assertEqual(observed_reads, [WRAPPER_NAME, BASE_NAME])
        self.assertEqual(observed_compiles, [WRAPPER_NAME, BASE_NAME])
        self.assertNotIn(ROUTE_PREDECESSOR_NAME, observed_reads)
        self.assertNotIn(ROUTE_PREDECESSOR_NAME, observed_compiles)
        self.assertNotIn(
            ROUTE_PREDECESSOR_NAME.removesuffix(".py"), observed_imports
        )

        manifest = fresh.capability_manifest()
        self.assertEqual(
            [item["relative_path"] for item in manifest["source_layers"]],
            [WRAPPER_NAME, BASE_NAME],
        )
        self.assertNotIn(
            ROUTE_PREDECESSOR_NAME,
            {item["relative_path"] for item in manifest["source_layers"]},
        )
        reference = manifest["route_predecessor_reference"]
        self.assertFalse(reference["compiled"])
        self.assertFalse(reference["executed"])
        self.assertFalse(reference["execution_source_layer"])
        self.assertEqual(
            pathlib.Path(fresh._BASE_KERNEL_MODULE.__file__).name, BASE_NAME
        )
        self.assertEqual(
            fresh._BASE_KERNEL_MODULE.__name__, fresh.BASE_PROVIDER_MODULE_NAME
        )
        self.assertNotIn(fresh.BASE_PROVIDER_MODULE_NAME, sys.modules)
        self.assertNotEqual(
            fresh._BASE_KERNEL_MODULE.__name__, ROUTE_PREDECESSOR_NAME.removesuffix(".py")
        )

    def test_04_only_two_capabilities_change_with_exact_direct_and_route_deltas(self):
        before = WRAPPER.RESOURCE_LIMITS_BEFORE_EXTENSION
        predecessor = WRAPPER.ROUTE_PREDECESSOR_RESOURCE_LIMITS
        after = WRAPPER.RESOURCE_LIMITS
        changed_direct = {
            key for key in set(before) | set(after)
            if before.get(key) != after.get(key)
        }
        changed_route = {
            key for key in set(predecessor) | set(after)
            if predecessor.get(key) != after.get(key)
        }
        self.assertEqual(changed_direct, {"max_candidate_count", "max_retained_K"})
        self.assertEqual(changed_route, {"max_candidate_count", "max_retained_K"})
        self.assertEqual(before["max_retained_K"], 524_288)
        self.assertEqual(predecessor["max_retained_K"], 573_440)
        self.assertEqual(after["max_retained_K"], 589_824)
        self.assertEqual(before["max_candidate_count"], 32)
        self.assertEqual(predecessor["max_candidate_count"], 33)
        self.assertEqual(after["max_candidate_count"], 34)
        for key in before:
            if key not in changed_direct:
                self.assertEqual(after[key], before[key], key)
                self.assertEqual(predecessor[key], before[key], key)
        self.assertEqual(
            WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
            {
                "max_candidate_count": {"before": 32, "after": 34},
                "max_retained_K": {"before": 524_288, "after": 589_824},
            },
        )
        self.assertEqual(
            WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K573440_C33,
            {
                "max_candidate_count": {"before": 33, "after": 34},
                "max_retained_K": {"before": 573_440, "after": 589_824},
            },
        )
        self.assertEqual(
            WRAPPER.RESOURCE_LIMIT_DELTA,
            WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
        )
        self.assertEqual(DIRECT_V2.RESOURCE_LIMITS, before)
        self.assertIs(WRAPPER.RESOURCE_LIMITS, WRAPPER._BASE_KERNEL_MODULE.RESOURCE_LIMITS)

        for value, expected in (
            (before, EXPECTED_BEFORE_LIMITS_SHA256),
            (predecessor, EXPECTED_ROUTE_LIMITS_SHA256),
            (after, EXPECTED_AFTER_LIMITS_SHA256),
            (WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2, EXPECTED_DIRECT_DELTA_SHA256),
            (WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K573440_C33, EXPECTED_ROUTE_DELTA_SHA256),
        ):
            self.assertEqual(sha256(canonical_bytes(value)), expected)

    def test_05_candidate_count_and_retained_K_boundaries_are_live(self):
        self.assertEqual(len(D_CANDIDATES_33), 33)
        self.assertEqual(D_CANDIDATES_33[-1], 573_440)
        self.assertEqual(
            sha256(canonical_bytes(list(D_CANDIDATES_33))),
            EXPECTED_D_CANDIDATES_33_SHA256,
        )
        self.assertEqual(
            WRAPPER.validate_candidates(D_CANDIDATES_33), D_CANDIDATES_33
        )
        self.assertEqual(len(D_CANDIDATES_34), 34)
        self.assertEqual(D_CANDIDATES_34[-1], 589_824)
        self.assertEqual(
            sha256(canonical_bytes(list(D_CANDIDATES_34))),
            EXPECTED_D_CANDIDATES_34_SHA256,
        )
        self.assertEqual(
            WRAPPER.validate_candidates(D_CANDIDATES_34), D_CANDIDATES_34
        )
        self.assertEqual(WRAPPER.validate_candidates((589_824,)), (589_824,))

        self.assertEqual(len(D_CANDIDATES_35), 35)
        self.assertEqual(
            sha256(canonical_bytes(list(D_CANDIDATES_35))),
            EXPECTED_D_CANDIDATES_35_SHA256,
        )
        with self.assertRaisesRegex(WRAPPER.SchemaError, "count"):
            WRAPPER.validate_candidates(D_CANDIDATES_35)
        with self.assertRaisesRegex(WRAPPER.SchemaError, "retained cap"):
            WRAPPER.validate_candidates((589_825,))
        with self.assertRaises(DIRECT_V2.SchemaError):
            DIRECT_V2.validate_candidates(D_CANDIDATES_33)
        with self.assertRaises(DIRECT_V2.SchemaError):
            DIRECT_V2.validate_candidates((589_824,))

    def test_06_functions_classes_and_counter_bind_to_the_isolated_v2_provider(self):
        capability = WRAPPER.fresh_self_module()
        provider = capability._BASE_KERNEL_MODULE
        self.assertIs(capability.RESOURCE_LIMITS, provider.RESOURCE_LIMITS)
        for name in capability.BASE_ARITHMETIC_FUNCTION_EXPORTS:
            function = getattr(capability, name)
            self.assertIs(function, getattr(provider, name), name)
            self.assertIsNot(function, getattr(DIRECT_V2, name), name)
            self.assertEqual(function.__module__, capability.BASE_PROVIDER_MODULE_NAME)
            self.assertEqual(pathlib.Path(function.__code__.co_filename).name, BASE_NAME)
            self.assertIs(function.__globals__["RESOURCE_LIMITS"], capability.RESOURCE_LIMITS)
        for name in (
            "PauliKey", "TickInterval", "TickExpansion", "SchemaError",
            "VerificationError",
        ):
            self.assertIs(getattr(capability, name), getattr(provider, name), name)

        counter = capability.PropagationCounterV2
        self.assertIs(counter, provider.PropagationCounterV2)
        self.assertIsNot(counter, DIRECT_V2.PropagationCounterV2)
        self.assertEqual(counter.__module__, capability.BASE_PROVIDER_MODULE_NAME)
        for method_name in (
            "__init__", "visit", "observe_count", "observe", "begin_window",
            "observe_interval", "observe_product_bits",
        ):
            method = getattr(counter, method_name)
            self.assertIs(
                method.__globals__["RESOURCE_LIMITS"], capability.RESOURCE_LIMITS
            )

    def test_07_manifest_layers_and_predecessor_hashes_are_frozen(self):
        manifest = WRAPPER.capability_manifest()
        self.assertEqual(
            sha256(canonical_bytes(manifest)), EXPECTED_MANIFEST_SHA256
        )
        self.assertEqual(WRAPPER.CAPABILITY_MANIFEST_SHA256, EXPECTED_MANIFEST_SHA256)
        self.assertEqual(
            WRAPPER.capability_manifest_sha256(), EXPECTED_MANIFEST_SHA256
        )
        self.assertEqual(manifest["certificate_authority"], "NONE")
        self.assertTrue(manifest["fresh_same_byte_wrapper_execution"])
        self.assertTrue(manifest["base_kernel_compiled_from_verified_bytes"])
        self.assertTrue(manifest["base_kernel_module_isolated"])
        self.assertFalse(manifest["base_kernel_registered_in_sys_modules"])
        self.assertEqual(
            manifest["changed_resource_limit_keys"],
            ["max_candidate_count", "max_retained_K"],
        )
        self.assertEqual(
            manifest["direct_resource_limit_delta_from_v2"],
            WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
        )
        self.assertEqual(
            manifest["route_resource_limit_delta_from_k573440_c33"],
            WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K573440_C33,
        )
        self.assertEqual(
            manifest["source_layers_sha256"], EXPECTED_SOURCE_LAYERS_SHA256
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest["source_layers"])),
            EXPECTED_SOURCE_LAYERS_SHA256,
        )
        self.assertEqual(
            manifest["route_predecessor_reference_sha256"],
            EXPECTED_ROUTE_REFERENCE_SHA256,
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest["route_predecessor_reference"])),
            EXPECTED_ROUTE_REFERENCE_SHA256,
        )
        self.assertEqual(
            manifest["route_predecessor_reference"],
            {
                "relative_path": ROUTE_PREDECESSOR_NAME,
                "role": "route_predecessor_capability_reference_only",
                "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SHA256,
                "capability_manifest_sha256": (
                    EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256
                ),
                "effective_resource_limits": (
                    WRAPPER.EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS
                ),
                "compiled": False,
                "executed": False,
                "execution_source_layer": False,
            },
        )
        expected_layers = [
            {
                "relative_path": WRAPPER_NAME,
                "role": "k589824_c34_kernel_capability_wrapper",
                "sha256": EXPECTED_WRAPPER_SHA256,
            },
            {
                "relative_path": BASE_NAME,
                "role": "pinned_arithmetic_v2_implementation",
                "sha256": EXPECTED_BASE_SHA256,
            },
        ]
        self.assertEqual(manifest["source_layers"], expected_layers)
        for item in expected_layers:
            self.assertEqual(
                sha256((HERE / item["relative_path"]).read_bytes()), item["sha256"]
            )
        self.assertEqual(
            sha256((HERE / ROUTE_PREDECESSOR_NAME).read_bytes()),
            EXPECTED_ROUTE_PREDECESSOR_SHA256,
        )

        detached = WRAPPER.capability_manifest()
        detached["resource_limits_after_extension"]["max_retained_K"] = 1
        self.assertEqual(
            WRAPPER.capability_manifest()["resource_limits_after_extension"]
            ["max_retained_K"],
            589_824,
        )


if __name__ == "__main__":
    unittest.main()
