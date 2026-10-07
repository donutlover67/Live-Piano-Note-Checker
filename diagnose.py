"""Diagnostic tool: record one take, save it, and show what the detector heard.

Run with:   python -m evenkeys.diagnose

It asks for the file, hand and measures exactly like the main program, records one take,
saves it as last_recording.wav in the current folder, and prints every sound it detected
next to the notes it expected. It does not change how the main program works.
"""

import librosa
import numpy as np
import soundfile as sf

from . import config
from .align import CORRECT, align
from .cli import ask_for_file, ask_for_hand, ask_for_section
from .detect import (detect_onsets, detect_pitches, drop_implausible_notes,
                     drop_sounds_before_first_note)
from .feedback import midi_to_name
from .recorder import Recorder, RecordingError

WAV_NAME = "last_recording.wav"


def show_take(audio: np.ndarray, notes) -> None:
    """Print what was detected, step by step."""
    sr = config.SAMPLE_RATE
    onsets = detect_onsets(audio, sr)
    kept = drop_sounds_before_first_note(audio, sr, onsets)
    played = detect_pitches(audio, sr, kept)

    rms = librosa.feature.rms(y=audio, frame_length=config.PITCH_FRAME_LENGTH,
                              hop_length=config.HOP_LENGTH)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=config.HOP_LENGTH)

    print(f"\nRecording length: {len(audio) / sr:.1f} s, "
          f"{len(onsets)} sound starts found, {len(kept)} after trimming the beginning.")
    print("\nEvery sound start detected (after trimming):")
    print("  time(s)  note   loudness")
    for note in played:
        window = (times >= note.time) & (times <= note.time + 0.2)
        print(f"  {note.time:7.2f}  {midi_to_name(note.midi):5}  {rms[window].max():.3f}")

    print("\nHow they were matched with the music:")
    print("  result        expected   played    time(s)")
    for pair in align(notes, drop_implausible_notes(played, notes)):
        expected = pair.expected.name if pair.expected else "-"
        heard = midi_to_name(pair.played.midi) if pair.played else "-"
        when = f"{pair.played.time:.2f}" if pair.played else ""
        print(f"  {pair.kind:13} {expected:10} {heard:9} {when}")


def main() -> None:
    score = ask_for_file()
    hand_notes = ask_for_hand(score)
    section = ask_for_section(hand_notes)
    if section is None:
        return
    notes, _label = section

    input("Press Enter to start recording, play, then press Enter again to stop: ")
    recorder = Recorder()
    try:
        recorder.start()
    except RecordingError as error:
        print(error)
        return
    input("Recording... ")
    audio = recorder.stop()

    sf.write(WAV_NAME, audio, config.SAMPLE_RATE)
    print(f"Saved {WAV_NAME}")
    show_take(audio, notes)


if __name__ == "__main__":
    main()
