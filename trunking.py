import json
import os
import signal
import shutil
import subprocess
import threading
import time
import logging

log = logging.getLogger("sdr.trunking")


class TrunkRecorder:
    """Manages trunk-recorder subprocess for trunked radio systems."""

    def __init__(self):
        self.process = None
        self.active = False
        self._config_path = None
        self._capture_dir = None
        self._calls = []
        self._calls_lock = threading.Lock()
        self._poll_thread = None
        self._seen_files = set()
        self._has_trunk_recorder = shutil.which("trunk-recorder") is not None

    def start(self, config_path=None, config_dict=None):
        if self.active:
            self.stop()

        if not self._has_trunk_recorder:
            raise RuntimeError("trunk-recorder not found")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._capture_dir = os.path.join(base_dir, "trunk_captures")
        os.makedirs(self._capture_dir, exist_ok=True)

        if config_dict:
            self._config_path = os.path.join(base_dir, "trunk_config.json")
            config_dict.setdefault("captureDir", self._capture_dir)
            with open(self._config_path, "w") as f:
                json.dump(config_dict, f, indent=2)
        elif config_path:
            self._config_path = config_path
        else:
            raise ValueError("Provide config_path or config_dict")

        cmd = ["trunk-recorder", "-c", self._config_path]

        log.info(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.active = True

        self._poll_thread = threading.Thread(target=self._poll_calls, daemon=True)
        self._poll_thread.start()

    def _poll_calls(self):
        while self.active:
            time.sleep(2)
            if not self._capture_dir or not os.path.exists(self._capture_dir):
                continue
            for fname in os.listdir(self._capture_dir):
                if fname.endswith(".json") and fname not in self._seen_files:
                    self._seen_files.add(fname)
                    fpath = os.path.join(self._capture_dir, fname)
                    try:
                        with open(fpath, "r") as f:
                            call_data = json.load(f)
                        call_data["_filename"] = fname
                        with self._calls_lock:
                            self._calls.append(call_data)
                            if len(self._calls) > 100:
                                self._calls = self._calls[-100:]
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
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self._seen_files.clear()

    def get_status(self):
        alive = self.process is not None and self.process.poll() is None
        return {
            "active": self.active and alive,
            "has_trunk_recorder": self._has_trunk_recorder,
            "config_path": self._config_path,
            "capture_dir": self._capture_dir,
            "pid": self.process.pid if self.process and alive else None,
            "call_count": len(self._calls),
        }

    def get_calls(self, last_n=50):
        with self._calls_lock:
            return list(self._calls[-last_n:])
