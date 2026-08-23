# Xiao Shu focus-follow asset contract v1

This contract defines the five dedicated motion atlases that replace the safe
fallback animations only after every file passes executable admission.

Common requirements:

- genuine 8-bit RGBA PNG, with alpha-zero background pixels;
- 192x208 cells, one populated row, no padding outside the declared grid;
- full Xiao Shu v3 identity and costume; one full body per cell;
- stable scale, no crop, shadow, text, checkerboard, guide, or motion trail;
- readable when projected into the deployed 90x130 Avatar viewport.

| Action | File | Frames | Sequence | Baseline limit |
| --- | --- | ---: | --- | ---: |
| wave | `xiao-shu-v3-focus-wave-v1-atlas.png` | 6 | neutral, raise, out, in, out, settle | 8 px |
| turn left | `xiao-shu-v3-focus-turn-left-v1-atlas.png` | 6 | front, quarter, profile, hold, quarter, front | 8 px |
| turn right | `xiao-shu-v3-focus-turn-right-v1-atlas.png` | 6 | front, quarter, profile, hold, quarter, front | 8 px |
| walk left | `xiao-shu-v3-focus-walk-left-v1-atlas.png` | 8 | contact, down, passing, up, repeated | 16 px |
| walk right | `xiao-shu-v3-focus-walk-right-v1-atlas.png` | 8 | contact, down, passing, up, repeated | 16 px |

The CLI is the source of truth:

```text
agent-bridge avatar sprite-asset-contract --json
```

It reports each exact path as `missing`, `rejected`, or `accepted`, embeds the
full per-frame audit for present files, and sets `ready=true` only when all five
assets pass. Runtime binding remains a separate reviewed change after readiness.

## Transparent CLI generation path

The approved Image API fallback uses `gpt-image-1.5`, because `gpt-image-2`
does not expose native transparent output. The environment must provide
`OPENAI_API_KEY`; the key must never be written into this repository or pasted
into a report.

Prompt invariant for every atlas:

```text
Use case: stylized-concept. Production desktop Avatar sprite atlas. Strictly
preserve the supplied Xiao Shu v3 identity, white bob haircut and antenna curl,
blue eyes, blue-white headphones, coat, inner outfit and boots. Use the exact
action-specific frame sequence from this contract, equal 192x208 conceptual
cells, identical scale and baseline, one full body per cell. Genuine transparent
background. No checkerboard, floor, shadow, labels, borders, cropping, duplicate
limbs, extra objects, glow, or motion trails.
```

API output still must pass the executable contract; model declarations are not
accepted as evidence of alpha or geometry.
