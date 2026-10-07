"""Step 8 (middle): line up the played notes with the expected notes.

THE PROBLEM
  Expected:  C  D  E  F  G
  Played:    C  D     F  G        (the player skipped E)

  If we compared note 1 with note 1, note 2 with note 2, and so on, then F would be
  compared with E and G with F, and everything after the mistake would look wrong.
  We need to realise that only ONE note is missing and that F and G are fine.

THE SOLUTION: Needleman-Wunsch sequence alignment
  This is a dynamic-programming method, originally made to line up DNA sequences.
  We build a table with one row for each expected note and one column for each played
  note. Cell (i, j) holds the best score we can get by lining up the first i expected
  notes with the first j played notes. From any cell there are three moves:

    diagonal  pair expected note i with played note j
                 +2 if they are the same piano key        (correct)
                 -1 if they are different keys            (one wrong note)
    up        expected note i has no partner: it was MISSED      (-1)
    left      played note j has no partner: it is an EXTRA note  (-1)

  Each cell takes the best of the three moves. When the table is full, we walk
  backwards from the bottom-right corner, always going to the cell the best score
  came from. That path IS the alignment.

WHY THESE NUMBERS
  * A matching pair earns points, so the alignment wants to pair up equal notes.
    This is what keeps F and G paired with F and G in the example above.
  * A wrong note (-1) is cheaper than "missed + extra" (-2), so a single wrong note
    is reported as one wrong note and not as two separate problems.
  * A missed note costs one gap (-1), the same as in real life: one error.
"""

from dataclasses import dataclass

from . import config
from .models import ExpectedNote, PlayedNote

MATCH_SCORE = 2
MISMATCH_SCORE = -1
GAP_SCORE = -1

# The possible outcomes for one position in the alignment.
CORRECT = "correct"
WRONG = "wrong"
WRONG_OCTAVE = "wrong_octave"   # right note letter, wrong octave (still counts as wrong)
MISSED = "missed"
EXTRA = "extra"


@dataclass
class AlignedPair:
    kind: str
    expected: ExpectedNote | None   # None for an extra note
    played: PlayedNote | None       # None for a missed note


def align(expected: list[ExpectedNote], played: list[PlayedNote]) -> list[AlignedPair]:
    """Align the two sequences. Result is in time order, one entry per position."""
    m, n = len(expected), len(played)

    # score[i][j] = best score for the first i expected and first j played notes.
    score = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        score[i][0] = i * GAP_SCORE          # all expected notes missed
    for j in range(1, n + 1):
        score[0][j] = j * GAP_SCORE          # all played notes extra

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            same = expected[i - 1].midi == played[j - 1].midi
            diagonal = score[i - 1][j - 1] + (MATCH_SCORE if same else MISMATCH_SCORE)
            up = score[i - 1][j] + GAP_SCORE      # expected note missed
            left = score[i][j - 1] + GAP_SCORE    # extra played note
            score[i][j] = max(diagonal, up, left)

    # Walk back from the corner to the start, rebuilding which move was taken.
    result = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            same = expected[i - 1].midi == played[j - 1].midi
            diagonal = score[i - 1][j - 1] + (MATCH_SCORE if same else MISMATCH_SCORE)
            if score[i][j] == diagonal:           # ties prefer the diagonal
                result.append(AlignedPair(_pair_kind(expected[i - 1], played[j - 1]),
                                          expected[i - 1], played[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and score[i][j] == score[i - 1][j] + GAP_SCORE:
            result.append(AlignedPair(MISSED, expected[i - 1], None))
            i -= 1
        else:
            result.append(AlignedPair(EXTRA, None, played[j - 1]))
            j -= 1

    result.reverse()   # we built it from the end, so flip it into time order
    return result


def drop_echo_extras(pairs: list[AlignedPair]) -> list[AlignedPair]:
    """Remove "extra" notes that are really a second detection of a neighbouring note.

    One key press can be detected twice (the sound swells as the string and the piano
    body resonate, or the room echoes). The second detection has the same pitch as the
    note next to it and arrives moments later, so it shows up as an extra note, even
    when the note it echoes was itself wrong. An extra with the same pitch as the
    previous or next played note, within config.ECHO_WINDOW_SECONDS, is dropped.
    """
    # Every played note in time order: paired notes and extras alike.
    played = [p.played for p in pairs if p.played is not None]
    kept = []
    for pair in pairs:
        if pair.kind == EXTRA:
            position = played.index(pair.played)
            neighbours = played[max(0, position - 1):position] + played[position + 1:position + 2]
            if any(n.midi == pair.played.midi
                   and abs(n.time - pair.played.time) <= config.ECHO_WINDOW_SECONDS
                   for n in neighbours):
                continue
        kept.append(pair)
    return kept


def _pair_kind(expected: ExpectedNote, played: PlayedNote) -> str:
    """Classify a paired note. Pitch only: MIDI numbers, so E#4 and F4 are equal."""
    if expected.midi == played.midi:
        return CORRECT
    if expected.midi % 12 == played.midi % 12:    # same note letter, different octave
        return WRONG_OCTAVE
    return WRONG
