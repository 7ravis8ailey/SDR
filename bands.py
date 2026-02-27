# Band definitions: name -> (freq_hz, mode, bandwidth_hz, description)
BANDS = {
    # FM Broadcast
    "fm_low": (88.1e6, "wfm", 200e3, "FM broadcast band start"),
    "fm_high": (107.9e6, "wfm", 200e3, "FM broadcast band end"),
    # Aviation (AM)
    "aviation_low": (118e6, "am", 25e3, "Aviation voice band start"),
    "aviation_high": (137e6, "am", 25e3, "Aviation voice band end"),
    "atis": (127.85e6, "am", 25e3, "Common ATIS frequency"),
    # NOAA Weather (NFM)
    "noaa_1": (162.400e6, "nfm", 25e3, "NOAA Weather 1"),
    "noaa_2": (162.425e6, "nfm", 25e3, "NOAA Weather 2"),
    "noaa_3": (162.450e6, "nfm", 25e3, "NOAA Weather 3"),
    "noaa_4": (162.475e6, "nfm", 25e3, "NOAA Weather 4"),
    "noaa_5": (162.500e6, "nfm", 25e3, "NOAA Weather 5"),
    "noaa_6": (162.525e6, "nfm", 25e3, "NOAA Weather 6"),
    "noaa_7": (162.550e6, "nfm", 25e3, "NOAA Weather 7"),
    # Marine VHF (NFM)
    "marine_ch16": (156.800e6, "nfm", 25e3, "Marine distress/calling"),
    "marine_ch13": (156.650e6, "nfm", 25e3, "Marine bridge-to-bridge"),
    # Public Safety VHF (NFM)
    "public_safety_low": (148e6, "nfm", 12.5e3, "VHF public safety"),
    "public_safety_high": (174e6, "nfm", 12.5e3, "VHF public safety"),
    # ADS-B
    "adsb": (1090e6, "adsb", 2e6, "ADS-B aircraft tracking"),
}

# RTL-SDR Blog V4 (R828D tuner) frequency range
RTL_SDR_MIN_FREQ = 24e6
RTL_SDR_MAX_FREQ = 1766e6
