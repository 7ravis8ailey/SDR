import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdr import SDR
from demod import fm_demod
from audio import AudioPlayer


def main():
    freq_mhz = float(sys.argv[1]) if len(sys.argv) > 1 else 101.1
    freq_hz = freq_mhz * 1e6

    print(f"Tuning to {freq_mhz} MHz FM...")

    radio = SDR()
    radio.open(sample_rate=2.048e6, center_freq=freq_hz, gain="auto")

    player = AudioPlayer(sample_rate=48000)
    player.start()

    # Discard first read (AGC settling)
    radio.read_samples(256 * 1024)

    print(f"Listening... Press Ctrl+C to stop.")
    try:
        while True:
            iq = radio.read_samples(256 * 1024)
            audio = fm_demod(iq, sample_rate=2.048e6, audio_rate=48000)
            player.play(audio)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        player.stop()
        radio.close()


if __name__ == "__main__":
    main()
