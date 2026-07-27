#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import argparse
import datetime
import json
import re


SPEAKER_RE = re.compile(r"^[\"“”]?(?P<speaker>[^\n：:，,:]{2,12})[：:]\s*")
QUOTE_OPEN = ("\"", "“", "『", "《")
QUOTE_CLOSE = ("\"", "”", "』", "》")

EMOTION_KEYWORDS = {
    "happy": ["高兴", "开心", "笑", "欢", "喜", "欣慰", "激动"],
    "sad": ["悲", "难过", "伤心", "哭", "泪", "绝望", "哀"],
    "angry": ["怒", "恼", "生气", "愤", "怒火", "恨", "骂", "咆哮"],
    "tense": ["急", "紧张", "慌", "恐", "危险", "突发", "赶紧", "着急"],
    "calm": ["平静", "安静", "轻声", "轻轻", "慢慢", "缓缓"],
}


DEFAULT_CONFIG = {
    "voice_male": "male_standard",
    "voice_female": "female_standard",
    "voice_narrator": "narrator_calm",
    "voice_unknown": "narrator_calm",
    "tts_backend": "ab-tts",
    "segment_limit": 260,
    "plan_priority": "normal",
    "plan_retry_limit": 2,
    "plan_cooldown_ms": 100,
    "plan_backoff_ms": 400,
}


@dataclass(frozen=True)
class SpeakerDecision:
    speaker_id: str
    name: str
    gender: str
    confidence: float
    source: str
    raw_hint: str = ""
    fallback_reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EmotionDecision:
    label: str
    intensity: int
    confidence: float
    source: str
    raw_hint: str = ""
    fallback_reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Segment:
    segment_id: str
    chapter: int
    index: int
    text: str
    speaker: Dict[str, Any]
    emotion: Dict[str, Any]
    voice_profile: Dict[str, Any]
    status: str
    audio_plan: Dict[str, Any]
    fallbacks: List[str]
    debug: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "chapter": self.chapter,
            "index": self.index,
            "text": self.text,
            "speaker": self.speaker,
            "emotion": self.emotion,
            "voice_profile": self.voice_profile,
            "status": self.status,
            "audio_plan": self.audio_plan,
            "fallbacks": self.fallbacks,
            "debug": self.debug,
        }


