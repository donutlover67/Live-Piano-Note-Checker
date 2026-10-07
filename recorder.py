"""Step 7: record from the microphone in a background thread.

Why a thread? The main program is waiting for you to type 'stop'. A thread lets the
recording keep running at the same time as the program waits for your typing.
"""

import threading

import numpy as np
import sounddevice as sd

from . import config

BLOCK_FRAMES = 1024   # how many audio samples to read at a time


class RecordingError(Exception):
    """Raised with a message that is safe to show directly to the user."""


class Recorder:
    def __init__(self, sample_rate: int = config.SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []      # pieces of audio, joined together at the end
        self._stop_requested = threading.Event()  # set when the user types 'stop'
        self._ready = threading.Event()           # set once the microphone is open (or failed)
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._record_loop, daemon=True)

    def start(self) -> None:
        """Begin recording. Raises RecordingError if there is no usable microphone."""
        self._thread.start()
        self._ready.wait(timeout=5)           # wait until we know whether the mic opened
        if self._error is not None:
            raise RecordingError(
                "No microphone could be opened. Check that one is connected, that it is "
                f"allowed in your system's privacy settings, and try again. ({self._error})")

    def stop(self) -> np.ndarray:
        """Stop recording and return all the audio as one array of numbers."""
        self._stop_requested.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._chunks)

    def _record_loop(self) -> None:
        """Runs in the background thread: keep reading audio until told to stop."""
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1,
                                dtype="float32") as stream:
                self._ready.set()
                while not self._stop_requested.is_set():
                    block, _overflowed = stream.read(BLOCK_FRAMES)
                    self._chunks.append(block[:, 0].copy())   # keep the single channel
        except Exception as error:     # no device, permission denied, device unplugged...
            self._error = error
            self._ready.set()
