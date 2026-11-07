"""SAMPLE FLIP — 30-second fragment built from one-shots chopped out of two source tracks
(supplied by the user, who states they have permission to use the sounds), re-sequenced
into a new arrangement and layered with the numpy synths from rubber_face.py.

The source audio is NOT stored in this repo. Usage:
    python3 sample_flip.py PONY.wav HARD.wav      (any format ffmpeg can read)
"""
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import rubber_face_lib as syn  # noqa: E402  (synth voices, see rubber_face_lib.py)

SR, BPM = 44100, 120
BEAT = 60 / BPM
BAR, S16 = 4 * BEAT, BEAT / 4
DUR = 30.0
N, TAIL = int(SR * DUR), SR * 3
rng = np.random.default_rng(99)


def load(path):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "2", str(out)],
                       check=True)
        with wave.open(str(out)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2)
    return x.astype(np.float64) / 32768


PONY, HARD = load(sys.argv[1]), load(sys.argv[2])


# ---------------------------------------------------------------- sampler
def cut(src, t, d, pre=0.004, fade=0.03):
    a = max(0, int((t - pre) * SR))
    x = src[a:a + int(d * SR)].copy()
    n = len(x)
    env = np.ones(n)
    env[:int(pre * SR)] = np.linspace(0, 1, int(pre * SR))
    nf = int(fade * SR)
    env[-nf:] *= np.linspace(1, 0, nf)
    return x * env[:, None]


def repitch(x, semis):
    """sampler-style pitch: resample (changes length too, like an MPC/SP-404)"""
    r = 2 ** (semis / 12)
    idx = np.arange(0, len(x) - 1, r)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def fit(x, d):
    """resample a loop so it lasts exactly d seconds"""
    idx = np.linspace(0, len(x) - 1, int(d * SR))
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def norm(x, peak=1.0):
    return x / (np.abs(x).max() + 1e-9) * peak


def crush(x, bits=6, hold=3):
    q = 2 ** bits
    y = np.round(x * q) / q
    return np.repeat(y[::hold], hold, axis=0)[:len(x)]


def est_pitch(x):
    m = x.mean(1)[:int(0.12 * SR)]
    m = m - m.mean()
    ac = np.correlate(m, m, "full")[len(m) - 1:]
    lo, hi = int(SR / 1000), int(SR / 70)
    lag = lo + np.argmax(ac[lo:hi])
    return 69 + 12 * np.log2(SR / lag / 440)


# one-shots (onset times found by spectral-flux analysis of the sources)
S = {
    "h_low":   norm(cut(HARD, 31.428, 0.55)),
    "h_low2":  norm(cut(HARD, 25.716, 0.45)),
    "h_low3":  norm(cut(HARD, 34.284, 0.45)),
    "h_mid":   norm(cut(HARD, 137.497, 0.35)),
    "h_mid2":  norm(cut(HARD, 74.641, 0.30)),
    "h_hi":    norm(cut(HARD, 4.853, 0.25)),
    "h_hi2":   norm(cut(HARD, 75.743, 0.25)),
    "h_hi3":   norm(cut(HARD, 62.044, 0.30)),
    "p_low":   norm(cut(PONY, 2.682, 0.55)),
    "p_low2":  norm(cut(PONY, 96.015, 0.5)),
    "p_hi":    norm(cut(PONY, 0.151, 0.3)),
    "p_hi2":   norm(cut(PONY, 70.74, 0.25)),
    "p_hi3":   norm(cut(PONY, 41.854, 0.35)),
}
# loops: chunks of each source's groove, squeezed to our grid
P_BEAT, H_BEAT = 60 / 103.4, 60 / 84.7          # estimated source tempos
S["p_loop"] = norm(fit(cut(PONY, 96.015, 2 * P_BEAT, fade=0.01), 2 * BEAT))
S["h_loop"] = norm(fit(cut(HARD, 31.428, 2 * H_BEAT, fade=0.01), 2 * BEAT))
MID_PITCH = est_pitch(S["h_mid"])
while MID_PITCH < 64:  # autocorrelation often lands an octave or two low on noisy hits
    MID_PITCH += 12


# ---------------------------------------------------------------- buses
class Bus:
    def __init__(self):
        self.x = np.zeros((N + TAIL, 2))

    def add(self, sig, start, pan=0.0, gain=1.0):
        if sig.ndim == 1:
            a = (pan + 1) * np.pi / 4
            sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)
        elif pan:
            sig = sig * np.array([min(1, 1 - pan), min(1, 1 + pan)])
        i = int(round(start * SR))
        n = min(len(sig), len(self.x) - i)
        if n > 0:
            self.x[i:i + n] += sig[:n] * gain


