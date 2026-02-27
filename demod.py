from math import gcd

import numpy as np
from scipy import signal


def fm_demod(iq_samples, sample_rate=2.048e6, audio_rate=48000):
    """Demodulate wideband FM from IQ samples. Returns audio at audio_rate."""
    # Quadrature demodulation (polar discriminator)
    discriminated = np.angle(iq_samples[1:] * np.conj(iq_samples[:-1]))

    # Low-pass filter at 15 kHz (mono audio bandwidth)
    nyq = sample_rate / 2
    b, a = signal.butter(5, 15000 / nyq, btype="low")
    filtered = signal.lfilter(b, a, discriminated)

    # De-emphasis filter (75 us time constant, North America)
    tau = 75e-6
    d = sample_rate * tau
    de_b = [1]
    de_a = [1, -np.exp(-1 / d)]
    filtered = signal.lfilter(de_b, de_a, filtered)

    # Resample to audio rate
    g = gcd(int(sample_rate), audio_rate)
    up = audio_rate // g
    down = int(sample_rate) // g
    audio = signal.resample_poly(filtered, up, down)

    # Normalize to [-1, 1]
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    return audio.astype(np.float32)


def am_demod(iq_samples, sample_rate=2.048e6, audio_rate=48000):
    """AM envelope detection. Used for aviation, AM broadcast."""
    envelope = np.abs(iq_samples)
    envelope = envelope - np.mean(envelope)

    # Low-pass filter at 5 kHz (AM audio bandwidth)
    nyq = sample_rate / 2
    b, a = signal.butter(5, 5000 / nyq, btype="low")
    filtered = signal.lfilter(b, a, envelope)

    g = gcd(int(sample_rate), audio_rate)
    audio = signal.resample_poly(filtered, audio_rate // g, int(sample_rate) // g)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak
    return audio.astype(np.float32)


def nfm_demod(iq_samples, sample_rate=2.048e6, audio_rate=48000):
    """Narrowband FM. Used for NOAA weather, marine, public safety."""
    discriminated = np.angle(iq_samples[1:] * np.conj(iq_samples[:-1]))

    # Narrower low-pass: 4 kHz for NFM
    nyq = sample_rate / 2
    b, a = signal.butter(5, 4000 / nyq, btype="low")
    filtered = signal.lfilter(b, a, discriminated)

    g = gcd(int(sample_rate), audio_rate)
    audio = signal.resample_poly(filtered, audio_rate // g, int(sample_rate) // g)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak
    return audio.astype(np.float32)


DEMODS = {
    "wfm": fm_demod,
    "fm": fm_demod,
    "am": am_demod,
    "nfm": nfm_demod,
}


def demodulate(iq_samples, mode, sample_rate=2.048e6, audio_rate=48000):
    """Demodulate IQ samples using the specified mode."""
    if mode not in DEMODS:
        raise ValueError(f"Unknown mode: {mode}. Available: {list(DEMODS.keys())}")
    return DEMODS[mode](iq_samples, sample_rate, audio_rate)
