"""Shared test helpers and fixtures."""

from pathlib import Path

import pytest

from evenkeys import config
from evenkeys.detect import analyze_audio
from evenkeys.feedback import build_report
from evenkeys.hands import select_hand
from evenkeys.score import load_score
from evenkeys.synth import expected_to_timed, plant_errors, synthesize

SAMPLES = Path(__file__).resolve().parent.parent / "sample_music"


@pytest.fixture(scope="session")
def samples():
    return SAMPLES


@pytest.fixture(scope="session")
def simple_score():
    return load_score(SAMPLES / "simple_piece.musicxml")


@pytest.fixture(scope="session")
def right_hand(simple_score):
    """14 expected notes: C4 D4 E4 F4 | G4 F#4 E4 D4 | C5 B4 A4 G4 | C5 E4"""
    return select_hand(simple_score, "R")


def perform(expected, bpm=100, staccato=False, **errors):
    """Synthesize a performance of `expected` with planted errors; return the audio.

    staccato=True cuts every note to 0.3 s so there is silence between notes. Tests
    that plant an extra note use it, so the extra note doesn't land on top of a note
    that is still ringing (which makes the pitch ambiguous, see README limitations).
    """
    timed = expected_to_timed(expected, bpm)
    if staccato:
        timed = [(m, s, min(d, 0.3)) for m, s, d in timed]
    return synthesize(plant_errors(timed, **errors))


def report_for(expected, tempo_marks=(), bpm=100, staccato=False, **errors):
    """The full pipeline on synthetic audio: audio -> notes -> alignment -> report text."""
    audio = perform(expected, bpm, staccato, **errors)
    played = analyze_audio(audio, config.SAMPLE_RATE)
    return build_report(expected, played, list(tempo_marks))
