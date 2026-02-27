import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtlsdr import RtlSdr


def main():
    print("Opening RTL-SDR device...")
    try:
        sdr = RtlSdr()
    except Exception as e:
        print(f"Failed to open device: {e}")
        print("Make sure the RTL-SDR dongle is plugged in.")
        sys.exit(1)

    print(f"Device opened successfully")
    print(f"Tuner type: {sdr.get_tuner_type()}")
    print(f"Available gains (dB): {sdr.valid_gains_db}")

    sdr.sample_rate = 2.048e6
    sdr.center_freq = 100e6
    sdr.gain = "auto"

    print(f"\nCapturing test samples at {sdr.center_freq / 1e6} MHz...")
    samples = sdr.read_samples(256 * 1024)
    print(f"Captured {len(samples)} IQ samples")
    print(f"Sample dtype: {samples.dtype}")
    print(f"Mean power: {(abs(samples) ** 2).mean():.6f}")

    sdr.close()
    print("\nDongle test passed!")


if __name__ == "__main__":
    main()
