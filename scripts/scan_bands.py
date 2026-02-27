import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdr import SDR
from scanner import scan_range
from bands import BANDS


def main():
    band = sys.argv[1] if len(sys.argv) > 1 else "noaa"

    matching = {k: v for k, v in BANDS.items() if k.startswith(band)}
    if not matching:
        print(f"Unknown band: {band}")
        print(f"Available prefixes: {', '.join(sorted(set(k.split('_')[0] for k in BANDS)))}")
        sys.exit(1)

    freqs = [v[0] for v in matching.values()]
    start, end = min(freqs) - 100e3, max(freqs) + 100e3
    step = list(matching.values())[0][2]

    radio = SDR()
    radio.open(sample_rate=2.048e6, center_freq=start, gain="auto")

    print(f"Scanning {start / 1e6:.3f} - {end / 1e6:.3f} MHz (step: {step / 1e3:.1f} kHz)...")
    signals = scan_range(radio, start, end, step=step)

    if signals:
        print(f"\nFound {len(signals)} signals:")
        for s in signals:
            # Try to match to a named preset
            name = ""
            for k, v in matching.items():
                if abs(v[0] - s["freq_hz"]) < step:
                    name = f"  ({k}: {v[3]})"
                    break
            print(f"  {s['freq_mhz']:.3f} MHz  {s['power_db']:+.1f} dB{name}")
    else:
        print("\nNo signals found above threshold.")

    radio.close()


if __name__ == "__main__":
    main()
