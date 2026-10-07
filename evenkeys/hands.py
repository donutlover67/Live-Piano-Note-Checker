"""Step 4-5: pick one hand's notes, choose which measures, and deal with chords."""

import re
from collections import defaultdict
from dataclasses import replace

from .loader import LoadError
from .models import ExpectedNote, LoadedScore

# Matches "3" or "1-4" (spaces allowed around the dash).
MEASURE_RANGE_PATTERN = re.compile(r"^(\d+)\s*(?:-\s*(\d+))?$")


class MeasureRangeError(Exception):
    """Raised with a message that is safe to show directly to the user."""


def parse_measure_range(text: str) -> tuple[int, int] | None:
    """Turn what the user typed into (first measure, last measure).

    Nothing typed means the whole piece, returned as None.
    "3" means measure 3 only; "1-4" means measures 1 to 4.
    """
    text = text.strip()
    if not text:
        return None
    match = MEASURE_RANGE_PATTERN.match(text)
    if match is None:
        raise MeasureRangeError("Please type a range like 1-4, a single measure like 3, "
                                "or just press Enter for the whole piece.")
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    if last < first:
        raise MeasureRangeError("The range must go upwards, for example 1-4.")
    return first, last


def select_measures(notes: list[ExpectedNote],
                    measure_range: tuple[int, int] | None) -> list[ExpectedNote]:
    """Keep only the notes in the chosen measures (all notes if no range was given)."""
    if measure_range is None:
        return notes
    first, last = measure_range
    # A repeated pass of a measure is played only if the measure holding the repeat sign
    # is inside the range too. Otherwise the range is played once, as written.
    chosen = [n for n in notes
              if first <= n.measure <= last
              and (n.repeat_pass == 0 or first <= n.repeat_from <= last)]
    if not chosen:
        lowest = min(n.measure for n in notes)
        highest = max(n.measure for n in notes)
        raise MeasureRangeError(f"There are no notes in measures {first}-{last}. "
                                f"This part has measures {lowest} to {highest}.")
    return _close_gaps_from_skipped_music(notes, chosen)


def _close_gaps_from_skipped_music(all_notes: list[ExpectedNote],
                                   chosen: list[ExpectedNote]) -> list[ExpectedNote]:
    """Remove the time that skipped measures would leave between chosen ones.

    If a range includes a repeat sign but only part of the repeated section, playing the
    repeat jumps straight from the end of the range back to its start. The music in
    between is skipped, so the notes after the jump are moved earlier by that much.
    Otherwise the tempo and timing maths would count silence you never waited through.
    A gap with no skipped notes in it is a real rest, and is kept.
    """
    chosen_ids = {id(n) for n in chosen}
    skipped_starts = [n.start_beat for n in all_notes if id(n) not in chosen_ids]
    if not skipped_starts:
        return chosen

    # One entry per measure as played (a repeated measure is a separate entry).
    measures = {}
    for n in chosen:
        measures[(n.measure, n.repeat_pass)] = (n.measure_start, n.measure_end)
    shift_for = {}      # measure start -> how many beats to move its notes earlier
    shift = 0.0
    previous_end = None
    for start, end in sorted(measures.values()):
        if previous_end is not None and start > previous_end + 1e-6:
            if any(previous_end - 1e-6 <= s < start for s in skipped_starts):
                shift += start - previous_end
        shift_for[start] = shift
        previous_end = end
    return [replace(n, start_beat=n.start_beat - shift_for[n.measure_start]) for n in chosen]


def select_hand(score: LoadedScore, hand: str) -> list[ExpectedNote]:
    """Return the notes for 'R' or 'L'. Raises LoadError if that hand has no notes."""
    notes = score.hands.get(hand, [])
    if not notes:
        name = "right" if hand == "R" else "left"
        raise LoadError(f"This file has no notes for the {name} hand.")
    return notes


def _group_by_start(notes: list[ExpectedNote]) -> dict[float, list[ExpectedNote]]:
    """Group notes that start at the same moment. Rounding avoids tiny float differences."""
    groups = defaultdict(list)
    for note in notes:
        groups[round(note.start_beat, 3)].append(note)
    return groups


def find_chords(notes: list[ExpectedNote]) -> tuple[int, int | None]:
    """Count the places where 2+ notes start together.

    Returns (number of such places, measure number of the first one or None).
    """
    chords = [group for group in _group_by_start(notes).values() if len(group) > 1]
    if not chords:
        return 0, None
    first = min(chords, key=lambda group: group[0].start_beat)
    return len(chords), first[0].measure


def chord_warning(count: int, first_measure: int) -> str:
    """The exact question from the spec."""
    return (f"This part contains {count} places where multiple notes are played at once "
            f"(first at measure {first_measure}). The program is designed for single notes "
            "and may not detect these accurately. Continue anyway? (Y/N):")


def keep_highest_notes(notes: list[ExpectedNote]) -> list[ExpectedNote]:
    """Reduce every chord to its highest note, so the result is one note at a time."""
    groups = _group_by_start(notes)
    result = [max(group, key=lambda n: n.midi) for group in groups.values()]
    return sorted(result, key=lambda n: n.start_beat)
