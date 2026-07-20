#!/usr/bin/env python3
import hashlib, json, pathlib, struct, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
A15 = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-evidence-request-template-contract-s21b-a15-v0.json"
A16 = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-request-instantiation-precondition-contract-s21b-a16-v0.json"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def load(path):
    raw = path.read_bytes(); value = json.loads(raw)
    if raw != canonical_bytes(value): raise ValueError(f"noncanonical JSON: {path.name}")
    return value, raw


def digest(domain_text, payload):
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = domain_text.encode("ascii")
    return hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()


def build(template_path):
    a16, _ = load(A16); a15, a15_raw = load(A15)
    if hashlib.sha256(a15_raw).hexdigest() != a16["a15_contract_sha256"]: raise ValueError("A15 contract version mismatch")
    value, raw = load(template_path)
    expected = {"a14_register_digest_sha256", "a14_register_sha256", "execution_capability_present", "format_id", "input_mode", "owner_authority_present", "side_effects_unlocked", "template_set_digest_sha256", "template_state", "templates", "test_only", "validity_boundary"}
    if set(value) != expected: raise ValueError("A15 template set field mismatch")
    claimed = value.pop("template_set_digest_sha256")
    if claimed != digest(a15["verification_digest_domain"], value): raise ValueError("A15 template set self digest mismatch")
    if value["format_id"] != a15["format_id"] or value["input_mode"] != a15["input_mode"]: raise ValueError("A15 template contract mismatch")
    if value["template_state"] != a15["template_state"] or value["execution_capability_present"] is not False or value["owner_authority_present"] is not False or value["side_effects_unlocked"] != "NONE" or value["test_only"] is not True: raise ValueError("A15 boundary mismatch")
    if [x["request_id"] for x in value["templates"]] != a15["required_request_ids"]: raise ValueError("A15 request IDs mismatch")
    for item in value["templates"]:
        if item["single_use_response_binding_required"] is not True or item["prior_response_reuse_allowed"] is not False or item["request_is_execution_capability"] is not False or item["request_is_owner_authority"] is not False or item["real_input_admission_present"] is not False or item["state"] != a15["template_state"]: raise ValueError("A15 nonreuse boundary mismatch")
    matrix = [{"fresh_bindings": [{"binding": binding, "status": "REQUIRED_ABSENT"} for binding in a16["required_fresh_bindings"]], "instantiation_allowed": False, "request_id": item["request_id"], "state": a16["template_state"]} for item in value["templates"]]
    payload = {"a15_template_set_digest_sha256": claimed, "a15_template_set_sha256": hashlib.sha256(raw).hexdigest(), "format_id": a16["format_id"], "input_mode": a16["input_mode"], "matrix": matrix, "request_instance_issued": False, "side_effects_unlocked": "NONE", "template_state": a16["template_state"], "test_only": True, "validity_boundary": a16["validity_boundary"]}
    return {"precondition_matrix_digest_sha256": digest(a16["verification_digest_domain"], payload), **payload}


def main():
    if len(sys.argv) != 2: raise SystemExit("usage: builder A15_TEMPLATE_SET")
    try: output = build(pathlib.Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A16_PRECONDITION_MATRIX_REJECTED\n"); return 65
    sys.stdout.buffer.write(canonical_bytes(output)); return 0


if __name__ == "__main__": raise SystemExit(main())
