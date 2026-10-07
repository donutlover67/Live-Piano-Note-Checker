"""Step 8 (last part): turn the alignment and tempo results into the text report."""

import math

from . import config
from .align import (CORRECT, EXTRA, MISSED, WRONG_OCTAVE, AlignedPair, align,
                    drop_echo_extras)
from .detect import drop_implausible_notes
from .models import ExpectedNote, PlayedNote
from .tempo import TempoResult, score_tempo

TREND_TEXT = {
    "sped up": "you sped up over the piece",
    "slowed down": "you slowed down over the piece",
    "steady": "you stayed steady",
}
SHARP_NAMES =["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    """Name of a played key, e.g. 60 -> "C4". Played notes have no sheet spelling, so
    black keys are always written with sharps."""
    return f"{SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def format_beat(beat: float) -> str:
    """2.0 -> "2", 2.5 -> "2.5"."""
    return f"{round(beat, 2):g}"


def _location(note: ExpectedNote) -> str:
    return f"Measure {note.measure}, beat {format_beat(note.beat)}"


def _wrong_note_lines(pairs: list[AlignedPair]) -> list[str]:
    """One line for every wrong or missed note. Correct notes are never listed."""
    lines = []
    for pair in pairs:
        if pair.kind == MISSED:
            lines.append(f"{_location(pair.expected)}: expected {pair.expected.name}, missed")
        elif pair.kind not in (CORRECT, EXTRA):
            line = (f"{_location(pair.expected)}: expected {pair.expected.name}, "
                    f"played {midi_to_name(pair.played.midi)}")
            if pair.kind == WRONG_OCTAVE:
                line += " (right note, wrong octave)"
            lines.append(line)
    return lines


def _extra_note_lines(pairs: list[AlignedPair]) -> list[str]:
    """Describe where each extra note was played, relative to the last expected note."""
    lines = []
    previous = None   # the most recent expected note we passed
    for pair in pairs:
        if pair.expected is not None:
            previous = pair.expected
        if pair.kind == EXTRA:
            name = midi_to_name(pair.played.midi)
            if previous is None:
                lines.append(f"Extra note {name}, before the first note")
            else:
                lines.append(f"Extra note {name}, after measure {previous.measure}, "
                             f"beat {format_beat(previous.beat)}")
    return lines


def _tempo_lines(result: TempoResult) -> list[str]:
    if not result.measured:
        return ["Tempo: not enough correctly played notes to measure."]
    return [
        f"Target tempo: {result.target_bpm:.0f} BPM",
        f"Your average tempo: {result.average_bpm:.0f} BPM",
        f"Average timing error: {result.average_error_ms:.0f} ms",
        "Tempo trend: " + TREND_TEXT[result.trend],
    ]


def build_report(expected: list[ExpectedNote], played: list[PlayedNote],
                 tempo_marks: list[tuple[float, float]]) -> str:
    """Compare a performance with the music and return the full feedback text."""
    played = drop_implausible_notes(played, expected)
    pairs = drop_echo_extras(align(expected, played))
    correct = sum(1 for p in pairs if p.kind == CORRECT)
    total = len(expected)

    # A few stray sounds are forgiven (a chair creak, a note's echo), but a flood of
    # extra notes is not: every extra note beyond the allowance counts as a wrong note.
    extra_count = sum(1 for p in pairs if p.kind == EXTRA)
    allowance = math.ceil(config.FREE_EXTRA_NOTES_RATIO * total)
    penalised_extras = max(0, extra_count - allowance)
    out_of = total + penalised_extras
    percent = correct / out_of * 100 if out_of else 0.0

    lines = [f"Notes correct: {correct} / {out_of} ({percent:.0f}%)"]
    if penalised_extras:
        lines.append(f"({penalised_extras} extra notes beyond the {allowance} allowed "
                     "count as wrong, so the total is higher than the music's note count.)")

    tempo_result = score_tempo(pairs, tempo_marks)     # None when no numeric tempo
    if tempo_result is not None:
        lines.append("")
        lines.extend(_tempo_lines(tempo_result))

    lines.append("")
    wrong = _wrong_note_lines(pairs)
    if wrong:
        lines.extend(wrong)
    elif penalised_extras:
        lines.append("No notes were wrong or missed, but too many extra notes were played.")
    else:
        lines.append("No wrong or missed notes.")

    extras = _extra_note_lines(pairs)
    if extras:
        lines.append("")
        if penalised_extras:
            lines.append(f"Extra notes (not in the music; {allowance} are forgiven, "
                         f"the other {penalised_extras} count as wrong):")
        else:
            lines.append("Extra notes (not in the music, not counted against your score):")
        lines.extend(extras)
    return "\n".join(lines)

