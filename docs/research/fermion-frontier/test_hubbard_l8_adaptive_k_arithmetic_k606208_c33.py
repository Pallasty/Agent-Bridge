#!/usr/bin/env python3
"""Durable contract tests for the M K=606208/C=33 capability."""

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
WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py"
BASE_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
ROUTE_PREDECESSOR_NAME = "hubbard_l8_adaptive_k_arithmetic_k589824.py"
CROSS_ROUTE_REFERENCE_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py"

EXPECTED_WRAPPER_SHA256 = (
    "447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558"
)
EXPECTED_BASE_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_ROUTE_PREDECESSOR_SHA256 = (
    "9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d"
)
EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256 = (
    "6906e56af531063800742e95304682f9bcd123d0086806d59691e0b099772b1a"
)
EXPECTED_CROSS_ROUTE_REFERENCE_SHA256 = (
    "34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd"
)
EXPECTED_CROSS_ROUTE_REFERENCE_MANIFEST_SHA256 = (
    "c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629"
)
EXPECTED_MANIFEST_SHA256 = (
    "116c8d37e11e2762a3a47d2d5844d059de0277dbd41724b5c65018b0b234b395"
)
EXPECTED_SOURCE_LAYERS_SHA256 = (
    "345b883e9dac2b657d30a629b4b0bb9339a96372deb05f7da2d769a6f5d2e1da"
)
EXPECTED_ROUTE_REFERENCE_SHA256 = (
    "bd7d856617c0af68ba781da24d055c05301d022ece4a77af1f5c50431daf7492"
)
EXPECTED_CROSS_ROUTE_REFERENCE_HASH = (
    "221d37ef7f58799cf1fa908f6c81b1410a332bbdaac604d75df6f03695aa7343"
)
EXPECTED_BEFORE_LIMITS_SHA256 = (
    "22067237fe211d42123b03a969b2484306a59be46e4c844d10f148dc0c5bc00b"
)
EXPECTED_ROUTE_LIMITS_SHA256 = (
    "c64a6feea0557a8668614a4076b249e88e2df8a090371e1701f06a9c1cf7e34e"
)
EXPECTED_CROSS_ROUTE_LIMITS_SHA256 = (
    "6527951f5ef4c0b6cb604b94677e4b95fdff1d7f02c013ea84c422deab5b41d6"
)
EXPECTED_AFTER_LIMITS_SHA256 = (
    "217c1638d5224f2d787f2a44b9b1b087b13ba43f70f2c2774cfddc6e960d8f3f"
)
EXPECTED_DIRECT_DELTA_SHA256 = (
    "7eab595c19793c78323a4d1fa1234588ce27f5ec9a297f35231aeccf4e743d85"
)
EXPECTED_ROUTE_DELTA_SHA256 = (
    "ba2dc9d5e4bfc9437f58882f829626b442db649fc4bef1c7ae18570d52074ef1"
)

CANDIDATES_32 = (
    81_920, 98_304, 114_688, 131_072, 147_456, 163_840, 180_224,
    196_608, 212_992, 229_376, 245_760, 262_144, 278_528, 294_912,
    311_296, 327_680, 344_064, 360_448, 376_832, 393_216, 409_600,
    425_984, 442_368, 458_752, 475_136, 491_520, 507_904, 524_288,
    540_672, 557_056, 573_440, 589_824,
)
EXPECTED_CANDIDATES_32_SHA256 = (
    "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80"
)
CANDIDATES_33 = CANDIDATES_32 + (606_208,)
EXPECTED_CANDIDATES_33_SHA256 = (
    "8c0105608be381ce3ecaeb6178d25c0eda50713e54aa22f734b964bbd5464f86"
)
CANDIDATES_34 = (65_536,) + CANDIDATES_33


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


WRAPPER = load_module("m_k606208_c33_wrapper_for_tests", WRAPPER_NAME)
DIRECT_V2 = load_module("direct_v2_for_k606208_c33_tests", BASE_NAME)


