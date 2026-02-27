# SDR Lab

RTL-SDR software-defined radio controlled via Python. RTL-SDR Blog V4 (R828D tuner).

## Tech Stack
- Python 3.13 / uv
- pyrtlsdr (RTL-SDR device control)
- numpy/scipy (DSP)
- sounddevice (audio output)
- FastMCP (MCP server)

## Commands
```bash
uv run python scripts/test_dongle.py              # verify hardware
uv run python scripts/listen_fm.py <freq_mhz>     # listen to FM (e.g. 101.1)
uv run python scripts/scan_bands.py <band>         # scan band (noaa, aviation, marine, fm)
```

## MCP Server
The `sdr` MCP server (sdr_server.py) exposes tools for controlling the RTL-SDR.
Requires the dongle to be physically connected via USB.

Key tools: open_device, tune, get_spectrum, scan_band, capture_audio, measure_power

## Frequency Reference
See bands.py for preset frequencies (NOAA weather, aviation, marine, FM broadcast).
RTL-SDR range: 24 MHz - 1766 MHz. AM broadcast (below 24 MHz) not supported without upconverter.

## Demodulation Modes
- `wfm` / `fm` — Wideband FM (broadcast radio)
- `am` — AM (aviation, shortwave)
- `nfm` — Narrowband FM (NOAA weather, marine, public safety)
