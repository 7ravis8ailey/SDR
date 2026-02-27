from bands import FREQUENCY_DB

# Frequency tolerance for database lookups (1 kHz)
FREQ_TOLERANCE = 1e3

# Band-based guesses for frequencies not in the database
BAND_RULES = [
    # (min_hz, max_hz, protocol, decoder, mode, description)
    (88e6, 108e6, "analog_wfm", "analog", "wfm", "FM broadcast"),
    (118e6, 137e6, "analog_am", "analog", "am", "Aviation"),
    (144.385e6, 144.395e6, "aprs", "aprs", "nfm", "APRS"),
    (148e6, 174e6, "unknown", "digital", "auto", "VHF public safety"),
    (156e6, 157e6, "analog_nfm", "analog", "nfm", "Marine VHF"),
    (162.395e6, 162.555e6, "analog_nfm", "analog", "nfm", "NOAA Weather"),
    (400e6, 470e6, "unknown", "digital", "auto", "UHF land mobile"),
    (433.9e6, 433.94e6, "ism", "ism", "nfm", "ISM 433 MHz"),
    (800e6, 900e6, "unknown", "digital", "auto", "800 MHz public safety"),
    (1089.5e6, 1090.5e6, "adsb", "adsb", "adsb", "ADS-B aircraft"),
]


def resolve_frequency(frequency_hz):
    """Look up a frequency and return recommended decoder settings.

    1. Exact match in FREQUENCY_DB (within 1 kHz)
    2. Band-based guess from frequency range
    3. Default: dsd-fme auto mode
    """
    # 1. Database lookup
    for name, ch in FREQUENCY_DB.items():
        if abs(ch["freq"] - frequency_hz) <= FREQ_TOLERANCE:
            return {
                "frequency_hz": ch["freq"],
                "frequency_mhz": round(ch["freq"] / 1e6, 4),
                "protocol": ch["protocol"],
                "decoder": ch["decoder"],
                "mode": ch["mode"],
                "tone": ch["tone"],
                "description": ch["description"],
                "name": name,
                "source": "database",
            }

    # 2. Band-based guess
    for min_hz, max_hz, protocol, decoder, mode, desc in BAND_RULES:
        if min_hz <= frequency_hz <= max_hz:
            return {
                "frequency_hz": frequency_hz,
                "frequency_mhz": round(frequency_hz / 1e6, 4),
                "protocol": protocol,
                "decoder": decoder,
                "mode": mode,
                "tone": None,
                "description": desc,
                "name": None,
                "source": "band_guess",
            }

    # 3. Default: try digital auto-detect
    return {
        "frequency_hz": frequency_hz,
        "frequency_mhz": round(frequency_hz / 1e6, 4),
        "protocol": "unknown",
        "decoder": "digital",
        "mode": "auto",
        "tone": None,
        "description": "Unknown frequency — trying auto-detect",
        "name": None,
        "source": "auto_detect",
    }
