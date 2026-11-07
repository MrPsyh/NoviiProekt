"""LATEX SPRING — 30-second hyperpop fragment, synthesized from scratch with numpy.

No samples, no external presets: every sound (kick, spring bass, latex squeaks,
plastic pops, metal snares, glass chords) is generated mathematically below.

Run:  python3 latex_spring.py   -> latex_spring.wav (+ .mp3 if ffmpeg exists)
"""
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 128
BEAT = 60 / BPM
BAR = 4 * BEAT          # 1.875 s -> 16 bars == 30 s
S16 = BEAT / 4
DUR = 30.0
N = int(SR * DUR)
TAIL = SR * 3
rng = np.random.default_rng(1312)


# ---------------------------------------------------------------- helpers
class Bus:
    def __init__(self):
        self.L = np.zeros(N + TAIL)
        self.R = np.zeros(N + TAIL)

    def add(self, sig, start, pan=0.0, gain=1.0):
        i = int(round(start * SR))
        n = min(len(sig), len(self.L) - i)
        if n <= 0:
            return
        a = (pan + 1) * np.pi / 4
        self.L[i:i + n] += sig[:n] * gain * np.cos(a) * np.sqrt(2)
        self.R[i:i + n] += sig[:n] * gain * np.sin(a) * np.sqrt(2)


def tt(d):
    return np.arange(int(d * SR)) / SR


def ph(freq):
    return 2 * np.pi * np.cumsum(freq) / SR


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def adsr(n, a=0.003, r=0.01):
    env = np.ones(n)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    env[:na] = np.linspace(0, 1, na)
    env[-nr:] *= np.linspace(1, 0, nr)
    return env


def lowpass_ma(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


def at(bar, step=0):
    """time of a 16th-note step inside a bar"""
    return bar * BAR + step * S16


# ---------------------------------------------------------------- instruments
def kick(d=0.55):
    t = tt(d)
    f = 42 + 190 * np.exp(-t * 32)
    body = np.sin(ph(f)) * np.exp(-t * 4.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 500) * 0.4
    return np.tanh(3.2 * (body + click)) * adsr(len(t), 0.0005, 0.02)


def spring_bass(note, d):
    """rubbery 'boing': starts an octave up, snaps down, then wobbles like a spring"""
    t = tt(d)
    f0 = mtof(note)
    bend = 1.0 * np.exp(-t * 28) + 0.32 * np.exp(-t * 5.5) * np.sin(2 * np.pi * 12 * t)
    f = f0 * 2 ** bend
    idx = 3.5 * np.exp(-t * 7) + 0.7
    mod = np.sin(ph(f * 2.0)) * idx
    car = np.sin(ph(f) + mod)
    sub = np.sin(ph(f)) * 0.8
    x = np.tanh(2.8 * (car * 0.7 + sub))
    env = (0.55 + 0.45 * np.exp(-t * 6)) * adsr(len(t), 0.002, 0.03)
    return x * env


def latex_squeak(note, d, up=0.7):
    """stretchy rubber/latex squeal: pitch arcs up and back, fast vibrato, FM grit"""
    t = tt(d)
    arc = up * np.sin(np.pi * np.clip(t / d, 0, 1)) - 0.25 * np.exp(-t * 30)
    vib = 0.05 * np.sin(2 * np.pi * 23 * t)
    f = mtof(note) * 2 ** (arc + vib)
    idx = 1.6 + 1.2 * np.sin(np.pi * t / d)
    x = np.sin(ph(f) + idx * np.sin(ph(f * 1.5)))
    x = np.tanh(1.8 * x)
    return x * adsr(len(t), 0.004, 0.02) * (0.6 + 0.4 * np.exp(-t * 4))


def plastic_pop(pitch=2200, d=0.07):
    t = tt(d)
    f = pitch * np.exp(-t * 70) + 320
    return np.sin(ph(f)) * np.exp(-t * 55) * adsr(len(t), 0.0003, 0.005)


def metal_snare(d=0.35):
    t = tt(d)
    base = 287.0
    x = np.zeros(len(t))
    for r in (1.0, 1.47, 2.09, 2.56, 3.11, 4.73, 5.9):
        x += np.sin(2 * np.pi * base * r * t + rng.uniform(0, 6.28)) * np.exp(-t * (14 + 4 * r))
    nz = rng.standard_normal(len(t))
    nz = (nz - lowpass_ma(nz, 6)) * np.exp(-t * 22)
    body = np.sin(ph(190 * np.exp(-t * 20) + 160)) * np.exp(-t * 25)
    return np.tanh(1.6 * (x * 0.35 + nz * 0.8 + body * 0.8)) * adsr(len(t), 0.0003, 0.02)


def hat(d=0.06, open_=False):
    if open_:
        d = 0.25
    t = tt(d)
    nz = rng.standard_normal(len(t))
    nz = nz - lowpass_ma(nz, 4)
    return nz * np.exp(-t * (14 if open_ else 70)) * 0.5 * adsr(len(t), 0.0002, 0.01)


def glass_bell(note, d=0.6):
    t = tt(d)
    f = mtof(note)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t * 9)
    return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 5) * adsr(len(t), 0.001, 0.05)


