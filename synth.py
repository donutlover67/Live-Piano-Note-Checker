"""Synthetic "piano" audio, used for testing without a real piano or microphone.

A timed note is a tuple (midi, start_seconds, duration_seconds).
  1. expected_to_timed()  turns sheet-music notes into timed notes at a given tempo.
  2. plant_errors()       changes that list to simulate mistakes.
  3. synthesize()         turns the list into an audio waveform.
"""

import numpy as np

from . import config
from .models import ExpectedNote

NUMBER_OF_OVERTONES = 6


def midi_to_hz(midi: int) -> float:
    """Piano key number to frequency. A4 (key 69) is 440 Hz; each key is 2^(1/12) higher."""
    return 440.0 * 2 ** ((midi - 69) / 12)


def expected_to_timed(notes: list[ExpectedNote], bpm: float) -> list[tuple[int, float, float]]:
    """Place sheet-music notes in time, at a steady tempo (quarter-note BPM)."""
    seconds_per_beat = 60.0 / bpm
    return [(n.midi, n.start_beat * seconds_per_beat, n.duration * seconds_per_beat)
            for n in notes]


def plant_errors(notes, *, wrong=None, missed=None, extra=None, wrong_octave=None,
                 drift=0.0, time_scale=1.0):
    """Return a copy of `notes` with mistakes planted.

    wrong        {note index: different MIDI number to play instead}
    missed       set of note indexes that are not played at all
    extra        list of (MIDI number, time in seconds) of notes that are not in the music
    wrong_octave {note index: octaves to move (+1 = one octave up, -1 = down)}
    drift        gradual slow-down: 0.2 means the player is 20% slower by the end
                 (negative = gradually speeding up)
    time_scale   uniform tempo change: 1.1 means everything is 10% slower
    """
    wrong = wrong or {}
    missed = missed or set()
    extra = extra or []
    wrong_octave = wrong_octave or {}

    played = []
    for index, (midi, start, duration) in enumerate(notes):
        if index in missed:
            continue
        if index in wrong:
            midi = wrong[index]
        if index in wrong_octave:
            midi += 12 * wrong_octave[index]
        played.append((midi, start, duration))

    for midi, start in extra:
        played.append((midi, start, 0.3))

    # Timing: stretch every start time. For drift, the stretch grows from 1 at the
    # start to (1 + drift) at the end of the piece.
    total = max((s + d for _, s, d in notes), default=1.0)
    stretched = []
    for midi, start, duration in played:
        factor = time_scale * (1 + drift * start / total)
        stretched.append((midi, start * factor, duration * factor))
    return sorted(stretched, key=lambda n: n[1])


def _one_note(midi: int, duration: float, sample_rate: int) -> np.ndarray:
    """One piano-like note: a fundamental plus decaying overtones."""
    t = np.arange(int(duration * sample_rate)) / sample_rate
    fundamental = midi_to_hz(midi)
    wave = np.zeros_like(t)
    for k in range(1, NUMBER_OF_OVERTONES + 1):
        if fundamental * k > sample_rate / 2 * 0.9:     # keep below the Nyquist limit
            break
        # Overtone k is quieter (1/k) and dies away faster (higher k = shorter life).
        wave += (1.0 / k) * np.sin(2 * np.pi * fundamental * k * t) * np.exp(-t * (2.0 + 1.5 * k))
    # Quick fade-in (5 ms) avoids a click. The fade-out over the last 100 ms imitates a
    # piano damper; a sharper cut-off would sound like a new note starting.
    fade_in = min(len(t), int(0.005 * sample_rate))
    fade_out = min(len(t), int(0.1 * sample_rate))
    wave[:fade_in] *= np.linspace(0, 1, fade_in)
    if fade_out:
        wave[-fade_out:] *= np.linspace(1, 0, fade_out)
    return wave


def synthesize(notes, sample_rate: int = config.SAMPLE_RATE,
               lead_in: float = 0.5, tail: float = 0.5) -> np.ndarray:
    """Mix all notes into one waveform with silence before and after."""
    if not notes:
        return np.zeros(int((lead_in + tail) * sample_rate), dtype=np.float32)
    end = max(start + duration for _, start, duration in notes)
    audio = np.zeros(int((lead_in + end + tail) * sample_rate))
    for midi, start, duration in notes:
        wave = _one_note(midi, max(duration, 0.1), sample_rate)
        begin = int((lead_in + start) * sample_rate)
        audio[begin:begin + len(wave)] += wave[:len(audio) - begin]
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.8      # normalise so it never clips
    return audio.astype(np.float32)
