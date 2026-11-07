"""RUBBER FACE — 30-second hyperpop / industrial-bubblegum fragment, synthesized from scratch.

Sound-design inspired by the late-2010s PC-music / SOPHIE school (sparse rubbery grooves,
metal slams, whip cracks, formant voice chops, a sudden euphoric supersaw switch,
stutter glitches). All melodies, rhythms and sounds are original and generated with numpy;
no samples, no presets.

Run:  python3 rubber_face.py   -> rubber_face.wav (+ .mp3 if ffmpeg exists)
"""
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT          # 2.0 s -> 15 bars == 30 s
S16 = BEAT / 4
DUR = 30.0
N = int(SR * DUR)
TAIL = SR * 3
rng = np.random.default_rng(2017)


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
    na, nr = max(1, min(n, int(a * SR))), max(1, min(n, int(r * SR)))
    env[:na] = np.linspace(0, 1, na)
    env[-nr:] *= np.linspace(1, 0, nr)
    return env


def lp(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


def at(bar, step=0.0):
    return bar * BAR + step * S16


# ---------------------------------------------------------------- instruments
def kick(d=0.45, drive=3.0):
    t = tt(d)
    f = 40 + 200 * np.exp(-t * 30)
    body = np.sin(ph(f)) * np.exp(-t * 5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 600) * 0.5
    return np.tanh(drive * (body + click)) * adsr(len(t), 0.0005, 0.02)


def dist_kick(d=0.5):
    """overdriven industrial kick with a square-ish clipped body"""
    t = tt(d)
    f = 38 + 260 * np.exp(-t * 24)
    body = np.sin(ph(f)) * np.exp(-t * 3.5)
    x = np.tanh(9 * body) * 0.8 + np.sign(body) * np.exp(-t * 12) * 0.2
    x += rng.standard_normal(len(t)) * np.exp(-t * 300) * 0.6
    return np.tanh(1.5 * x) * adsr(len(t), 0.0003, 0.03)


def spring_bass(note, d, drive=2.8, wobble=12.0):
    t = tt(d)
    f0 = mtof(note)
    bend = 1.2 * np.exp(-t * 26) + 0.35 * np.exp(-t * 5) * np.sin(2 * np.pi * wobble * t)
    f = f0 * 2 ** bend
    idx = 4.0 * np.exp(-t * 6) + 0.8
    car = np.sin(ph(f) + idx * np.sin(ph(f * 2.0)))
    x = np.tanh(drive * (car * 0.7 + np.sin(ph(f)) * 0.8))
    return x * (0.55 + 0.45 * np.exp(-t * 6)) * adsr(len(t), 0.002, 0.03)


def latex_squeak(note, d, up=0.7):
    t = tt(d)
    arc = up * np.sin(np.pi * np.clip(t / d, 0, 1)) - 0.3 * np.exp(-t * 30)
    f = mtof(note) * 2 ** (arc + 0.05 * np.sin(2 * np.pi * 24 * t))
    idx = 1.6 + 1.4 * np.sin(np.pi * t / d)
    x = np.tanh(1.9 * np.sin(ph(f) + idx * np.sin(ph(f * 1.5))))
    return x * adsr(len(t), 0.004, 0.02) * (0.6 + 0.4 * np.exp(-t * 4))


def metal_clang(pitch=180.0, d=0.6, drive=2.5):
    """heavy FM metal slam: inharmonic ratios, pitch drop, distorted"""
    t = tt(d)
    f = pitch * (1 + 0.6 * np.exp(-t * 40))
    m1 = np.sin(ph(f * 1.414)) * 6 * np.exp(-t * 8)
    m2 = np.sin(ph(f * 2.76)) * 3 * np.exp(-t * 14)
    x = np.sin(ph(f) + m1 + m2)
    nz = rng.standard_normal(len(t))
    x += (nz - lp(nz, 5)) * np.exp(-t * 30) * 0.8
    return np.tanh(drive * x) * np.exp(-t * 6) * adsr(len(t), 0.0003, 0.03)


def whip(d=0.18):
    t = tt(d)
    nz = rng.standard_normal(len(t))
    hp = nz - lp(nz, 3)
    zap = np.sin(ph(5200 * np.exp(-t * 90) + 700)) * np.exp(-t * 40)
    return np.tanh(2 * (hp * np.exp(-t * 35) + zap)) * adsr(len(t), 0.0002, 0.02)


def plastic_pop(pitch=2200, d=0.07):
    t = tt(d)
    return np.sin(ph(pitch * np.exp(-t * 70) + 320)) * np.exp(-t * 55) * adsr(len(t), 0.0003, 0.005)


def hat(d=0.05):
    t = tt(d)
    nz = rng.standard_normal(len(t))
    return (nz - lp(nz, 3)) * np.exp(-t * 80) * 0.5 * adsr(len(t), 0.0002, 0.01)


VOWELS = {  # formant centre frequencies (Hz), shifted up later for a pitched-up "doll" voice
    "a": (800, 1150, 2900), "o": (450, 800, 2830), "i": (300, 2200, 3000),
    "e": (420, 1800, 2600), "u": (330, 700, 2400),
}


def voice(note, d, v1="a", v2=None, glide=0.0, shift=1.35, breath=0.15):
    """additive formant voice: harmonics weighted by a vowel envelope that can morph v1->v2"""
    t = tt(d)
    f0 = mtof(note) * 2 ** (glide * t / d) * (1 + 0.012 * np.sin(2 * np.pi * 6 * t))
    phase0 = ph(f0)
    F1 = np.array(VOWELS[v1]) * shift
    F2 = np.array(VOWELS[v2 or v1]) * shift
    m = np.clip(t / d, 0, 1)[None, :]
    F = F1[:, None] * (1 - m) + F2[:, None] * m          # (3, n)
    bw = np.array([90, 120, 180])[:, None] * shift
    gains = np.array([1.0, 0.6, 0.3])[:, None]
    out = np.zeros(len(t))
    kmax = int((SR / 2.3) / mtof(note))
    for k in range(1, min(kmax, 40) + 1):
        fk = f0 * k
        a = (gains * np.exp(-((fk[None, :] - F) / bw) ** 2)).sum(0)
        out += a * np.sin(k * phase0)
    nz = rng.standard_normal(len(t))
    out += (nz - lp(nz, 4)) * breath * 0.3
    return np.tanh(1.5 * out) * adsr(len(t), 0.006, 0.02)


def glass_bell(note, d=0.5):
    t = tt(d)
    f = mtof(note)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.0 * np.exp(-t * 9)
    return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 5) * adsr(len(t), 0.001, 0.05)


