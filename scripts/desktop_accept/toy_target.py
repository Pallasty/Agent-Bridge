#!/usr/bin/env python3
"""Cage acceptance toy target (Linux Computer Use, forum thread 79).

A borderless GTK window whose DrawingArea fills the cage/nested-sway output. It
paints a known-position rectangular "button" labelled CLICK_TARGET with a
crosshair at its center, and records every click's window-local coordinates
plus hit/miss vs the button rect to a JSON state file. Window-local coords ==
output pixels (borderless, app fills the output), so they line up 1:1 with a
grim screenshot — letting run_accept.sh quantify landing accuracy of the
snapshot -> grounding -> desktop_action(moveto+click) loop in an isolated sway.
"""
import gi, json, os, time
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

STATE = os.path.expanduser("~/.cache/agent-bridge/cage_toy_hit.json")
# Button rect in window-local (== output pixel) coords. Ground truth target.
BX, BY, BW, BH = 600, 380, 140, 60
CX, CY = BX + BW // 2, BY + BH // 2  # target center -> (670, 410)


def write_state(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump(d, f)
    os.replace(STATE + ".tmp", STATE)


class App(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.clicks = 0
        da = Gtk.DrawingArea()
        self.add(da)
        da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        da.connect("draw", self.on_draw)
        da.connect("button-press-event", self.on_press)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event",
                     lambda w, e: Gtk.main_quit() if e.keyval == Gdk.KEY_q else None)
        write_state({"phase": "ready", "target_center": [CX, CY],
                     "button_rect": [BX, BY, BW, BH], "clicks": 0, "ts": time.time()})

    def on_draw(self, da, cr):
        cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.paint()
        cr.set_source_rgb(0.20, 0.55, 0.95)
        cr.rectangle(BX, BY, BW, BH)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Sans")
        cr.set_font_size(22)
        cr.move_to(BX + 8, BY + 38)
        cr.show_text("CLICK_TARGET")
        cr.set_source_rgb(1, 0.3, 0.3)
        cr.set_line_width(1)
        cr.move_to(CX - 14, CY); cr.line_to(CX + 14, CY)
        cr.move_to(CX, CY - 14); cr.line_to(CX, CY + 14)
        cr.stroke()
        return False

    def on_press(self, da, ev):
        self.clicks += 1
        x, y = int(ev.x), int(ev.y)
        in_btn = (BX <= x <= BX + BW) and (BY <= y <= BY + BH)
        dist = ((x - CX) ** 2 + (y - CY) ** 2) ** 0.5
        write_state({"phase": "clicked", "click": [x, y], "target_center": [CX, CY],
                     "button_rect": [BX, BY, BW, BH], "in_button": in_btn,
                     "dist_to_center": round(dist, 1), "clicks": self.clicks,
                     "ts": time.time()})
        return True


if __name__ == "__main__":
    App().show_all()
    Gtk.main()
