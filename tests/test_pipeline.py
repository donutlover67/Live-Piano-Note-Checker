"""End to end on synthetic audio: plant an error, check the report says exactly that.

Expected right hand (index: note):
  0 C4  1 D4  2 E4  3 F4 | 4 G4  5 F#4  6 E4  7 D4 | 8 C5  9 B4  10 A4  11 G4 | 12 C5  13 E4
"""

from dataclasses import replace

from conftest import report_for

from evenkeys import config
from evenkeys.detect import analyze_audio


def wrong_lines(report):
    return [line for line in report.splitlines() if line.startswith("Measure")]


def test_wrong_note_reported(right_hand):
    report = report_for(right_hand, wrong={5: 67})          # F#4 -> G4
    assert "Notes correct: 13 / 14 (93%)" in report
    assert wrong_lines(report) == ["Measure 2, beat 2: expected F#4, played G4"]


def test_missed_note_reported(right_hand):
    report = report_for(right_hand, missed={8})              # C5 never played
    assert "Notes correct: 13 / 14 (93%)" in report
    assert wrong_lines(report) == ["Measure 3, beat 1: expected C5, missed"]


def test_wrong_octave_labelled(right_hand):
    report = report_for(right_hand, wrong_octave={6: 1})     # E4 -> E5
    assert wrong_lines(report) == [
        "Measure 2, beat 3: expected E4, played E5 (right note, wrong octave)"]
    assert "Notes correct: 13 / 14" in report


def test_extra_note_listed_but_not_penalised(right_hand):
    report = report_for(right_hand, staccato=True, extra=[(77, 0.9)])   # stray F5 between D4 and E4
    assert "Notes correct: 14 / 14 (100%)" in report
    assert "No wrong or missed notes." in report
    assert "Extra note F5, after measure 1, beat 2" in report


def test_missed_note_early_does_not_shift_the_rest(right_hand):
    """The key alignment test: miss note 1 of 14 and ONLY that note is reported."""
    report = report_for(right_hand, missed={1})              # D4 skipped
    assert wrong_lines(report) == ["Measure 1, beat 2: expected D4, missed"]
    assert "Notes correct: 13 / 14" in report


def test_e_sharp_matches_f(right_hand):
    """The sheet says E#4, the player plays the F key: this is correct."""
    expected = [replace(n) for n in right_hand]
    expected[3] = replace(expected[3], name="E#4")           # same key (65) as F4
    report = report_for(expected)
    assert "14 / 14" in report
    # ...and when it IS wrong, the sheet's spelling is what's shown.
    report = report_for(expected, wrong={3: 67})
    assert "expected E#4, played G4" in report


def test_tempo_skipped_without_numeric_marking(right_hand):
    report = report_for(right_hand, tempo_marks=[])
    assert "tempo" not in report.lower()
    assert "BPM" not in report


def _click(audio, at_seconds, amplitude=0.12):
    """Add a short noisy burst (like a key click) to audio at the given time."""
    import numpy as np
    rng = np.random.default_rng(1)
    start = int(at_seconds * config.SAMPLE_RATE)
    burst = rng.normal(0, amplitude, int(0.03 * config.SAMPLE_RATE)).astype(np.float32)
    audio = audio.copy()
    audio[start:start + len(burst)] += burst
    return audio


def test_fast_passage_pitches_are_exact():
    """Sixteenth notes at ~140 BPM (0.107 s each) with neighbouring semitones, like the
    run in Rondo alla Turca. A long analysis window mislabelled these by a semitone."""
    from evenkeys.synth import synthesize
    run = [85, 86, 85, 83, 81, 83, 81, 80, 78, 81, 80, 78, 77, 78, 80, 77,
           73, 75, 77, 73, 78, 77, 78, 80, 81, 80, 81, 83]
    spacing = 60 / 140 / 4
    audio = synthesize([(midi, i * spacing, spacing) for i, midi in enumerate(run)])
    assert [n.midi for n in analyze_audio(audio, config.SAMPLE_RATE)] == run
