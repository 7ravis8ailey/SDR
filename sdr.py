import threading

from rtlsdr import RtlSdr

# Module-level device lock — only one consumer (webui or digital) at a time
_device_lock = threading.Lock()
_device_owner = None  # "webui", "digital", or None


def acquire_device(owner):
    """Acquire exclusive device access. Returns True if acquired."""
    global _device_owner
    with _device_lock:
        if _device_owner is None or _device_owner == owner:
            _device_owner = owner
            return True
        return False


def release_device(owner):
    """Release device access."""
    global _device_owner
    with _device_lock:
        if _device_owner == owner:
            _device_owner = None


def device_owner():
    """Return current owner or None."""
    return _device_owner


class SDR:
    def __init__(self):
        self.device = None

    def open(self, sample_rate=2.048e6, center_freq=100e6, gain="auto"):
        self.device = RtlSdr()
        self.device.sample_rate = sample_rate
        self.device.center_freq = center_freq
        self.device.gain = gain

    def close(self):
        if self.device:
            self.device.close()
            self.device = None

    def read_samples(self, num_samples=256 * 1024):
        return self.device.read_samples(num_samples)

    @property
    def center_freq(self):
        return self.device.center_freq

    @center_freq.setter
    def center_freq(self, freq):
        self.device.center_freq = freq

    @property
    def sample_rate(self):
        return self.device.sample_rate

    @sample_rate.setter
    def sample_rate(self, rate):
        self.device.sample_rate = rate

    @property
    def gain(self):
        return self.device.gain

    @gain.setter
    def gain(self, value):
        self.device.gain = value
