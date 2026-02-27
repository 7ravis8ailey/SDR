import os
import wave
import time

from fastmcp import FastMCP
import numpy as np

from sdr import SDR, acquire_device, release_device
from demod import demodulate, DEMODS
from spectrum import compute_spectrum, ascii_spectrum
from scanner import scan_range
from bands import BANDS, DIGITAL_CHANNELS, RTL_SDR_MIN_FREQ, RTL_SDR_MAX_FREQ
from digital import DigitalVoiceDecoder
from adsb import ADSBDecoder
from ism import ISMDecoder
from pager import PagerDecoder
from aprs import APRSDecoder
from trunking import TrunkRecorder

mcp = FastMCP("SDR Lab")

radio = SDR()
decoder = DigitalVoiceDecoder()
adsb_decoder = ADSBDecoder()
ism_decoder = ISMDecoder()
pager_decoder = PagerDecoder()
aprs_decoder = APRSDecoder()
trunk_recorder = TrunkRecorder()

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")


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

    if not acquire_device("mcp"):
        return {"error": "Device in use. Stop other consumers first."}

    try:
        gain_value = gain if gain == "auto" else float(gain)
        radio.open(sample_rate=sample_rate, center_freq=freq_hz, gain=gain_value)
    except Exception as e:
        release_device("mcp")
        return {"error": f"Failed to open device: {e}"}

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
    release_device("mcp")
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


# --- Digital decoder tools ---


@mcp.tool
def start_digital_decode(
    frequency_mhz: float,
    mode: str = "auto",
    gain: str = "auto",
    squelch: int = 0,
) -> dict:
    """Start real-time digital voice decoding. Modes: auto, dmr, p25, nxdn, dstar, ysf, nfm, am, wfm."""
    if radio.device:
        radio.close()
        release_device("mcp")
    acquire_device("digital")
    decoder.start(frequency_mhz * 1e6, mode, gain, squelch)
    return decoder.get_status()


@mcp.tool
def stop_digital_decode() -> str:
    """Stop digital voice decoding and release the device."""
    decoder.stop()
    release_device("digital")
    return "Digital decoder stopped"


@mcp.tool
def digital_status() -> dict:
    """Get digital decoder status — active frequency, mode, process info."""
    return decoder.get_status()


@mcp.tool
def digital_get_calls() -> list[dict]:
    """Get recent decoded calls/activity from the digital decoder."""
    return decoder.get_calls()


@mcp.tool
def list_digital_channels() -> dict:
    """List available digital channel presets (local frequencies)."""
    return DIGITAL_CHANNELS


@mcp.tool
def tune_digital_preset(preset_name: str) -> dict:
    """Start digital decoding on a named preset channel."""
    if preset_name not in DIGITAL_CHANNELS:
        return {"error": f"Unknown preset: {preset_name}", "available": list(DIGITAL_CHANNELS.keys())}
    ch = DIGITAL_CHANNELS[preset_name]
    if radio.device:
        radio.close()
        release_device("mcp")
    acquire_device("digital")
    decoder.start(ch["freq"], ch["mode"], "auto", 0)
    return {"preset": preset_name, **decoder.get_status()}


# --- WAV recording tools ---


@mcp.tool
def record_audio(
    duration_seconds: float = 10.0,
    mode: str = "nfm",
    filename: str = "",
) -> dict:
    """Record demodulated audio to a WAV file. Device must be open first."""
    os.makedirs(RECORDINGS_DIR, exist_ok=True)

    if not filename:
        freq_str = f"{radio.center_freq / 1e6:.3f}MHz"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{freq_str}_{mode}.wav"

    filepath = os.path.join(RECORDINGS_DIR, filename)
    audio_rate = 48000

    num_samples = int(radio.sample_rate * duration_seconds)
    iq = radio.read_samples(num_samples)
    audio = demodulate(iq, mode, sample_rate=radio.sample_rate, audio_rate=audio_rate)

    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(audio_rate)
        wf.writeframes(pcm.tobytes())

    return {
        "file": filepath,
        "filename": filename,
        "duration_seconds": round(len(audio) / audio_rate, 2),
        "frequency_mhz": radio.center_freq / 1e6,
        "mode": mode,
        "size_bytes": os.path.getsize(filepath),
    }


