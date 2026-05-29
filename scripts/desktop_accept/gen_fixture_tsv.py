#!/usr/bin/env python3
"""Generate a tesseract-format TSV for the cage grounding e2e (forum thread 79).

The cage toy (toy_target.py) draws the literal text "CLICK_TARGET" on its button
with cairo (Sans 22) at baseline origin (BX+8, BY+38). A *real* OCR pass would
return that text's ink bounding box. Here we measure that exact box with the
SAME cairo font metrics the toy renders with — so the fixture is the
ground-truth box a perfect OCR would emit, NOT a hand-picked coordinate. This
keeps the e2e honest: it exercises the real OCR->bbox->center->click->hit
pipeline, with only tesseract's *recognition accuracy* (blocked on the apt
install) swapped for a metrically-exact stand-in.

Emits tesseract `--psm 6 tsv`-shaped columns. vision_grounding_ocr.py reads
left/top/width/height/conf/text and computes center = bbox center.

A decoy row ("status_label" top-left) is included so --hint-text must actually
select CLICK_TARGET among candidates rather than trivially picking the only row.
"""
from __future__ import annotations

import sys

# --- MUST mirror toy_target.py constants ---
BX, BY, BW, BH = 600, 380, 140, 60
TEXT = "CLICK_TARGET"
FONT = "Sans"
FONT_SIZE = 22
TEXT_ORIGIN_X = BX + 8   # cairo move_to x (baseline origin), matches toy
TEXT_ORIGIN_Y = BY + 38  # cairo move_to y (baseline origin), matches toy

TSV_HEADER = [
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
]


def measure_ink_bbox() -> tuple[int, int, int, int]:
    """Return (left, top, width, height) of TEXT as the toy renders it."""
    import cairo  # pycairo; ships with GTK3 python stacks the toy depends on

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1280, 800)
    cr = cairo.Context(surf)
    cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(FONT_SIZE)
    ext = cr.text_extents(TEXT)  # x_bearing, y_bearing, width, height, x_adv, y_adv
    left = int(round(TEXT_ORIGIN_X + ext.x_bearing))
    top = int(round(TEXT_ORIGIN_Y + ext.y_bearing))
    width = int(round(ext.width))
    height = int(round(ext.height))
    return left, top, width, height


def row(level, text, left, top, w, h, conf):
    return "\t".join(str(v) for v in
                     [level, 1, 1, 1, 1, 1, left, top, w, h, conf, text])


def main() -> int:
    try:
        left, top, w, h = measure_ink_bbox()
    except Exception as exc:  # pragma: no cover - environment-specific
        print(f"# ERROR measuring text extents: {exc}", file=sys.stderr)
        return 3
    lines = ["\t".join(TSV_HEADER)]
    # decoy first so selection (not position) must do the work
    lines.append(row(5, "status_label", 12, 10, 120, 20, 95))
    lines.append(row(5, TEXT, left, top, w, h, 96))
    sys.stdout.write("\n".join(lines) + "\n")
    # ground-truth center to stderr for the runner's record (not parsed)
    print(f"# {TEXT} ink bbox=({left},{top},{w},{h}) center=({left + w // 2},{top + h // 2})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
