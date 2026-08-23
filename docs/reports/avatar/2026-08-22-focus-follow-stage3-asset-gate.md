# Xiao Shu focus-follow stage 3: sprite admission gate

Date: 2026-08-22

## Outcome

The focus-follow runtime keeps its verified fallback atlases. A newly generated
six-frame wave candidate was not admitted because both the source and the
background-removal result were RGB images, and the latter baked a checkerboard
into the pixels. It also used a 1672x941 canvas instead of the required
1152x208 six-cell atlas.

The CLI now exposes a fail-closed admission check:

```text
agent-bridge avatar sprite-asset-audit \
  --path candidate.png --columns 6 --rows 1 \
  --cell-width 192 --cell-height 208 --json
```

Admission requires all of the following:

- PNG color type is genuine 8-bit RGBA;
- canvas dimensions exactly equal the declared cell grid;
- at least one fully transparent pixel exists;
- every declared frame contains visible pixels.

Rejected candidates exit non-zero and cannot be mistaken for production-ready
assets. The next art pass should generate wave, turn, and walk atlases against
this executable contract before any runtime binding changes.

## Generation evidence

- Model/tool: built-in Codex image generation tool
- Source prompt: six sequential Xiao Shu wave frames on uniform `#FF00FF`
  chroma background, preserving the v3 character-sheet identity
- Source output:
  `/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-c9a3fa20-1fbe-4b4c-85c5-02ecf9296900.png`
- Edit prompt: remove only the chroma background and emit genuine RGBA
  transparency without redrawing or resizing
- Edit output:
  `/home/pallasting/.codex/generated_images/01a02a8b-1e0f-7491-b409-aff5a46ad74b/exec-622113ed-918c-44c3-b9b7-48df5a57f9ab.png`
- Audit result: rejected (`Rgb`, 1672x941; expected `Rgba`, 1152x208)

No generated image was copied into the repository.

## Verification

- `cargo test -p ab-bridge avatar_asset_audit --lib`: 2 passed
- `cargo check -p ab-bridge --bin agent-bridge`: passed
- Rejected candidate CLI probe: non-zero as designed, with both format and
  geometry failures reported

The `linux-native-avatar` test variant could not run on this host because the
system `xkbcommon.pc` development metadata is unavailable. This does not affect
the platform-independent PNG admission module or the normal binary check.
