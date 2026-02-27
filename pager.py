import os
import signal
import shutil
import subprocess
import threading
import time
import logging

log = logging.getLogger("sdr.pager")

DEFAULT_DECODERS = ["POCSAG512", "POCSAG1200", "POCSAG2400"]


class PagerDecoder:
    """Manages rtl_fm | multimon-ng pipeline for pager/EAS/DTMF decoding."""

    def __init__(self):
        self.rtl_process = None
        self.mm_process = None
        self.active = False
        self.frequency = None
        self.decoders = None
        self._messages = []
        self._messages_lock = threading.Lock()
        self._stdout_thread = None
        self._has_multimon = shutil.which("multimon-ng") is not None
        self._has_rtl_fm = shutil.which("rtl_fm") is not None

    def start(self, frequency_hz, decoders=None, gain="auto", squelch=0):
        if self.active:
            self.stop()

        if not self._has_rtl_fm:
            raise RuntimeError("rtl_fm not found. Install with: brew install librtlsdr")
        if not self._has_multimon:
            raise RuntimeError("multimon-ng not found")

        self.frequency = frequency_hz
        self.decoders = decoders or DEFAULT_DECODERS

        rtl_cmd = [
            "rtl_fm",
            "-f", str(int(frequency_hz)),
            "-M", "fm",
            "-s", "22050",
            "-l", str(squelch),
            "-",
        ]
        if gain != "auto":
            rtl_cmd.insert(1, "-g")
            rtl_cmd.insert(2, str(gain))

        mm_cmd = ["multimon-ng", "-t", "raw", "--timestamp"]
        for d in self.decoders:
            mm_cmd.extend(["-a", d])
        mm_cmd.append("-")

        log.info(f"Launching: {' '.join(rtl_cmd)} | {' '.join(mm_cmd)}")

        self.rtl_process = subprocess.Popen(
            rtl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        self.mm_process = subprocess.Popen(
            mm_cmd,
            stdin=self.rtl_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        # Allow rtl_fm to get SIGPIPE if multimon-ng exits
        self.rtl_process.stdout.close()

        self.active = True

        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()

    def _read_stdout(self):
        while self.active and self.mm_process and self.mm_process.poll() is None:
            try:
                line = self.mm_process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                with self._messages_lock:
                    self._messages.append({
                        "time": time.strftime("%H:%M:%S"),
                        "raw": text,
                    })
                    if len(self._messages) > 200:
                        self._messages = self._messages[-200:]
            except Exception:
                break

    def stop(self):
        self.active = False
        for proc in [self.mm_process, self.rtl_process]:
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
        self.rtl_process = None
        self.mm_process = None
        self.frequency = None
        self.decoders = None

    def get_status(self):
        mm_alive = self.mm_process is not None and self.mm_process.poll() is None
        rtl_alive = self.rtl_process is not None and self.rtl_process.poll() is None
        return {
            "active": self.active and mm_alive,
            "has_multimon": self._has_multimon,
            "has_rtl_fm": self._has_rtl_fm,
            "frequency_hz": self.frequency,
            "frequency_mhz": round(self.frequency / 1e6, 4) if self.frequency else None,
            "decoders": self.decoders,
            "rtl_pid": self.rtl_process.pid if self.rtl_process and rtl_alive else None,
            "mm_pid": self.mm_process.pid if self.mm_process and mm_alive else None,
            "message_count": len(self._messages),
        }

    def get_messages(self, last_n=50):
        with self._messages_lock:
            return list(self._messages[-last_n:])
