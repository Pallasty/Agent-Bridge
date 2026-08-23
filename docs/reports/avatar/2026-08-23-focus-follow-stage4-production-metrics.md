# Xiao Shu focus-follow stage 4: production sprite metrics

Date: 2026-08-23

## Outcome

The sprite admission command now supports padded atlases and exposes the visual
metrics needed before a dedicated focus-follow action is bound:

- `--frame-count` validates only populated row-major cells;
- per-frame alpha bounds and visible-pixel counts;
- per-frame projected bounds at the deployed 90x130 viewport;
- baseline drift with a configurable hard limit.

The existing `xiao-shu-v3-ai-soft-bounce-v1-atlas.png` provides a positive RGBA
regression. Its first eight populated cells project to roughly 70-72 pixels wide
and 89-101 pixels high. The measured 14-pixel baseline range is intentional for
the bounce action, so its acceptance profile uses a 16-pixel limit. A restrained
wave atlas should use the stricter default 8-pixel limit.

## New candidate result

Built-in Codex image generation was asked to produce a direct transparent
six-frame wave strip, using the Xiao Shu v3 character sheet as the identity and
costume reference. The composition and action sequence were visually useful,
but the saved file was again an RGB checkerboard preview rather than RGBA:

`/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-fb0b94f6-349f-4783-8051-cf1832e8b9e9.png`

Audit result: rejected (`Rgb`, 2172x724; required `Rgba`, 1152x208). No generated
image was copied into the repository and no runtime action binding was changed.

## Production acceptance profiles

Wave/turn, six frames:

```text
agent-bridge avatar sprite-asset-audit --path candidate.png \
  --columns 6 --rows 1 --frame-count 6 \
  --cell-width 192 --cell-height 208 \
  --target-width 90 --target-height 130 \
  --max-baseline-drift-px 8 --json
```

Padded eight-frame atlas regression:

```text
agent-bridge avatar sprite-asset-audit --path atlas.png \
  --columns 8 --rows 9 --frame-count 8 \
  --cell-width 192 --cell-height 208 \
  --target-width 90 --target-height 130 \
  --max-baseline-drift-px 16 --json
```

## Verification

- `cargo test -p ab-bridge avatar_asset_audit --lib`: 3 tests passed
- `cargo check -p ab-bridge --bin agent-bridge`: passed
- generated RGB candidate: rejected as designed
- existing production RGBA atlas: metrics decoded for all eight populated cells

The next binding step remains closed until a dedicated wave, turn, or walk atlas
passes its action-specific profile.
