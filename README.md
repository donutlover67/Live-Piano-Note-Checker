# Live Piano Note Checker

A terminal-based piano practice checker. (The Python package inside is called `evenkeys`, so you run it with `python -m evenkeys`.) You give it sheet music (MusicXML or MIDI), play
one hand's part on a piano, and it listens through your computer's microphone. It then tells
you which notes were wrong or missed, and, if the music has a tempo marking, how well you
kept time.

Example output (from synthetic audio with a planted missed note, a planted wrong note and a gradual slow-down):

```
Notes correct: 12 / 14 (86%)

Target tempo: 100 BPM
Your average tempo: 91 BPM
Average timing error: 288 ms
Tempo trend: you slowed down over the piece

Measure 1, beat 3: expected E4, missed
Measure 2, beat 2: expected F#4, played G4
```

## Install

Requires **Python 3.11 or newer**, [Git](https://git-scm.com/), and a microphone.

```bash
git clone https://github.com/donutlover67/Live-Piano-Note-Checker.git
cd Live-Piano-Note-Checker
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

(`pytest` is in `requirements.txt` only so you can run the tests.) On macOS and Windows,
your terminal must be allowed to use the microphone in the system privacy settings.

## Run

From the project folder (the one that contains the `evenkeys/` package):

```bash
python -m evenkeys
```

Or, in VS Code, press **Run** on `run.py` in the project folder (or type `python run.py`). Do not press Run on `evenkeys/__main__.py`: it only works when started with `-m`.

The program then walks you through:

1. **Load a file.** Drag a `.musicxml`, `.xml`, `.mxl`, `.mid` or `.midi` file into the
   terminal, or paste a direct download link to one. Quotes and trailing spaces added by
   dragging are removed.
2. **Choose a hand** (`R` or `L`).
3. **Choose measures.** Type a range like `1-4` (or `3` for one measure) if you will only play part of the piece, or press Enter for the whole piece. Only those measures are checked; the rest is ignored.
4. If those measures have chords, you are warned and can continue (the highest note of each chord
   is used) or go back and load a different file.
5. Type `s` and press Enter to start recording, play, then type `s` and Enter again to stop. If you make a mess of it, type `r` while recording to throw the take away; you are asked for `s` again, with the same file, hand and measures.
6. Read the feedback, then type `again`, `new` or `quit`. After `again` you are asked whether to keep the same section. Answer `Y` to repeat it, or `N` to type a different range of measures (or press Enter for the whole piece). The file and hand stay the same. `new` loads a different file.

Try it with the files in `sample_music/`, for example `simple_piece.musicxml`.

### Getting a MusicXML file from MuseScore

1. Open your piece in MuseScore (free; musescore.org). Many pieces can be found on
   musescore.com or imslp.org, or you can enter them yourself.
2. **File → Export…**
3. Choose **MusicXML** (`.musicxml`, or compressed `.mxl`) as the format and save.
4. Drag that file into evenkeys.

Piano music should be one part with two staves. evenkeys treats the upper staff as the
right hand and the lower staff as the left hand.

## How it works

The code is split into one small module per step. Each file begins with a comment saying
what it does.

| Step | File | What happens |
|---|---|---|
| Read input | `loader.py` | Cleans the typed text (quotes, spaces, PowerShell's `& '...'`), checks the extension, downloads links. A link that isn't a direct file (wrong extension, error, or an HTML page) gives the "That link isn't a direct file" message. |
| Read the music | `score.py` | music21 parses the file. For each note we store: piano key number, the spelling on the sheet (e.g. `F#4`), start time in beats, length, measure and beat. Rests are not stored; they only affect timing. Repeat signs are expanded with music21's `expandRepeats()`; if that fails, the music is used as written. Tied notes count once, and grace notes are skipped. |
| Pick a hand | `score.py`, `hands.py` | MusicXML: upper staff = right hand, lower = left. MIDI with two note tracks: first = right, second = left. MIDI with one track: notes C4 and above = right hand, with a warning. |
| Choose measures | `hands.py` | `parse_measure_range` reads `1-4` / `3` / Enter, and `select_measures` keeps only the notes in those measures. So measures you don't play are never marked as missed. |
| Chord check | `hands.py` | Notes that start at the same moment are grouped. If any group has 2+ notes, you get the warning. If you continue, only the highest note of each chord is kept. |
| Record | `recorder.py` | A background thread reads the microphone while the main thread waits for you to type `s` to finish (or `r` to discard the take and start over). |
| Find note starts | `detect.py` | `librosa.onset.onset_detect` finds sudden rises in loudness. `ONSET_DELTA` in `config.py` sets the sensitivity. |
| Start at the first note | `detect.py` | You can take as long as you like to start playing. Sounds before your first note that are much quieter than a typical note (the click of pressing Enter, hands settling) are ignored: see `FIRST_NOTE_MIN_LOUDNESS_RATIO`. Only the start is trimmed. |
| Merge echoes | `align.py` | One key press can be detected twice (the note swells, the room echoes). An extra note with the same pitch as the played note just before or after it, within 0.5 s (`ECHO_WINDOW_SECONDS`), is dropped, so a wrong note is not also listed as an extra. A real repeated note played within 0.5 s of the same pitch would be merged too. |
| Ignore noise | `detect.py` | Detected notes more than 2 octaves (`PITCH_OCTAVE_MARGIN`) below the lowest or above the highest expected note are dropped. Keyboard clicks (pressing Enter, typing `stop`) otherwise show up as very low "notes". One octave off is still reported as a real mistake. |
| Find pitches | `detect.py` | For each note start, a slice of audio (until just before the next note) goes to `librosa.pyin`, which estimates the pitch. We take the median, convert to a MIDI key number, and round. Each note is analysed on its own slice with a short 46 ms window, not the whole recording at once (see "Things I learned" below). Notes below A1 are not detected. |
| Line up notes | `align.py` | Needleman-Wunsch alignment, explained below. |
| Tempo | `tempo.py` | Explained below. |
| Report | `feedback.py` | Builds the text shown at the end. |

All comparisons use MIDI key numbers, not note names, so E#4 and F4 (the same key) match.
The feedback shows the spelling from your sheet music for the expected note. Played notes
have no spelling, so black keys are shown as sharps.

### Alignment (Needleman-Wunsch)

Comparing note 1 with note 1, note 2 with note 2, and so on fails as soon as you skip a note:
everything after it would look wrong. Instead we build a table with one row per expected
note and one column per played note. Each cell holds the best score for lining up the notes
so far, from three possible moves:

- **Pair** an expected note with a played note: **+2** if same key, **-1** if different.
- **Expected note has no partner** → it was **missed** (-1).
- **Played note has no partner** → it is an **extra** note (-1).

Walking back from the bottom-right corner shows which moves gave the best score. Because
matches earn points, the later notes stay lined up after a miss, so one skipped note
costs exactly one error. A single wrong note (-1) is cheaper than "missed + extra" (-2), so
it is reported as one wrong note. The detailed explanation is at the top of `align.py`.

The same pitch class in a different octave (`midi % 12` equal) is still wrong, but gets the
label "right note, wrong octave". Extra notes are listed separately. A few are forgiven: up to 25% of the notes in your section, rounded up (`FREE_EXTRA_NOTES_RATIO`), so a stray click does not hurt you. Each extra beyond that counts as a wrong note and is added to the total, so a flood of notes cannot score well just because the right ones are somewhere in it. The score is `correct / (notes in the music + extra notes beyond the allowance)`.

### Tempo scoring

Only runs when the file has a **numeric** tempo marking (for example ♩ = 100). Words such as
"Allegro" are ignored. If there are several markings, `beat_to_seconds` adds up each stretch
at its own tempo, so tempo changes are handled. All tempos are converted to quarter-note BPM.

Only correctly matched notes are used (for a wrong or missed note we don't know when the
right one would have been played):

- The first correctly played note is time zero, so starting late is not an error.
- **Average timing error:** for each matched note, the gap between when you played it and when
  the music says it should fall (measured from that first note), averaged, in milliseconds.
- **Your average tempo:** beats between the first and last matched notes divided by the
  time you took.
- **Sped up / slowed down / steady:** your speed relative to the target in the first half of
  the matched notes, compared with the second half. More than 5% difference
  (`TEMPO_CHANGE_THRESHOLD_PERCENT`) counts as sped up or slowed down. Comparing with the
  target, not raw BPM, means that a tempo change written in the music is not mistaken for
  speeding up. Note that "steady" can still go with an average tempo far from the target,
  if you played steadily at the wrong speed; the average BPM line shows that.

"Beat" in the feedback always means a quarter-note beat counted from the start of the
measure (so 6/8 music is counted in quarter notes, and eighth notes fall on x.5).

### Settings

`evenkeys/config.py` holds everything you might want to change, most importantly
`ONSET_DELTA` (lower finds quieter notes but also more noise; higher is stricter).

## Tests

```bash
pytest
```

(Run it with the virtual environment active. `python -m pytest` does the same.)

**Result: 21 passed** (17 tests, one of them run on 5 different inputs; about 20 seconds,
Python 3.12, music21 10.5, librosa 1.0). The tests are a small set that covers the rules
that matter most. They are not exhaustive.

There is probably no piano or microphone where you run tests, so `evenkeys/synth.py` creates
piano-like audio (a fundamental plus decaying overtones) from a list of notes and can plant
errors: wrong notes, missed notes, extra notes, wrong-octave notes, and tempo drift or a
uniform speed change. The tests play that audio through the real detection, alignment and
feedback code. The microphone and the keyboard are replaced by fakes only in `test_cli.py`.

| Test file | Covers |
|---|---|
| `test_loader.py` | Quoted and spaced paths from dragging a file (including PowerShell's format), and links that are not direct files |
| `test_score_and_hands.py` | E#4 and F4 are the same key; the chord warning text and counts; a measure range includes a repeat only if its repeat sign is in the range |
| `test_pipeline.py` | Each planted error is reported exactly (wrong, missed, extra, wrong octave); a missed note early in the piece reports only that note; E#4 matches F4; tempo is skipped without a numeric marking; a fast run of notes is read correctly |
| `test_align_tempo.py` | The right notes in the wrong order are not full marks; a barrage of notes hiding the right ones is not full marks |
| `test_cli.py` | A whole session including `again`; typing `r` discards a take and restarts with the same measures |

Sample files in `sample_music/` come from `python tests/make_samples.py`.

**What the tests do not show:** they use synthetic audio. I have not been able to test with a
real piano, so accuracy on real recordings is untested. See limitations.

## Things I learned while building it

- **pyin can "correct" big leaps by an octave.** Run over a whole recording, it assumes the
  pitch moves smoothly, so a jump from D4 up to C6 was reported as C5. Raising its
  jump limit instead made it fail completely for some settings. The fix is to analyse each
  note on its own slice of audio.
- **Short notes need a short analysis window.** With a 93 ms window, fast passages (sixteenth notes at 100+ BPM, like the run in Rondo alla Turca) were mislabelled by a semitone, even on perfect synthetic audio, because the window reached into neighbouring notes. A 46 ms window with small steps fixed it from 60 to 160 BPM (see limitations for faster). Found when a correctly played run was marked wrong.
- **A change of tempo written in the music looked like speeding up** until the trend compared
  speed with the target tempo, not with raw BPM. (Found by a test.)
- **Abrupt note endings are heard as new notes** by the onset detector, so the synthetic notes
  fade out like a piano damper.

## Known limitations

- **Single notes only.** For chords, only the highest expected note is checked, and the
  detector does not try to find several notes at once.
- **Sustain pedal and ringing notes blur things.** An extra note struck on top of another note
  that is still ringing can be misread (in my tests, as the ringing note or as the wrong
  octave). The tests plant extra notes in silent gaps for this reason. Holding the pedal
  through several notes will likely cause missed or wrong detections.
- **Background noise.** Noise can create false note starts, which show up as "extra notes"
  (harmless to the score, but cluttering). With synthetic white noise at 0.5% of full scale
  the detector found one false note, at 2% none, and at 5% and above several. Real rooms
  differ; adjust `ONSET_DELTA` and play close to the microphone.
- **Time resolution is about 23 ms** (one analysis frame), so very small timing errors
  can't be measured.
- **Ambiguous cases in alignment.** A wrong note placed right next to an extra note can't be
  told apart from each other (either could be "the wrong one"). With several identical notes
  in a row, if one is missed, the count is right but the reported position among them may
  be off by one.
- **Very fast passages.** On clean synthetic audio, a run of sixteenth notes was exact up to 160 BPM, but at 180 BPM (a note every 0.083 s) 3 of 28 notes were mislabelled. On a real piano it will be worse.
- **Pitch detection** looks for notes from A1 to C8 (lower notes are not detected) with a 46 ms analysis window, which is least
  reliable for the lowest notes. Real piano low notes have a weak fundamental, which can
  cause octave errors that I could not test with synthetic sound.
- **MIDI hand separation.** A one-track MIDI file is split at middle C, which won't match the
  sheet music for passages that cross it. Files with more than two note tracks use only the
  first two. MusicXML files with only one staff have no left hand.
- **Measure ranges and repeats.** Choosing the whole piece plays every repeat. For a range like `1-4`, a repeat is played only if the measure holding its repeat sign is inside the range (for example, a section repeated by a sign on measure 8 is played twice in `1-8` but once in `1-4`). The measure count shown is the number printed on the sheet. If a range includes a repeat sign but only part of the repeated section, the skipped measures are left out of the timing, so you are not marked for silence you never waited through (real rests are kept). A pickup measure is measure 0, so type `0-4` to include it. Repeat detection looks for measure numbers jumping backwards, which covers normal repeats and endings; unusual jumps (D.C., D.S., codas) are handled by music21's expansion but are not tested here.
- **Repeats** are expanded when music21 can do it. If it can't, the piece is played through as
  written, with no repeats, and measure numbers on repeated passes are the sheet's numbers.
- **Not handled:** grace notes (skipped), trills and ornaments, and recordings with several
  instruments.
- **Alignment time** grows with (notes played × notes expected); I only tested pieces of a
  few dozen notes.
- The first analysis in a session takes a few seconds longer while librosa prepares itself.
- Only the default microphone is used.

## Project layout

```
run.py               launcher: press Run on this file in VS Code
evenkeys/            the package (run with python -m evenkeys)
  config.py          settings
  models.py          the small data types
  loader.py          file path / link handling
  score.py           music21 reading, hands
  hands.py           hand selection and chord check
  recorder.py        background microphone recording
  detect.py          onset and pitch detection
  align.py           Needleman-Wunsch alignment
  tempo.py           tempo scoring
  feedback.py        the report
  synth.py           synthetic audio for testing
  cli.py             the terminal flow
  diagnose.py        developer tool: record a take and show what was detected
tests/               pytest tests and make_samples.py
sample_music/        small generated test pieces
requirements.txt     libraries to install
pytest.ini           test settings
LICENSE, .gitignore
```

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Bryan Xia.
