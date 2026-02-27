from rtlsdr import RtlSdr


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
