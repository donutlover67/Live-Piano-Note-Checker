"""Step 8 (first half): find the notes in a recording.

Two questions are answered separately:
  WHEN was a note struck?   -> onset detection
  WHICH note was it?        -> pitch detection
"""

import librosa
import numpy as np

from . import config
from .models import PlayedNote


class AnalysisError(Exception):
    """Raised with a message that is safe to show directly to the user."""


def detect_onsets(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Return the time (seconds) of each sudden rise in loudness, i.e. each new note.

    librosa first measures how much the sound's frequency content grows from one
    short time slice to the next (the "onset strength"). A new note makes it spike.
    We then pick the peaks that rise more than config.ONSET_DELTA above their
    surroundings. A smaller delta means more sensitivity.
    """
    strength = librosa.onset.onset_strength(y=audio, sr=sample_rate,
                                            hop_length=config.HOP_LENGTH)
    return librosa.onset.onset_detect(onset_envelope=strength, sr=sample_rate,
                                      hop_length=config.HOP_LENGTH,
                                      delta=config.ONSET_DELTA, units="time")


def detect_pitches(audio: np.ndarray, sample_rate: int,
                   onset_times: np.ndarray) -> list[PlayedNote]:
    """Work out which piano key was pressed at each onset.

    Each note is analysed on its own: we cut out the slice of audio from just before
    its onset to just before the next onset, so neighbouring notes can't confuse it.
    librosa.pyin estimates the fundamental frequency (the pitch we hear) for every short
    time frame of that slice. We take the median estimate, convert it to a MIDI key
    number and round to the nearest key. Onsets where no clear pitch is found (clicks,
    noise) are dropped.
    """
    fmin = librosa.note_to_hz(config.PITCH_FMIN)
    fmax = librosa.note_to_hz(config.PITCH_FMAX)
    minimum_samples = config.PITCH_FRAME_LENGTH * 2    # pyin needs a few frames to work with

    played = []
    for i, onset in enumerate(onset_times):
        # Where this note's slice starts and ends, in seconds.
        start = max(0.0, onset - config.PITCH_LEAD_SECONDS)
        end = onset + config.PITCH_WINDOW_SECONDS
        if i + 1 < len(onset_times):
            end = min(end, onset_times[i + 1] - config.PITCH_END_TRIM_SECONDS)
        piece = audio[int(start * sample_rate):int(end * sample_rate)]
        if len(piece) < minimum_samples:               # very fast notes: pad with silence
            piece = np.pad(piece, (0, minimum_samples - len(piece)))

        f0, _, _ = librosa.pyin(piece, fmin=fmin, fmax=fmax, sr=sample_rate,
                                frame_length=config.PITCH_FRAME_LENGTH,
                                hop_length=config.PITCH_HOP_LENGTH)
        # f0[k] is the pitch of frame k in Hz, or NaN where pyin hears no steady pitch.
        frame_times = librosa.times_like(f0, sr=sample_rate, hop_length=config.PITCH_HOP_LENGTH)
        # Skip the first frames (half padding, plus the noisy key "thump") and the last ones
        # (their window reaches into the next note).
        slice_seconds = end - start
        in_note = ((frame_times >= config.PITCH_SKIP_SECONDS)
                   & (frame_times <= slice_seconds - config.PITCH_END_TRIM_SECONDS / 2))
        values = f0[in_note]
        values = values[~np.isnan(values)]
        if len(values) == 0:
            continue
        midi = int(round(librosa.hz_to_midi(float(np.median(values)))))
        played.append(PlayedNote(midi=midi, time=float(onset)))
    return played


def drop_implausible_notes(played: list[PlayedNote], expected) -> list[PlayedNote]:
    """Ignore detected notes far outside the range of the music being played.

    Keyboard clicks, a chair creaking or a door closing are often "heard" as extremely
    low notes. A note more than config.PITCH_OCTAVE_MARGIN octaves below the lowest
    expected note (or above the highest) is almost certainly noise, not a mistake.
    Genuine mistakes, including wrong-octave notes, are far closer than that.
    """
    low = min(n.midi for n in expected) - 12 * config.PITCH_OCTAVE_MARGIN
    high = max(n.midi for n in expected) + 12 * config.PITCH_OCTAVE_MARGIN
    return [p for p in played if low <= p.midi <= high]


def drop_sounds_before_first_note(audio: np.ndarray, sample_rate: int,
                                  onset_times: np.ndarray) -> np.ndarray:
    """Start listening at the first real note.

    Recording starts the moment you press Enter, so the beginning usually contains
    the click of that key, a chair moving, hands settling, and so on. A piano note is
    much louder than that. We measure how loud each detected sound is, find the typical
    (median) loudness, and ignore everything before the first sound that is at least
    config.FIRST_NOTE_MIN_LOUDNESS_RATIO of that. Only the start is trimmed: quiet notes
    later in the piece are kept.
    """
    if len(onset_times) < 2:
        return onset_times
    # Loudness over time: root-mean-square (RMS) of each short slice of audio.
    rms = librosa.feature.rms(y=audio, frame_length=config.PITCH_FRAME_LENGTH,
                              hop_length=config.HOP_LENGTH)[0]
    frame_times = librosa.times_like(rms, sr=sample_rate, hop_length=config.HOP_LENGTH)
    # Loudness of one sound = the loudest slice in the 0.2 s after its onset.
    loudness = np.array([rms[(frame_times >= t) & (frame_times <= t + 0.2)].max(initial=0.0)
                         for t in onset_times])
    threshold = config.FIRST_NOTE_MIN_LOUDNESS_RATIO * np.median(loudness)
    first_real = int(np.argmax(loudness >= threshold))    # index of the first loud-enough sound
    return onset_times[first_real:]


def analyze_audio(audio: np.ndarray, sample_rate: int) -> list[PlayedNote]:
    """Recording in, list of played notes out. Raises AnalysisError on bad recordings."""
    if audio is None or len(audio) == 0:
        raise AnalysisError("The recording is empty. Check that your microphone is "
                            "working and try again.")
    onsets = detect_onsets(audio, sample_rate)
    onsets = drop_sounds_before_first_note(audio, sample_rate, onsets)
    played = detect_pitches(audio, sample_rate, onsets) if len(onsets) else []
    if not played:
        raise AnalysisError("No notes were detected. Play closer to the microphone, "
                            "or lower ONSET_DELTA in evenkeys/config.py.")
    return played