def plastic_chord(notes, d, bright_start, bright_end, detune=0.12, pluck=False):
    """additive detuned saws with time-varying brightness (a filter sweep without a filter)"""
    t = tt(d)
    b = np.linspace(bright_start, bright_end, len(t))
    if pluck:
        b = bright_end + (bright_start - bright_end) * np.exp(-t * 14)
    out = np.zeros(len(t))
    for n in notes:
        for dt in (-detune, 0.0, detune):
            f = mtof(n + dt)
            kmax = int(min(28, (SR / 2.2) / f))
            p0 = rng.uniform(0, 6.28)
            for k in range(1, kmax + 1):
                out += np.sin(2 * np.pi * k * f * t + p0 * k) / k * np.exp(-k / b)
    out /= len(notes) * 3
    env = adsr(len(t), 0.004 if pluck else 0.08, 0.06)
    if pluck:
        env *= 0.35 + 0.65 * np.exp(-t * 9)
    return np.tanh(2.0 * out) * env


def riser(d):
    t = tt(d)
    nz = rng.standard_normal(len(t))
    hp = nz - lowpass_ma(nz, 3)
    sweep = np.sin(ph(200 * 2 ** (5 * (t / d) ** 2)))
    return (hp * 0.35 + sweep * 0.4) * (t / d) ** 2


def crash(d=1.6):
    t = tt(d)
    x = np.zeros(len(t))
    for r in rng.uniform(1.0, 9.0, 18):
        x += np.sin(2 * np.pi * 420 * r * t + rng.uniform(0, 6.28))
    nz = rng.standard_normal(len(t))
    x = x / 18 * 0.6 + (nz - lowpass_ma(nz, 3)) * 0.6
    return x * np.exp(-t * 2.6) * adsr(len(t), 0.001, 0.1)


# ---------------------------------------------------------------- arrangement
drums, bass, music, fx = Bus(), Bus(), Bus(), Bus()
kick_times = []

# chords:      Dbmaj9            Ebadd9            Fm9               Abmaj7(#11-ish)
PROG = [[61, 65, 68, 72, 75], [63, 67, 70, 77, 82], [65, 68, 72, 75, 79], [68, 72, 75, 79, 86]]
ROOTS = [37, 39, 41, 44]

