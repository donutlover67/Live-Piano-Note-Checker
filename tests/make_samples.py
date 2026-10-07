"""Creates the small test files in sample_music/.

Run from the project folder:   python tests/make_samples.py

Each piece is written as a list of measures; each measure is a list of
(note name, length in quarter-note beats) pairs. Use a list of names for a chord.
"""

from pathlib import Path

from music21 import chord, clef, layout, meter, note, stream, tempo

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_music"

# --- the pieces --------------------------------------------------------------
Q = 1.0   # quarter note
H = 2.0   # half note

# Right hand: 4 measures of 4/4, single notes only. Contains F#4.
RIGHT_HAND = [
    [("C4", Q), ("D4", Q), ("E4", Q), ("F4", Q)],
    [("G4", Q), ("F#4", Q), ("E4", Q), ("D4", Q)],
    [("C5", Q), ("B4", Q), ("A4", Q), ("G4", Q)],
    [("C5", H), ("E4", H)],
]
LEFT_HAND = [
    [("C3", H), ("G3", H)],
    [("C3", H), ("G3", H)],
    [("F3", H), ("G3", H)],
    [("C3", 4.0)],
]
# Same right hand, but measure 2 has a chord (C4+E4+G4) on beat 1.
RIGHT_HAND_WITH_CHORD = [
    RIGHT_HAND[0],
    [(["C4", "E4", "G4"], Q), ("F#4", Q), ("E4", Q), ("D4", Q)],
    RIGHT_HAND[2],
    RIGHT_HAND[3],
]


def _make_part(measures, treble=True, bpm=None, part_class=stream.Part):
    """Build one staff from a list of measures."""
    part = part_class()
    for number, content in enumerate(measures, start=1):
        measure = stream.Measure(number=number)
        if number == 1:
            measure.append(clef.TrebleClef() if treble else clef.BassClef())
            measure.append(meter.TimeSignature("4/4"))
            if bpm is not None and treble:
                measure.append(tempo.MetronomeMark(number=bpm))
        for pitches, length in content:
            if isinstance(pitches, list):
                element = chord.Chord(pitches, quarterLength=length)
            else:
                element = note.Note(pitches, quarterLength=length)
            measure.append(element)
        part.append(measure)
    return part


def write_piano_musicxml(path, right, left, bpm):
    """One piano part with two staves, like a real piano score."""
    score = stream.Score()
    upper = _make_part(right, treble=True, bpm=bpm, part_class=stream.PartStaff)
    lower = _make_part(left, treble=False, part_class=stream.PartStaff)
    score.insert(0, upper)
    score.insert(0, lower)
    score.insert(0, layout.StaffGroup([upper, lower], symbol="brace"))
    from music21 import metadata
    score.insert(0, metadata.Metadata(title=path.stem.replace("_", " ").title()))
    score.write("musicxml", fp=str(path))


def write_midi(path, tracks, bpm):
    """tracks: list of measure-lists; each becomes one MIDI track."""
    score = stream.Score()
    for index, measures in enumerate(tracks):
        score.insert(0, _make_part(measures, treble=(index == 0), bpm=bpm if index == 0 else None))
    score.write("midi", fp=str(path))


def write_midi_one_track(path, bpm):
    """A single track holding both hands (notes above and below middle C)."""
    # Interleave: one measure of right hand, then the same measure of left hand,
    # so the one track has notes on both sides of middle C.
    measures = [RIGHT_HAND[0], LEFT_HAND[0], RIGHT_HAND[1], LEFT_HAND[1]]
    write_midi(path, [measures], bpm)


def main():
    SAMPLE_DIR.mkdir(exist_ok=True)
    write_piano_musicxml(SAMPLE_DIR / "simple_piece.musicxml", RIGHT_HAND, LEFT_HAND, bpm=100)
    write_piano_musicxml(SAMPLE_DIR / "no_tempo.musicxml", RIGHT_HAND, LEFT_HAND, bpm=None)
    write_piano_musicxml(SAMPLE_DIR / "chords_right_hand.musicxml", RIGHT_HAND_WITH_CHORD, LEFT_HAND, bpm=100)
    write_midi(SAMPLE_DIR / "two_tracks.mid", [RIGHT_HAND, LEFT_HAND], bpm=100)
    write_midi_one_track(SAMPLE_DIR / "one_track.mid", bpm=100)
    print("Wrote sample files to", SAMPLE_DIR)


if __name__ == "__main__":
    main()
