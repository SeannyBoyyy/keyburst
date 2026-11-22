"""KeyBurst: hotkey spam clicker with per-key speed."""
import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

import keyboard

from engine import MIN_INTERVAL_MS, Clicker



def config_path():
    """Settings live in %APPDATA%\\KeyBurst so they survive when run as an .exe."""
    folder = Path(os.environ.get("APPDATA") or Path.home()) / "KeyBurst"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return folder / "config.json"


CONFIG_PATH = config_path()
MAX_ROWS = 12
MAX_CPS = 1000 // MIN_INTERVAL_MS  # 50 clicks per second
MIN_CPS = 0.5
DEFAULT_CONFIG = {
    "toggle_hotkey": "f6",
    "entries": [
        {"key": "1", "cps": 10, "enabled": True},
        {"key": "3", "cps": 10, "enabled": True},
        {"key": "4", "cps": 10, "enabled": True},
        {"key": "5", "cps": 10, "enabled": True},
    ],
}

BG = "#14161a"
CARD = "#1e2127"
FIELD = "#2a2f38"
FIELD_HOVER = "#363c47"
TEXT = "#e8eaed"
MUTED = "#8b929c"
ACCENT = "#4f8cff"
GREEN = "#2ea043"
GREEN_HOVER = "#3fb950"
RED = "#e5484d"
RED_HOVER = "#f0565b"
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_S = ("Segoe UI", 9)


def load_config():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data.get("entries"), list) and data.get("toggle_hotkey"):
            for e in data["entries"]:  # upgrade old configs saved in ms
                if "cps" not in e:
                    e["cps"] = round(1000 / max(MIN_INTERVAL_MS, e.get("interval_ms", 100)), 1)
            # start/stop is a single key now: keep only the last part of a combo
            data["toggle_hotkey"] = data["toggle_hotkey"].split("+")[-1] or "f6"
            return data
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_CONFIG))


def read_one_key():
    """Block until one key is pressed and return its name."""
    while True:
        ev = keyboard.read_event()
        if ev.event_type == "down":
            return ev.name


def hover(widget, normal, over):
    widget.bind("<Enter>", lambda e: widget.config(bg=over))
    widget.bind("<Leave>", lambda e: widget.config(bg=normal))


def flat_button(parent, text="", command=None, bg=FIELD, over=FIELD_HOVER,
                fg=TEXT, font=FONT_B, width=None, padx=10, pady=4):
    b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                  activebackground=over, activeforeground=fg, relief="flat",
                  bd=0, font=font, cursor="hand2", padx=padx, pady=pady)
    if width:
        b.config(width=width)
    hover(b, bg, over)
    return b


def make_card(parent, title, hint):
    card = tk.Frame(parent, bg=CARD, padx=14, pady=12)
    card.pack(fill="x", pady=(0, 12))
    tk.Label(card, text=title, font=("Segoe UI", 11, "bold"), bg=CARD,
             fg=TEXT).pack(anchor="w")
    tk.Label(card, text=hint, font=FONT_S, bg=CARD, fg=MUTED).pack(anchor="w", pady=(0, 8))
    body = tk.Frame(card, bg=CARD)
    body.pack(fill="x")
    return body


