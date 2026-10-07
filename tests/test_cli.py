"""The whole terminal flow, with typed input and the microphone replaced by fakes."""

import pytest

from conftest import perform

from evenkeys import cli


class FakeRecorder:
    """Stands in for the microphone. `audio` is what 'stop' returns."""
    audio = None          # set by each test
    error = None          # set to a RecordingError to simulate no microphone
    starts = 0

    def start(self):
        FakeRecorder.starts += 1
        if FakeRecorder.error:
            raise FakeRecorder.error

    def stop(self):
        return FakeRecorder.audio


@pytest.fixture
def terminal(monkeypatch, capsys):
    """Returns run(inputs) -> everything printed. Running out of input = Ctrl+D."""
    FakeRecorder.audio = None
    FakeRecorder.error = None
    FakeRecorder.starts = 0
    monkeypatch.setattr(cli, "Recorder", FakeRecorder)

    def run(*inputs):
        lines = iter(inputs)

        def fake_input(prompt=""):
            print(prompt, end="")
            try:
                return next(lines)
            except StopIteration:
                raise EOFError
        monkeypatch.setattr("builtins.input", fake_input)
        cli.main()
        return capsys.readouterr().out
    return run


def piece(samples, name="simple_piece.musicxml"):
    return f'"{samples / name}" '       # quoted and with a trailing space, like a drag


def test_full_session_with_again_and_quit(terminal, samples, right_hand):
    FakeRecorder.audio = perform(right_hand)
    out = terminal(piece(samples), "R", "", "s", "s",
                   "again", "Y", "s", "s", "quit")
    assert "Title: Simple Piece" in out
    assert "Measures: 4" in out
    assert out.count("Notes correct: 14 / 14 (100%)") == 2       # 'again' replayed it
    assert out.count("Type 's' and press Enter when ready.") == 2
    assert "Recording... type 's' and press Enter when finished" in out
    assert "Type 'again' to replay this piece, 'new' to load a different file, or 'quit' to exit." in out
    assert out.rstrip().endswith("Goodbye!")


def test_r_discards_the_take_and_restarts_with_the_same_setup(terminal, samples, right_hand):
    """Typing r while recording throws the take away and asks for s again. The file, hand
    and measures are not asked for again and the next take is graded on the same notes."""
    FakeRecorder.audio = perform(right_hand[:8])
    out = terminal(piece(samples), "R", "1-2", "s", "r", "s", "s", "quit")
    assert "Recording discarded." in out
    assert FakeRecorder.starts == 2                                  # recorded twice
    assert out.count("Type 's' and press Enter when ready.") == 2    # asked for s again
    assert out.count("Notes correct:") == 1                          # only the second take graded
    assert "Notes correct: 8 / 8 (100%)" in out                      # on measures 1-2, as before
    assert out.count("Drag your sheet music file here") == 1
    assert out.count("Which hand will you play?") == 1
    assert out.count("Which measures will you play?") == 1
