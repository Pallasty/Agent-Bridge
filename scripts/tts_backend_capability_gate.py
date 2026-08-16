#!/usr/bin/env python3
"""Fail-closed backend selection from an explicit TTS capability request."""

import argparse
import json
from pathlib import Path


ALIASES = {"zh": "chinese", "en": "english"}


def evaluate(spec, *, language, speaker=None, instruction=None, reference_audio=None,
             reference_text=None, require_production=False):
    language = ALIASES.get(language.lower(), language.lower())
    if bool(reference_audio) != bool(reference_text):
        raise ValueError("reference_audio and reference_text must be supplied together")
    decisions = {}
    for name, capability in spec["backends"].items():
        blockers = []
        if language not in capability["languages"]:
            blockers.append("language_unsupported")
        elif language not in capability["verified_languages"]:
            blockers.append("language_not_locally_verified")
        if speaker and speaker.lower() not in capability["named_speakers"]:
            blockers.append("named_speaker_unsupported")
        if instruction and not capability["natural_language_instruction"]:
            blockers.append("instruction_unsupported")
        if reference_audio and not capability["reference_voice_clone"]:
            blockers.append("reference_clone_unsupported")
        if reference_audio and not capability.get("clone_identity_human_approved", True):
            blockers.append("clone_identity_not_human_approved")
        if require_production and not capability["production_default"]:
            blockers.append("not_production_approved")
        decisions[name] = {"eligible": not blockers, "blockers": blockers}
    eligible = [name for name, row in decisions.items() if row["eligible"]]
    return {
        "schema": "agent_bridge.tts_backend_capability_decision.v0",
        "request": {"language": language, "speaker": speaker,
                    "instruction_requested": bool(instruction),
                    "reference_clone_requested": bool(reference_audio),
                    "require_production": require_production},
        "eligible_backends": eligible,
        "decisions": decisions,
        "route": eligible[0] if len(eligible) == 1 else None,
        "status": "eligible" if eligible else "blocked_no_compatible_backend",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capabilities", type=Path,
                    default=Path(__file__).parents[1] / "config/tts-backend-capabilities.json")
    ap.add_argument("--language", required=True)
    ap.add_argument("--speaker")
    ap.add_argument("--instruction")
    ap.add_argument("--reference-audio")
    ap.add_argument("--reference-text")
    ap.add_argument("--require-production", action="store_true")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = evaluate(json.loads(args.capabilities.read_text()), language=args.language,
                      speaker=args.speaker, instruction=args.instruction,
                      reference_audio=args.reference_audio, reference_text=args.reference_text,
                      require_production=args.require_production)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if result["eligible_backends"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