class Row:
    def __init__(self, app, parent, data):
        self.app = app
        self.frame = tk.Frame(parent, bg=CARD)
        self.enabled = tk.BooleanVar(value=data.get("enabled", True))
        self.key = tk.StringVar(value=data.get("key", "1"))
        self.label = tk.StringVar(value=self.key.get().upper())
        self.cps = tk.StringVar(value=f"{data.get('cps', 10):g}")
        f = self.frame

        tk.Checkbutton(f, variable=self.enabled, command=app.sync, bg=CARD,
                       activebackground=CARD, selectcolor=FIELD, fg=TEXT,
                       bd=0, highlightthickness=0, cursor="hand2"
                       ).grid(row=0, column=0, padx=(0, 10))
        self.key_btn = flat_button(f, command=lambda: app.record_key(self), width=12)
        self.key_btn.config(textvariable=self.label)
        self.key_btn.grid(row=0, column=1, padx=(0, 14))

        flat_button(f, "−", lambda: self.step(-1), width=2, padx=4).grid(row=0, column=2)
        self.entry = tk.Entry(f, textvariable=self.cps, width=5, justify="center",
                              bg=FIELD, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=FONT_B)
        self.entry.grid(row=0, column=3, padx=4, ipady=4)
        self.entry.bind("<KeyRelease>", lambda e: app.sync())
        self.entry.bind("<FocusOut>", lambda e: self.normalize())
        flat_button(f, "+", lambda: self.step(1), width=2, padx=4).grid(row=0, column=4)
        tk.Label(f, text="per second", bg=CARD, fg=MUTED, font=FONT_S
                 ).grid(row=0, column=5, padx=(8, 0))

        rm = flat_button(f, "✕", lambda: app.remove_row(self), bg=CARD, over=RED,
                         fg=MUTED, width=2, padx=4)
        rm.grid(row=0, column=6, padx=(10, 0))

    def show(self):
        self.label.set(self.key.get().upper())
        self.key_btn.config(bg=FIELD)
        hover(self.key_btn, FIELD, FIELD_HOVER)

    def show_recording(self):
        self.label.set("Press a key…")
        self.key_btn.config(bg=ACCENT)
        hover(self.key_btn, ACCENT, ACCENT)

    def cps_value(self):
        try:
            return min(MAX_CPS, max(MIN_CPS, float(self.cps.get())))
        except ValueError:
            return 10.0

    def interval_ms(self):
        return 1000.0 / self.cps_value()

    def step(self, delta):
        self.cps.set(f"{min(MAX_CPS, max(MIN_CPS, self.cps_value() + delta)):g}")
        self.app.sync()

    def normalize(self):
        self.cps.set(f"{self.cps_value():g}")
        self.app.sync()

    def to_dict(self):
        return {"key": self.key.get(), "cps": self.cps_value(),
                "enabled": self.enabled.get()}