@mcp.tool
def list_recordings() -> list[dict]:
    """List all saved WAV recordings."""
    if not os.path.exists(RECORDINGS_DIR):
        return []
    files = []
    for f in sorted(os.listdir(RECORDINGS_DIR)):
        if f.endswith(".wav"):
            path = os.path.join(RECORDINGS_DIR, f)
            files.append({
                "filename": f,
                "path": path,
                "size_bytes": os.path.getsize(path),
            })
    return files


# --- ADS-B decoder tools ---


@mcp.tool
def start_adsb(gain: str = "auto") -> dict:
    """Start ADS-B aircraft tracking on 1090 MHz using dump1090."""
    if radio.device:
        radio.close()
        release_device("mcp")
    if not acquire_device("adsb"):
        return {"error": "Device in use. Stop other consumers first."}
    try:
        adsb_decoder.start(gain=gain)
    except Exception as e:
        release_device("adsb")
        return {"error": str(e)}
    return adsb_decoder.get_status()


@mcp.tool
def stop_adsb() -> str:
    """Stop ADS-B tracking and release the device."""
    adsb_decoder.stop()
    release_device("adsb")
    return "ADS-B decoder stopped"


@mcp.tool
def adsb_status() -> dict:
    """Get ADS-B decoder status."""
    return adsb_decoder.get_status()


@mcp.tool
def get_aircraft() -> list[dict]:
    """Get currently tracked aircraft from ADS-B decoder."""
    return adsb_decoder.get_aircraft()


# --- ISM band decoder tools ---


@mcp.tool
def start_ism(frequency_mhz: float = 433.92, gain: str = "auto") -> dict:
    """Start ISM band decoder (weather stations, sensors, etc.) using rtl_433."""
    if radio.device:
        radio.close()
        release_device("mcp")
    if not acquire_device("ism"):
        return {"error": "Device in use. Stop other consumers first."}
    try:
        ism_decoder.start(frequency_hz=frequency_mhz * 1e6, gain=gain)
    except Exception as e:
        release_device("ism")
        return {"error": str(e)}
    return ism_decoder.get_status()


@mcp.tool
def stop_ism() -> str:
    """Stop ISM band decoder and release the device."""
    ism_decoder.stop()
    release_device("ism")
    return "ISM decoder stopped"


@mcp.tool
def ism_status() -> dict:
    """Get ISM decoder status."""
    return ism_decoder.get_status()


@mcp.tool
def get_ism_events(last_n: int = 50) -> list[dict]:
    """Get recent decoded ISM events (weather stations, sensors, tire pressure, etc.)."""
    return ism_decoder.get_events(last_n)


# --- Pager decoder tools ---


@mcp.tool
def start_pager(
    frequency_mhz: float,
    decoders: str = "POCSAG512,POCSAG1200,POCSAG2400",
    gain: str = "auto",
    squelch: int = 0,
) -> dict:
    """Start pager/EAS decoder using multimon-ng. Decoders: POCSAG512, POCSAG1200, POCSAG2400, EAS, DTMF, AFSK1200, MORSE_CW."""
    if radio.device:
        radio.close()
        release_device("mcp")
    if not acquire_device("pager"):
        return {"error": "Device in use. Stop other consumers first."}
    try:
        decoder_list = [d.strip() for d in decoders.split(",")]
        pager_decoder.start(
            frequency_hz=frequency_mhz * 1e6,
            decoders=decoder_list,
            gain=gain,
            squelch=squelch,
        )
    except Exception as e:
        release_device("pager")
        return {"error": str(e)}
    return pager_decoder.get_status()


