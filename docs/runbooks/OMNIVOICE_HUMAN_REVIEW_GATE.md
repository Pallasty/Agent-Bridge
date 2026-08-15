# OmniVoice human review admission

1. Complete both public blind-review sheets without opening their private answer
   keys.
2. Listen to the clone reference/candidate and long Chinese sample in the
   official perceptual packet.
3. Copy `docs/reports/tts-comparison/human-review-submission-template.json` to a
   new reviewer-owned file. Replace every sample `null` with an object containing
   integer scores for `intelligibility`, `naturalness`, `pronunciation`,
   `artifacts`, and `overall`, each from 1 through 5.
4. Fill reviewer, ISO-8601 review time, playback device, clone scores/confidence,
   and the long-Chinese boolean. Keep `synthetic` set to `false` only for a real
   listening session.
5. Run:

```bash
python3 scripts/omnivoice_human_review_gate.py \
  --policy config/omnivoice-human-review-policy.json \
  --submission /path/to/completed-review.json \
  --output /path/to/review-decision.json
```

Exit code 0 and `status=canary_eligible` permit preparation of a default-off
canary only. They never authorize a production-default change. Missing fields,
scores outside 1–5, candidate threshold failures, material Qwen regressions,
unapproved clone identity, and incorrect long Chinese pronunciation all hold the
route. Synthetic submissions can exercise the validator but never unlock it.
