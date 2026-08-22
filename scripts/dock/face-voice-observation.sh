#!/usr/bin/env bash
# Read-only, privacy-bounded summary of the sparse Avatar voice receipt log.
set -euo pipefail

receipt="${AB_FACE_VOICE_RECEIPT_LOG:-${XDG_RUNTIME_DIR:-/tmp/ab-face-$(id -u)}/ab-face-voice-receipts.jsonl}"
minimum_spoken="${AB_FACE_OBSERVATION_MIN_SPOKEN:-6}"
minimum_window_secs="${AB_FACE_OBSERVATION_MIN_WINDOW_SECS:-86400}"

if ! [[ "$minimum_spoken" =~ ^[1-9][0-9]*$ && "$minimum_window_secs" =~ ^[1-9][0-9]*$ ]]; then
  echo "observation thresholds must be positive integers" >&2
  exit 2
fi

files=()
[ -f "$receipt.1" ] && files+=("$receipt.1")
[ -f "$receipt" ] && files+=("$receipt")
if [ "${#files[@]}" -eq 0 ]; then
  jq -n --arg path "$receipt" '{
    schema:"agent_bridge.sparse_voice_observation.v1",
    read_only:true,
    receipt_path:$path,
    state:"no_evidence",
    total:0,
    recommendation:"continue_natural_observation"
  }'
  exit 0
fi

mode="$(stat -c '%a' "$receipt")"
jq -s \
  --arg path "$receipt" \
  --arg mode "$mode" \
  --argjson minimum_spoken "$minimum_spoken" \
  --argjson minimum_window_secs "$minimum_window_secs" '
  def tally($field):
    group_by(.[$field] // "unknown")
    | map({key:(.[0][$field] // "unknown"), value:length})
    | from_entries;
  def allowed_keys: [
    "schema", "ts", "status", "verify_status", "play_ok", "tier",
    "decision", "evidence_ids", "voice_line_id", "text_hash",
    "worker_protocol", "worker_engine", "qwen_device", "qwen_dtype",
    "playback_gain_db", "playback_peak_limit"
  ];
  sort_by(.ts // 0) as $rows
  | ($rows | map(select(.schema != "agent_bridge.sparse_voice_receipt.v1")) | length) as $invalid_schema
  | ($rows | map(keys - allowed_keys) | add // [] | unique) as $unexpected_keys
  | ($rows | map(select(.decision == "speak" and .play_ok == true)) | length) as $spoken
  | (($rows[-1].ts // 0) - ($rows[0].ts // 0)) as $window_secs
  | (($invalid_schema == 0) and ($unexpected_keys | length == 0) and ($mode == "600")) as $privacy_ok
  | (($spoken >= $minimum_spoken) and ($window_secs >= $minimum_window_secs)) as $sample_sufficient
  | {
      schema:"agent_bridge.sparse_voice_observation.v1",
      read_only:true,
      emits_audio:false,
      receipt_path:$path,
      receipt_mode:$mode,
      privacy_shape_ok:$privacy_ok,
      invalid_schema_count:$invalid_schema,
      unexpected_keys:$unexpected_keys,
      total:($rows|length),
      first_ts:($rows[0].ts // null),
      last_ts:($rows[-1].ts // null),
      observed_window_secs:$window_secs,
      by_status:($rows|tally("status")),
      by_decision:($rows|tally("decision")),
      successful_spoken_count:$spoken,
      thresholds:{minimum_spoken:$minimum_spoken, minimum_window_secs:$minimum_window_secs},
      sample_sufficient:$sample_sufficient,
      state:(if $privacy_ok|not then "invalid_receipt_boundary" elif $sample_sufficient then "review_ready" else "collecting" end),
      recommendation:(if $privacy_ok|not then "inspect_receipt_writer_before_using_results" elif $sample_sufficient then "review_frequency_and_failures_without_generalising_audibility" else "continue_natural_observation" end),
      not_verified:["physical audibility", "subjective audio quality", "future delivery"]
    }
  ' "${files[@]}"