def at(bar, step=0.0):
    return bar * BAR + step * S16


drums, bass, music, fx = Bus(), Bus(), Bus(), Bus()
kicks = []


def hit(name, bar, s, gain=0.8, pan=0.0, semis=0.0, bus=None, send=0.0):
    x = S[name] if not semis else repitch(S[name], semis)
    (bus or drums).add(x, at(bar, s), pan, gain)
    if send:
        fx.add(x, at(bar, s), pan, send)


def keyhit(bar, s, note, ln=None, gain=0.35, pan=0.0, send=0.15):
    """play the HARD mid one-shot as a tuned sampler instrument"""
    x = repitch(S["h_mid"], note - MID_PITCH)
    if ln:
        x = x[:int(ln * S16 * SR)] * syn.adsr(min(len(x), int(ln * S16 * SR)), 0.001, 0.02)[:, None]
    music.add(x, at(bar, s), pan, gain)
    fx.add(x, at(bar, s), pan, send)


def kick_at(bar, s, name="p_low", gain=0.9, layer=True):
    hit(name, bar, s, gain)
    if layer:
        drums.add(syn.kick(0.4, 2.5), at(bar, s), gain=0.45)
    kicks.append(at(bar, s))


# ===== A: bars 0-3 — HARD one-shots, sparse rubber groove
ROOT_A = [34, 34, 37, 32]
for bar in range(4):
    kick_at(bar, 0, "h_low", 0.9)
    hit("h_low2", bar, 6, 0.7, semis=-2)
    hit("h_low3", bar, 10, 0.75)
    for s, ln in ((0, 4), (7.5, 2)):
        bass.add(syn.spring_bass(ROOT_A[bar] + (12 if s else 0), ln * S16), at(bar, s), gain=0.4)
    hit("h_hi", bar, 8, 0.6, pan=0.1)
    hit("h_hi2", bar, 3, 0.4, pan=-0.4, semis=5, send=0.2)
    hit("h_mid2", bar, 13, 0.45, pan=0.35, semis=7 if bar % 2 else 3, send=0.25)
    if bar in (1, 3):
        for i, s in enumerate((12, 12.5, 13, 14)):
            keyhit(bar, s, 74 + (3 if bar == 3 else 0) + (5 if i == 3 else 0), ln=0.5 if i < 3 else 2,
                   pan=0.25 * (-1) ** i)

# ===== B: bars 4-7 — PONY one-shots + loop, industrial
for bar in range(4, 8):
    last = bar == 7
    hit("p_loop", bar, 0, 0.45)
    if not last:
        hit("p_loop", bar, 8, 0.45, semis=-1 if bar % 2 else 0)
    for s in ((0, 3, 6, 10, 11) if not last else (0, 3, 6)):
        kick_at(bar, s, "p_low2" if s % 2 else "p_low", 0.85)
    hit("p_hi3", bar, 4, 0.6, pan=-0.1)
    if not last:
        hit("p_hi3", bar, 12, 0.6, pan=0.1, semis=-2)
        hit("p_hi", bar, 14, 0.5, pan=0.5)
        bass.add(syn.spring_bass(30 + (bar % 2) * 2, 4 * S16, drive=4.5, wobble=16), at(bar, 10), gain=0.45)
    hit("p_hi2", bar, 7, 0.5, pan=-0.5, send=0.15)
    for s in range(1, 16, 2):
        if (last and s >= 8) or rng.random() < 0.3:
            continue
        hit("h_hi3", bar, s, 0.25, pan=0.4 * np.sin(s * 1.7), semis=12)
keyhit(7, 14, 86, ln=2, gain=0.4, send=0.35)

# ===== C: bars 8-10 — sweet switch: supersaw + tuned sample arp
PROG_C = [[63, 67, 70, 74, 79], [58, 65, 70, 74, 77], [60, 63, 67, 70, 75]]
SUB_C = [39, 34, 36]
for i, bar in enumerate(range(8, 11)):
    ch = PROG_C[i]
    music.add(syn.supersaw(ch, BAR, bright=(4 + 2 * i, 16), attack=0.12), at(bar), gain=0.38)
    bass.add(syn.sub(SUB_C[i], BAR * 0.98), at(bar), gain=0.4)
    for s in range(16):
        keyhit(bar, s, ch[(s * 3) % len(ch)] + 12 + (12 if s % 8 == 7 else 0), ln=1.2,
               gain=0.16, pan=0.6 * (-1) ** s, send=0.08)
    rev = S["h_low"][::-1] * np.linspace(0, 1, len(S["h_low"]))[:, None] ** 2
    fx.add(repitch(rev, 12), at(bar, 12), gain=0.35)