@mcp.tool
def stop_pager() -> str:
    """Stop pager decoder and release the device."""
    pager_decoder.stop()
    release_device("pager")
    return "Pager decoder stopped"


@mcp.tool
def pager_status() -> dict:
    """Get pager decoder status."""
    return pager_decoder.get_status()


@mcp.tool
def get_pager_messages(last_n: int = 50) -> list[dict]:
    """Get recent decoded pager/EAS messages."""
    return pager_decoder.get_messages(last_n)


# --- APRS decoder tools ---


@mcp.tool
def start_aprs(frequency_mhz: float = 144.39, gain: str = "auto") -> dict:
    """Start APRS packet decoder using direwolf. Default 144.390 MHz (NA standard)."""
    if radio.device:
        radio.close()
        release_device("mcp")
    if not acquire_device("aprs"):
        return {"error": "Device in use. Stop other consumers first."}
    try:
        aprs_decoder.start(frequency_hz=frequency_mhz * 1e6, gain=gain)
    except Exception as e:
        release_device("aprs")
        return {"error": str(e)}
    return aprs_decoder.get_status()


@mcp.tool
def stop_aprs() -> str:
    """Stop APRS decoder and release the device."""
    aprs_decoder.stop()
    release_device("aprs")
    return "APRS decoder stopped"


@mcp.tool
def aprs_status() -> dict:
    """Get APRS decoder status."""
    return aprs_decoder.get_status()


@mcp.tool
def get_aprs_packets(last_n: int = 50) -> list[dict]:
    """Get recent decoded APRS packets."""
    return aprs_decoder.get_packets(last_n)


# --- Trunk recorder tools ---


@mcp.tool
def start_trunk(config_path: str = "") -> dict:
    """Start trunk-recorder for trunked radio systems (P25, SmartNet). Requires config file."""
    if not config_path:
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trunk_config.json")
        if os.path.exists(default):
            config_path = default
        else:
            return {"error": "No config_path provided and no trunk_config.json found. Use generate_trunk_config first."}
    if radio.device:
        radio.close()
        release_device("mcp")
    if not acquire_device("trunk"):
        return {"error": "Device in use. Stop other consumers first."}
    try:
        trunk_recorder.start(config_path=config_path)
    except Exception as e:
        release_device("trunk")
        return {"error": str(e)}
    return trunk_recorder.get_status()


@mcp.tool
def stop_trunk() -> str:
    """Stop trunk-recorder and release the device."""
    trunk_recorder.stop()
    release_device("trunk")
    return "Trunk recorder stopped"


@mcp.tool
def trunk_status() -> dict:
    """Get trunk-recorder status."""
    return trunk_recorder.get_status()


@mcp.tool
def get_trunk_calls(last_n: int = 50) -> list[dict]:
    """Get recent trunk-recorder call metadata."""
    return trunk_recorder.get_calls(last_n)


@mcp.tool
def generate_trunk_config(
    system_type: str,
    control_channels: str,
) -> dict:
    """Generate a trunk-recorder config.json for a trunked system.

    system_type: 'p25' or 'smartnet'
    control_channels: Comma-separated control channel frequencies in Hz (e.g. '851012500,852012500')
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "trunk_config.json")
    capture_dir = os.path.join(base_dir, "trunk_captures")

    channels = [int(f.strip()) for f in control_channels.split(",")]

    config = {
        "sources": [{
            "center": channels[0],
            "rate": 2048000,
            "driver": "osmosdr",
            "device": "rtl=0",
            "gain": 40,
        }],
        "systems": [{
            "type": system_type,
            "control_channels": channels,
            "shortName": system_type,
        }],
        "captureDir": capture_dir,
    }

    os.makedirs(capture_dir, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {"config_path": config_path, "config": config}


if __name__ == "__main__":
    mcp.run()
