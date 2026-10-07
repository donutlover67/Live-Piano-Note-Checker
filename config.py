"""Settings for evenkeys. Change values here; nothing else needs editing."""

# ---------------------------------------------------------------- audio
SAMPLE_RATE = 22050        # samples per second used for recording and analysis
HOP_LENGTH = 512           # samples between analysis frames (512 / 22050 = ~23 ms)

# ---------------------------------------------------------------- onset detection
# How big a jump in loudness must be before it counts as a new note.
# LOWER = more sensitive (finds quiet notes, but may find false notes from noise).
# HIGHER = less sensitive (ignores noise, but may miss soft notes).
ONSET_DELTA = 0.07

# ---------------------------------------------------------------- pitch detection
PITCH_FMIN = "A1"          # lowest note we look for (55 Hz). Lower notes are not detected.
PITCH_FMAX = "C8"          # highest piano key
# Each note is analysed on its own short slice of audio, so notes can't influence
# each other. (Analysing the whole recording at once made pyin "correct" big leaps
# between notes by an octave, because it assumes the pitch changes smoothly.)
# The analysis window is short (1024 samples = 46 ms) and moves in small steps, so that
# fast notes (a sixteenth note at 140 BPM lasts only ~0.1 s) still give several clean
# measurements. A longer window blurred a note with its neighbours and mislabelled
# fast passages by a semitone. 1024 samples is the shortest that works for A1.
PITCH_FRAME_LENGTH = 1024
PITCH_HOP_LENGTH = 256     # samples between pitch measurements (256 / 22050 = ~12 ms)
PITCH_LEAD_SECONDS = 0.01    # start the slice this long before the detected onset
PITCH_SKIP_SECONDS = 0.02    # ignore the first frames of the slice (noisy "thump")
PITCH_END_TRIM_SECONDS = 0.02  # stop this long before the next note starts
PITCH_WINDOW_SECONDS = 0.35  # only listen to the first part of each note (clearest pitch)

# Grading starts at the first sound that is at least this fraction as loud as a typical
# note. Quieter sounds before it (key clicks, hands settling) are ignored.
FIRST_NOTE_MIN_LOUDNESS_RATIO = 0.3

# Extra notes (played but not in the music) are forgiven up to this fraction of the number
# of notes in the section, rounded up. Beyond that, each extra note counts as a wrong note.
# This stops a flood of notes from scoring well just because the right ones are in there.
FREE_EXTRA_NOTES_RATIO = 0.25

# An "extra" note with the same pitch as the played note just before or after it, within
# this many seconds, is treated as a second detection of the same key press (an echo),
# not as a separate extra note.
ECHO_WINDOW_SECONDS = 0.5

# Detected notes further than this many octaves outside the range of the music
# are treated as noise (for example keyboard clicks) and ignored.
PITCH_OCTAVE_MARGIN = 2

# ---------------------------------------------------------------- tempo scoring
# We compare your speed in the first half of the piece with the second half.
# If they differ by more than this percentage, we say you sped up or slowed down.
TEMPO_CHANGE_THRESHOLD_PERCENT = 5.0

# ---------------------------------------------------------------- input / download
DOWNLOAD_TIMEOUT_SECONDS = 15

