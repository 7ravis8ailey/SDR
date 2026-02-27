import subprocess
import shutil

import numpy as np


def decode_digital(audio_samples, sample_rate=22050, modes=None):
    """Pipe audio to multimon-ng and return decoded messages.

    audio_samples should be float32 at the specified sample_rate.
    Default sample_rate is 22050 Hz (multimon-ng default).
    """
    if shutil.which("multimon-ng") is None:
        raise RuntimeError("multimon-ng not found. Install with: brew install multimon-ng")

    if modes is None:
        modes = ["POCSAG512", "POCSAG1200", "POCSAG2400", "EAS"]

    cmd = ["multimon-ng", "-t", "raw", "-a"]
    cmd.extend(modes[0:1])
    for mode in modes[1:]:
        cmd.extend(["-a", mode])
    cmd.append("/dev/stdin")

    # Convert float32 audio to 16-bit PCM
    pcm = (audio_samples * 32767).astype(np.int16)
    raw_bytes = pcm.tobytes()

    result = subprocess.run(
        cmd,
        input=raw_bytes,
        capture_output=True,
        text=True,
        timeout=10,
    )

    messages = []
    for line in result.stdout.strip().split("\n"):
        if line and not line.startswith("multimon-ng"):
            messages.append(line)

    return messages
