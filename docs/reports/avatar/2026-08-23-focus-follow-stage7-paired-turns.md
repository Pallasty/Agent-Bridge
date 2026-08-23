# Xiao Shu focus-follow stage 7: paired production turns

Date: 2026-08-23

## Outcome

Dedicated six-frame left-turn and right-turn atlases are accepted and runtime-bound. The production asset contract advances from 1/5 to **3 accepted / 2 missing / 0 rejected**. Only the paired walk cycles remain on the safe fallback.

No API key was used. Source artwork was generated with Codex's logged-in built-in image generation capability.

## Image generation

Identity reference:

`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-focus-follow-actions-v1-contact.png`

Selected left-turn source:

`/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-70601c1e-d5a4-4478-8f8b-be52b5f9546a.png`

Rejected independent right-turn candidate:

`/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-57e9f7f1-d49d-4088-a7b8-e990eac146d8.png`

Prompt set: preserve Xiao Shu v3's chibi proportions, white bob and antenna curl, blue eyes, blue-white headset, coat, inner outfit, boots, line quality, and palette. Draw exactly six full-body poses in a single horizontal row on uniform `#FF00FF`: front, quarter-turn, profile, profile hold, quarter-turn return, front. Keep identical scale and one baseline; avoid locomotion, waving, shadows, guides, labels, text, extra limbs, crops, and overlap. The two calls differed only in the requested screen-left versus screen-right direction.

The independent right-turn candidate did not satisfy directional review: its profile still faced the same screen direction as the left-turn source. It was not compiled or admitted.

## Deterministic pairing

The compiler now supports `--flip-horizontal`, which mirrors pixels inside every frame cell without reversing frame order. The accepted left-turn source is therefore the single visual master for both directions:

- left turn: normal compilation;
- right turn: per-frame horizontal mirror.

This guarantees matching identity, silhouette, scale, timing, transparency, and baseline across both directions. It also avoids the costume and headset drift expected from independently generated counterparts.

## Accepted artifacts

- `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-left-v1-atlas.png`
- `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-right-v1-atlas.png`

Both assets:

- are 1152 x 208, 8-bit RGBA PNG;
- contain six frames in one row;
- contain 164424 transparent pixels;
- have 0 px baseline drift;
- project to 123 px character height in every frame;
- have projected widths 55, 55, 46, 46, 54, 55 px;
- pass the executable asset contract with no failures.

## Runtime binding

`turn_left` and `turn_right` now resolve to their dedicated assets in the focus-follow registry and native motion override. Native timing recognizes these atlases as six-frame motions even while the semantic renderer mode remains `orienting`. Both sidecar HTTP and native embedded-asset paths are covered.

Focus-follow remains disabled by default and preserves its existing confirmation, travel bound, cancellation, pointer, focus, and input guarantees.

## Next bounded stage

Generate one coherent eight-frame walk cycle, compile it normally for one direction and per-frame mirrored for the other, then validate controlled vertical motion against the 16 px baseline-drift contract. Bind both only if the pair passes together.
