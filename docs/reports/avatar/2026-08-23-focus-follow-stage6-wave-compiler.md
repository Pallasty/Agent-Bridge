# Xiao Shu focus-follow stage 6: production wave atlas

Date: 2026-08-23

## Outcome

The first dedicated focus-follow production motion is now accepted and runtime-bound. Xiao Shu plays a six-frame wave after the bounded arrival-settle motion. The production contract is now **1 accepted / 4 missing / 0 rejected**; turn-left, turn-right, walk-left, and walk-right remain intentionally unbound.

No API key was used. The source artwork was created through Codex's logged-in built-in image generation capability, then compiled locally into the deterministic runtime contract.

## Source artwork

- Built-in image output: `/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-c9a3fa20-1fbe-4b4c-85c5-02ecf9296900.png`
- Source dimensions: 1672 x 941, RGB
- Use case: stylized concept source for a production sprite atlas
- Prompt intent: preserve Xiao Shu v3 identity; draw six sequential wave poses on a uniform `#FF00FF` background; sequence `neutral / raise / out / in / out / settle`; equal cells, stable character scale and baseline; no shadow, text, labels, border, or checkerboard.

The generator is used for visual authorship. It is not treated as a pixel-contract compiler: generated dimensions and color mode are allowed to vary and must pass through the deterministic compiler and audit before runtime binding.

## Deterministic compiler

The new `avatar sprite-asset-compile` command:

- defaults to a read-only preview;
- requires both `--execute` and `--confirm` before writing;
- refuses to overwrite an existing output;
- extracts a saturated-magenta chroma background into alpha;
- replaces partial-alpha fringe colors with the nearest opaque subject color;
- partitions the source into declared frames;
- scales with premultiplied bilinear sampling;
- centers every frame in a 192 x 208 cell on a shared baseline;
- writes an 8-bit RGBA PNG.

Two intermediate edge treatments were rejected during visual inspection: the first retained a purple fringe, and the second produced a cyan fringe. The selected third treatment removes both visible chroma halos. Discarded candidates are not production artifacts.

## Accepted artifact

- Runtime asset: `crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-focus-wave-v1-atlas.png`
- Asset id: `xiao-shu-v3-focus-wave-v1`
- Dimensions: 1152 x 208
- Format: 8-bit RGBA PNG
- Frames: 6 in one row
- Transparent pixels: 165146
- Visible pixels per frame: 12590, 12369, 12506, 12140, 12401, 12464
- Baseline drift: 0 px (contract maximum: 8 px)
- Projected frame bounds at the 90 x 130 Avatar target: widths 46-53 px, height 123 px
- Audit result: accepted, no failures

## Runtime behavior

The sidecar HTTP route and native renderer both embed and decode the production atlas. Focus-follow now declares the terminal sequence as:

1. `arriving` -> `arrive_settle`
2. `acknowledging` -> `wave`
3. `completed` -> `idle_breathe`

The wave lasts 960 ms after a 520 ms arrival settle. Pointer position, application focus, and keyboard input remain untouched. Focus-follow remains disabled by default and still requires explicit execute, confirmation, and operator reason.

## Verification

- Sprite compiler unit test: passed
- Focus-follow integration tests: 7 passed
- Native wave decode test: passed
- Full `agent-bridge` binary check: passed
- Production asset contract: 1 accepted, 4 missing, 0 rejected

Repository-wide pre-existing compiler warnings remain unchanged and are outside this stage.

## Next bounded stage

Use the same built-in-imagegen-plus-compiler pipeline for paired turn atlases. Review left/right consistency together before binding either direction, then proceed to the two eight-frame walk cycles. Until an atlas passes the existing contract, the current alpha-ready fallback remains active.
