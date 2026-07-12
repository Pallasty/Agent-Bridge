import hashlib
import importlib.util
import itertools
import json
import pathlib
import random
import unittest
from fractions import Fraction


HERE = pathlib.Path(__file__).resolve().parent


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BACKEND = load_module("pauli_bitset_backend", "pauli_bitset_backend.py")
CHECKER = load_module(
    "pauli_bitset_reference_checker", "operator_propagation_certificate_checker.py"
)


class PauliBitsetBackendTests(unittest.TestCase):
    def as_string_expansion(self, expansion, n_qubits):
        return {
            BACKEND.masks_to_pauli_string(*key, n_qubits): coefficient
            for key, coefficient in expansion.items()
        }

    def as_bitset_expansion(self, expansion):
        return {
            BACKEND.pauli_string_to_masks(pauli): coefficient
            for pauli, coefficient in expansion.items()
        }

    def reference_multiply(self, left, right):
        return CHECKER.pauli_multiply(left, right)

    def test_single_qubit_encoding_table_is_explicit(self):
        self.assertEqual(BACKEND.pauli_string_to_masks("I"), (0, 0))
        self.assertEqual(BACKEND.pauli_string_to_masks("X"), (1, 0))
        self.assertEqual(BACKEND.pauli_string_to_masks("Y"), (1, 1))
        self.assertEqual(BACKEND.pauli_string_to_masks("Z"), (0, 1))

    def test_q0_is_character_zero_and_mask_bit_zero(self):
        self.assertEqual(BACKEND.pauli_string_to_masks("XYZI"), (0b0011, 0b0110))
        self.assertEqual(BACKEND.masks_to_pauli_string(0b0011, 0b0110, 4), "XYZI")

    def test_all_three_qubit_strings_round_trip(self):
        for symbols in itertools.product("IXYZ", repeat=3):
            pauli = "".join(symbols)
            with self.subTest(pauli=pauli):
                self.assertEqual(
                    BACKEND.masks_to_pauli_string(
                        *BACKEND.pauli_string_to_masks(pauli), len(pauli)
                    ),
                    pauli,
                )

    def test_string_conversion_rejects_bad_type_empty_symbols_and_width(self):
        for value in (True, 1, "", "IXA", "I" * (BACKEND.MAX_QUBITS + 1)):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.pauli_string_to_masks(value)

    def test_mask_conversion_rejects_bool_negative_and_out_of_width(self):
        for arguments in (
            (True, 0, 1),
            (0, False, 1),
            (-1, 0, 1),
            (0, -1, 1),
            (2, 0, 1),
            (0, 2, 1),
            (0, 0, True),
            (0, 0, 0),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.masks_to_pauli_string(*arguments)

    def test_all_single_qubit_products_match_string_reference(self):
        for left, right in itertools.product("IXYZ", repeat=2):
            phase, key = BACKEND.pauli_multiply(
                BACKEND.pauli_string_to_masks(left),
                BACKEND.pauli_string_to_masks(right),
                1,
            )
            reference_phase, reference_output = self.reference_multiply(left, right)
            with self.subTest(left=left, right=right):
                self.assertEqual(phase, reference_phase)
                self.assertEqual(BACKEND.masks_to_pauli_string(*key, 1), reference_output)

    def test_all_two_qubit_products_match_string_reference(self):
        strings = ["".join(value) for value in itertools.product("IXYZ", repeat=2)]
        for left, right in itertools.product(strings, repeat=2):
            phase, key = BACKEND.pauli_multiply(
                BACKEND.pauli_string_to_masks(left),
                BACKEND.pauli_string_to_masks(right),
                2,
            )
            reference_phase, reference_output = self.reference_multiply(left, right)
            self.assertEqual((phase, BACKEND.masks_to_pauli_string(*key, 2)),
                             (reference_phase, reference_output))

    def test_random_six_qubit_products_match_string_reference(self):
        rng = random.Random(20260712)
        for _ in range(1_000):
            left = "".join(rng.choice("IXYZ") for _ in range(6))
            right = "".join(rng.choice("IXYZ") for _ in range(6))
            phase, key = BACKEND.pauli_multiply(
                BACKEND.pauli_string_to_masks(left),
                BACKEND.pauli_string_to_masks(right),
                6,
            )
            self.assertEqual(
                (phase, BACKEND.masks_to_pauli_string(*key, 6)),
                self.reference_multiply(left, right),
            )

    def test_random_multiplication_is_associative_including_phase(self):
        rng = random.Random(11)
        for _ in range(500):
            values = [
                BACKEND.pauli_string_to_masks(
                    "".join(rng.choice("IXYZ") for _ in range(5))
                )
                for _ in range(3)
            ]
            phase_ab, ab = BACKEND.pauli_multiply(values[0], values[1], 5)
            phase_left, left = BACKEND.pauli_multiply(ab, values[2], 5)
            phase_bc, bc = BACKEND.pauli_multiply(values[1], values[2], 5)
            phase_right, right = BACKEND.pauli_multiply(values[0], bc, 5)
            self.assertEqual(left, right)
            self.assertEqual((phase_ab + phase_left) % 4,
                             (phase_bc + phase_right) % 4)

    def test_all_three_qubit_commutation_predicates_match_reference(self):
        strings = ["".join(value) for value in itertools.product("IXYZ", repeat=3)]
        for left, right in itertools.product(strings, repeat=2):
            self.assertEqual(
                BACKEND.pauli_commutes(
                    BACKEND.pauli_string_to_masks(left),
                    BACKEND.pauli_string_to_masks(right),
                    3,
                ),
                CHECKER.pauli_commutes(left, right),
            )

    def test_anticommuting_branch_signs_match_reference(self):
        strings = ["".join(value) for value in itertools.product("IXYZ", repeat=2)]
        checked = 0
        for generator, operator in itertools.product(strings, repeat=2):
            if CHECKER.pauli_commutes(generator, operator):
                continue
            sign, key = BACKEND.anticommuting_branch(
                BACKEND.pauli_string_to_masks(generator),
                BACKEND.pauli_string_to_masks(operator),
                2,
            )
            reference_sign, reference_output = CHECKER.anticommuting_branch(
                generator, operator
            )
            self.assertEqual(
                (sign, BACKEND.masks_to_pauli_string(*key, 2)),
                (reference_sign, reference_output),
            )
            checked += 1
        self.assertEqual(checked, 120)

    def test_anticommuting_branch_rejects_commuting_pair(self):
        with self.assertRaises(BACKEND.BitsetSchemaError):
            BACKEND.anticommuting_branch(
                BACKEND.pauli_string_to_masks("XX"),
                BACKEND.pauli_string_to_masks("ZZ"),
                2,
            )

    def test_canonical_sort_key_is_numeric_and_stable(self):
        keys = [(3, 0), (0, 5), (0, 1), (2, 7)]
        self.assertEqual(
            sorted(keys, key=BACKEND.canonical_sort_key),
            [(0, 1), (0, 5), (2, 7), (3, 0)],
        )
        for bad in ((True, 0), (-1, 0), [0, 0], (0,)):
            with self.subTest(bad=bad):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_sort_key(bad)

    def sample_records(self):
        return [
            ((3, 2), (Fraction(-7, 3), Fraction(5, 2))),
            ((0, 1), (Fraction(1, 2), Fraction(1, 2))),
            ((1, 1), (Fraction(-1, 7), Fraction(2, 7))),
        ]

    def test_checkpoint_payload_sorts_and_formats_canonically(self):
        payload = BACKEND.canonical_checkpoint_payload(3, self.sample_records())
        self.assertEqual(payload["term_count"], 3)
        self.assertEqual(
            [(item["x_mask"], item["z_mask"]) for item in payload["terms"]],
            [("0x0", "0x1"), ("0x1", "0x1"), ("0x3", "0x2")],
        )
        self.assertEqual(payload["terms"][0]["lower"], "1/2")
        self.assertEqual(payload["terms"][0]["upper"], "1/2")

    def test_checkpoint_bytes_are_ascii_compact_sorted_json(self):
        encoded = BACKEND.canonical_checkpoint_bytes(3, self.sample_records())
        self.assertEqual(encoded, encoded.decode("ascii").encode("ascii"))
        self.assertNotIn(b" ", encoded)
        self.assertEqual(
            encoded,
            json.dumps(
                json.loads(encoded),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii"),
        )

    def test_checkpoint_is_independent_of_input_order(self):
        records = self.sample_records()
        self.assertEqual(
            BACKEND.canonical_checkpoint_bytes(3, records),
            BACKEND.canonical_checkpoint_bytes(3, list(reversed(records))),
        )
        self.assertEqual(
            BACKEND.checkpoint_sha256(3, records),
            BACKEND.checkpoint_sha256(3, list(reversed(records))),
        )

    def test_checkpoint_digest_matches_direct_sha256(self):
        encoded = BACKEND.canonical_checkpoint_bytes(3, self.sample_records())
        self.assertEqual(
            BACKEND.checkpoint_sha256(3, self.sample_records()),
            hashlib.sha256(encoded).hexdigest(),
        )
        self.assertEqual(
            BACKEND.checkpoint_sha256(3, self.sample_records()),
            "c69ecf852f053106f0feb89cd0c2e220903ef862974fd5821786605cec9929dd",
        )

    def test_checkpoint_binds_prototype_status_and_non_authority_scope(self):
        payload = json.loads(
            BACKEND.canonical_checkpoint_bytes(3, self.sample_records())
        )
        self.assertEqual(
            payload["prototype_status"],
            "BITSET_CONSISTENCY_AND_PERFORMANCE_PROTOTYPE_ONLY",
        )
        self.assertEqual(payload["scope_claims"]["certificate_authority"], "NONE")
        self.assertEqual(
            payload["scope_claims"]["fermion_to_qubit_mapping_identity"],
            "NOT_ASSESSED",
        )
        self.assertEqual(
            payload["scope_claims"]["product_formula_to_exact_hamiltonian"],
            "NOT_ASSESSED",
        )
        self.assertFalse(payload["scope_claims"]["ready_gate_eligible"])

    def test_checkpoint_rejects_duplicate_keys(self):
        records = self.sample_records()
        records.append(records[0])
        with self.assertRaisesRegex(BACKEND.BitsetSchemaError, "duplicate"):
            BACKEND.canonical_checkpoint_bytes(3, records)

    def test_checkpoint_rejects_out_of_width_masks(self):
        for key in ((8, 0), (0, 8), (-1, 0), (True, 0)):
            with self.subTest(key=key):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_checkpoint_bytes(
                        3, [(key, (Fraction(1), Fraction(1)))]
                    )

    def test_checkpoint_rejects_illegal_and_reversed_intervals(self):
        for interval in (
            (1, 1),
            (Fraction(1), 1),
            [Fraction(1), Fraction(1)],
            (Fraction(2), Fraction(1)),
        ):
            with self.subTest(interval=interval):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_checkpoint_bytes(1, [((0, 1), interval)])

    def test_checkpoint_rejects_rational_strings_including_non_reduced(self):
        for interval in (("1/2", "1/2"), ("2/4", "1/1"), ("0/2", "1/1")):
            with self.subTest(interval=interval):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_checkpoint_bytes(1, [((0, 1), interval)])

    def test_checkpoint_rejects_exact_zero_sparse_entry(self):
        with self.assertRaisesRegex(BACKEND.BitsetSchemaError, "zero"):
            BACKEND.canonical_checkpoint_bytes(
                1, [((0, 1), (Fraction(0), Fraction(0)))]
            )

    def test_checkpoint_rejects_malformed_sequences_and_records(self):
        for records in ({}, iter(()), [[(0, 1), (Fraction(1), Fraction(1))]], [(0,) ]):
            with self.subTest(records=type(records).__name__):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_checkpoint_bytes(1, records)

    def test_checkpoint_enforces_term_digit_and_byte_caps(self):
        records = self.sample_records()
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.canonical_checkpoint_bytes(3, records, max_terms=2)
        huge = Fraction(10**20 + 1, 3)
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.canonical_checkpoint_bytes(
                1,
                [((0, 1), (huge, huge))],
                max_rational_digits=5,
            )
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.canonical_checkpoint_bytes(3, records, max_bytes=1)

    def test_checkpoint_rejects_bool_caps_and_bool_width(self):
        records = self.sample_records()
        for keyword in (
            {"max_terms": True},
            {"max_rational_digits": True},
            {"max_bytes": True},
            {"max_qubits": True},
        ):
            with self.subTest(keyword=keyword):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.canonical_checkpoint_bytes(3, records, **keyword)
        with self.assertRaises(BACKEND.BitsetSchemaError):
            BACKEND.canonical_checkpoint_bytes(True, records)

    def test_commuting_gate_leaves_coefficient_exactly_unchanged(self):
        coefficient = (Fraction(-2, 3), Fraction(4, 5))
        source = {BACKEND.pauli_string_to_masks("ZZ"): coefficient}
        result = BACKEND.propagate_gate(
            source,
            BACKEND.pauli_string_to_masks("XX"),
            (Fraction(-1, 2), Fraction(1, 2)),
            (Fraction(3, 4), Fraction(5, 4)),
            2,
        )
        self.assertEqual(result, source)

    def test_anticommuting_gate_matches_checker_sign_and_intervals(self):
        sine = (Fraction(1, 3), Fraction(2, 5))
        cosine = (Fraction(4, 5), Fraction(9, 10))
        for generator, operator in (("X", "Z"), ("Z", "X")):
            source = {operator: (Fraction(1), Fraction(1))}
            reference = CHECKER._propagate_gate(source, generator, sine, cosine, 8)
            result = BACKEND.propagate_gate(
                self.as_bitset_expansion(source),
                BACKEND.pauli_string_to_masks(generator),
                sine,
                cosine,
                1,
                max_live_terms=8,
            )
            self.assertEqual(self.as_string_expansion(result, 1), reference)

    def test_interval_multiplication_matches_checker_four_corners(self):
        source = {"Z": (Fraction(-2), Fraction(3))}
        sine = (Fraction(-4), Fraction(5))
        cosine = (Fraction(-6), Fraction(7))
        reference = CHECKER._propagate_gate(source, "X", sine, cosine, 8)
        result = BACKEND.propagate_gate(
            self.as_bitset_expansion(source),
            BACKEND.pauli_string_to_masks("X"),
            sine,
            cosine,
            1,
            max_live_terms=8,
        )
        self.assertEqual(self.as_string_expansion(result, 1), reference)

    def test_random_small_gate_propagations_match_string_checker(self):
        rng = random.Random(9041)
        strings = ["".join(value) for value in itertools.product("IXYZ", repeat=3)]
        for _ in range(300):
            chosen = rng.sample(strings, rng.randint(1, 8))
            source = {}
            for pauli in chosen:
                lower = Fraction(rng.randint(-5, 3), rng.randint(1, 5))
                width = Fraction(rng.randint(0, 3), rng.randint(1, 5))
                interval = (lower, lower + width)
                if interval != (Fraction(0), Fraction(0)):
                    source[pauli] = interval
            if not source:
                source[chosen[0]] = (Fraction(1), Fraction(1))
            generator = rng.choice(strings)
            sine = (Fraction(-1, 3), Fraction(2, 5))
            cosine = (Fraction(3, 4), Fraction(5, 4))
            reference = CHECKER._propagate_gate(
                source, generator, sine, cosine, 256
            )
            result = BACKEND.propagate_gate(
                self.as_bitset_expansion(source),
                BACKEND.pauli_string_to_masks(generator),
                sine,
                cosine,
                3,
                max_live_terms=256,
            )
            self.assertEqual(self.as_string_expansion(result, 3), reference)

    def test_batch_applies_gates_left_to_right_like_checker(self):
        source = {"ZI": (Fraction(1), Fraction(1))}
        gate_strings = ["XI", "ZZ", "IY", "YX"]
        sine = (Fraction(1, 4), Fraction(1, 3))
        cosine = (Fraction(4, 5), Fraction(9, 10))
        reference = source
        for generator in gate_strings:
            reference = CHECKER._propagate_gate(
                reference, generator, sine, cosine, 256
            )
        gates = [
            (BACKEND.pauli_string_to_masks(generator), sine, cosine)
            for generator in gate_strings
        ]
        result = BACKEND.propagate_batch(
            self.as_bitset_expansion(source), gates, 2, max_live_terms=256
        )
        self.assertEqual(self.as_string_expansion(result, 2), reference)

    def test_batch_rejects_malformed_or_over_limit_gate_list(self):
        source = {BACKEND.pauli_string_to_masks("Z"): (Fraction(1), Fraction(1))}
        sine = (Fraction(0), Fraction(0))
        cosine = (Fraction(1), Fraction(1))
        gate = (BACKEND.pauli_string_to_masks("X"), sine, cosine)
        for gates in (iter(()), [[gate[0], sine, cosine]], [(gate[0], sine)]):
            with self.subTest(gates=type(gates).__name__):
                with self.assertRaises(BACKEND.BitsetSchemaError):
                    BACKEND.propagate_batch(source, gates, 1)
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.propagate_batch(source, [gate, gate], 1, max_gates=1)

    def test_empty_batch_still_validates_and_copies_the_expansion(self):
        source = {BACKEND.pauli_string_to_masks("Z"): (Fraction(1), Fraction(1))}
        result = BACKEND.propagate_batch(source, [], 1)
        self.assertEqual(result, source)
        self.assertIsNot(result, source)
        with self.assertRaises(BACKEND.BitsetSchemaError):
            BACKEND.propagate_batch(
                {BACKEND.pauli_string_to_masks("Z"): (Fraction(0), Fraction(0))},
                [],
                1,
            )
        with self.assertRaises(BACKEND.BitsetSchemaError):
            BACKEND.propagate_batch(source, [], 1, max_live_terms=True)

    def test_live_term_cap_is_enforced_after_branching(self):
        source = {BACKEND.pauli_string_to_masks("Z"): (Fraction(1), Fraction(1))}
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.propagate_gate(
                source,
                BACKEND.pauli_string_to_masks("X"),
                (Fraction(1), Fraction(1)),
                (Fraction(1), Fraction(1)),
                1,
                max_live_terms=1,
            )

        # Canonical key order reaches four working terms before the final input
        # would cancel one back to three.  A hard live cap applies throughout
        # the update, not only to the returned expansion.
        source = {
            BACKEND.pauli_string_to_masks(pauli): (Fraction(1), Fraction(1))
            for pauli in ("ZI", "ZZ", "YI")
        }
        with self.assertRaises(BACKEND.BitsetResourceError):
            BACKEND.propagate_gate(
                source,
                BACKEND.pauli_string_to_masks("XI"),
                (Fraction(1), Fraction(1)),
                (Fraction(1), Fraction(1)),
                2,
                max_live_terms=3,
            )

    def test_l2_witness_gate_prefix_matches_checker_without_full_claim(self):
        witness = load_module(
            "pauli_bitset_l2_witness_reference", "operator_propagation_l2_witness.py"
        )
        forward_gates = witness.build_forward_gate_sequence()
        self.assertEqual(len(forward_gates), 112)
        prefix = forward_gates[:8]
        source = {"Z" + "I" * 7: (Fraction(1), Fraction(1))}
        reference = source
        bitset_gates = []
        for gate in prefix:
            theta = CHECKER.parse_fraction(gate["theta"])
            sine, cosine = CHECKER.taylor_sin_cos_interval(theta, 2)
            reference = CHECKER._propagate_gate(
                reference, gate["pauli"], sine, cosine, 4_096
            )
            bitset_gates.append(
                (BACKEND.pauli_string_to_masks(gate["pauli"]), sine, cosine)
            )
        result = BACKEND.propagate_batch(
            self.as_bitset_expansion(source),
            bitset_gates,
            8,
            max_live_terms=4_096,
        )
        self.assertEqual(self.as_string_expansion(result, 8), reference)
        digest = BACKEND.checkpoint_sha256(
            8, BACKEND.expansion_term_records(result)
        )
        self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
