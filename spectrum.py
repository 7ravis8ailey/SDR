import numpy as np


def compute_spectrum(iq_samples, sample_rate, center_freq, fft_size=1024):
    """Compute power spectrum from IQ samples. Returns (freqs_mhz, power_db)."""
    x = iq_samples[-fft_size:]

    window = np.hanning(fft_size)
    spectrum = np.fft.fftshift(np.fft.fft(x * window))
    power_db = 10 * np.log10(np.abs(spectrum) ** 2 + 1e-10)

    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, 1 / sample_rate))
    freqs_mhz = (freqs + center_freq) / 1e6

    return freqs_mhz, power_db


def plot_spectrum(freqs_mhz, power_db):
    """Show matplotlib spectrum plot."""
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 4))
    plt.plot(freqs_mhz, power_db)
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Power (dB)")
    plt.title("RF Spectrum")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def ascii_spectrum(freqs_mhz, power_db, width=80, height=20):
    """Terminal-based ASCII spectrum display."""
    indices = np.linspace(0, len(power_db) - 1, width, dtype=int)
    values = power_db[indices]
    freqs = freqs_mhz[indices]

    vmin, vmax = values.min(), values.max()
    if vmax - vmin < 1e-6:
        vmax = vmin + 1
    normalized = ((values - vmin) / (vmax - vmin) * height).astype(int)

    lines = []
    for row in range(height, -1, -1):
        line = ""
        for col in range(width):
            line += "#" if normalized[col] >= row else " "
        lines.append(line)

    lines.append(f"{freqs[0]:.1f} MHz{' ' * (width - 20)}{freqs[-1]:.1f} MHz")
    return "\n".join(lines)
