from fastmcp import FastMCP
import numpy as np

from sdr import SDR
from demod import demodulate, DEMODS
from spectrum import compute_spectrum, ascii_spectrum
from scanner import scan_range
from bands import BANDS, RTL_SDR_MIN_FREQ, RTL_SDR_MAX_FREQ

mcp = FastMCP("SDR Lab")

radio = SDR()


@mcp.tool
def open_device(
    frequency_mhz: float = 100.0,
    sample_rate: float = 2.048e6,
    gain: str = "auto",
) -> dict:
    """Open the RTL-SDR device and tune to a frequency."""
    freq_hz = frequency_mhz * 1e6
    if not (RTL_SDR_MIN_FREQ <= freq_hz <= RTL_SDR_MAX_FREQ):
        return {
            "error": f"Frequency {frequency_mhz} MHz out of range ({RTL_SDR_MIN_FREQ/1e6}-{RTL_SDR_MAX_FREQ/1e6} MHz)"
        }

    gain_value = gain if gain == "auto" else float(gain)
    radio.open(sample_rate=sample_rate, center_freq=freq_hz, gain=gain_value)

    return {
        "status": "open",
        "frequency_mhz": frequency_mhz,
        "sample_rate": sample_rate,
        "gain": gain,
    }


@mcp.tool
def close_device() -> str:
    """Close the RTL-SDR device."""
    radio.close()
    return "Device closed"


@mcp.tool
def tune(frequency_mhz: float) -> dict:
    """Change the tuned frequency (MHz)."""
    radio.center_freq = frequency_mhz * 1e6
    return {"frequency_mhz": frequency_mhz}


@mcp.tool
def set_gain(gain: str) -> dict:
    """Set receiver gain. Use 'auto' or a numeric value in dB."""
    radio.gain = gain if gain == "auto" else float(gain)
    return {"gain": gain}


@mcp.tool
def get_spectrum(fft_size: int = 1024) -> dict:
    """Capture IQ samples and return ASCII power spectrum with peak info."""
    iq = radio.read_samples(fft_size * 4)
    freqs_mhz, power_db = compute_spectrum(
        iq, radio.sample_rate, radio.center_freq, fft_size
    )

    ascii = ascii_spectrum(freqs_mhz, power_db, width=60, height=15)

    peak_idx = np.argmax(power_db)
    return {
        "center_freq_mhz": radio.center_freq / 1e6,
        "span_mhz": radio.sample_rate / 1e6,
        "peak_freq_mhz": round(float(freqs_mhz[peak_idx]), 4),
        "peak_power_db": round(float(power_db[peak_idx]), 1),
        "noise_floor_db": round(float(np.median(power_db)), 1),
        "ascii_spectrum": ascii,
    }


@mcp.tool
def capture_audio(duration_seconds: float = 2.0, mode: str = "wfm") -> dict:
    """Capture and demodulate audio. Returns signal stats (not playback)."""
    num_samples = int(radio.sample_rate * duration_seconds)
    iq = radio.read_samples(num_samples)
    audio = demodulate(iq, mode, sample_rate=radio.sample_rate)

    rms = float(np.sqrt(np.mean(audio**2)))
    return {
        "mode": mode,
        "duration_seconds": duration_seconds,
        "audio_samples": len(audio),
        "audio_peak": round(float(np.max(np.abs(audio))), 4),
        "audio_rms": round(rms, 4),
        "has_signal": rms > 0.01,
    }


@mcp.tool
def scan_frequencies(
    start_mhz: float,
    end_mhz: float,
    step_khz: float = 25.0,
    threshold_db: float = -30.0,
) -> list[dict]:
    """Scan a frequency range and return signals above the threshold."""
    return scan_range(
        radio,
        start_mhz * 1e6,
        end_mhz * 1e6,
        step=step_khz * 1e3,
        threshold_db=threshold_db,
    )


@mcp.tool
def scan_band(band_name: str) -> list[dict]:
    """Scan a named band (e.g., 'noaa', 'aviation', 'marine', 'fm')."""
    matching = {k: v for k, v in BANDS.items() if k.startswith(band_name)}
    if not matching:
        return [{"error": f"Unknown band: {band_name}", "available": list(BANDS.keys())}]

    freqs = [v[0] for v in matching.values()]
    start, end = min(freqs) - 100e3, max(freqs) + 100e3
    step = list(matching.values())[0][2]

    return scan_range(radio, start, end, step=step)


@mcp.tool
def list_bands() -> dict:
    """List all available band presets."""
    result = {}
    for name, (freq, mode, bw, desc) in BANDS.items():
        result[name] = {
            "frequency_mhz": freq / 1e6,
            "mode": mode,
            "bandwidth_khz": bw / 1e3,
            "description": desc,
        }
    return result


@mcp.tool
def tune_preset(preset_name: str) -> dict:
    """Tune to a named preset frequency."""
    if preset_name not in BANDS:
        return {"error": f"Unknown preset: {preset_name}", "available": list(BANDS.keys())}

    freq, mode, bw, desc = BANDS[preset_name]
    radio.center_freq = freq
    return {
        "preset": preset_name,
        "frequency_mhz": freq / 1e6,
        "mode": mode,
        "description": desc,
    }


@mcp.tool
def measure_power() -> dict:
    """Measure signal power at current frequency."""
    iq = radio.read_samples(256 * 1024)
    power = float(np.mean(np.abs(iq) ** 2))
    power_db = 10 * np.log10(power + 1e-10)
    return {
        "frequency_mhz": radio.center_freq / 1e6,
        "power_db": round(power_db, 1),
        "has_signal": power_db > -30,
    }


@mcp.tool
def available_modes() -> list[str]:
    """List available demodulation modes."""
    return list(DEMODS.keys())


if __name__ == "__main__":
    mcp.run()
