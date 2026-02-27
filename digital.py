import os
import signal
import shutil
import socket
import subprocess
import threading
import time
import logging

import numpy as np

log = logging.getLogger("sdr.digital")

# dsd-fme mode flags
DSD_MODES = {
    "auto": "-fa",
    "dmr": "-fr",
    "p25": "-fp",
    "nxdn": "-fn",
    "dstar": "-fd",
    "ysf": "-fy",
    "analog": "-fA",
}

# rtl_fm demod modes
RTL_FM_MODES = {"nfm": "fm", "am": "am", "wfm": "wbfm"}


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DigitalVoiceDecoder:
    """Manages rtl_fm or dsd-fme subprocess for voice monitoring."""

    def __init__(self):
        self.process = None
        self.frequency = None
        self.mode = None
        self.active = False
        self._udp_port = None
        self._udp_sock = None
        self._audio_thread = None
        self._audio_buffer = b""
        self._buffer_lock = threading.Lock()
        self._calls = []
        self._stderr_thread = None
        self._has_dsd = shutil.which("dsd-fme") is not None
        self._has_rtl_fm = shutil.which("rtl_fm") is not None

    def start(self, frequency_hz, mode="nfm", gain="auto", squelch=0):
        """Launch subprocess to monitor a frequency.

        For digital modes (dmr, p25, nxdn, dstar, ysf, auto):
            Uses dsd-fme with built-in RTL support and UDP audio output.
        For analog modes (nfm, am, wfm):
            Uses rtl_fm piping raw PCM to stdout.
        """
        if self.active:
            self.stop()

        self.frequency = frequency_hz
        self.mode = mode
        freq_mhz = frequency_hz / 1e6

        is_digital = mode in DSD_MODES

        if is_digital:
            if not self._has_dsd:
                raise RuntimeError("dsd-fme not found. Build from source: github.com/lwvmobile/dsd-fme")
            self._start_dsd(frequency_hz, mode, gain, squelch)
        else:
            if not self._has_rtl_fm:
                raise RuntimeError("rtl_fm not found. Install with: brew install librtlsdr")
            self._start_rtl_fm(frequency_hz, mode, gain, squelch)

        self.active = True
        log.info(f"Digital decoder started: {freq_mhz:.4f} MHz, mode={mode}")

    def _start_dsd(self, frequency_hz, mode, gain, squelch):
        """Launch dsd-fme with RTL input and UDP audio output."""
        self._udp_port = _find_free_port()

        gain_val = 26 if gain == "auto" else int(float(gain))
        freq_str = f"{frequency_hz / 1e6:.6f}M"

        cmd = [
            "dsd-fme",
            DSD_MODES[mode],
            "-i", f"rtl:0:{freq_str}:{gain_val}:0:12:{squelch}:1",
            "-o", f"udp:127.0.0.1:{self._udp_port}",
        ]

        log.info(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # UDP listener for decoded audio
        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock.bind(("127.0.0.1", self._udp_port))
        self._udp_sock.settimeout(0.5)

        self._audio_thread = threading.Thread(target=self._udp_audio_loop, daemon=True)
        self._audio_thread.start()

        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _start_rtl_fm(self, frequency_hz, mode, gain, squelch):
        """Launch rtl_fm for analog monitoring."""
        rtl_mode = RTL_FM_MODES.get(mode, "fm")
        sample_rate = "48000" if mode != "wfm" else "170000"

        cmd = [
            "rtl_fm",
            "-f", str(int(frequency_hz)),
            "-M", rtl_mode,
            "-s", sample_rate,
            "-l", str(squelch),
            "-",
        ]

        if gain != "auto":
            cmd.insert(1, "-g")
            cmd.insert(2, str(gain))

        log.info(f"Launching: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self._audio_thread = threading.Thread(target=self._pipe_audio_loop, daemon=True)
        self._audio_thread.start()

        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _udp_audio_loop(self):
        """Read decoded audio from dsd-fme UDP output."""
        while self.active and self._udp_sock:
            try:
                data, _ = self._udp_sock.recvfrom(8192)
                with self._buffer_lock:
                    self._audio_buffer += data
                    # Keep buffer under 1MB
                    if len(self._audio_buffer) > 1_000_000:
                        self._audio_buffer = self._audio_buffer[-500_000:]
            except socket.timeout:
                continue
            except OSError:
                break

    def _pipe_audio_loop(self):
        """Read raw PCM audio from rtl_fm stdout."""
        while self.active and self.process and self.process.poll() is None:
            try:
                data = self.process.stdout.read(8192)
                if not data:
                    break
                with self._buffer_lock:
                    self._audio_buffer += data
                    if len(self._audio_buffer) > 1_000_000:
                        self._audio_buffer = self._audio_buffer[-500_000:]
            except Exception:
                break

    def _read_stderr(self):
        """Capture stderr for logging and call metadata."""
        while self.active and self.process and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    log.debug(f"decoder: {text}")
                    # Track interesting lines as "calls"
                    if any(kw in text.lower() for kw in ["voice", "call", "talkgroup", "source", "target"]):
                        self._calls.append({
                            "time": time.strftime("%H:%M:%S"),
                            "message": text,
                        })
                        # Keep last 50 calls
                        if len(self._calls) > 50:
                            self._calls = self._calls[-50:]
            except Exception:
                break

    def stop(self):
        """Kill subprocess pipeline and clean up."""
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

        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            self._udp_sock = None

        with self._buffer_lock:
            self._audio_buffer = b""

        self.frequency = None
        self.mode = None
        self._udp_port = None
        log.info("Digital decoder stopped")

    def read_audio(self, num_bytes=8192):
        """Read and consume decoded audio from buffer.

        Returns int16 PCM bytes at 48kHz mono.
        """
        with self._buffer_lock:
            chunk = self._audio_buffer[:num_bytes]
            self._audio_buffer = self._audio_buffer[num_bytes:]
        return chunk

    def get_status(self):
        """Return current decoder status."""
        alive = self.process is not None and self.process.poll() is None
        return {
            "active": self.active and alive,
            "frequency_hz": self.frequency,
            "frequency_mhz": round(self.frequency / 1e6, 4) if self.frequency else None,
            "mode": self.mode,
            "has_dsd": self._has_dsd,
            "has_rtl_fm": self._has_rtl_fm,
            "pid": self.process.pid if self.process and alive else None,
        }

    def get_calls(self):
        """Return recent decoded calls/activity."""
        return list(self._calls)