def supersaw(notes, d, bright=(3.0, 14.0), voices=(-0.18, -0.09, -0.03, 0, 0.03, 0.09, 0.18),
             attack=0.25, pluck=False):
    t = tt(d)
    b = np.linspace(bright[0], bright[1], len(t))
    if pluck:
        b = bright[0] + (bright[1] - bright[0]) * np.exp(-t * 12)
    out = np.zeros(len(t))
    for n in notes:
        for dt in voices:
            f = mtof(n + dt)
            p0 = rng.uniform(0, 6.28)
            for k in range(1, int(min(24, (SR / 2.2) / f)) + 1):
                out += np.sin(2 * np.pi * k * f * t + p0 * k) / k * np.exp(-k / b)
    out /= len(notes) * len(voices) ** 0.5 * 2
    env = adsr(len(t), 0.004 if pluck else attack, 0.05)
    if pluck:
        env *= 0.3 + 0.7 * np.exp(-t * 8)
    return np.tanh(1.8 * out) * env


def sub(note, d):
    t = tt(d)
    return np.sin(2 * np.pi * mtof(note) * t) * adsr(len(t), 0.02, 0.05)


def riser(d):
    t = tt(d)
    nz = rng.standard_normal(len(t))
    return ((nz - lp(nz, 3)) * 0.35 + np.sin(ph(300 * 2 ** (4 * (t / d) ** 2))) * 0.4) * (t / d) ** 2


# ---------------------------------------------------------------- arrangement
drums, bass, music, fx = Bus(), Bus(), Bus(), Bus()
kick_times = []


def k(bar, s, kind="kick", gain=1.0):
    drums.add(dist_kick() if kind == "dist" else kick(), at(bar, s), gain=gain)
    kick_times.append(at(bar, s))


def squeak(bar, s, note, ln, up=0.6, pan=0.0, gain=0.24, send=0.2):
    x = latex_squeak(note, ln * S16 * 0.95, up)
    music.add(x, at(bar, s), pan=pan, gain=gain)
    fx.add(x, at(bar, s), gain=send)


def chop(bar, s, note, ln, v1, v2=None, glide=0.0, pan=0.0, gain=0.3, send=0.12):
    x = voice(note, ln * S16 * 0.92, v1, v2, glide)
    music.add(x, at(bar, s), pan=pan, gain=gain)
    fx.add(x, at(bar, s), gain=send)


