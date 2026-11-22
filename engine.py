"""KeyBurst engine: taps several keys, each on its own interval."""
import threading
import time

import keyboard

MIN_INTERVAL_MS = 20   # below this Roblox tends to drop presses
HOLD_SECONDS = 0.008   # how long each key stays down


class Clicker:
    def __init__(self):
        self._entries = []          # list of (key, interval_ms)
        self._lock = threading.Lock()
        self._running = False
        self._quit = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    @property
    def running(self):
        return self._running

    def set_entries(self, entries):
        clean = [(k, max(MIN_INTERVAL_MS, float(ms))) for k, ms in entries if k]
        with self._lock:
            self._entries = clean

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def toggle(self):
        self._running = not self._running
        return self._running

    def shutdown(self):
        self._running = False
        self._quit.set()

    def _tap(self, key):
        try:
            keyboard.press(key)
            time.sleep(HOLD_SECONDS)
            keyboard.release(key)
        except Exception:
            pass  # bad key name: skip it instead of crashing the loop

    def _loop(self):
        next_due = {}
        while not self._quit.is_set():
            if not self._running:
                next_due.clear()
                time.sleep(0.02)
                continue
            now = time.perf_counter()
            with self._lock:
                entries = list(self._entries)
            soonest = now + 0.05
            for i, (key, ms) in enumerate(entries):
                slot = (i, key)
                due = next_due.get(slot, now)
                if now >= due:
                    self._tap(key)
                    due = time.perf_counter() + ms / 1000.0
                next_due[slot] = due
                soonest = min(soonest, due)
            time.sleep(max(0.001, soonest - time.perf_counter()))
