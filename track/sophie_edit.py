"""SOPHIE EDIT — 30-second cut-up edit built from whole bars of two user-supplied tracks
(HARD @ 84 BPM, Ponyboy @ 108 BPM; the user states they have permission to use them).
Bars are sliced on the detected beat grid and re-arranged with beat-repeats, reverse,
pitch-up stutters, filter build, tape stop, bitcrush and abrupt tempo switches.
Source audio is not stored in this repo.

    python3 sophie_edit.py PONY.m4a HARD.m4a
"""
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 44100
OUT_LEN = int(30.0 * SR)


def load(path):
    with tempfile.TemporaryDirectory() as d:
        o = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "2", str(o)],
                       check=True)
        with wave.open(str(o)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768


PONY, HARD = load(sys.argv[1]), load(sys.argv[2])
# beat grids measured from the sources (onset-flux comb + autocorrelation)
GRID = {"hard": (HARD, 84.0, 0.02), "pony": (PONY, 108.0, 1.88)}


def beats(src, bar, b0=0.0, nb=4.0):
    """slice nb beats starting at beat b0 of bar `bar` from source `src`"""
    x, bpm, phase = GRID[src]
    beat = 60 / bpm
    a = int(round((phase + bar * 4 * beat + b0 * beat) * SR))
    return x[a:a + int(round(nb * beat * SR))].copy()


def beat_len(src, nb=1.0):
    return int(round(nb * 60 / GRID[src][1] * SR))


def declick(x, ms=2.0):
    n = min(len(x) // 2, int(ms / 1000 * SR))
    if n:
        x[:n] *= np.linspace(0, 1, n)[:, None]
        x[-n:] *= np.linspace(1, 0, n)[:, None]
    return x


def repitch(x, semis):
    idx = np.arange(0, len(x) - 1, 2 ** (semis / 12))
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def loop_to(x, n):
    x = declick(x.copy())
    return np.tile(x, (int(np.ceil(n / len(x))), 1))[:n]


def stutter(x, divisions, pitch_rise=0.0):
    """chop x into `divisions` repeats of its head; optional rising pitch per repeat"""
    n = len(x)
    s = n // divisions
    out = []
    for i in range(divisions):
        p = x[:s].copy()
        if pitch_rise:
            p = loop_to(repitch(p, pitch_rise * i / max(1, divisions - 1)), s)
        out.append(declick(p))
    y = np.concatenate(out)
    return np.pad(y, ((0, n - len(y)), (0, 0)))


def sweep_lp(x, f0, f1, q=2.5, block=256):
    y = np.zeros_like(x)
    nb = int(np.ceil(len(x) / block))
    for c in (0, 1):
        zi = np.zeros(2)
        for i in range(nb):
            f = f0 * (f1 / f0) ** ((i / max(1, nb - 1)) ** 2)
            w = 2 * np.pi * min(f, SR * 0.45) / SR
            al, cs = np.sin(w) / (2 * q), np.cos(w)
            b = np.array([(1 - cs) / 2, 1 - cs, (1 - cs) / 2]) / (1 + al)
            a = np.array([1, -2 * cs / (1 + al), (1 - al) / (1 + al)])
            seg = x[i * block:(i + 1) * block, c]
            y[i * block:i * block + len(seg), c], zi = signal.lfilter(b, a, seg, zi=zi)
    return y


def tape_stop(x):
    n = len(x)
    speed = (1 - np.linspace(0, 1, n)) ** 1.6
    pos = np.cumsum(speed)
    pos -= pos[0]
    return np.stack([np.interp(pos, np.arange(n), x[:, c]) for c in (0, 1)], 1)


def crush(x, bits=5, hold=5):
    q = 2 ** bits
    return np.repeat(np.round(x[::hold] * q) / q, hold, axis=0)[:len(x)]


def rms(x):
    return np.sqrt((x ** 2).mean())


# ------------------------------------------------------------------ the edit
seq = []

# 1) HARD bar 4 — filtered build opening up into the drop
seq.append(("hard", sweep_lp(beats("hard", 4), 300, 18000)))
# 2) HARD bars 5-6 — the drop, untouched
seq.append(("hard", beats("hard", 5, 0, 8)))
# 3) HARD bar 9 — cut-up: beat 1, beat 2, beat 1 as 8th-stutter pitched up an octave, beat 4 reversed
b = [beats("hard", 9, i, 1) for i in range(4)]
seq.append(("hard", np.concatenate([
    declick(b[0]), declick(b[1]),
    stutter(loop_to(repitch(b[0][:beat_len("hard", 0.5)], 12), beat_len("hard")), 4),
    declick(b[3][::-1].copy()),
])))
# 4) HARD bar 10 — straight, last beat tape-stops into the tempo switch
x = beats("hard", 10)
tl = beat_len("hard")
x[-tl:] = tape_stop(x[-tl:])
seq.append(("hard", x))
# 5) PONY bars 48-49 — switch to 108 BPM, straight
seq.append(("pony", beats("pony", 48, 0, 8)))
# 6) PONY bar 50 straight; bar 51: beats 1-2, rising 16th stutter on beat 3, bitcrushed beat 4
seq.append(("pony", beats("pony", 50)))
pb = [beats("pony", 51, i, 1) for i in range(4)]
seq.append(("pony", np.concatenate([declick(pb[0]), declick(pb[1]), stutter(pb[2], 4, pitch_rise=7),
                                    crush(declick(pb[3]))])))
# 7) HARD bars 40-41 — slam back to 84 BPM on the loudest section
seq.append(("hard", beats("hard", 40, 0, 8)))
# 8) PONY bar 79 — accelerating beat-repeat to the hard cut at 30.0 s
pb = beats("pony", 79, 0, 2)
q = beat_len("pony")
seq.append(("pony", np.concatenate([declick(pb[:q].copy()), stutter(pb[q:2 * q], 4),
                                    stutter(pb[q:2 * q], 8, pitch_rise=12)])))

# level-match: bring every block to the same loudness as the HARD drop
ref = rms(beats("hard", 5, 0, 8))
out = []
for src, x in seq:
    g = ref / max(rms(x), 1e-6)
    out.append(declick(x * min(g, 2.5)))
mix = np.concatenate(out)
print(f"edit length before cut: {len(mix) / SR:.2f}s")
mix = np.pad(mix, ((0, max(0, OUT_LEN - len(mix))), (0, 0)))[:OUT_LEN]

# master: gentle glue + peak normalize, 3 ms declick at the cut
mix = np.tanh(1.1 * mix / np.percentile(np.abs(mix), 99.97))
mix = mix / np.abs(mix).max() * 0.966
mix[-int(0.003 * SR):] *= np.linspace(1, 0, int(0.003 * SR))[:, None]

dst = Path(__file__).with_name("sophie_edit.wav")
with wave.open(str(dst), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("wrote", dst, f"{len(mix) / SR:.2f}s")
if shutil.which("ffmpeg"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(dst), "-b:a", "320k",
                    str(dst.with_suffix(".mp3"))], check=True)
    print("wrote", dst.with_suffix(".mp3"))
