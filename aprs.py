import os
import signal
import shutil
import subprocess
import threading
import time
import logging

log = logging.getLogger("sdr.aprs")

APRS_FREQUENCY = 144.39e6  # North America standard


class APRSDecoder:
    """Manages rtl_fm | direwolf pipeline for APRS packet decoding."""

    def __init__(self):
        self.rtl_process = None
        self.dw_process = None
        self.active = False
        self.frequency = None
        self._packets = []
        self._packets_lock = threading.Lock()
        self._stdout_thread = None
        self._has_direwolf = shutil.which("direwolf") is not None
        self._has_rtl_fm = shutil.which("rtl_fm") is not None

    def start(self, frequency_hz=APRS_FREQUENCY, gain="auto"):
        if self.active:
            self.stop()

        if not self._has_rtl_fm:
            raise RuntimeError("rtl_fm not found. Install with: brew install librtlsdr")
        if not self._has_direwolf:
            raise RuntimeError("direwolf not found. Install with: brew install direwolf")

        self.frequency = frequency_hz

        rtl_cmd = [
            "rtl_fm",
            "-f", str(int(frequency_hz)),
            "-M", "fm",
            "-s", "22050",
            "-",
        ]
        if gain != "auto":
            rtl_cmd.insert(1, "-g")
            rtl_cmd.insert(2, str(gain))

        dw_cmd = [
            "direwolf",
            "-r", "22050",
            "-D", "1",
            "-t", "0",
            "-",
        ]

        log.info(f"Launching: {' '.join(rtl_cmd)} | {' '.join(dw_cmd)}")

        self.rtl_process = subprocess.Popen(
            rtl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        self.dw_process = subprocess.Popen(
            dw_cmd,
            stdin=self.rtl_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        self.rtl_process.stdout.close()
        self.active = True

        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()

    def _read_stdout(self):
        while self.active and self.dw_process and self.dw_process.poll() is None:
            try:
                line = self.dw_process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                with self._packets_lock:
                    self._packets.append({
                        "time": time.strftime("%H:%M:%S"),
                        "raw": text,
                    })
                    if len(self._packets) > 200:
                        self._packets = self._packets[-200:]
            except Exception:
                break

    def stop(self):
        self.active = False
        for proc in [self.dw_process, self.rtl_process]:
            if proc:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self.dw_process = None
        self.rtl_process = None
        self.frequency = None

    def get_status(self):
        dw_alive = self.dw_process is not None and self.dw_process.poll() is None
        return {
            "active": self.active and dw_alive,
            "has_direwolf": self._has_direwolf,
            "has_rtl_fm": self._has_rtl_fm,
            "frequency_hz": self.frequency,
            "frequency_mhz": round(self.frequency / 1e6, 4) if self.frequency else None,
            "pid": self.dw_process.pid if self.dw_process and dw_alive else None,
            "packet_count": len(self._packets),
        }

    def get_packets(self, last_n=50):
        with self._packets_lock:
            return list(self._packets[-last_n:])
