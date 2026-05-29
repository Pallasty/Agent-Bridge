#!/usr/bin/env python3
"""AT-SPI invoke acceptance toy (Linux Computer Use, forum thread 79).

A real Gtk.Button (not a DrawingArea) so it exposes an AT-SPI Action ("click").
Its "clicked" handler — which fires for BOTH a pointer click and an AT-SPI
Action.do_action invoke — records an activation to a JSON state file. This lets
run_invoke_accept.sh prove desktop_invoke activates the control via the a11y bus
with ZERO coordinates, in an isolated nested sway.
"""
import gi, json, os, time
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

STATE = os.path.expanduser("~/.cache/agent-bridge/cage_invoke_hit.json")
LABEL = "INVOKE_TARGET"


def write_state(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        json.dump(d, f)
    os.replace(STATE + ".tmp", STATE)


class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="invoke-toy")
        self.set_decorated(False)
        self.n = 0
        btn = Gtk.Button(label=LABEL)
        btn.get_accessible().set_name(LABEL)  # ensure AT-SPI name matches label
        btn.connect("clicked", self.on_click)
        box = Gtk.Box()
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.pack_start(btn, True, True, 0)
        self.add(box)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event",
                     lambda w, e: Gtk.main_quit() if e.keyval == 0xff51 else None)
        write_state({"phase": "ready", "label": LABEL, "activations": 0, "ts": time.time()})

    def on_click(self, btn):
        self.n += 1
        write_state({"phase": "activated", "label": LABEL,
                     "activations": self.n, "ts": time.time()})


if __name__ == "__main__":
    App().show_all()
    Gtk.main()
