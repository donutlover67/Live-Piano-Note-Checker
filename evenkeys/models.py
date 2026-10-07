"""The small data types passed between the modules."""

from dataclasses import dataclass


@dataclass
class ExpectedNote:
    """One note that the sheet music says should be played."""

    midi: int            # piano key number (60 = middle C). E#4 and F4 are both 65.
    name: str            # spelling from the sheet music, e.g. "F#4" or "Bb3"
    start_beat: float    # when the note starts, in quarter-note beats from the piece start
    duration: float      # length in quarter-note beats
    measure: int         # measure number printed on the sheet music
    beat: float          # beat within the measure (1 = first beat)
    repeat_pass: int = 0  # 0 = first time this measure is played, 1 = its repeat, ...
    repeat_from: int = 0  # for a repeated pass: the measure holding the repeat sign that caused it
    measure_start: float = 0.0  # where this measure begins, in beats from the piece start
    measure_end: float = 0.0    # where this measure ends (so rests at its end are included)


@dataclass
class PlayedNote:
    """One note heard in the recording."""

    midi: int            # piano key number we think was played
    time: float          # when it started, in seconds from the recording start


@dataclass
class LoadedScore:
    """Everything we learn from the sheet music file."""

    title: str | None
    num_measures: int
    tempo_marks: list[tuple[float, float]]   # (beat where it starts, quarter-note BPM)
    hands: dict[str, list[ExpectedNote]]     # "R" and/or "L" -> notes (chords included)
    warnings: list[str]                      # messages to show the user (e.g. hand split)
    has_repeats: bool = False                # True if repeat signs made the piece longer
