"""Step 8 (second half): how well did the player keep the tempo?

Only runs when the sheet music has a numeric tempo marking.
Only correctly matched notes are used, because for a wrong or missed note we
don't know when the right note would have been played.
"""

from dataclasses import dataclass

from . import config
from .align import CORRECT, AlignedPair


@dataclass
class TempoResult:
    measured: bool                 # False if there were too few correct notes to judge
    target_bpm: float = 0.0        # average target tempo over the part that was measured
    average_bpm: float = 0.0       # the tempo the player actually averaged
    average_error_ms: float = 0.0  # average size of the timing error, in milliseconds
    trend: str = "steady"          # "sped up", "slowed down" or "steady"


def beat_to_seconds(beat: float, tempo_marks: list[tuple[float, float]]) -> float:
    """Where a beat should fall in time, following every tempo marking in the file.

    tempo_marks is a sorted list of (beat where the tempo starts, quarter-note BPM).
    We add up the time of each stretch of music played at its own tempo.
    """
    marks = list(tempo_marks)
    if marks[0][0] > 0:
        marks.insert(0, (0.0, marks[0][1]))    # before the first marking, use the first tempo
    seconds = 0.0
    for index, (start, bpm) in enumerate(marks):
        if beat <= start:
            break
        end = marks[index + 1][0] if index + 1 < len(marks) else float("inf")
        seconds += (min(beat, end) - start) * 60.0 / bpm
    return seconds


def score_tempo(pairs: list[AlignedPair],
                tempo_marks: list[tuple[float, float]]) -> TempoResult | None:
    """Return the tempo result, or None if the file has no numeric tempo marking."""
    if not tempo_marks:
        return None

    good = [p for p in pairs if p.kind == CORRECT]
    if len(good) < 2:
        return TempoResult(measured=False)

    # Time zero = the first correctly played note. Everything is measured from there.
    played_zero = good[0].played.time
    expected_zero = beat_to_seconds(good[0].expected.start_beat, tempo_marks)

    errors_ms = []
    for p in good:
        played_seconds = p.played.time - played_zero
        expected_seconds = beat_to_seconds(p.expected.start_beat, tempo_marks) - expected_zero
        errors_ms.append(abs(played_seconds - expected_seconds) * 1000)

    average_bpm = _tempo_between(good[0], good[-1])
    target_seconds = (beat_to_seconds(good[-1].expected.start_beat, tempo_marks)
                      - beat_to_seconds(good[0].expected.start_beat, tempo_marks))
    beats = good[-1].expected.start_beat - good[0].expected.start_beat
    target_bpm = beats / target_seconds * 60.0 if target_seconds > 0 else 0.0

    return TempoResult(measured=True,
                       target_bpm=target_bpm,
                       average_bpm=average_bpm,
                       average_error_ms=sum(errors_ms) / len(errors_ms),
                       trend=_trend(good, tempo_marks))


def _tempo_between(first: AlignedPair, last: AlignedPair) -> float:
    """Played tempo (quarter-note BPM) between two matched notes: beats / minutes."""
    beats = last.expected.start_beat - first.expected.start_beat
    seconds = last.played.time - first.played.time
    return beats / seconds * 60.0 if seconds > 0 else 0.0


def _speed_ratio(first: AlignedPair, last: AlignedPair,
                 tempo_marks: list[tuple[float, float]]) -> float:
    """How fast the player went between two matched notes, as a fraction of the target
    speed (1.0 = exactly on tempo, 0.8 = 20% too slow). Comparing with the target, not
    with raw BPM, means a tempo change written in the music is not counted as speeding up."""
    target_seconds = (beat_to_seconds(last.expected.start_beat, tempo_marks)
                      - beat_to_seconds(first.expected.start_beat, tempo_marks))
    played_seconds = last.played.time - first.played.time
    return target_seconds / played_seconds if played_seconds > 0 else 0.0


def _trend(good: list[AlignedPair], tempo_marks: list[tuple[float, float]]) -> str:
    """Compare the playing speed of the first half with the second half."""
    if len(good) < 4:
        return "steady"
    middle = len(good) // 2
    first_half = _speed_ratio(good[0], good[middle], tempo_marks)
    second_half = _speed_ratio(good[middle], good[-1], tempo_marks)
    if first_half <= 0 or second_half <= 0:
        return "steady"
    change_percent = (second_half / first_half - 1) * 100
    if change_percent > config.TEMPO_CHANGE_THRESHOLD_PERCENT:
        return "sped up"
    if change_percent < -config.TEMPO_CHANGE_THRESHOLD_PERCENT:
        return "slowed down"
    return "steady"
