import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/embodied-media-episode-dogfood-collector.py"
SPEC = importlib.util.spec_from_file_location("embodied_media_collector", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def settlement(candidate, settled=True):
    return {
        "schema": "agent_bridge.app_control.track_settlement.v0",
        "candidate_track_id": candidate,
        "required_consecutive_observations": 3,
        "observed_consecutive_observations": 3 if settled else 2,
        "required_stable_ms": 500,
        "observed_stable_ms": 600 if settled else 100,
        "settled": settled,
    }


def pending():
    return {"schema":"agent_bridge.app_control.v0","status":"indeterminate","verdict":"error","recover":"retry","player":"rhythmbox","before":{"track_id":"/track/a"},"after":{"track_id":"/track/b"},"dispatch":{"argv":["playerctl","-p","rhythmbox","next"],"rc":0},"verification":{"predicate":"track_identity_change_not_settled","settlement":settlement("/track/b",False)},"error":{"code":"operation_effect_not_settled"},"transaction":{"phase":"dispatch_started","dispatch_count":1,"idempotent_replay":False,"recovered_after_interruption":False,"external_execution_repeated":False},"mcp_wrapper":{"source_contract_ok":True}}


def recovery():
    return {"schema":"agent_bridge.app_control.v0","status":"verified","verdict":"verified","recover":"proceed","player":"rhythmbox","before":{"track_id":"/track/a"},"after":{"track_id":"/track/b"},"verification":{"predicate":"track_identity_changed_after_restart_settled","reason":None,"observation_error":None,"settlement":settlement("/track/b")},"transaction":{"dispatch_count":1,"recovered_after_interruption":True,"external_execution_repeated":False},"mcp_wrapper":{"source_contract_ok":True}}


def baseline_bundle():
    session="private-session"; digest="a"*64
    receipts=[
      {"tool":"app_control","payload":pending()},
      {"tool":"app_control","payload":recovery()},
      {"tool":"mobile_projection_start","payload":{"auto_connect":True,"confirmation_mode":"test_only_auto_connect","session_id":session}},
      {"tool":"mobile_projection_wait","payload":{"schema":"agent_bridge.mobile_projection_wait.v1","session_id":session,"status":"test_only_authenticated_connection_observed","verdict":"verified"}},
      {"tool":"mobile_projection_sync_media","payload":{"schema":"agent_bridge.mobile_projection_sync_media.v0","session_id":session,"status":"updated","app_control":{"player":"rhythmbox"},"media_context":{"track_id":"/track/b","title":"must not escape"},"projection_update":{"revision":2,"frame_sha256":digest}}},
      {"tool":"mobile_projection_wait","payload":{"schema":"agent_bridge.mobile_projection_wait.v1","session_id":session,"target_revision":2,"target_frame_sha256":digest,"verdict":"verified","exact_revision_and_digest_draw_reported":True,"draw_report":{"revision":2,"frame_sha256":digest},"claim_boundary":{"human_observed":False,"pixel_verified":False}}},
      {"tool":"mobile_projection_stop","payload":{"session_id":session,"listener_stop_requested":True,"adb_force_stop":{"exit_code":0}}},
    ]
    return {"schema":mod.INPUT_SCHEMA,"pair_id":"embodied-media-pair-03","side":"baseline","operation_id_sha256":"b"*64,"receipts":receipts,"metrics":{"owner_restatements":0,"manual_interventions":0,"failed_or_replanned_calls":0,"elapsed_ms":1000}}


def trial_bundle():
    b=baseline_bundle(); action=recovery(); action["source_contract_ok"]=True
    digest="c"*64; revision=2
    b["side"]="trial"; b["receipts"]=[b["receipts"][0],{"tool":"advance_track_then_project","payload":{"schema":"agent_bridge.advance_track_then_project.v0","verdict":"verified","recover":"proceed","last_completed_phase":"projection_stopped","steps":{"app_control":action,"wait":{"schema":"agent_bridge.mobile_projection_wait.v1","verdict":"verified","target_revision":revision,"target_frame_sha256":digest,"draw_report":{"revision":revision,"frame_sha256":digest},"claim_boundary":{"device_activity_draw_reported":True,"human_observed":False,"pixel_verified":False}}},"binding":{"player_exact_match":True,"track_exact_match":True,"projected_track_id":"/track/b","revision_and_digest_exact_match":True,"target_revision":revision,"target_frame_sha256":digest},"cleanup":{"attempted":True,"verified":True}}}]; return b


class CollectorTests(unittest.TestCase):
    def test_baseline_uses_versioned_flat_track_id_and_redacts_content(self):
        result=mod.collect(baseline_bundle())
        self.assertEqual(result["agent_orchestration_calls"],7)
        self.assertTrue(result["evidence"]["exact_draw_verified"])
        self.assertNotIn("must not escape",str(result))
        self.assertFalse(result["privacy"]["track_metadata_present"])

    def test_trial_accepts_only_two_call_composite(self):
        result=mod.collect(trial_bundle())
        self.assertEqual(result["agent_orchestration_calls"],2)

    def test_old_nested_track_path_is_rejected(self):
        b=baseline_bundle(); ctx=b["receipts"][4]["payload"]["media_context"]; ctx["track"]={"id":ctx.pop("track_id")}
        with self.assertRaisesRegex(mod.ContractError,"sync track_id"):
            mod.collect(b)

    def test_served_or_wrong_digest_never_proves_draw(self):
        for mutate in (lambda p:p.update(exact_revision_and_digest_draw_reported=False),lambda p:p["draw_report"].update(frame_sha256="d"*64)):
            b=baseline_bundle(); mutate(b["receipts"][5]["payload"])
            with self.assertRaises(mod.ContractError): mod.collect(b)

    def test_recovery_dispatch_or_repeat_is_rejected(self):
        for key,value in (("dispatch",{}),("external_execution_repeated",True)):
            b=baseline_bundle()
            target=b["receipts"][1]["payload"] if key=="dispatch" else b["receipts"][1]["payload"]["transaction"]
            target[key]=value
            with self.assertRaises(mod.ContractError): mod.collect(b)

    def test_type_confusion_and_extra_fields_are_rejected(self):
        for mutate in (lambda b:b["metrics"].update(elapsed_ms=True),lambda b:b.update(notes="secret")):
            b=baseline_bundle(); mutate(b)
            with self.assertRaises(mod.ContractError): mod.collect(b)

    def test_cleanup_is_mandatory(self):
        b=baseline_bundle(); b["receipts"][6]["payload"]["adb_force_stop"]["exit_code"]=1
        with self.assertRaisesRegex(mod.ContractError,"force-stop"): mod.collect(b)

    def test_output_never_grants_stronger_claims(self):
        result=mod.collect(baseline_bundle())
        self.assertTrue(all(value is False for value in result["claim_boundary"].values()))


if __name__ == "__main__": unittest.main()
