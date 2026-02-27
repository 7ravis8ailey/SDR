import json
import os
import signal
import shutil
import subprocess
import threading
import time
import logging

log = logging.getLogger("sdr.adsb")


class ADSBDecoder:
    """Manages dump1090 subprocess for ADS-B aircraft tracking."""

    def __init__(self):
        self.process = None
        self.active = False
        self._json_dir = None
        self._aircraft = []
        self._aircraft_lock = threading.Lock()
        self._poll_thread = None
        self._http_port = None
        self._has_dump1090 = shutil.which("dump1090") is not None

    def start(self, gain="auto", http_port=8888):
        if self.active:
            self.stop()

        if not self._has_dump1090:
            raise RuntimeError("dump1090 not found")

        self._json_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "adsb_json"
        )
        os.makedirs(self._json_dir, exist_ok=True)
        self._http_port = http_port

        cmd = [
            "dump1090",
            "--net",
            "--net-http-port", str(http_port),
            "--write-json", self._json_dir,
            "--write-json-every", "1",
            "--quiet",
        ]
        if gain != "auto":
            cmd.extend(["--gain", str(gain)])

        log.info(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.active = True

        self._poll_thread = threading.Thread(target=self._poll_json, daemon=True)
        self._poll_thread.start()

    def _poll_json(self):
        while self.active:
            time.sleep(1)
            json_path = os.path.join(self._json_dir, "aircraft.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        data = json.load(f)
                    with self._aircraft_lock:
                        self._aircraft = data.get("aircraft", [])
                except (json.JSONDecodeError, IOError):
                    pass

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
        with self._aircraft_lock:
            self._aircraft = []
        self._http_port = None

    def get_status(self):
        alive = self.process is not None and self.process.poll() is None
        return {
            "active": self.active and alive,
            "has_dump1090": self._has_dump1090,
            "frequency_mhz": 1090.0 if self.active else None,
            "http_port": self._http_port if self.active else None,
            "pid": self.process.pid if self.process and alive else None,
            "aircraft_count": len(self._aircraft),
        }

    def get_aircraft(self):
        with self._aircraft_lock:
            return list(self._aircraft)
