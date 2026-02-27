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
    # APRS
    "aprs": (144.39e6, "nfm", 12.5e3, "APRS packet radio (144.390 MHz)"),
    # ISM Band
    "ism_433": (433.92e6, "nfm", 200e3, "ISM band 433.92 MHz (weather stations, sensors)"),
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

# Frequency database: name -> {freq, protocol, decoder, mode, tone, description}
#
# protocol: analog_nfm, analog_am, analog_wfm, dmr, p25, nxdn, dstar, ysf, aprs, adsb, ism
# decoder:  analog (rtl_fm), digital (dsd-fme), adsb (dump1090), aprs (direwolf),
#           ism (rtl_433), pager (multimon-ng)
# mode:     the mode flag passed to the decoder (nfm, am, wfm, dmr, p25, nxdn, dstar, ysf, auto)
# tone:     CTCSS tone or DCS code, or None
FREQUENCY_DB = {
    # --- Carter County Public Safety — Analog ---
    "carter_fire_dispatch": {
        "freq": 154.295e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "100.0", "description": "Carter County Fire Dispatch",
    },
    "carter_sheriff_holston": {
        "freq": 155.535e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "100.0", "description": "Carter County Sheriff - Holston Mtn",
    },
    "carter_sheriff_roan": {
        "freq": 155.760e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "141.3", "description": "Carter County Sheriff - Roan Mtn",
    },
    "carter_ema": {
        "freq": 155.385e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "179.9", "description": "Carter County EMA",
    },
    "ems_holston": {
        "freq": 151.3925e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "DPL 025", "description": "EMS/Rescue - Holston Mtn",
    },
    "ems_white_rock": {
        "freq": 151.0475e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "DPL 025", "description": "EMS/Rescue - White Rock",
    },
    "sycamore_hospital": {
        "freq": 155.340e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "Sycamore Shoals Hospital HEAR",
    },
    "ems_dispatch_backup": {
        "freq": 155.160e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "179.9", "description": "EMS Dispatch Backup",
    },
    "elizabethton_pd_tac": {
        "freq": 155.940e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "100.0", "description": "Elizabethton PD Tac",
    },
    "carter_jail": {
        "freq": 153.740e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "146.2", "description": "Carter County Jail",
    },
    # --- Carter County Public Safety — Digital ---
    "elizabethton_pd_dispatch": {
        "freq": 155.415e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "Elizabethton Police Dispatch (DMR)",
    },
    "elizabethton_fire": {
        "freq": 151.070e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "Elizabethton Fire (DMR)",
    },
    # --- State/Federal — Digital ---
    "tn_wildlife": {
        "freq": 159.300e6, "protocol": "p25", "decoder": "digital",
        "mode": "p25", "tone": None, "description": "TN Wildlife (P25)",
    },
    "tn_tbi_1": {
        "freq": 460.525e6, "protocol": "p25", "decoder": "digital",
        "mode": "p25", "tone": None, "description": "TN Bureau of Investigation (P25)",
    },
    "tn_tbi_2": {
        "freq": 460.550e6, "protocol": "p25", "decoder": "digital",
        "mode": "p25", "tone": None, "description": "TN Bureau of Investigation (P25)",
    },
    # --- Carter County Ham Repeaters — Analog FM ---
    "wr4cc_2m": {
        "freq": 146.700e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "77.0", "description": "WR4CC CCARA 2m Repeater",
    },
    "k4lns_2m": {
        "freq": 145.110e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "K4LNS 2m Repeater - Holston Mtn",
    },
    "k4lns_2m_b": {
        "freq": 147.270e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "K4LNS 2m Repeater - Holston Mtn",
    },
    "km4hdm_2m": {
        "freq": 145.170e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": "123.0", "description": "KM4HDM 2m Repeater - Holston Mtn",
    },
    # --- Carter County Ham Repeaters — Digital ---
    "ae2ey_dmr": {
        "freq": 438.625e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "AE2EY DMR/D-STAR Repeater (CC 1)",
    },
    "w4ysf_dmr": {
        "freq": 440.525e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "W4YSF DMR Repeater - Holston Mtn (CC 11)",
    },
    "ke4ccb_dmr": {
        "freq": 442.700e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "KE4CCB FM/DMR Repeater - Holston Mtn (CC 7)",
    },
    "k4lns_dmr": {
        "freq": 444.100e6, "protocol": "dmr", "decoder": "digital",
        "mode": "dmr", "tone": None, "description": "K4LNS DMR Repeater (CC 7)",
    },
    "ae2ey_nxdn": {
        "freq": 447.875e6, "protocol": "nxdn", "decoder": "digital",
        "mode": "nxdn", "tone": None, "description": "AE2EY NXDN Repeater",
    },
    "kc4ayx_p25": {
        "freq": 920.000e6, "protocol": "p25", "decoder": "digital",
        "mode": "p25", "tone": None, "description": "KC4AYX P25 Repeater (NAC 293)",
    },
    "kc4ayx_dstar": {
        "freq": 1295.000e6, "protocol": "dstar", "decoder": "digital",
        "mode": "dstar", "tone": None, "description": "KC4AYX D-STAR Repeater - Ripshin Ridge",
    },
    # --- Standard Frequencies ---
    "noaa_weather_1": {
        "freq": 162.400e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "NOAA Weather 1",
    },
    "noaa_weather_2": {
        "freq": 162.425e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "NOAA Weather 2",
    },
    "noaa_weather_3": {
        "freq": 162.450e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "NOAA Weather 3",
    },
    "marine_ch16": {
        "freq": 156.800e6, "protocol": "analog_nfm", "decoder": "analog",
        "mode": "nfm", "tone": None, "description": "Marine Distress/Calling Ch 16",
    },
    "aprs_na": {
        "freq": 144.390e6, "protocol": "aprs", "decoder": "aprs",
        "mode": "nfm", "tone": None, "description": "APRS North America (144.390 MHz)",
    },
}

# Legacy alias for backward compatibility with existing code
DIGITAL_CHANNELS = {
    name: {"freq": ch["freq"], "mode": ch["mode"], "description": ch["description"]}
    for name, ch in FREQUENCY_DB.items()
}

# RTL-SDR Blog V4 (R828D tuner) frequency range
RTL_SDR_MIN_FREQ = 24e6
RTL_SDR_MAX_FREQ = 1766e6