# ===== A: bars 0-3 (0-8 s) — sparse bouncy rubber groove, lots of air
ROOT_A = [34, 34, 37, 32]
for bar in range(4):
    r = ROOT_A[bar]
    k(bar, 0, gain=0.8)
    for s, ln in ((0, 4), (6, 1.5), (7.5, 2), (10, 3)):
        bass.add(spring_bass(r if s != 7.5 else r + 12, ln * S16), at(bar, s), gain=0.62)
    drums.add(metal_clang(170 if bar % 2 == 0 else 200, 0.5), at(bar, 8), pan=0.1, gain=0.55)
    squeak(bar, 3, 82 if bar % 2 == 0 else 85, 2, up=0.8, pan=-0.35)
    squeak(bar, 13, 89 if bar < 3 else 92, 1.5, up=0.5, pan=0.35)
    drums.add(plastic_pop(2400), at(bar, 5), pan=0.6, gain=0.4)
    drums.add(plastic_pop(3100), at(bar, 14.5), pan=-0.6, gain=0.35)
    if bar in (1, 3):  # stuttered doll-voice chops
        for i, (s, v) in enumerate(((12, "a"), (12.5, "a"), (13, "a"), (14, "o"))):
            chop(bar, s, 74 + (2 if bar == 3 else 0), 0.5 if i < 3 else 2, v, "u" if v == "o" else None,
                 glide=-0.4 if v == "o" else 0, pan=0.2 * (-1) ** i, gain=0.32)

# ===== B: bars 4-7 (8-16 s) — industrial: overdriven kicks, slams, whips
ROOT_B = [32, 32, 35, 30]
for bar in range(4, 8):
    r = ROOT_B[bar - 4]
    last = bar == 7
    for s in ((0, 3, 6, 10, 11) if not last else (0, 3, 6)):
        k(bar, s, "dist", gain=0.95)
    for s, ln in ((0, 2.5), (3, 2.5), (6, 3), (10, 1), (11, 4)):
        if last and s > 6:
            continue
        bass.add(spring_bass(r, ln * S16, drive=4.5, wobble=16), at(bar, s), gain=0.55)
    drums.add(metal_clang(130, 0.7, drive=4), at(bar, 4), pan=-0.1, gain=0.6)
    if not last:
        drums.add(metal_clang(150, 0.7, drive=4), at(bar, 12), pan=0.1, gain=0.6)
        drums.add(whip(), at(bar, 14), pan=0.5, gain=0.5)
    drums.add(whip(), at(bar, 7), pan=-0.5, gain=0.45)
    for s in range(16):  # gated noise hats, random holes
        if (last and s >= 8) or rng.random() < 0.3:
            continue
        drums.add(hat(), at(bar, s), pan=0.4 * np.sin(s * 1.7), gain=0.5)
    if not last:
        chop(bar, 9, 70, 2, "e", "a", glide=-0.6, pan=0.25, gain=0.3)
    squeak(bar, 1, 87, 1, up=1.0, pan=-0.4, gain=0.18)
# bar 7 back half: dead silence, then one lonely pitched-up voice blip
chop(7, 14, 86, 2, "i", "o", glide=0.5, gain=0.35, send=0.3)

# ===== C: bars 8-10 (16-22 s) — the sudden sweet switch: supersaw euphoria
PROG_C = [[63, 67, 70, 74, 79], [58, 65, 70, 74, 77], [60, 63, 67, 70, 75]]
SUB_C = [39, 34, 36]
for i, bar in enumerate(range(8, 11)):
    ch = PROG_C[i]
    music.add(supersaw(ch, BAR, bright=(4 + 2 * i, 16), attack=0.12), at(bar), gain=0.42)
    bass.add(sub(SUB_C[i], BAR * 0.98), at(bar), gain=0.45)
    for s in range(16):  # glossy 16th arp
        n = ch[(s * 3) % len(ch)] + 12 + (12 if s % 8 == 7 else 0)
        b = glass_bell(n, 0.35)
        music.add(b, at(bar, s), pan=0.6 * (-1) ** s, gain=0.12)
        fx.add(b, at(bar, s), gain=0.06)
    chop(bar, 0, ch[-1], 6, "a", "o", glide=0.0, gain=0.22, send=0.25)
    chop(bar, 8, ch[-2] + 12 if i == 2 else ch[-1], 6, "o", "a", gain=0.2, send=0.25)
    for s in (4, 12):
        drums.add(plastic_pop(3600), at(bar, s), gain=0.25)
