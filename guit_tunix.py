#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, GLib

import threading

from pulse_selector import PulseSelector
from tuner import Tuner
from audio_stream import AudioStream

class GuitTunixWin(Tuner, Gtk.ApplicationWindow):
    device = GObject.Property(type=str, default="")

    def __init__(self, app, device=""):
        super().__init__(application=app, device="")
        self.name = self.__class__.__name__
        self.set_title("Guit Tunix")
        self.set_default_size(400,100)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        self.set_child(vbox)

        self.pulse_sel = PulseSelector(search="")
        self.pulse_sel.connect("notify::device", self.on_device_changed)
        vbox.append(self.pulse_sel)

        self.device = self.pulse_sel.device

        self.note_label = Gtk.Label()
        self.note_label.set_markup("<span font='24'>E-A-D-G-B-E</span>")
        self.note_label.set_xalign(0.5)
        vbox.append(self.note_label)

        self.bar_label = Gtk.Label()
        self.bar_label.set_use_markup(True)
        self.bar_label.set_xalign(0.5)
        self.bar_label.set_selectable(True)
        self.bar_label.set_margin_bottom(40)
        vbox.append(self.bar_label)

        btn_close = Gtk.Button(label="Close")
        btn_close.set_hexpand(False)
        btn_close.connect("clicked", lambda b: self.close())
        vbox.append(btn_close)

        if self.device:
            # print(self.name, device)
            self.stream = AudioStream(device=self.device, callback=self.audio_callback)
        self.connect("map", self.on_map)
        threading.Thread(target=self.processing_thread, args=(self,), daemon=True).start()

    def on_map(self, widget):
        if self.stream:
            self.stream.start()

    def on_device_changed(self, pulse_sel, pspec):
        self.device = self.pulse_sel.device
        self.stream.set_device(self.device)
        # print(self.name, self.pulse_sel.device)
        with self.buf_lock:
            self.buffer[:] = 0.0
        self.noise_rms = 1e-8

    def rgb_for_diff(self, diff_hz, span):
        t = max(-1.0, min(1.0, diff_hz / span))
        if t <= -0.5:
            s = (t + 1.0) / 0.5
            r, g, b = 0, self.lerp(0, 255, s), 255
        elif t <= 0.0:
            s = (t + 0.5) / 0.5
            r, g, b = 0, 255, self.lerp(255, 0, s)
        elif t <= 0.5:
            s = (t - 0.0) / 0.5
            r, g, b = self.lerp(0, 255, s), 255, 0
        else:
            s = (t - 0.5) / 0.5
            r, g, b = 255, self.lerp(255, 0, s), 0
        return r, g, b

    def ansi_truecolor(self, r,g,b): return f"<span foreground='#{r:02x}{g:02x}{b:02x}'>"

    def freq_to_bar_pango(self, current, target):
        width=self.cfg['BAR_WIDTH']
        span=self.cfg['BAR_SPAN']
        low, high = target - span/2, target + span/2
        rng, center = high - low, width//2
        chars = []
        for i in range(width):
            pos_freq = low + (i/(width-1))*rng
            diff_pos = pos_freq - target
            r,g,b = self.rgb_for_diff(diff_pos, span/2)
            col = self.ansi_truecolor(r,g,b)
            ch = '◎' if i==center else '▢'
            chars.append(f"{col}{ch}</span>")
        cur_pos = int(round((current - low) / rng * (width - 1)))
        cur_pos = max(0, min(width - 1, cur_pos))
        cur_diff = current - target
        r,g,b = self.rgb_for_diff(cur_diff, span/2)
        cursor_col = self.ansi_truecolor(r,g,b)
        cursor_sym = '◉' if cur_pos==center else '▶' if cur_pos < center else '◀'
        chars[cur_pos] = f"{cursor_col}{cursor_sym}</span>"
        return ''.join(chars)
    
    def update_display(self, note, freq, offset, bar_markup):
        r,g,b = self.rgb_for_diff(offset, self.cfg['BAR_SPAN']/2)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self.note_label.set_markup(f"<span foreground='{color}' font='24'>{note}</span>")
        self.bar_label.set_markup(bar_markup)

if __name__ == "__main__":
    app = Gtk.Application(application_id="org.example.GuitTunix")

    def on_activate(app):
        win = GuitTunixWin(app)
        win.present()

    app.connect("activate", on_activate)
    app.run()