def sha256_bytes(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha1(text.encode("utf-8")).hexdigest()


def split_paragraphs(text: str, limit: int = 260) -> List[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    cleaned: List[str] = []
    for p in parts:
        seg = p.strip()
        if not seg:
            continue
        if len(seg) > limit:
            cleaned.extend(_split_long_block(seg, limit))
        else:
            cleaned.append(seg)
    return cleaned


def _split_long_block(block: str, limit: int = 260) -> List[str]:
    items: List[str] = []
    cur = ""
    for piece in re.split(r"([。！？!?])", block):
        if not piece:
            continue
        cur += piece
        if len(cur) >= limit and piece in "。！？!?":
            piece = cur.strip()
            if piece:
                items.append(piece)
            cur = ""
    if cur.strip():
        items.append(cur.strip())
    return items or [block]


def infer_speaker_heuristic(text: str) -> SpeakerDecision:
    m = SPEAKER_RE.match(text)
    if m:
        speaker_name = m.group("speaker").strip("『「」\"“”").strip()
        return SpeakerDecision(
            speaker_id=f"spk_{speaker_name}",
            name=speaker_name,
            gender=_infer_gender_from_hint(speaker_name, explicit=True),
            confidence=0.78,
            source="heuristic:regex",
            raw_hint=speaker_name,
        )
    if any(ch in text for ch in QUOTE_OPEN) and any(ch in text for ch in QUOTE_CLOSE):
        return SpeakerDecision(
            speaker_id="spk_unknown",
            name="UNKNOWN",
            gender="unknown",
            confidence=0.24,
            source="heuristic:quoted",
            raw_hint="quoted-speech-pattern",
            fallback_reasons=("speaker_infer_fallback",),
        )
    return SpeakerDecision(
        speaker_id="spk_narrator",
        name="旁白",
        gender="narrator",
        confidence=0.88,
        source="heuristic:narrator-fallback",
    )


def _infer_gender_from_hint(name: str, explicit: bool = False) -> str:
    if re.search(r"(她|夫人|女士|小姐|女士|女)", name):
        return "female"
    if re.search(r"(他|先生|师兄|夫君|男士|男)", name):
        return "male"
    if explicit:
        return "unknown"
    return "unknown"


def infer_emotion_heuristic(text: str) -> EmotionDecision:
    scores = {label: 0 for label in EMOTION_KEYWORDS}
    for label, kws in EMOTION_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                scores[label] += 1
    label = "neutral"
    count = 0
    for k, c in scores.items():
        if c > count:
            label = k
            count = c
    confidence = 0.25 + 0.22 * min(count, 4)
    intensity = 2 if count >= 2 else 1
    if label == "neutral":
        confidence = 0.9
    fallback = () if (label != "neutral" and count > 0) else ("emotion_infer_fallback",)
    return EmotionDecision(
        label=label,
        intensity=intensity,
        confidence=min(confidence, 0.98),
        source="heuristic:keycount",
        fallback_reasons=fallback,
    )


def map_voice_profile(speaker: Dict[str, Any], emotion: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "backend": cfg.get("tts_backend", "ab-tts"),
        "speed": 1.0,
        "pause_ms": 260,
        "gain_db": 0.0,
        "pitch_shift": 0.0,
        "notes": "",
    }
    if speaker["gender"] == "female":
        profile["voice_key"] = cfg["voice_female"]
        profile["pitch_shift"] = 1.0
    elif speaker["gender"] == "male":
        profile["voice_key"] = cfg["voice_male"]
        profile["pitch_shift"] = -0.8
    elif speaker["gender"] == "narrator":
        profile["voice_key"] = cfg["voice_narrator"]
    else:
        profile["voice_key"] = cfg["voice_unknown"]

    if emotion["label"] == "happy":
        profile["speed"] = 1.1
        profile["pause_ms"] = 220
        profile["notes"] = "happy"
    elif emotion["label"] == "sad":
        profile["speed"] = 0.9
        profile["pause_ms"] = 300
        profile["gain_db"] = -1.0
        profile["notes"] = "sad"
    elif emotion["label"] == "angry":
        profile["speed"] = 1.06
        profile["gain_db"] = 1.5
        profile["notes"] = "angry"
    elif emotion["label"] == "tense":
        profile["speed"] = 1.12
        profile["pause_ms"] = 210
        profile["notes"] = "tense"
    elif emotion["label"] == "calm":
        profile["speed"] = 0.96
        profile["pause_ms"] = 300
        profile["notes"] = "calm"
    return profile


def build_audio_plan(segment_text: str, cfg: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    segment_hash = sha256_text(segment_text)
    output_file = output_dir / f"{segment_hash[:12]}.wav"
    duration = max(1.0, len(segment_text) / 10.8)
    return {
        "segment_hash": segment_hash,
        "output_file": str(output_file),
        "estimated_duration_sec": round(duration, 3),
        "cached": False,
    }


def _coerce_int(raw: Any) -> Optional[int]:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if raw.is_integer():
            return int(raw)
        return None
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            return None
    return None


def _add_issue(issues: Optional[Dict[Any, List[str]]], index: Any, message: str) -> None:
    if issues is None:
        return
    issues.setdefault(index, []).append(message)


def parse_annotations(raw: Any) -> tuple[Dict[int, Dict[str, Any]], Dict[Any, List[str]]]:
    if raw is None:
        return {}, {}

    if isinstance(raw, dict):
        if "segments" in raw and isinstance(raw["segments"], list):
            records = [r for r in raw["segments"] if isinstance(r, dict)]
        else:
            # dict keyed by segment index
            records = []
            for k, v in raw.items():
                row = {"index": k}
                if isinstance(v, dict):
                    row.update(v)
                records.append(row)
    elif isinstance(raw, list):
        records = [r for r in raw if isinstance(r, dict)]
    else:
        return {}, {"global": ["annotations_root_must_be_list_or_map"]}

    overrides: Dict[int, Dict[str, Any]] = {}
    issues: Dict[Any, List[str]] = {}
    for row in records:
        raw_idx = row.get("index")
        idx = _coerce_int(raw_idx)
        if idx is None or idx < 0:
            _add_issue(issues, -1, f"annotation_index_invalid:{raw_idx!r}")
            continue

        speaker_payload = row.get("speaker")
        emotion_payload = row.get("emotion")
        entry: Dict[str, Any] = {}

        hinted_speaker = _coerce_speaker_hint(
            speaker_payload if isinstance(speaker_payload, dict) else None,
            index=idx,
            issues=issues,
        )
        if hinted_speaker is not None:
            entry["speaker"] = speaker_payload

        hinted_emotion = _coerce_emotion_hint(
            emotion_payload if isinstance(emotion_payload, dict) else None,
            index=idx,
            issues=issues,
        )
        if hinted_emotion is not None:
            entry["emotion"] = emotion_payload

        if entry:
            overrides[idx] = entry
        else:
            _add_issue(issues, idx, "annotation_row_has_no_valid_fields")

    return overrides, issues


def _coerce_speaker_hint(
    raw: Optional[Dict[str, Any]],
    index: Optional[int] = None,
    issues: Optional[Dict[Any, List[str]]] = None,
) -> Optional[SpeakerDecision]:
    if not raw:
        _add_issue(issues, index if index is not None else -1, "speaker_missing_or_empty")
        return None

    sid = raw.get("id")
    if not isinstance(sid, str) or not sid.strip():
        _add_issue(issues, index if index is not None else -1, "speaker_id_missing_or_invalid")
        return None

    name = raw.get("name") or sid
    if not isinstance(name, str) or not name.strip():
        _add_issue(issues, index if index is not None else -1, "speaker_name_missing_or_invalid")
        return None

    gender = raw.get("gender")
    if gender not in {"male", "female", "narrator", "unknown"}:
        _add_issue(issues, index if index is not None else -1, f"speaker_gender_invalid:{gender!r}")
        gender = "unknown"

    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.6
    else:
        if confidence < 0 or confidence > 1:
            _add_issue(issues, index if index is not None else -1, "speaker_confidence_out_of_range")
            confidence = max(0.0, min(1.0, float(confidence)))

    if confidence < 0.65:
        _add_issue(issues, index if index is not None else -1, "speaker_confidence_below_threshold")

    source = raw.get("source", "agent-subagent")
    if not isinstance(source, str) or not source.strip():
        source = "agent-subagent"

    raw_hint = raw.get("raw_hint", "")
    if raw_hint is None:
        raw_hint = ""
    if not isinstance(raw_hint, str):
        _add_issue(issues, index if index is not None else -1, "speaker_raw_hint_invalid")
        raw_hint = str(raw_hint)

    return SpeakerDecision(
        speaker_id=sid,
        name=str(name),
        gender=gender,
        confidence=float(confidence),
        source=source,
        raw_hint=raw_hint,
        fallback_reasons=(),
    )


def _coerce_emotion_hint(
    raw: Optional[Dict[str, Any]],
    index: Optional[int] = None,
    issues: Optional[Dict[Any, List[str]]] = None,
) -> Optional[EmotionDecision]:
    if not raw:
        _add_issue(issues, index if index is not None else -1, "emotion_missing_or_empty")
        return None

    label = raw.get("label")
    if not isinstance(label, str):
        _add_issue(issues, index if index is not None else -1, "emotion_label_missing_or_invalid")
        return None
    if label not in {"neutral", "calm", "happy", "sad", "angry", "tense"}:
        _add_issue(issues, index if index is not None else -1, f"emotion_label_invalid:{label!r}")
        return None

    intensity = raw.get("intensity")
    if not isinstance(intensity, int) or intensity < 0 or intensity > 2:
        _add_issue(issues, index if index is not None else -1, f"emotion_intensity_invalid:{intensity!r}")
        intensity = 1

    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.62
    else:
        if confidence < 0 or confidence > 1:
            _add_issue(issues, index if index is not None else -1, "emotion_confidence_out_of_range")
            confidence = max(0.0, min(1.0, float(confidence)))

    if confidence < 0.65:
        _add_issue(issues, index if index is not None else -1, "emotion_confidence_below_threshold")

    source = raw.get("source", "agent-subagent")
    if not isinstance(source, str) or not source.strip():
        source = "agent-subagent"

    raw_hint = raw.get("raw_hint", "")
    if raw_hint is None:
        raw_hint = ""
    if not isinstance(raw_hint, str):
        _add_issue(issues, index if index is not None else -1, "emotion_raw_hint_invalid")
        raw_hint = str(raw_hint)

    return EmotionDecision(
        label=label,
        intensity=intensity,
        confidence=float(confidence),
        source=source,
        raw_hint=raw_hint,
        fallback_reasons=() if confidence >= 0.65 else ("emotion_infer_fallback",),
    )


def build_segments(
    text: str,
    cfg: Dict[str, Any],
    chapter: int = 1,
    annotation_map: Optional[Dict[int, Dict[str, Any]]] = None,
    annotation_issues: Optional[Dict[Any, List[str]]] = None,
) -> List[Dict[str, Any]]:
    items = split_paragraphs(text, limit=int(cfg.get("segment_limit", 260)))
    annotations = annotation_map or {}
    annotation_issues = annotation_issues or {}
    segments: List[Dict[str, Any]] = []

    for i, block in enumerate(items):
        speaker = infer_speaker_heuristic(block)
        emotion = infer_emotion_heuristic(block)
        block_fallbacks: List[str] = []

        ann = annotations.get(i)
        if ann:
            hinted_speaker = _coerce_speaker_hint(
                ann.get("speaker", {}),
                index=i,
                issues=annotation_issues,
            )
            hinted_emotion = _coerce_emotion_hint(
                ann.get("emotion", {}),
                index=i,
                issues=annotation_issues,
            )
            if hinted_speaker:
                speaker = hinted_speaker
            if hinted_emotion:
                emotion = hinted_emotion

        issues_for_segment = annotation_issues.get(i)
        if issues_for_segment:
            block_fallbacks.extend(f"annotation:{item}" for item in issues_for_segment)
        block_fallbacks.extend(speaker.fallback_reasons)
        block_fallbacks.extend(emotion.fallback_reasons)

        voice = map_voice_profile(
            {
                "gender": speaker.gender,
                "id": speaker.speaker_id,
                "name": speaker.name,
                "confidence": speaker.confidence,
            },
            {
                "label": emotion.label,
                "intensity": emotion.intensity,
                "confidence": emotion.confidence,
            },
            cfg,
        )

        status = "ready"
        if speaker.speaker_id == "spk_unknown" or speaker.confidence < 0.35:
            status = "needs_review"

        if not block.strip():
            status = "failed"
            block_fallbacks.append("segment_split_fallback")

        audio_plan = build_audio_plan(block, cfg, Path(cfg["output_dir"]))
        seg = Segment(
            segment_id=f"{chapter:03d}-{i:04d}-{audio_plan['segment_hash'][:6]}",
            chapter=chapter,
            index=i,
            text=block,
            speaker={
                "id": speaker.speaker_id,
                "name": speaker.name,
                "gender": speaker.gender,
                "confidence": round(speaker.confidence, 3),
            },
            emotion={
                "label": emotion.label,
                "intensity": emotion.intensity,
                "confidence": round(emotion.confidence, 3),
            },
            voice_profile=voice,
            status=status,
            audio_plan=audio_plan,
            fallbacks=list(dict.fromkeys(block_fallbacks)),
            debug={
                "speaker_source": speaker.source,
                "emotion_source": emotion.source,
                "raw_speaker_hint": speaker.raw_hint,
                "raw_emotion_hint": emotion.raw_hint,
                "error": "",
                "annotation_issues": annotation_issues.get(i, []),
            },
        )
        segments.append(seg.as_dict())
    return segments


def compute_manifest_version(v1: bool) -> str:
    return "novel_tts_embodied:v1.1" if v1 else "novel_tts_embodied:v0.1"


def build_manifest(
    segments: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    source_meta: Dict[str, Any],
    created_at_iso: str,
    version: str,
) -> Dict[str, Any]:
    fallback_segments = sum(1 for s in segments if any(bool(fb) for fb in s["fallbacks"]))
    needs_review = sum(1 for s in segments if s["status"] == "needs_review")
    failed_segments = sum(1 for s in segments if s["status"] == "failed")
    total_chars = sum(len(s["text"]) for s in segments)
    estimated = sum(float(s["audio_plan"]["estimated_duration_sec"]) for s in segments)
    return {
        "version": version,
        "created_at": created_at_iso,
        "input": source_meta,
        "config": {k: v for k, v in cfg.items() if k != "output_dir"},
        "segments_path": str(Path(cfg["output_dir"]) / "segments.jsonl"),
        "fallback_stats": {
            "fallback_segments": fallback_segments,
            "needs_review": needs_review,
            "failed_segments": failed_segments,
        },
        "segments": [s["segment_id"] for s in segments],
        "summary": {
            "segment_count": len(segments),
            "total_chars": total_chars,
            "estimated_total_sec": round(estimated, 3),
            "duration_sec": 0.0,
        },
        "notes": "fallback-first strategy active; low-confidence model outputs degrade to safer defaults",
    }


def _summarize_annotation_issues(annotation_issues: Dict[Any, List[str]], segment_count: int) -> Dict[str, Any]:
    if not annotation_issues:
        return {
            "count": 0,
            "global_count": 0,
            "row_count": 0,
            "rows": {},
        }

    global_count = len(annotation_issues.get("global", []))
    row_count = sum(
        1
        for idx, items in annotation_issues.items()
        if idx != "global" and isinstance(items, list) and items
    )
    normalized_rows: Dict[str, List[str]] = {}
    for idx, items in annotation_issues.items():
        if not items:
            continue
        if idx == "global":
            continue
        if isinstance(idx, int) and 0 <= idx < segment_count:
            normalized_rows[str(idx)] = items

    return {
        "count": sum(len(items) for items in annotation_issues.values() if isinstance(items, list)),
        "global_count": global_count,
        "row_count": row_count,
        "rows": normalized_rows,
    }


def build_replay_plan(segments: List[Dict[str, Any]], cfg: Dict[str, Any], task_id: str = "") -> List[Dict[str, Any]]:
    backend = cfg.get("tts_backend", "ab-tts")
    retry_limit = int(cfg.get("plan_retry_limit", 2))
    cooldown_ms = int(cfg.get("plan_cooldown_ms", 100))
    backoff_ms = int(cfg.get("plan_backoff_ms", 400))
    if retry_limit < 0:
        retry_limit = 0
    if cooldown_ms < 0:
        cooldown_ms = 0
    if backoff_ms < 0:
        backoff_ms = 100
    priority = str(cfg.get("plan_priority", "normal")) or "normal"

    plan = []
    for idx, seg in enumerate(segments, start=1):
        if seg["status"] == "failed":
            segment_status = "failed"
        else:
            segment_status = seg["status"]
        plan.append(
            {
                "task_id": task_id,
                "order": idx,
                "segment_id": seg["segment_id"],
                "tool": "present_voice",
                "priority": priority,
                "retry_policy": {
                    "retry_limit": retry_limit,
                    "cooldown_ms": cooldown_ms,
                    "backoff_ms": backoff_ms,
                },
                "tool_args": {
                    "backend": backend,
                    "text": seg["text"],
                    "voice": seg["voice_profile"]["voice_key"],
                    "speed": seg["voice_profile"]["speed"],
                    "pause_ms": seg["voice_profile"]["pause_ms"],
                    "gain_db": seg["voice_profile"]["gain_db"],
                    "pitch_shift": seg["voice_profile"]["pitch_shift"],
                    "output_file": seg["audio_plan"]["output_file"],
                    "segment_hash": seg["audio_plan"]["segment_hash"],
                    "estimated_duration_sec": seg["audio_plan"]["estimated_duration_sec"],
                },
                "segment_status": segment_status,
            }
        )
    return plan


def write_outputs(
    segments: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    out_dir: Path,
    make_plan: bool = True,
    task_id: str = "",
    dry_run: bool = False,
) -> Tuple[Path, Path, Optional[Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    segment_file = out_dir / "segments.jsonl"
    manifest_file = out_dir / "manifest.json"
    plan_file: Optional[Path] = None

    if dry_run:
        return segment_file, manifest_file, plan_file

    with segment_file.open("w", encoding="utf-8") as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False))
            f.write("\n")
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if make_plan:
        plan_file = out_dir / "embodiment_plan.jsonl"
        with plan_file.open("w", encoding="utf-8") as f:
            for row in build_replay_plan(segments, manifest.get("config", {}), task_id):
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")

    return segment_file, manifest_file, plan_file


def build_result_payload(
    segments: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    segment_file: Path,
    manifest_file: Path,
    plan_file: Optional[Path],
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    needs_review = [s for s in segments if s["status"] == "needs_review"]
    return {
        "status": "ok" if all(s["status"] != "failed" for s in segments) else "partial",
        "task_id": task_id,
        "manifest_path": str(manifest_file),
        "segments_path": str(segment_file),
        "replay_plan_path": str(plan_file) if plan_file else None,
        "segment_count": len(segments),
        "needs_review_count": len(needs_review),
        "needs_review_segments": [s["segment_id"] for s in needs_review],
        "summary": manifest["summary"],
    }


def build_input_meta(path: Optional[Path], text: str) -> Dict[str, Any]:
    if path is not None:
        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_bytes(path),
        }
    encoded = text.encode("utf-8")
    return {
        "path": "inline-text",
        "size_bytes": len(encoded),
        "sha256": sha1(encoded).hexdigest(),
    }


def _default_output_dir(text: str) -> Path:
    fallback = re.sub(r"\W+", "-", text[:16]).strip("-") or "novel-run"
    return Path(f"out/{fallback}")


def run_pipeline(
    text: str,
    output_dir: Path,
    *,
    config: Optional[Dict[str, Any]] = None,
    chapter: int = 1,
    source_path: Optional[Path] = None,
    task_id: Optional[str] = None,
    annotation_payload: Optional[Any] = None,
    emit_plan: bool = True,
    dry_run: bool = False,
    version: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Tuple[Path, Path, Optional[Path]]]:
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    cfg["output_dir"] = str(output_dir)
    annotations, annotation_issues = parse_annotations(annotation_payload)
    segments = build_segments(
        text=text,
        cfg=cfg,
        chapter=chapter,
        annotation_map=annotations,
        annotation_issues=annotation_issues,
    )
    annotation_issues_summary = _summarize_annotation_issues(annotation_issues, len(segments))
    source_meta = build_input_meta(source_path, text)
    manifest = build_manifest(
        segments=segments,
        cfg=cfg,
        source_meta=source_meta,
        created_at_iso=datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        version=version or compute_manifest_version(v1=True),
    )
    manifest["annotation_issues"] = {
        "summary": {
            "count": annotation_issues_summary["count"],
            "global_count": annotation_issues_summary["global_count"],
            "row_count": annotation_issues_summary["row_count"],
            "summary_text": (
                f"{annotation_issues_summary['count']} issues "
                f"(global={annotation_issues_summary['global_count']}, "
                f"rows={annotation_issues_summary['row_count']})"
            ),
        },
        "rows": annotation_issues_summary["rows"],
        "all": {str(k): v for k, v in annotation_issues.items() if isinstance(v, list) and v},
    }
    segment_file, manifest_file, plan_file = write_outputs(
        segments=segments,
        manifest=manifest,
        out_dir=output_dir,
        make_plan=emit_plan,
        task_id=task_id or "",
        dry_run=dry_run,
    )
    result_payload = build_result_payload(
        segments=segments,
        manifest=manifest,
        segment_file=segment_file,
        manifest_file=manifest_file,
        plan_file=plan_file,
        task_id=task_id,
    )
    result_payload["annotation_issues_summary"] = {
        "count": annotation_issues_summary["count"],
        "global_count": annotation_issues_summary["global_count"],
        "row_count": annotation_issues_summary["row_count"],
        "rows": annotation_issues_summary["rows"],
    }
    return segments, manifest, result_payload, (segment_file, manifest_file, plan_file)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="小说文本文件")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--voice-male", default=DEFAULT_CONFIG["voice_male"])
    parser.add_argument("--voice-female", default=DEFAULT_CONFIG["voice_female"])
    parser.add_argument("--voice-narrator", default=DEFAULT_CONFIG["voice_narrator"])
    parser.add_argument("--voice-unknown", default=DEFAULT_CONFIG["voice_unknown"])
    parser.add_argument("--tts-backend", default=DEFAULT_CONFIG["tts_backend"])
    parser.add_argument("--chapter", type=int, default=1)
    parser.add_argument("--segment-limit", type=int, default=DEFAULT_CONFIG["segment_limit"])
    parser.add_argument("--annotation-json", help="可选模型输出 JSON (segment-level speaker/emotion)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--emit-plan", action="store_true", default=True)
    parser.add_argument("--no-emit-plan", dest="emit_plan", action="store_false")
    return parser.parse_args(list(argv) if argv is not None else None)