class K606208C33ArithmeticTests(unittest.TestCase):
    def test_01_exact_wrapper_base_and_route_predecessor_pins(self):
        wrapper_payload = (HERE / WRAPPER_NAME).read_bytes()
        base_payload = (HERE / BASE_NAME).read_bytes()
        predecessor_payload = (HERE / ROUTE_PREDECESSOR_NAME).read_bytes()
        cross_route_payload = (HERE / CROSS_ROUTE_REFERENCE_NAME).read_bytes()
        self.assertEqual(sha256(wrapper_payload), EXPECTED_WRAPPER_SHA256)
        self.assertEqual(sha256(base_payload), EXPECTED_BASE_SHA256)
        self.assertEqual(
            sha256(predecessor_payload), EXPECTED_ROUTE_PREDECESSOR_SHA256
        )
        self.assertEqual(
            sha256(cross_route_payload), EXPECTED_CROSS_ROUTE_REFERENCE_SHA256
        )
        self.assertEqual(WRAPPER.SELF_NAME, WRAPPER_NAME)
        self.assertEqual(WRAPPER.BASE_KERNEL_NAME, BASE_NAME)
        self.assertEqual(WRAPPER.ROUTE_PREDECESSOR_NAME, ROUTE_PREDECESSOR_NAME)
        self.assertEqual(
            WRAPPER.CROSS_ROUTE_REFERENCE_NAME, CROSS_ROUTE_REFERENCE_NAME
        )
        self.assertEqual(WRAPPER.EXPECTED_BASE_KERNEL_SHA256, EXPECTED_BASE_SHA256)
        self.assertEqual(
            WRAPPER.EXPECTED_ROUTE_PREDECESSOR_SHA256,
            EXPECTED_ROUTE_PREDECESSOR_SHA256,
        )
        self.assertEqual(
            WRAPPER.EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256,
            EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256,
        )
        self.assertEqual(
            WRAPPER.EXPECTED_CROSS_ROUTE_REFERENCE_SHA256,
            EXPECTED_CROSS_ROUTE_REFERENCE_SHA256,
        )
        self.assertEqual(
            WRAPPER.EXPECTED_CROSS_ROUTE_REFERENCE_MANIFEST_SHA256,
            EXPECTED_CROSS_ROUTE_REFERENCE_MANIFEST_SHA256,
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
            module = types.ModuleType("injected_m_k606208_c33_for_test")
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
        for reference_name in (ROUTE_PREDECESSOR_NAME, CROSS_ROUTE_REFERENCE_NAME):
            self.assertNotIn(reference_name, observed_reads)
            self.assertNotIn(reference_name, observed_compiles)
            self.assertNotIn(
                reference_name.removesuffix(".py"), observed_imports
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
        self.assertNotIn(
            CROSS_ROUTE_REFERENCE_NAME,
            {item["relative_path"] for item in manifest["source_layers"]},
        )
        reference = manifest["route_predecessor_reference"]
        self.assertFalse(reference["compiled"])
        self.assertFalse(reference["executed"])
        self.assertFalse(reference["execution_source_layer"])
        cross_reference = manifest["cross_route_reference"]
        self.assertFalse(cross_reference["compiled"])
        self.assertFalse(cross_reference["executed"])
        self.assertFalse(cross_reference["execution_source_layer"])
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

    def test_04_only_declared_caps_change_with_exact_direct_and_route_deltas(self):
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
        declared = {"max_candidate_count", "max_retained_K"}
        self.assertEqual(changed_direct, declared)
        self.assertEqual(changed_route, declared)
        self.assertEqual(before["max_retained_K"], 524_288)
        cross_route = WRAPPER.CROSS_ROUTE_REFERENCE_RESOURCE_LIMITS
        self.assertEqual(predecessor["max_retained_K"], 589_824)
        self.assertEqual(after["max_retained_K"], 606_208)
        self.assertEqual(before["max_candidate_count"], 32)
        self.assertEqual(predecessor["max_candidate_count"], 32)
        self.assertEqual(after["max_candidate_count"], 33)
        self.assertEqual(cross_route["max_retained_K"], 606_208)
        self.assertEqual(cross_route["max_candidate_count"], 35)
        self.assertEqual(
            {
                key for key in set(after) | set(cross_route)
                if after.get(key) != cross_route.get(key)
            },
            {"max_candidate_count"},
        )
        for key in before:
            if key not in changed_direct:
                self.assertEqual(after[key], before[key], key)
                self.assertEqual(predecessor[key], before[key], key)
        self.assertEqual(
            WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
            {
                "max_candidate_count": {"before": 32, "after": 33},
                "max_retained_K": {"before": 524_288, "after": 606_208},
            },
        )
        self.assertEqual(
            WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C32,
            {
                "max_candidate_count": {"before": 32, "after": 33},
                "max_retained_K": {"before": 589_824, "after": 606_208},
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
            (cross_route, EXPECTED_CROSS_ROUTE_LIMITS_SHA256),
            (after, EXPECTED_AFTER_LIMITS_SHA256),
            (WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2, EXPECTED_DIRECT_DELTA_SHA256),
            (WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C32, EXPECTED_ROUTE_DELTA_SHA256),
        ):
            self.assertEqual(sha256(canonical_bytes(value)), expected)

    def test_05_candidate_count_and_retained_K_boundaries_are_live(self):
        self.assertEqual(len(CANDIDATES_32), 32)
        self.assertEqual(CANDIDATES_32[-1], 589_824)
        self.assertEqual(
            sha256(canonical_bytes(list(CANDIDATES_32))),
            EXPECTED_CANDIDATES_32_SHA256,
        )
        self.assertEqual(
            WRAPPER.validate_candidates(CANDIDATES_32), CANDIDATES_32
        )
        self.assertEqual(WRAPPER.validate_candidates(CANDIDATES_33), CANDIDATES_33)
        self.assertEqual(WRAPPER.validate_candidates((606_208,)), (606_208,))

        self.assertEqual(len(CANDIDATES_33), 33)
        self.assertEqual(
            sha256(canonical_bytes(list(CANDIDATES_33))),
            EXPECTED_CANDIDATES_33_SHA256,
        )
        with self.assertRaisesRegex(WRAPPER.SchemaError, "count"):
            WRAPPER.validate_candidates(CANDIDATES_34)
        with self.assertRaisesRegex(WRAPPER.SchemaError, "retained cap"):
            WRAPPER.validate_candidates((606_209,))
        with self.assertRaises(DIRECT_V2.SchemaError):
            DIRECT_V2.validate_candidates(CANDIDATES_32)
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
            manifest["cross_route_reference_sha256"],
            EXPECTED_CROSS_ROUTE_REFERENCE_HASH,
        )
        self.assertEqual(
            sha256(canonical_bytes(manifest["cross_route_reference"])),
            EXPECTED_CROSS_ROUTE_REFERENCE_HASH,
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
        self.assertEqual(
            manifest["cross_route_reference"],
            {
                "relative_path": CROSS_ROUTE_REFERENCE_NAME,
                "role": "same_K_cross_route_capability_reference_only",
                "source_sha256": EXPECTED_CROSS_ROUTE_REFERENCE_SHA256,
                "capability_manifest_sha256": (
                    EXPECTED_CROSS_ROUTE_REFERENCE_MANIFEST_SHA256
                ),
                "effective_resource_limits": (
                    WRAPPER.EXPECTED_CROSS_ROUTE_REFERENCE_RESOURCE_LIMITS
                ),
                "relationship": "same_retained_K_different_candidate_count",
                "compiled": False,
                "executed": False,
                "execution_source_layer": False,
            },
        )
        self.assertEqual(
            manifest["direct_resource_limit_delta_from_v2"],
            WRAPPER.DIRECT_RESOURCE_LIMIT_DELTA_FROM_V2,
        )
        self.assertEqual(
            manifest["route_resource_limit_delta_from_k589824_c32"],
            WRAPPER.ROUTE_RESOURCE_LIMIT_DELTA_FROM_K589824_C32,
        )
        expected_layers = [
            {
                "relative_path": WRAPPER_NAME,
                "role": "m_k606208_c33_kernel_capability_wrapper",
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
        self.assertEqual(
            sha256((HERE / CROSS_ROUTE_REFERENCE_NAME).read_bytes()),
            EXPECTED_CROSS_ROUTE_REFERENCE_SHA256,
        )

        detached = WRAPPER.capability_manifest()
        detached["resource_limits_after_extension"]["max_retained_K"] = 1
        self.assertEqual(
            WRAPPER.capability_manifest()["resource_limits_after_extension"]
            ["max_retained_K"],
            606_208,
        )


if __name__ == "__main__":
    unittest.main()
