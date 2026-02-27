import numpy as np


def scan_range(sdr, start_freq, end_freq, step=25e3, threshold_db=-30, dwell_ms=50):
    """Scan frequency range and return signals above threshold.

    Returns list of {freq_hz, freq_mhz, power_db} sorted by power descending.
    """
    signals = []
    freq = start_freq
    samples_per_dwell = int(sdr.sample_rate * dwell_ms / 1000)

    while freq <= end_freq:
        sdr.center_freq = freq
        iq = sdr.read_samples(samples_per_dwell)
        power_db = 10 * np.log10(np.mean(np.abs(iq) ** 2) + 1e-10)

        if power_db > threshold_db:
            signals.append(
                {
                    "freq_hz": freq,
                    "freq_mhz": freq / 1e6,
                    "power_db": round(power_db, 1),
                }
            )
        freq += step

    return sorted(signals, key=lambda s: s["power_db"], reverse=True)
