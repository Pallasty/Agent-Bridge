# Xiao Shu v3 Visual Baseline

Date: 2026-05-26
Status: accepted `alert_peek` visual-motion candidate, sidecar-only
Reference asset: `docs/design/assets/xiao-shu-v3-baseline-infographic-20260526.png`
Character sheet candidate:
`docs/design/assets/xiao-shu-v3-character-sheet-20260526.png`
Sidecar alert_peek sheet-derived candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-alert-peek-sheet-v1-atlas.png`
Sidecar alert_peek AI-frame candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-atlas.png`
Sidecar alert_peek AI-frame cleanup candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v2-atlas.png`
Sidecar alert_peek AI-frame chroma cleanup candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v3-atlas.png`
Sidecar idle_breathe AI-frame candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-idle-breathe-v1-atlas.png`
Sidecar soft_bounce AI-frame candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-soft-bounce-v1-atlas.png`
Sidecar completion_nod AI-frame candidate:
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-atlas.png`

## Decision

Adopt the newly generated blue-white Xiao Shu illustration as the `xiao-shu-v3`
visual direction candidate.

This does not replace `xiao-shu-dev`, mutate the official Codex Pet package, or
promote renderer bindings. The next step is to derive a clean character sheet and
animation-frame candidate from this baseline, then review it through the existing
sidecar renderer path.

## Current Review Assets

- Baseline infographic:
  `docs/design/assets/xiao-shu-v3-baseline-infographic-20260526.png`
- First character sheet candidate:
  `docs/design/assets/xiao-shu-v3-character-sheet-20260526.png`
- First sidecar alert_peek atlas candidate:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-alert-peek-sheet-v1-atlas.png`
- Human-readable contact sheet for that atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-alert-peek-sheet-v1-contact.png`
- First coherent v3 AI-frame alert_peek atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-atlas.png`
- Human-readable contact sheet for the AI-frame atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-contact.png`
- Original generated chroma-key source for the AI-frame atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-source.png`
- Edge-cleaned v3 AI-frame alert_peek atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v2-atlas.png`
- Human-readable contact sheet for the edge-cleaned atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v2-contact.png`
- Chroma-fringe-cleaned v3 AI-frame alert_peek atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v3-atlas.png`
- Human-readable contact sheet for the chroma-fringe-cleaned atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v3-contact.png`
- First v3 AI-frame idle_breathe atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-idle-breathe-v1-atlas.png`
- Human-readable contact sheet for the idle_breathe atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-idle-breathe-v1-contact.png`
- First v3 AI-frame soft_bounce atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-soft-bounce-v1-atlas.png`
- Human-readable contact sheet for the soft_bounce atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-soft-bounce-v1-contact.png`
- Anchored v3 AI-frame completion_nod atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-atlas.png`
- Human-readable contact sheet for the completion_nod atlas:
  `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-contact.png`

The character sheet is a design reference, not a spritesheet. It is useful for
locking the face, body thickness, headset, grounded boots, and initial motion
language before deriving transparent animation frames.

The first `alert_peek` atlas is intentionally labeled `sheet_v1`: it crops and
stages poses from the character sheet so the renderer can test v3 identity,
scale, and staging. It is not the final motion source and should not be treated
as an approved animation pass.

The first coherent AI-frame candidate is exposed as `sidecar_v3_ai_peek_v1`.
Unlike `sheet_v1`, it is a single continuous motion: low peek, rise, hand lift,
attention hold, blink, and return. Human desktop review on 2026-05-26 accepted
the action, character consistency, and expression quality as good enough for the
v3 `alert_peek` baseline. It should still not become a binding default without
a separate promotion decision.

The follow-up cleanup pass is exposed as `sidecar_v3_ai_peek_v2`. It preserves
the accepted v1 frame order and timings, then removes faint alpha fringe and
tiny extraction specks so the sidecar renderer has a cleaner reference for
future matching motion strips. It is a comparison candidate, not a replacement
decision by itself.

The second cleanup pass is exposed as `sidecar_v3_ai_peek_v3`. It targets the
remaining green chroma-key residue near hair tips by removing low-alpha green
boundary pixels and neutralizing dense green-cast outline pixels. This keeps the
same motion timing as v1/v2 and exists for direct visual comparison.

The first quiet-state pass is exposed as `sidecar_v3_idle_breathe_v1`. It reuses
the accepted v3 identity and chroma-cleaned pixels, then derives a six-frame
low-amplitude breathing loop with one blink. It is intentionally not default:
human desktop review on 2026-05-26 accepted the direction as good enough for the
v3 quiet-presence baseline candidate. It still should not become a binding
default without a separate promotion decision.

The first completion-state pass is exposed as `sidecar_v3_soft_bounce_v1`. It
derives an eight-frame low-amplitude bounce from the accepted v3 idle identity:
idle, compress, lift, apex, float, descend, settle-blink, and return. It avoids
detached success effects so the motion can stay usable in a compact desktop
panel.

Human review rejected the half-body bounce language for this shape because a
head-and-hands crop reads as "the head is jumping" rather than a whole-person
action. The replacement completion-state candidate is exposed as
`sidecar_v3_completion_nod_v1`. It keeps the lower body, hands, and bottom bbox
anchored, then uses only a small face-level nod, blink, smile, and attached
antenna glint to say "received" or "done". This establishes the v3 animation
rule that jumping belongs to full-body sprites only; half-body assistant states
should use expression, eye, hand, and head-tilt cues.

## Why This Direction

The candidate reads better than the current sidecar prototype at small and medium
sizes:

- Clearer face and eye silhouette.
- Friendlier proportions without becoming a toy mascot.
- Stronger blue-white assistant identity.
- More stable body thickness for future frame animation.
- Better fit for Chinese sparse voice and operator-console surfaces.

## Identity Cues

The next image and sprite work should preserve these cues:

- Soft white hair with a small upward curl.
- Large blue eyes, open and attentive.
- Compact chibi assistant body, not too thin or flat.
- Blue-white hooded coat or robe with clean trim.
- Small headset, antenna, or signal accessory.
- Rounded sleeves and small grounded boots.
- Cheerful, capable, warm expression.
- "Quietly helpful" rather than loud, alarmed, or decorative.

## Safety Boundary

All v3 work stays behind the current Avatar sidecar boundary:

- No official Codex Pet package mutation.
- No direct replacement of `xiao-shu-dev`.
- No automatic audio emission.
- No HTTP emit route.
- No direct LLM control of Xiao Shu.
- No binding promotion until a separate explicit review decision.

## Sprite Target

If v3 proceeds to a Codex-compatible pet candidate, use the existing atlas
contract:

- Atlas: `1536x1872`.
- Cell: `192x208`.
- Grid: 8 columns x 9 rows = 72 cells.
- Transparent PNG source.
- Feet remain grounded on a stable baseline.
- Head, torso, and boots keep consistent scale across frames.
- First and last frames of loops return to an idle-compatible pose.

## Initial Motion Set

The first v3 animation pass should focus on these sidecar-only tracks:

- `idle_breathe`: quiet presence.
- `soft_bounce`: caught-up / small success.
- `alert_peek`: attention request with raised hand.
- `sorting_glow`: processing / organizing signal.
- `look_sideways`: inspection / mismatch.
- `waiting_for_user`: gentle hold state.

## Review Gates

Promote only after these gates pass:

1. Character sheet review: front pose plus 3-5 expression/pose thumbnails.
2. Motion-key review: `alert_peek` has real hand, face, and body-frame change.
3. Sidecar render review: browser view is nonblank and readable at panel size.
4. Voice-link review: sparse Chinese line matches the visual intent.
5. Safety review: output remains sidecar-only and local-confirmed.

## Immediate Task Queue

1. Done: generate a clean `xiao-shu-v3` character reference sheet from the
   baseline.
2. Done: derive a small `alert_peek` keyframe strip from that sheet.
3. Done: add a sidecar-only v3 review asset and route variant
   `sidecar_v3_peek_sheet_v1`.
4. Done: generate a coherent v3 AI-frame `alert_peek` sequence and expose it as
   `sidecar_v3_ai_peek_v1`.
5. Done: browser visual QA and human review accepted
   `sidecar_v3_ai_peek_v1` as the v3 `alert_peek` visual-motion baseline.
6. Done: add edge-cleaned comparison variant `sidecar_v3_ai_peek_v2`.
7. Done: add chroma-fringe cleanup comparison variant `sidecar_v3_ai_peek_v3`.
8. Done: derive matching v3 `idle_breathe` and expose it as
   `sidecar_v3_idle_breathe_v1`.
9. Done: human review accepted `sidecar_v3_idle_breathe_v1` as the v3
   quiet-presence baseline candidate.
10. Done: derive matching v3 `soft_bounce` and expose it as
   `sidecar_v3_soft_bounce_v1`.
11. Done: human review rejected half-body jump semantics; add anchored
    completion acknowledgement `sidecar_v3_completion_nod_v1`.
12. Next: derive matching v3 `sorting_glow` and `focused_review` motion strips
   before any package or binding promotion.