# --- INTRO bars 0-3: pops, squeaks, a pad slowly opening, glass arps
for bar in range(4):
    chord = PROG[bar % 4]
    music.add(plastic_chord(chord, BAR, 1.0 + bar * 1.2, 2.2 + bar * 1.6), at(bar), gain=0.22)
    for s in range(0, 16, 3):  # 3-against-4 plastic pops
        drums.add(plastic_pop(1800 + 600 * ((s // 3) % 3)), at(bar, s), pan=0.6 * np.sin(s), gain=0.45)
    for i, s in enumerate((0, 6, 10, 14)):
        n = chord[i % len(chord)] + 12
        b = glass_bell(n, 0.5)
        music.add(b, at(bar, s), pan=-0.5 + 0.33 * i, gain=0.14)
        fx.add(b, at(bar, s), gain=0.1)
    if bar in (1, 3):
        sq = latex_squeak(79 if bar == 1 else 82, S16 * 3)
        music.add(sq, at(bar, 12), pan=0.3, gain=0.22)
        fx.add(sq, at(bar, 12), gain=0.2)

# --- BUILD bars 4-7: half-time kick, metal snare, sparse springs
for bar in range(4, 8):
    chord = PROG[bar % 4]
    last = bar == 7
    music.add(plastic_chord(chord, BAR if not last else BAR / 2, 4.0, 7.0), at(bar), gain=0.2)
    for s in (0, 6, 10) if not last else (0,):
        drums.add(kick(), at(bar, s), gain=0.9)
        kick_times.append(at(bar, s))
    if not last:
        drums.add(metal_snare(), at(bar, 8), pan=0.05, gain=0.55)
        for s in range(2, 16, 4):
            drums.add(hat(), at(bar, s), pan=0.35, gain=0.6)
        for s in (0, 7, 11):
            bass.add(spring_bass(ROOTS[bar % 4], S16 * 3), at(bar, s), gain=0.55)
    for s in range(1, 16, 3):
        drums.add(plastic_pop(2600), at(bar, s), pan=-0.6, gain=0.3)
    if not last:
        sq = latex_squeak(PROG[bar % 4][-1], S16 * 2, up=0.9)
        music.add(sq, at(bar, 14), pan=-0.3, gain=0.2)
        fx.add(sq, at(bar, 14), gain=0.25)

# bar 7 second half: dropout + riser + accelerating snare roll
fx.add(riser(BAR / 2), at(7, 8), gain=0.6)
for i, s in enumerate(np.linspace(8, 15.5, 12)):
    drums.add(metal_snare(0.12), at(7, 0) + s * S16, gain=0.15 + 0.03 * i)

# --- DROP bars 8-15
BASS_PAT = [0, 3, 6, 8, 10, 13, 14]
BASS_LEN = [3, 3, 2, 2, 3, 1, 2]
LEAD = [  # (step, note, length-in-16ths) per 2-bar phrase
    (0, 84, 2), (3, 82, 1), (4, 80, 2), (7, 77, 3), (10, 80, 1), (12, 82, 2), (14, 89, 2),
    (16, 84, 2), (19, 87, 1), (20, 84, 2), (23, 80, 2), (26, 77, 1), (27, 80, 1), (28, 82, 4),
]
drums.add(crash(), at(8), gain=0.45)
for bar in range(8, 16):
    ci = (bar - 8) // 2
    chord, root = PROG[ci], ROOTS[ci]
    for s in (0, 4, 8, 12):
        drums.add(kick(), at(bar, s), gain=1.0)
        kick_times.append(at(bar, s))
    for s in (4, 12):
        drums.add(metal_snare(), at(bar, s), pan=0.0, gain=0.7)
    for s in range(16):
        if s % 2:
            drums.add(hat(open_=(s % 8 == 7)), at(bar, s), pan=0.3 * (-1) ** s, gain=0.55)
    for s, ln in zip(BASS_PAT, BASS_LEN):
        bass.add(spring_bass(root + (12 if s == 13 else 0), ln * S16), at(bar, s), gain=0.62)
    for s in (2, 5, 9, 11, 15):  # plastic chord stabs on the off-steps
        music.add(plastic_chord(chord, S16 * 1.6, 18, 2.5, pluck=True), at(bar, s),
                  pan=-0.4 if s % 2 else 0.4, gain=0.3)
    for s in (0, 3, 6, 9, 12, 15):
        drums.add(plastic_pop(3200), at(bar, s), pan=0.7 * (-1) ** s, gain=0.25)
    if bar % 2 == 0:
        for step, note, ln in LEAD:
            if bar == 14 and step >= 28:
                ln = 6  # last squeak gets cut by the hard stop
            sq = latex_squeak(note, ln * S16 * 0.95, up=0.35)
            p = 0.25 * np.sin(step)
            music.add(sq, at(bar) + step * S16, pan=p, gain=0.26)
            fx.add(sq, at(bar) + step * S16, gain=0.22)

# ---------------------------------------------------------------- mix
# sidechain pump on the music bus
t_all = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for k in kick_times:
    i = int(k * SR)
    seg = t_all[i:] - k
    duck[i:] = np.minimum(duck[i:], 1 - 0.75 * np.exp(-seg / 0.11))
for b in (music, bass):
    g = duck if b is music else 0.4 + 0.6 * duck
    b.L *= g
    b.R *= g

# ping-pong dotted-8th delay on the fx send
dl = int(S16 * 3 * SR)
dL, dR = np.zeros(N + TAIL), np.zeros(N + TAIL)
src = (fx.L + fx.R) / 2
for tap in range(1, 6):
    sh = dl * tap
    amp = 0.55 ** tap
    tgt = dL if tap % 2 else dR
    tgt[sh:] += src[:-sh] * amp
dL, dR = lowpass_ma(dL, 3), lowpass_ma(dR, 3)

L = drums.L + bass.L + music.L + dL * 0.7
R = drums.R + bass.R + music.R + dR * 0.7
L, R = L[:N], R[:N]

# master: glue + soft clip + normalize, hard cut at 30.0 s (only a 4 ms declick)
mx = max(np.abs(L).max(), np.abs(R).max())
L, R = np.tanh(1.6 * L / mx), np.tanh(1.6 * R / mx)
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L / peak * 0.95, R / peak * 0.95
nd = int(0.004 * SR)
L[-nd:] *= np.linspace(1, 0, nd)
R[-nd:] *= np.linspace(1, 0, nd)

out = Path(__file__).with_name("latex_spring.wav")
pcm = (np.stack([L, R], axis=1) * 32767).astype("<i2")
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", out, f"{len(L) / SR:.2f}s")

if shutil.which("ffmpeg"):
    mp3 = out.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-b:a", "320k", str(mp3)], check=True)
    print("wrote", mp3)