fx.add(riser(BAR * 0.75), at(10, 4), gain=0.55)

# ===== D: bars 11-14 (22-30 s) — everything at once, then cut
PROG_D = [[63, 67, 70, 74], [61, 65, 68, 72], [58, 62, 65, 70], [60, 63, 67, 70]]
ROOT_D = [39, 37, 34, 36]
drums.add(metal_clang(110, 1.2, drive=5), at(11), gain=0.6)
for i, bar in enumerate(range(11, 15)):
    r, ch = ROOT_D[i], PROG_D[i]
    for s in (0, 4, 8, 11, 12):
        k(bar, s, "dist" if s in (0, 8) else "kick", gain=0.95)
    for s in (4, 12):
        drums.add(metal_clang(165, 0.45, drive=4), at(bar, s), gain=0.6)
    drums.add(whip(), at(bar, 15), pan=0.5 * (-1) ** i, gain=0.45)
    for s in range(1, 16, 2):
        drums.add(hat(), at(bar, s), pan=0.3 * (-1) ** s, gain=0.45)
    for s, ln in ((0, 3), (3, 3), (6, 2), (9, 2), (11, 1), (13, 3)):
        bass.add(spring_bass(r + (12 if s == 11 else 0), ln * S16, drive=3.5), at(bar, s), gain=0.6)
    for s in (2, 7, 10, 15):
        music.add(supersaw(ch, S16 * 1.8, bright=(18, 2.5), voices=(-0.12, 0, 0.12), pluck=True),
                  at(bar, s), pan=0.4 * (-1) ** s, gain=0.3)
    hook = [(0, 86, 2), (2, 84, 1), (3, 82, 2), (6, 79, 2), (9, 82, 1), (10, 86, 3)]
    if i % 2:
        hook = [(0, 89, 2), (2, 87, 1), (3, 86, 2), (6, 84, 1), (8, 82, 2), (10, 91, 4)]
    for s, n, ln in hook:
        squeak(bar, s, n, ln, up=0.35, pan=0.25 * np.sin(s), gain=0.26, send=0.22)
    chop(bar, 14, 78, 2, "a", "i", glide=0.3 if i % 2 else -0.3, gain=0.26)

# ---------------------------------------------------------------- mix
t_all = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for kt in kick_times:
    i = int(kt * SR)
    duck[i:] = np.minimum(duck[i:], 1 - 0.7 * np.exp(-(t_all[i:] - kt) / 0.1))
music.L *= duck
music.R *= duck
bass.L *= 0.45 + 0.55 * duck
bass.R *= 0.45 + 0.55 * duck

dl = int(S16 * 3 * SR)
dL, dR = np.zeros(N + TAIL), np.zeros(N + TAIL)
src = (fx.L + fx.R) / 2
for tap in range(1, 6):
    sh = dl * tap
    (dL if tap % 2 else dR)[sh:] += src[:-sh] * 0.55 ** tap
dL, dR = lp(dL, 3), lp(dR, 3)

L = (drums.L + bass.L + music.L + dL * 0.7)[:N]
R = (drums.R + bass.R + music.R + dR * 0.7)[:N]


def stutter(x, start, dur, slice_len):
    """glitch: loop a tiny slice of the mix (with micro-fades) over [start, start+dur)"""
    a, n, s = int(start * SR), int(dur * SR), int(slice_len * SR)
    piece = x[a:a + s] * adsr(s, 0.001, 0.002)
    reps = int(np.ceil(n / s))
    x[a:a + n] = np.tile(piece, reps)[:n]


for ch in (L, R):
    stutter(ch, at(3, 14), S16 * 2, S16 / 2)          # A: voice-chop glitch
    stutter(ch, at(6, 14), S16 * 2, S16 / 4)          # B: machine-gun slam
    stutter(ch, at(10, 14), S16 * 2, S16 / 3)         # C->D: sweet part shatters
    stutter(ch, at(12, 12), S16 * 4, S16 / 2)         # D: half-beat loop
    stutter(ch, at(14, 13), S16 * 3, S16 / 8)         # D: final buzz before the cut

mx = max(np.abs(L).max(), np.abs(R).max())
L, R = np.tanh(1.7 * L / mx), np.tanh(1.7 * R / mx)
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L / peak * 0.95, R / peak * 0.95
nd = int(0.004 * SR)
L[-nd:] *= np.linspace(1, 0, nd)
R[-nd:] *= np.linspace(1, 0, nd)

out = Path(__file__).with_name("rubber_face.wav")
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
