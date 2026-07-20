#!/usr/bin/env python3
import hashlib, json, pathlib, struct, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-request-instantiation-precondition-contract-s21b-a16-v0.json"


def canonical_bytes(value): return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 3: raise SystemExit("usage: checker A15_TEMPLATE_SET MATRIX")
    templates, matrix_path = map(pathlib.Path, sys.argv[1:]); contract = json.loads(CONTRACT.read_text(encoding="ascii")); raw = matrix_path.read_bytes(); value = json.loads(raw)
    assert raw == canonical_bytes(value); claimed = value.pop("precondition_matrix_digest_sha256")
    body = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii"); domain = contract["verification_digest_domain"].encode("ascii")
    assert claimed == hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert value["format_id"] == contract["format_id"] and value["input_mode"] == contract["input_mode"] and value["a15_template_set_sha256"] == hashlib.sha256(templates.read_bytes()).hexdigest()
    assert value["request_instance_issued"] is False and value["side_effects_unlocked"] == "NONE" and value["test_only"] is True and value["template_state"] == contract["template_state"] and value["validity_boundary"] == contract["validity_boundary"]
    for item in value["matrix"]:
        assert item["instantiation_allowed"] is False and item["state"] == contract["template_state"]
        assert [binding["binding"] for binding in item["fresh_bindings"]] == contract["required_fresh_bindings"]
        assert all(binding["status"] == "REQUIRED_ABSENT" for binding in item["fresh_bindings"])
    print("S21B_A16_PRECONDITION_MATRIX_GATE\tPASS")


if __name__ == "__main__": main()