class App:
    def __init__(self, root):
        self.root = root
        root.title("KeyBurst")
        root.configure(bg=BG)
        root.resizable(False, False)

        self.cfg = load_config()
        self.toggle_name = self.cfg["toggle_hotkey"]
        self.clicker = Clicker()
        self.events = queue.Queue()
        self.recording = False
        self.ignore_toggle_until = 0.0
        self.last_toggle = 0.0
        self.hotkey_handle = None
        self.rows = []

        outer = tk.Frame(root, bg=BG, padx=20, pady=18)
        outer.pack()
        tk.Label(outer, text="KeyBurst", font=("Segoe UI", 18, "bold"), bg=BG,
                 fg=TEXT).pack(anchor="w")
        tk.Label(outer, text="Spam keys at your own speed. Works in games, notes, anywhere.",
                 font=FONT, bg=BG, fg=MUTED).pack(anchor="w", pady=(0, 14))

        # 1. start/stop key
        body = make_card(outer, "1   Start / stop key",
                         "Press this one key anytime to start or stop the spamming.")
        self.toggle_label = tk.StringVar()
        self.toggle_btn = flat_button(body, command=self.record_toggle, width=14,
                                      font=("Segoe UI", 12, "bold"), pady=6)
        self.toggle_btn.config(textvariable=self.toggle_label)
        self.toggle_btn.pack(side="left")
        self.toggle_help = tk.Label(body, bg=CARD, fg=MUTED, font=FONT_S)
        self.toggle_help.pack(side="left", padx=12)
        self.show_toggle()

        # 2. keys
        body = make_card(outer, "2   Keys to spam",
                         "Tick the keys you want. Click a key to change it.")
        head = tk.Frame(body, bg=CARD)
        head.pack(anchor="w")
        tk.Label(head, text="On", width=4, bg=CARD, fg=MUTED, font=FONT_S).grid(row=0, column=0)
        tk.Label(head, text="Key", width=14, bg=CARD, fg=MUTED, font=FONT_S).grid(row=0, column=1)
        tk.Label(head, text="Clicks per second", bg=CARD, fg=MUTED, font=FONT_S
                 ).grid(row=0, column=2, padx=(10, 0))
        self.rows_frame = tk.Frame(body, bg=CARD)
        self.rows_frame.pack(anchor="w", pady=(4, 0))
        for entry in self.cfg["entries"][:MAX_ROWS]:
            self._add_row(entry)
        self.add_btn = flat_button(body, "+  Add key", self.add_row, bg=CARD,
                                   over=FIELD, fg=ACCENT)
        self.add_btn.pack(anchor="w", pady=(8, 0))

        # run button + status
        self.run_btn = tk.Button(outer, command=self.toggle, relief="flat", bd=0,
                                 font=("Segoe UI", 14, "bold"), fg="white",
                                 activeforeground="white", cursor="hand2", pady=10)
        self.run_btn.pack(fill="x")
        self.status = tk.Label(outer, bg=BG, font=FONT, wraplength=420, justify="center")
        self.status.pack(fill="x", pady=(10, 0))

        self.register_hotkey()
        self.sync()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self.poll)

    # ---- rows
    def _add_row(self, data):
        row = Row(self, self.rows_frame, data)
        row.frame.pack(anchor="w", pady=3)
        self.rows.append(row)

    def add_row(self):
        if len(self.rows) < MAX_ROWS:
            used = {r.key.get() for r in self.rows} | {self.toggle_name}
            key = next((k for k in "1234567890qwertyuiop" if k not in used), "2")
            self._add_row({"key": key, "cps": 10, "enabled": True})
            self.sync()

    def remove_row(self, row):
        row.frame.destroy()
        self.rows.remove(row)
        self.sync()

    # ---- state
    def sync(self):
        self.clicker.set_entries(
            [(r.key.get(), r.interval_ms()) for r in self.rows if r.enabled.get()])
        self.cfg = {"toggle_hotkey": self.toggle_name,
                    "entries": [r.to_dict() for r in self.rows]}
        try:
            CONFIG_PATH.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.add_btn.config(state="normal" if len(self.rows) < MAX_ROWS else "disabled")

    def toggle(self):
        self.clicker.toggle()
        self.refresh()

    def set_status(self, text, color):
        self.status.config(text=text, fg=color)

    def refresh(self):
        key = self.toggle_name.upper()
        if self.clicker.running:
            self.run_btn.config(text=f"■   STOP  ({key})", bg=RED, activebackground=RED_HOVER)
            hover(self.run_btn, RED, RED_HOVER)
            self.set_status(f"Running. Press {key} to stop.", GREEN_HOVER)
        else:
            self.run_btn.config(text=f"▶   START  ({key})", bg=GREEN, activebackground=GREEN_HOVER)
            hover(self.run_btn, GREEN, GREEN_HOVER)
            self.set_status(f"Ready. Click your game or app first, then press {key}.", MUTED)

    def show_toggle(self):
        self.toggle_label.set(self.toggle_name.upper())
        self.toggle_btn.config(bg=FIELD)
        hover(self.toggle_btn, FIELD, FIELD_HOVER)
        self.toggle_help.config(text="Click the key to change it")

    # ---- hotkey
    def register_hotkey(self):
        if self.hotkey_handle is not None:
            try:
                keyboard.unhook(self.hotkey_handle)
            except Exception:
                pass
            self.hotkey_handle = None
        try:
            self.hotkey_handle = keyboard.on_press_key(
                self.toggle_name, lambda e: self.events.put(("toggle", None)))
        except Exception:
            self.set_status("That key can't be used. Pick another.", RED)

    def record_key(self, row):
        self._record("row", row)

    def record_toggle(self):
        self._record("toggle", None)

    def _record(self, kind, row):
        if self.recording:
            return
        self.recording = True
        if self.clicker.running:  # otherwise we would record our own key presses
            self.clicker.stop()
            self.refresh()
        if kind == "toggle":
            self.toggle_label.set("Press one key…")
            self.toggle_btn.config(bg=ACCENT)
            hover(self.toggle_btn, ACCENT, ACCENT)
            self.toggle_help.config(text="Esc to cancel")
        else:
            row.show_recording()
        self.set_status("Press the key you want. Esc cancels.", ACCENT)

        def work():
            self.events.put(("recorded", (kind, row, read_one_key())))

        threading.Thread(target=work, daemon=True).start()

    def finish_record(self, kind, row, name):
        self.recording = False
        self.ignore_toggle_until = time.time() + 0.4
        notice = None
        spam_keys = {r.key.get() for r in self.rows}
        if kind == "toggle":
            if name == "esc":
                pass
            elif name in spam_keys:
                notice = f"{name.upper()} is already one of your spam keys. Pick another."
            else:
                self.toggle_name = name
                self.register_hotkey()
            self.show_toggle()
        else:
            if name == "esc":
                pass
            elif name == self.toggle_name:
                notice = f"{name.upper()} is your start/stop key. Pick another."
            else:
                row.key.set(name)
            row.show()
        self.sync()
        self.refresh()
        if notice:
            self.set_status(notice, RED)

    def poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "toggle":
                    now = time.time()
                    # the 0.3s gap ignores key auto-repeat while the key is held
                    if (not self.recording and now > self.ignore_toggle_until
                            and now - self.last_toggle > 0.3):
                        self.last_toggle = now
                        self.toggle()
                elif kind == "recorded":
                    self.finish_record(*payload)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def close(self):
        self.clicker.shutdown()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