fx.add(syn.riser(BAR * 0.75), at(10, 4), gain=0.5)

# ===== D: bars 11-14 — everything, both sources colliding
PROG_D = [[63, 67, 70, 74], [61, 65, 68, 72], [58, 62, 65, 70], [60, 63, 67, 70]]
ROOT_D = [39, 37, 34, 36]
hit("p_hi3", 11, 0, 0.8, semis=-7)
for i, bar in enumerate(range(11, 15)):
    r, ch = ROOT_D[i], PROG_D[i]
    hit("h_loop" if i % 2 else "p_loop", bar, 0, 0.35)
    for s in (0, 4, 8, 11, 12):
        kick_at(bar, s, "p_low" if s in (0, 8) else "h_low", 0.85)
    for s in (4, 12):
        hit("h_hi" if i % 2 else "p_hi3", bar, s, 0.6)
    hit("p_hi", bar, 15, 0.45, pan=0.5 * (-1) ** i)
    for s in range(1, 16, 2):
        hit("h_hi3", bar, s, 0.22, pan=0.3 * (-1) ** s, semis=12)
    for s, ln in ((0, 3), (3, 3), (6, 2), (9, 2), (11, 1), (13, 3)):
        bass.add(syn.spring_bass(r + (12 if s == 11 else 0), ln * S16, drive=3.5), at(bar, s), gain=0.45)
    for s in (2, 7, 10, 15):
        music.add(syn.supersaw(ch, S16 * 1.8, bright=(18, 2.5), voices=(-0.12, 0, 0.12), pluck=True),
                  at(bar, s), pan=0.4 * (-1) ** s, gain=0.25)
    hook = [(0, 86, 2), (2, 84, 1), (3, 82, 2), (6, 79, 2), (9, 82, 1), (10, 86, 3)]
    if i % 2:
        hook = [(0, 89, 2), (2, 87, 1), (3, 86, 2), (6, 84, 1), (8, 82, 2), (10, 91, 4)]
    for s, n, ln in hook:
        keyhit(bar, s, n, ln=ln, gain=0.3, pan=0.25 * np.sin(s), send=0.2)
        music.add(syn.latex_squeak(n, ln * S16 * 0.95, 0.35), at(bar, s), gain=0.12)

# ---------------------------------------------------------------- mix
t_all = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for kt in kicks:
    i = int(kt * SR)
    duck[i:] = np.minimum(duck[i:], 1 - 0.7 * np.exp(-(t_all[i:] - kt) / 0.1))
music.x *= duck[:, None]
bass.x *= (0.45 + 0.55 * duck)[:, None]

dl = int(S16 * 3 * SR)
dly = np.zeros((N + TAIL, 2))
src = fx.x.mean(1)
for tap in range(1, 6):
    dly[dl * tap:, tap % 2] += src[:-dl * tap] * 0.55 ** tap
dly = np.stack([np.convolve(dly[:, c], np.ones(3) / 3, "same") for c in (0, 1)], 1)

mix = (drums.x + bass.x + music.x + dly * 0.7 + fx.x * 0.4)[:N]


def stutter(x, start, dur, slice_len):
    a, n, s = int(start * SR), int(dur * SR), int(slice_len * SR)
    piece = x[a:a + s] * syn.adsr(s, 0.001, 0.002)[:, None]
    x[a:a + n] = np.tile(piece, (int(np.ceil(n / s)), 1))[:n]


stutter(mix, at(3, 14), S16 * 2, S16 / 2)
stutter(mix, at(6, 14), S16 * 2, S16 / 4)
stutter(mix, at(10, 14), S16 * 2, S16 / 3)
stutter(mix, at(12, 12), S16 * 4, S16 / 2)
stutter(mix, at(14, 13), S16 * 3, S16 / 8)
# bitcrushed slam right before the sweet section
a = int(at(7, 8) * SR)
mix[a:a + int(BEAT * SR)] = crush(mix[a:a + int(BEAT * SR)], 5, 4) * 0.8

mix = np.tanh(1.7 * mix / np.abs(mix).max())
mix = mix / np.abs(mix).max() * 0.95
nd = int(0.004 * SR)
mix[-nd:] *= np.linspace(1, 0, nd)[:, None]

out = Path(__file__).with_name("sample_flip.wav")
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("wrote", out, f"{len(mix) / SR:.2f}s  (h_mid pitch ~ midi {MID_PITCH:.1f})")
if shutil.which("ffmpeg"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-b:a", "320k",
                    str(out.with_suffix(".mp3"))], check=True)
    print("wrote", out.with_suffix(".mp3"))
