import queue

import numpy as np
import sounddevice as sd


class AudioPlayer:
    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate
        self.queue = queue.Queue(maxsize=20)
        self.stream = None

    def start(self):
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=self._callback,
        )
        self.stream.start()

    def _callback(self, outdata, frames, time, status):
        try:
            data = self.queue.get_nowait()
            if len(data) < frames:
                outdata[: len(data), 0] = data
                outdata[len(data) :, 0] = 0
            else:
                outdata[:, 0] = data[:frames]
        except queue.Empty:
            outdata[:] = 0

    def play(self, audio_chunk):
        """Queue an audio chunk for playback. Drops if buffer full."""
        try:
            self.queue.put_nowait(audio_chunk)
        except queue.Full:
            pass

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
