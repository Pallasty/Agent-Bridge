"""Directed-negative checks for T21 terminal governance audit."""
import copy, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("t21",ROOT/"scripts/eval/biocortex_ab_track_b_t21_terminal_governance_offline_application_audit_v1.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
x=mod.load(); assert mod.audit(x)["status"]=="PASS_OFFLINE_APPLICATIONS_ONLY"
ops=[lambda y:y["chain"].pop(),lambda y:y["chain"][0].update(coverage="PRODUCTION"),lambda y:y["chain"][0].update(artifact="missing"),lambda y:y["allowed_offline_applications"][0].update(network=True),lambda y:y["allowed_offline_applications"][1].update(real_evidence=True),lambda y:y["forbidden_capabilities"].update(downstream_execution=False),lambda y:y["forbidden_capabilities"].pop("successor_authorization"),lambda y:y.update(content_sha256="0"*64)]
for op in ops:
    y=copy.deepcopy(x); op(y)
    try: mod.audit(y)
    except (AssertionError,KeyError,TypeError): continue
    raise AssertionError("mutation admitted")
print("t21_terminal_governance_audit_check\tpass")
print(f"directed_negative_test_count\t{len(ops)}")
