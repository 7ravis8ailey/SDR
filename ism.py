import json
import os
import signal
import shutil
import subprocess
import threading
import time
import logging

log = logging.getLogger("sdr.ism")


class ISMDecoder:
    """Manages rtl_433 subprocess for ISM band device decoding."""

    def __init__(self):
        self.process = None
        self.active = False
        self.frequency = None
        self._events = []
        self._events_lock = threading.Lock()
        self._stdout_thread = None
        self._has_rtl_433 = shutil.which("rtl_433") is not None

    def start(self, frequency_hz=433.92e6, gain="auto"):
        if self.active:
            self.stop()

        if not self._has_rtl_433:
            raise RuntimeError("rtl_433 not found. Install with: brew install rtl_433")

        self.frequency = frequency_hz

        cmd = [
            "rtl_433",
            "-f", str(int(frequency_hz)),
            "-F", "json",
        ]
        if gain != "auto":
            cmd.extend(["-g", str(gain)])

        log.info(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.active = True

        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()

    def _read_stdout(self):
        while self.active and self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                    event["_received_at"] = time.strftime("%H:%M:%S")
                    with self._events_lock:
                        self._events.append(event)
                        if len(self._events) > 100:
                            self._events = self._events[-100:]
                except json.JSONDecodeError:
                    log.debug(f"rtl_433 non-json: {text}")
            except Exception:
                break

    def stop(self):
        self.active = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.frequency = None

    def get_status(self):
        alive = self.process is not None and self.process.poll() is None
        return {
            "active": self.active and alive,
            "has_rtl_433": self._has_rtl_433,
            "frequency_hz": self.frequency,
            "frequency_mhz": round(self.frequency / 1e6, 4) if self.frequency else None,
            "pid": self.process.pid if self.process and alive else None,
            "event_count": len(self._events),
        }

    def get_events(self, last_n=50):
        with self._events_lock:
            return list(self._events[-last_n:])
