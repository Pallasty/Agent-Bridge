# Xiao Shu focus-follow stage 8: paired production walks

Date: 2026-08-23

## Outcome

Dedicated eight-frame left-walk and right-walk atlases are accepted and runtime-bound. The focus-follow production asset contract is now **ready: 5 accepted / 0 missing / 0 rejected**. No focus-follow motion remains on the generic safe animation fallback.

No API key was used. The walk-cycle mother artwork was generated with Codex's logged-in built-in image generation capability.

## Image generation

Identity and motion reference:

`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-focus-follow-actions-v1-contact.png`

Selected mother source:

`/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-f1767e4a-801f-4f10-942f-ca7780ed9122.png`

Final prompt: preserve Xiao Shu v3's white bob and antenna curl, blue eyes, blue-white headset, coat, inner outfit, boots, chibi proportions, line quality, and palette. Draw exactly eight complete screen-left side-profile poses in one horizontal row on uniform `#FF00FF`. Use the cyclic sequence contact, down, passing, up, opposite contact, down, passing, up. Keep each character centered in its own equal cell, with alternating legs and arms, stable identity and scale, subtle vertical bounce, and loop continuity. Avoid running, jumping, front/right-facing poses, per-cell translation, shadows, guides, labels, text, extra limbs, fused legs, crop, and overlap.

The generated mother source passed structural visual review on the first candidate: exactly eight left-facing cells, readable alternating legs, low-energy gait, stable head/costume, and no forbidden scene elements.

## Deterministic pairing

The left walk is compiled normally. The right walk is generated from the same source through the compiler's per-frame `--flip-horizontal` path. This retains frame order while guaranteeing identical silhouette, headset, costume, timing, transparency, projected size, and baseline behavior in both directions.

## Accepted artifacts

- `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-left-v1-atlas.png`
- `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-right-v1-atlas.png`

Both assets:

- are 1536 x 208, 8-bit RGBA PNG;
- contain eight 192 x 208 cells in one row;
- contain 222959 transparent pixels;
- have 0 px baseline drift (contract maximum: 16 px);
- project to 123 px character height in every frame;
- have projected widths 51, 51, 51, 49, 50, 53, 51, 50 px;
- pass the executable asset contract with no failures.

## Runtime binding

`walk_left` and `walk_right` now resolve to the dedicated production atlases. Native playback recognizes these assets as eight-frame motions at 140 ms per frame. The sidecar HTTP route and native embedded asset decoder expose both files.

The action registry now reports:

- `concept_only: false`;
- dedicated turn atlases ready;
- dedicated walk atlases ready;
- dedicated wave atlas ready;
- `runtime_bound: true`.

Focus-follow remains disabled by default and retains explicit execute, confirmation, reason, travel bounds, focus-target stability, cancellation, pointer, keyboard, and application-focus guarantees.

## Completion boundary

The production motion-asset program is complete at 5/5. The next work should be behavioral validation rather than more asset production: one explicitly authorized live focus-follow traversal, observation of turn/walk/settle/wave transitions, and a bounded timing adjustment only if the desktop-scale motion appears too fast or too slow.
