"""Scoring rules on exact (non-audio) input: order matters, and a barrage is not full marks."""

import random

from evenkeys.feedback import build_report
from evenkeys.models import ExpectedNote, PlayedNote

EIGHT = [60, 62, 64, 65, 67, 69, 71, 72]     # C D E F G A B C


def _report(expected_midis, played_midis):
    expected = [ExpectedNote(m, str(m), float(i), 1.0, 1, i + 1.0)
                for i, m in enumerate(expected_midis)]
    played = [PlayedNote(m, i * 0.6) for i, m in enumerate(played_midis)]
    return build_report(expected, played, [])


def test_order_matters():
    """The right notes in the wrong order are not full marks."""
    assert "Notes correct: 8 / 8" in _report(EIGHT, EIGHT)
    assert "Notes correct: 1 / 8" in _report(EIGHT, EIGHT[::-1])
    assert "Notes correct: 7 / 8" in _report(EIGHT, [60, 64, 62, 65, 67, 69, 71, 72])  # one swap


def test_barrage_hiding_the_right_notes_is_not_full_marks():
    rng = random.Random(1)
    noise = [rng.randint(55, 80) for _ in range(40)]
    for position, midi in zip([3, 9, 15, 21, 27, 33, 38, 39], EIGHT):
        noise[position] = midi                          # right notes hidden, in order
    report = _report(EIGHT, noise)
    assert "Notes correct: 8 / 8" not in report
    first_line = report.splitlines()[0]
    percent = int(first_line.split("(")[1].split("%")[0])
    assert percent < 25                                  # a barrage scores badly
    assert "count as wrong" in report
