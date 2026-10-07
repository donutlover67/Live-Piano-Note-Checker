"""The terminal program: steps 1-9 of the flow."""

from . import config
from .detect import AnalysisError, analyze_audio
from .feedback import build_report
from .hands import (MeasureRangeError, chord_warning, find_chords, keep_highest_notes,
                    parse_measure_range, select_hand, select_measures)
from .loader import LoadError, resolve_input
from .recorder import Recorder, RecordingError
from .score import describe, load_score

FILE_PROMPT = "Drag your sheet music file here (or paste a direct download link) and press Enter: "
MEASURES_PROMPT = "Which measures will you play? Press Enter for the whole piece, or type a range like 1-4: "
AFTER_PIECE_MENU = "Type 'again' to replay this piece, 'new' to load a different file, or 'quit' to exit."


def ask_for_file():
    """Steps 2-3: keep asking until a readable file is given. Returns a LoadedScore."""
    while True:
        try:
            path = resolve_input(input(FILE_PROMPT))
            score = load_score(path)
        except LoadError as error:
            print(error)
            continue
        print()
        print(describe(score))
        for warning in score.warnings:
            print(warning)
        print()
        return score


def ask_for_hand(score):
    """Step 4: choose a hand. Returns all of that hand's notes."""
    while True:
        answer = input("Which hand will you play? (R/L): ").strip().upper()
        if answer not in ("R", "L"):
            continue
        try:
            return select_hand(score, answer)
        except LoadError as error:
            print(error)


def ask_for_section(hand_notes):
    """Steps 4-5: choose which measures to play, then handle chords.

    Only the measures you say you will play are checked; the rest is ignored.
    Returns (expected notes one at a time, a label like "measures 1-4"), or None if
    the user declined the chord warning.
    """
    while True:
        try:
            measure_range = parse_measure_range(input(MEASURES_PROMPT))
            notes = select_measures(hand_notes, measure_range)
            break
        except MeasureRangeError as error:
            print(error)
    if measure_range is None:
        label = "the whole piece"
    elif measure_range[0] == measure_range[1]:
        label = f"measure {measure_range[0]}"
    else:
        label = f"measures {measure_range[0]}-{measure_range[1]}"

    count, first_measure = find_chords(notes)
    if count == 0:
        return notes, label
    while True:
        answer = input(chord_warning(count, first_measure) + " ").strip().upper()
        if answer == "N":
            return None
        if answer == "Y":
            return keep_highest_notes(notes), label


def ask_for_new_section(hand_notes, current_label):
    """After 'again': keep the same section, or choose a different one.

    Returns None to keep the current section, or (notes, label) for a new one.
    """
    while True:
        answer = input(f"Keep playing the same section ({current_label})? (Y/N): ").strip().upper()
        if answer == "Y":
            return None
        if answer == "N":
            break
    while True:                           # a declined chord warning just asks again
        section = ask_for_section(hand_notes)
        if section is not None:
            return section


def wait_for(commands: tuple[str, ...], prompt_again: str) -> str:
    """Block until the user types one of `commands` (ignoring case and spaces at the ends).

    Returns the command that was typed.
    """
    while True:
        typed = input().strip().lower()
        if typed in commands:
            return typed
        print(prompt_again)


def record_and_report(notes, tempo_marks) -> None:
    """Steps 6-8: record one attempt and print the feedback.

    While recording, 's' finishes the take and 'r' throws it away and goes back to waiting for 's'.
    The notes (file, hand and measures) stay exactly the same.
    """
    while True:
        print("Type 's' and press Enter when ready.")
        wait_for(("s",), "Please type s and press Enter to start.")
        recorder = Recorder()
        try:
            recorder.start()
        except RecordingError as error:
            print(error)       # e.g. no microphone: go back and let the user try again
            continue

        try:
            print("Recording... type 's' and press Enter when finished, "
                  "or 'r' to throw this take away and start over.")
            print("Start playing whenever you are ready: grading begins at your first note.")
            command = wait_for(("s", "r"), "Type 's' to finish, or 'r' to start over.")
        finally:
            audio = recorder.stop()    # always release the microphone, even on Ctrl+C

        if command == "r":
            print("Recording discarded.")
            print()
            continue                   # back to the top: wait for 's' again
        break

    print("Analyzing... (the first analysis in a session can take a little longer)")
    try:
        played = analyze_audio(audio, config.SAMPLE_RATE)
    except AnalysisError as error:
        print(error)
        return
    print()
    print(build_report(notes, played, tempo_marks))
    print()


def practice(hand_notes, notes, label, tempo_marks) -> str:
    """Steps 6-9 for one file and hand. Returns 'new' or 'quit'.

    hand_notes is everything the chosen hand plays; notes is the section being practised.
    """
    while True:
        record_and_report(notes, tempo_marks)
        print(AFTER_PIECE_MENU)
        while True:
            choice = input().strip().lower()
            if choice == "again":
                # Same file and hand, but the user may want a different section.
                new_section = ask_for_new_section(hand_notes, label)
                if new_section is not None:
                    notes, label = new_section
                break               # back to the top: record again
            if choice in ("new", "quit"):
                return choice
            print(AFTER_PIECE_MENU)


def main() -> None:
    print("evenkeys: piano practice checker")
    print()
    try:
        while True:
            score = ask_for_file()
            hand_notes = ask_for_hand(score)
            section = ask_for_section(hand_notes)
            if section is None:
                continue                        # chord warning declined: back to step 2
            notes, label = section
            if practice(hand_notes, notes, label, score.tempo_marks) == "quit":
                break
    except (KeyboardInterrupt, EOFError):
        print()
    print("Goodbye!")
