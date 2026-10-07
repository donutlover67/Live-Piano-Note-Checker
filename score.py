"""Read a MusicXML or MIDI file with music21 and produce a LoadedScore."""

from pathlib import Path

from music21 import converter, tempo

from .loader import LoadError, MIDI_EXTENSIONS
from .models import ExpectedNote, LoadedScore

MIDDLE_C = 60  # MIDI number of C4; used to split one-track MIDI files into hands


def _display_name(pitch) -> str:
    """Spelling as written on the sheet, e.g. "F#4". music21 writes flats as "-", we use "b"."""
    return pitch.nameWithOctave.replace("-", "b")


def _notes_from_part(part) -> list[ExpectedNote]:
    """Collect every note in one staff/part. Chords give one ExpectedNote per pitch."""
    notes = []
    times_seen = {}   # measure number -> how many times we have met it so far
    previous_number = None
    repeat_sign_measure = 0   # the measure holding the repeat sign we last jumped back from
    for measure in part.getElementsByClass("Measure"):
        # With repeats expanded the same measure number appears again; count which pass this is.
        repeat_pass = times_seen.get(measure.number, 0)
        # A repeat shows up as the measure numbers jumping backwards (or standing still, for a
        # one-measure repeat). The measure just before the jump is the one with the repeat sign.
        if previous_number is not None and measure.number <= previous_number:
            repeat_sign_measure = previous_number
        previous_number = measure.number
        times_seen[measure.number] = repeat_pass + 1
        for element in measure.recurse().notes:
            if element.duration.isGrace:
                continue  # grace notes have no real length; skip them
            # Absolute start in quarter-note beats from the very beginning of the part.
            start = float(element.getOffsetInHierarchy(part))
            # Beat inside the measure. paddingLeft handles a short first measure (pickup).
            beat = start - float(measure.offset) + 1 + float(measure.paddingLeft)
            for single in element.notes if element.isChord else [element]:
                # A tied note that continues an earlier one is not played again.
                if single.tie is not None and single.tie.type in ("stop", "continue"):
                    continue
                notes.append(ExpectedNote(
                    midi=single.pitch.midi,
                    name=_display_name(single.pitch),
                    start_beat=start,
                    duration=float(element.quarterLength),
                    measure=measure.number,
                    beat=beat,
                    repeat_pass=repeat_pass,
                    repeat_from=repeat_sign_measure if repeat_pass else 0,
                    measure_start=float(measure.offset),
                    measure_end=float(measure.offset) + float(measure.duration.quarterLength),
                ))
    notes.sort(key=lambda n: (n.start_beat, n.midi))
    return notes


def _tempo_marks(score) -> list[tuple[float, float]]:
    """Numeric tempo markings only, as (beat, quarter-note BPM). Text like "Allegro" is ignored."""
    marks = {}
    for mark in score.recurse().getElementsByClass(tempo.MetronomeMark):
        # numberImplicit=True means music21 guessed a number from a word like "Allegro".
        if mark.number is None or mark.numberImplicit:
            continue
        marks[float(mark.getOffsetInHierarchy(score))] = float(mark.getQuarterBPM())
    return sorted(marks.items())


def _expand_repeats(score):
    """Play repeats out in full if music21 can; otherwise play the music as written."""
    try:
        return score.expandRepeats(), True
    except Exception:
        return score, False


def load_score(path: Path) -> LoadedScore:
    """Parse the file. Raises LoadError with a friendly message if it can't be read."""
    path = Path(path)
    is_midi = path.suffix.lower() in MIDI_EXTENSIONS
    try:
        parsed = converter.parse(str(path))
        if not hasattr(parsed, "parts"):          # a bare Stream: wrap it as one part
            raise ValueError("no parts found")
        score, _ = _expand_repeats(parsed)
        written_parts = [p for p in parsed.parts if len(p.recurse().notes) > 0]
        parts = [p for p in score.parts if len(p.recurse().notes) > 0]
        title = parsed.metadata.bestTitle if parsed.metadata is not None else None
        # music21 invents a title when the file has none: the file name, or "Music21 Fragment".
        if title in (path.name, path.stem, "Music21 Fragment"):
            title = None
        marks = _tempo_marks(score)
        # Count measures as printed on the sheet (before repeats were played out).
        num_measures = max((len(list(p.getElementsByClass("Measure"))) for p in written_parts),
                           default=0)
        played_measures = max((len(list(p.getElementsByClass("Measure"))) for p in parts),
                              default=0)
        hands, warnings = _split_hands(parts, is_midi)
    except LoadError:
        raise
    except Exception as error:
        raise LoadError(f"Could not read that file. It may be corrupted ({error}).") from None

    if not any(hands.values()):
        raise LoadError("No notes were found in that file.")
    return LoadedScore(title=title, num_measures=num_measures,
                       tempo_marks=marks, hands=hands, warnings=warnings,
                       has_repeats=played_measures > num_measures)


def _split_hands(parts, is_midi: bool):
    """Decide which notes belong to the right and left hand."""
    warnings = []
    if not parts:
        return {}, warnings

    if not is_midi:
        # MusicXML piano: music21 gives one part per staff, upper staff first.
        hands = {"R": _notes_from_part(parts[0])}
        if len(parts) > 1:
            hands["L"] = _notes_from_part(parts[1])
        return hands, warnings

    # MIDI with two or more note tracks: first = right hand, second = left hand.
    if len(parts) >= 2:
        if len(parts) > 2:
            warnings.append("This MIDI file has more than two note tracks; "
                            "only the first two are used (right hand, left hand).")
        return {"R": _notes_from_part(parts[0]), "L": _notes_from_part(parts[1])}, warnings

    # MIDI with a single track: split at middle C.
    everything = _notes_from_part(parts[0])
    warnings.append("Warning: this file has one track, so the hands were separated "
                    "automatically at middle C (C4 and above = right hand). "
                    "This may not match the sheet music exactly.")
    return {"R": [n for n in everything if n.midi >= MIDDLE_C],
            "L": [n for n in everything if n.midi < MIDDLE_C]}, warnings


def describe(score: LoadedScore) -> str:
    """The short summary printed after loading (step 3)."""
    lines = []
    if score.title:
        lines.append(f"Title: {score.title}")
    lines.append(f"Measures: {score.num_measures}")
    if score.has_repeats:
        lines.append("Repeat signs found: the whole piece is played with its repeats. A measure "
                     "range includes a repeat only if it includes the measure with the repeat sign.")
    if score.tempo_marks:
        bpms = []
        for _, bpm in score.tempo_marks:
            text = f"{bpm:g}"
            if text not in bpms:
                bpms.append(text)
        lines.append("Tempo marking: " + ", ".join(bpms) + " BPM"
                     + (" (changes during the piece)" if len(score.tempo_marks) > 1 else ""))
    else:
        lines.append("No numeric tempo marking found: tempo will not be scored.")
    return "\n".join(lines)
