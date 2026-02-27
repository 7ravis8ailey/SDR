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
    # Carter County / Elizabethton, TN
    "carter_fire_dispatch": (154.295e6, "nfm", 12.5e3, "Carter County Fire Dispatch (PL 100.0)"),
    "carter_sheriff_holston": (155.535e6, "nfm", 12.5e3, "Carter County Sheriff - Holston Mtn (PL 100.0)"),
    "carter_sheriff_roan": (155.760e6, "nfm", 12.5e3, "Carter County Sheriff - Roan Mtn (PL 141.3)"),
    "ems_holston": (151.3925e6, "nfm", 12.5e3, "EMS/Rescue Squad - Holston Mtn (DPL 025)"),
    "ems_white_rock": (151.0475e6, "nfm", 12.5e3, "EMS/Rescue Squad - White Rock (DPL 025)"),
    "sycamore_hospital": (155.340e6, "nfm", 12.5e3, "Sycamore Shoals Hospital HEAR"),
    "ems_dispatch_backup": (155.160e6, "nfm", 12.5e3, "EMS Dispatch Backup (PL 179.9)"),
    "happy_valley_hs": (464.550e6, "nfm", 12.5e3, "Happy Valley High School (PL 67.0)"),
    "unaka_hs": (462.575e6, "nfm", 12.5e3, "Unaka High School (DPL 053)"),
    "elizabethton_pd_tac": (155.940e6, "nfm", 12.5e3, "Elizabethton PD Tac (PL 100.0)"),
    "walmart_elizabethton": (154.570e6, "nfm", 12.5e3, "Walmart Elizabethton"),
}

# RTL-SDR Blog V4 (R828D tuner) frequency range
RTL_SDR_MIN_FREQ = 24e6
RTL_SDR_MAX_FREQ = 1766e6
