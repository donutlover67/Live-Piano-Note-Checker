"""Reading sheet music, choosing a hand, and the chord check."""

from music21 import bar, meter, note, stream

from evenkeys.hands import chord_warning, find_chords, select_hand
from evenkeys.score import load_score


def test_enharmonic_spellings_are_the_same_key():
    """E#4 and F4 are the same piano key, so their MIDI numbers must be equal."""
    assert note.Note("E#4").pitch.midi == note.Note("F4").pitch.midi == 65
    assert note.Note("B#3").pitch.midi == note.Note("C4").pitch.midi == 60


def test_chord_warning_appears_with_correct_counts(samples):
    score = load_score(samples / "chords_right_hand.musicxml")
    notes = select_hand(score, "R")
    count, first_measure = find_chords(notes)
    assert (count, first_measure) == (1, 2)
    assert chord_warning(count, first_measure) == (
        "This part contains 1 places where multiple notes are played at once "
        "(first at measure 2). The program is designed for single notes and may "
        "not detect these accurately. Continue anyway? (Y/N):")


def _write_repeat_piece(tmp_path):
    """Measures 1-2 are repeated, then measure 3 follows: played as 1 2 1 2 3."""
    part = stream.Part()
    for number, pitch in enumerate(["C4", "D4", "E4"], start=1):
        measure = stream.Measure(number=number)
        if number == 1:
            measure.append(meter.TimeSignature("1/4"))
            measure.leftBarline = bar.Repeat(direction="start")
        if number == 2:
            measure.rightBarline = bar.Repeat(direction="end")
        measure.append(note.Note(pitch, quarterLength=1))
        part.append(measure)
    path = tmp_path / "repeat_range.musicxml"
    stream.Score([part]).write("musicxml", fp=str(path))
    return path


def test_measure_range_includes_a_repeat_only_if_its_repeat_sign_is_in_range(tmp_path):
    """Played order is 1 2 1 2 3. The repeat sign is on measure 2."""
    from evenkeys.hands import parse_measure_range, select_measures
    score = load_score(_write_repeat_piece(tmp_path))
    right = select_hand(score, "R")
    assert [n.name for n in right] == ["C4", "D4", "C4", "D4", "E4"]      # whole piece: with repeats

    def played(text):
        return [n.name for n in select_measures(right, parse_measure_range(text))]

    assert played("1-2") == ["C4", "D4", "C4", "D4"]     # repeat sign (measure 2) is in range
    assert played("2") == ["D4", "D4"]                    # the sign's own measure repeats
    assert played("1-3") == ["C4", "D4", "C4", "D4", "E4"]
    assert played("1") == ["C4"]                          # sign is on measure 2: outside, so once
    assert played("3") == ["E4"]


def _write_four_measure_repeat(tmp_path):
    """Played order 1 2 3 4 1 2 3 4, with the repeat sign on measure 4. One note per measure."""
    part = stream.Part()
    for number, pitch in enumerate(["C4", "D4", "E4", "F4"], start=1):
        measure = stream.Measure(number=number)
        if number == 1:
            measure.append(meter.TimeSignature("1/4"))
            measure.leftBarline = bar.Repeat(direction="start")
        if number == 4:
            measure.rightBarline = bar.Repeat(direction="end")
        measure.append(note.Note(pitch, quarterLength=1))
        part.append(measure)
    path = tmp_path / "four_repeat.musicxml"
    stream.Score([part]).write("musicxml", fp=str(path))
    return path
