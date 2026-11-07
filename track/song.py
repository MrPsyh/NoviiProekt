"""SONG — 30-second hyperpop fragment written song-first.

Clear structure (verse -> build -> chorus x2), a 4-bar chord loop (Bb - C - Dm - F,
IV-V-vi-I in F major), a singable verse melody and a repeating chorus hook played by one
upfront lead and doubled by a pitched-up formant "voice". Steady drums, an 808 that follows
the chords. Kick/snare tone is layered with one-shots from user-supplied source tracks
(user states they have permission; source audio is not in the repo).

    python3 song.py PONY.m4a HARD.m4a
"""
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d

sys.path.insert(0, str(Path(__file__).parent))
import rubber_face_lib as syn  # noqa: E402

SR, BPM = 44100, 160
BEAT = 60 / BPM
BAR, S16 = 4 * BEAT, BEAT / 4      # 1.5 s bars, 20 bars = 30 s
N, TAIL = int(30 * SR), 4 * SR
rng = np.random.default_rng(5)
adsr, tt, ph, mtof = syn.adsr, syn.tt, syn.ph, syn.mtof


def at(bar, step=0.0):
    return bar * BAR + step * S16


# ------------------------------------------------------------------ dsp
def hp(x, f, o=2):
    return signal.sosfilt(signal.butter(o, f, "highpass", fs=SR, output="sos"), x, axis=0)


def lp(x, f, o=2):
    return signal.sosfilt(signal.butter(o, f, "lowpass", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi):
    return signal.sosfilt(signal.butter(2, [lo, hi], "bandpass", fs=SR, output="sos"), x, axis=0)


def stereo(x, pan=0.0):
    if x.ndim == 2:
        return x
    a = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1) * np.sqrt(2)


def widen(x, amt=1.4):
    m, s = (x[:, 0] + x[:, 1]) / 2, hp((x[:, 0] - x[:, 1]) / 2, 200) * amt
    return np.stack([m + s, m - s], 1)


def haas(x, ms=11):
    d = int(ms / 1000 * SR)
    return np.stack([x, np.concatenate([np.zeros(d), x[:-d]])], 1)


_t = tt(2.2)
IR = lp(rng.standard_normal((len(_t), 2)) * np.exp(-_t * 3.0)[:, None], 6500)
IR = np.concatenate([np.zeros((int(0.02 * SR), 2)), IR])
IR /= np.sqrt((IR ** 2).sum(0))


def reverb(x):
    return np.stack([signal.fftconvolve(x[:, c], IR[:, c])[:len(x)] for c in (0, 1)], 1)


def repitch(x, semis):
    idx = np.arange(0, len(x) - 1, 2 ** (semis / 12))
    if x.ndim == 1:
        return np.interp(idx, np.arange(len(x)), x)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def saw(freq):
    fu = np.repeat(freq, 2)
    p = np.cumsum(fu) / (2 * SR) + rng.uniform()
    return signal.resample_poly(2 * (p % 1.0) - 1, 1, 2)


# ------------------------------------------------------------------ source one-shots
def load(path):
    with tempfile.TemporaryDirectory() as d:
        o = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "2", str(o)],
                       check=True)
        with wave.open(str(o)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768


def cut(src, t, d):
    x = src[max(0, int((t - 0.003) * SR)):][:int(d * SR)].copy()
    x *= adsr(len(x), 0.003, 0.04)[:, None]
    return x / np.abs(x).max()


PONY, HARD = load(sys.argv[1]), load(sys.argv[2])
KICK_SMP = cut(PONY, 2.682, 0.35)
SNARE_SMP = cut(HARD, 4.853, 0.22)
METAL_SMP = cut(PONY, 41.854, 0.3)


# ------------------------------------------------------------------ instruments
def kick_snd():
    t = tt(0.4)
    body = np.sin(ph(48 + 170 * np.exp(-t * 35))) * np.exp(-t * 6)
    k = np.tanh(2.5 * body)
    out = stereo(k) * 0.75
    out[:len(KICK_SMP)] += KICK_SMP[:len(t)] * 0.35
    return out


KICK = kick_snd()


def snare_snd():
    t = tt(0.3)
    nz = rng.standard_normal(len(t))
    env = sum(np.where(t >= o, np.exp(-(t - o) * 160), 0) for o in (0, 0.008, 0.017))
    env = env + np.where(t >= 0.017, np.exp(-(t - 0.017) * 16) * 0.55, 0)
    clap = np.tanh(2 * bp(nz * env, 900, 6000))
    tone = np.sin(ph(200 + 60 * np.exp(-t * 40))) * np.exp(-t * 28) * 0.6
    s = stereo(clap + tone) * 0.7
    s[:len(SNARE_SMP)] += SNARE_SMP * 0.45
    return s


SNARE = snare_snd()


def hat_snd(open_=False):
    t = tt(0.25 if open_ else 0.045)
    nz = hp(rng.standard_normal(len(t)), 7000)
    return nz * np.exp(-t * (12 if open_ else 75)) * adsr(len(t), 0.0005, 0.01)


HAT, OHAT = hat_snd(), hat_snd(True)


def bass808(note, d, glide_to=None):
    t = tt(d)
    m = np.full(len(t), float(note))
    if glide_to is not None:
        g0 = max(0, len(t) - int(0.09 * SR))
        m[g0:] = np.linspace(note, glide_to, len(t) - g0)
    f = mtof(m) * (1 + 0.6 * np.exp(-t * 70))
    s = np.sin(ph(f))
    x = 0.7 * s + 0.35 * np.tanh(4 * s)
    return x * adsr(len(t), 0.002, 0.04)


def lead(notes, total, bright=5200, vib=0.28):
    """mono lead: 2 detuned saws + square, portamento, delayed vibrato, per-note gate"""
    n = int(total * SR)
    m = np.full(n, float(notes[0][1]))
    gate = np.zeros(n)
    vib_env = np.zeros(n)
    for (s, note, d) in notes:
        a, b = int(s * SR), min(n, int((s + d) * SR))
        m[a:] = note
        g = np.ones(b - a)
        g[:int(0.005 * SR)] = np.linspace(0, 1, int(0.005 * SR))
        r = min(len(g), int(0.035 * SR))
        g[-r:] *= np.linspace(1, 0, r)
        tg = np.arange(b - a) / SR
        g *= 0.82 + 0.18 * np.exp(-tg * 8)
        gate[a:b] = np.maximum(gate[a:b], g)
        vib_env[a:b] = np.clip((tg - 0.14) / 0.2, 0, 1)
    al = np.exp(-1 / (0.022 * SR))
    m = signal.lfilter([1 - al], [1, -al], m, zi=[m[0] * al])[0]
    m = m + vib * vib_env * np.sin(2 * np.pi * 5.8 * np.arange(n) / SR)
    f = mtof(m)
    s1, s2 = saw(f * 2 ** (0.07 / 12))[:n], saw(f * 2 ** (-0.07 / 12))[:n]
    sq = np.sign(saw(f * 0.5)[:n]) * 0.35
    x = lp(0.45 * s1 + 0.45 * s2 + sq, bright, 2)
    x = np.tanh(1.6 * x) * gate
    return widen(haas(x, 9) * 0.8, 1.2)


VOWELS = "aoeaiaoa"


def voice_line(notes, octave=12, gain=1.0):
    out = np.zeros((N + TAIL, 2))
    for i, (s, note, d) in enumerate(notes):
        v = VOWELS[i % len(VOWELS)]
        x = syn.voice(note + octave, d * 0.95, v, "a" if v != "a" else "o", 0.0, shift=1.6, breath=0.2)
        a = int(s * SR)
        out[a:a + len(x)] += stereo(x) * gain
    return out


def pad(chord, d, bright=(5, 9)):
    x = syn.supersaw(chord, d, bright=bright, attack=0.06,
                     voices=(-0.16, -0.08, 0, 0.08, 0.16))
    return widen(stereo(x), 1.7)


def keys(chord, d):
    """bright bell-piano chord stab"""
    out = sum(syn.glass_bell(n, d) for n in chord) / len(chord)
    return stereo(out)


def arp_note(note, d):
    t = tt(d)
    x = np.sign(np.sin(2 * np.pi * mtof(note) * t)) * 0.5
    return lp(x, 4000) * np.exp(-t * 10) * adsr(len(t), 0.002, 0.01)


# ------------------------------------------------------------------ the song
# chords (one per bar, 4-bar loop):   Bb        C         Dm        F
CHORDS = [[58, 62, 65, 69], [60, 64, 67, 72], [62, 65, 69, 74], [65, 69, 72, 77]]
ROOTS = [34, 36, 38, 41]          # 808 roots: Bb1, C2, D2, F2

# verse melody (4 bars). (step-in-bar, midi, length-in-16ths)
VERSE = [
    [(0, 74, 2), (2, 77, 2), (4, 74, 2), (6, 72, 4), (10, 70, 2), (12, 72, 4)],
    [(0, 76, 2), (2, 79, 2), (4, 76, 2), (6, 74, 2), (8, 72, 6)],
    [(0, 74, 2), (2, 77, 2), (4, 81, 4), (8, 79, 2), (10, 77, 2), (12, 76, 4)],
    [(0, 77, 6), (6, 72, 2), (8, 69, 2), (10, 72, 6)],
]
# chorus hook (4 bars): same rhythmic motif repeated, rising in bar 3, resolving in bar 4
HOOK = [
    [(0, 77, 3), (3, 77, 3), (6, 79, 2), (8, 81, 4), (12, 79, 2), (14, 77, 2)],
    [(0, 76, 3), (3, 76, 3), (6, 77, 2), (8, 79, 8)],
    [(0, 81, 3), (3, 81, 3), (6, 82, 2), (8, 84, 4), (12, 82, 2), (14, 81, 2)],
    [(0, 81, 4), (4, 79, 2), (6, 77, 10)],
]
HOOK_END2 = [(0, 81, 4), (4, 84, 2), (6, 89, 10)]   # 2nd chorus: leap up, then the cut


def to_notes(phrase, bar0, transpose=0, last=None):
    out = []
    for i, bar_notes in enumerate(phrase):
        if last is not None and i == len(phrase) - 1:
            bar_notes = last
        for s, n, ln in bar_notes:
            out.append((at(bar0 + i, s), n + transpose, ln * S16 * 0.94))
    return out


class Bus:
    def __init__(self):
        self.x = np.zeros((N + TAIL, 2))

    def add(self, sig, t, gain=1.0, pan=0.0):
        sig = stereo(sig, pan)
        i = int(round(t * SR))
        n = min(len(sig), len(self.x) - i)
        if n > 0:
            self.x[i:i + n] += sig[:n] * gain


drums, bass, music, ld, vox, send = (Bus() for _ in range(6))
kicks = []


def K(bar, s, g=1.0):
    drums.add(KICK, at(bar, s), g)
    kicks.append(at(bar, s))


def SN(bar, s, g=0.8):
    drums.add(SNARE, at(bar, s), g)
    send.add(SNARE, at(bar, s), g * 0.25)


# Sections: intro 0-1 | verse 2-7 | build 8-9 | chorus 10-13 | chorus 14-17 | tag 18-19 (cut)
# -- intro (bars 0-1): keys + filtered verse first line
for b in range(2):
    c = CHORDS[b % 4]
    for s in (0, 3, 6, 10, 12):
        music.add(keys([n + 12 for n in c], 0.5), at(b, s), 0.7)
        send.add(keys([n + 12 for n in c], 0.5), at(b, s), 0.3)
    music.add(pad(c, BAR, (3, 6)), at(b), 0.3)
    bass.add(bass808(ROOTS[b % 4], BAR * 0.95), at(b), 0.45)

# -- verse (bars 2-7 -> verse melody over bars 2-5, repeated first half 6-7)
for b in range(2, 8):
    ci = b % 4
    c, r = CHORDS[ci], ROOTS[ci]
    K(b, 0)
    K(b, 10, 0.85)
    if b % 2:
        K(b, 7, 0.6)
    SN(b, 8)
    for s in range(0, 16, 2):
        drums.add(HAT, at(b, s), 0.35 if s % 4 else 0.22, pan=0.25)
    bass.add(bass808(r, 7 * S16), at(b, 0), 0.8)
    bass.add(bass808(r, 6 * S16, glide_to=ROOTS[(ci + 1) % 4]), at(b, 10), 0.8)
    for s in (0, 3, 6, 10, 12):
        music.add(keys([n + 12 for n in c], 0.45), at(b, s), 0.25)
    music.add(pad(c, BAR, (3, 5)), at(b), 0.18)
v_notes = to_notes(VERSE, 2) + to_notes(VERSE[:2], 6)
ld.add(lead([(s, n, d) for s, n, d in v_notes], N / SR + 1, bright=3800), 0, 0.5)
# rubbery SOPHIE-style squeak answering each verse line
for b in (3, 5, 7):
    music.add(syn.latex_squeak(84, 3 * S16, up=0.7), at(b, 13), 0.18, pan=0.4)
    send.add(syn.latex_squeak(84, 3 * S16, up=0.7), at(b, 13), 0.15)

# -- build (bars 8-9): snare roll speeding up, riser, melody climbs
for b in (8, 9):
    ci = b % 4
    music.add(pad(CHORDS[ci], BAR, (4, 14)), at(b), 0.22)
    bass.add(bass808(ROOTS[ci], BAR * 0.95), at(b), 0.6)
    K(b, 0)
roll = [s for s in range(0, 16, 4)] + [16 + s for s in range(0, 8, 2)] + [24 + s for s in range(0, 8, 1)]
for i, st in enumerate(roll):
    drums.add(repitch(SNARE, i * 0.4), at(8) + st * S16, 0.25 + 0.03 * i)
drums.add(syn.riser(BAR * 2), at(8), 0.35)
build_line = [(at(8, 0), 72, 4 * S16), (at(8, 4), 74, 4 * S16), (at(8, 8), 76, 4 * S16), (at(8, 12), 77, 4 * S16),
              (at(9, 0), 79, 4 * S16), (at(9, 4), 81, 4 * S16), (at(9, 8), 84, 6 * S16)]
ld.add(lead(build_line, N / SR + 1, bright=4500), 0, 0.5)
vox.add(voice_line([(at(9, 14), 84, 2 * S16)], 12, 0.4), 0)  # "ya!" pickup into the drop

# -- chorus (bars 10-17), then tag 18-19 cut
for b in range(10, 20):
    ci = b % 4
    c, r = CHORDS[ci], ROOTS[ci]
    for s in (0, 6, 8, 14) if b % 2 == 0 else (0, 6, 8, 11):
        K(b, s, 1.0 if s in (0, 8) else 0.8)
    SN(b, 4)
    SN(b, 12)
    for s in range(0, 16, 2):
        drums.add(HAT, at(b, s), 0.32, pan=0.25)
        drums.add(HAT, at(b, s + 1), 0.18, pan=-0.25)
    if ci == 3:
        drums.add(OHAT, at(b, 14), 0.3)
        for i in range(6):  # triplet hat roll into next phrase
            drums.add(repitch(HAT, i), at(b, 12) + i * S16 * 2 / 3, 0.2 + 0.03 * i, pan=-0.3 + 0.12 * i)
    if b in (10, 14):
        drums.add(stereo(METAL_SMP), at(b), 0.5)
        drums.add(stereo(hp(rng.standard_normal(int(1.2 * SR)) * np.exp(-tt(1.2) * 3), 4000)), at(b), 0.35)
    for s, ln in ((0, 6), (6, 2), (8, 6), (14, 2)):
        nxt = ROOTS[(ci + 1) % 4] if s == 14 else None
        bass.add(bass808(r + (12 if s == 6 else 0), ln * S16, glide_to=nxt), at(b, s), 0.85)
    music.add(pad([n + 12 for n in c], BAR, (6, 10)), at(b), 0.3)
    send.add(pad([n + 12 for n in c], BAR, (6, 10)), at(b), 0.12)
    for s in range(0, 16, 2):  # 8th-note arp up the chord
        n = c[[0, 1, 2, 3, 2, 1, 2, 3][s // 2]] + 24
        music.add(arp_note(n, S16 * 1.8), at(b, s), 0.10, pan=0.5 * (-1) ** (s // 2))

ch1 = to_notes(HOOK, 10)
ch2 = to_notes(HOOK, 14)
tag = to_notes(HOOK[:2], 18)
lead_ch = lead(ch1 + ch2 + tag, N / SR + 1, bright=6500)
ld.add(lead_ch, 0, 0.55)
send.add(lead_ch, 0, 0.12)
# voice doubles the hook an octave up — first chorus quietly, second louder (+ harmony a 3rd below)
vox.add(voice_line(ch1, 12, 0.22), 0)
vox.add(voice_line(ch2 + tag, 12, 0.32), 0)
vox.add(voice_line([(s, n - 3 if n % 12 in (5, 9) else n - 4, d) for s, n, d in ch2], 12, 0.14), 0)

# ------------------------------------------------------------------ mix
tg = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for k in kicks:
    i = int(k * SR)
    j = min(len(duck), i + int(0.4 * SR))
    duck[i:j] = np.minimum(duck[i:j], 1 - 0.6 * np.exp(-(tg[i:j] - k) / 0.08))
d = duck[:, None]

# ping-pong 3/16 delay on the lead
dl = int(3 * S16 * SR)
src = ld.x.mean(1)
dly = np.zeros_like(ld.x)
for tap in range(1, 5):
    dly[dl * tap:, tap % 2] += src[:-dl * tap] * 0.4 ** tap
dly = lp(hp(dly, 400), 5000)

wet = reverb(hp(send.x + vox.x * 0.5, 300))

mix = (drums.x
       + hp(bass.x, 30) * (0.5 + 0.5 * d)
       + music.x * d
       + ld.x * (0.85 + 0.15 * d)
       + vox.x
       + dly * 0.35
       + wet * 0.35 * d)[:N].copy()

# intro low-pass opening & a short glitch on the last beat before the cut
mix[:int(at(2) * SR)] = signal.sosfilt(signal.butter(2, 1800, "lowpass", fs=SR, output="sos"),
                                       mix[:int(at(2) * SR)], axis=0) * 0.75 + mix[:int(at(2) * SR)] * 0.25
a, sl = int(at(19, 12) * SR), int(S16 / 2 * SR)
piece = mix[a:a + sl] * adsr(sl, 0.001, 0.002)[:, None]
n2 = int(2 * S16 * SR)
mix[a:a + n2] = np.tile(piece, (4, 1))[:n2]

# master
mix = hp(mix, 28, 4)
mix = np.tanh(1.2 * mix / np.percentile(np.abs(mix), 99.95))
pk = maximum_filter1d(np.abs(mix).max(1), size=int(0.008 * SR) + 1)
g = np.minimum(1, 0.9 / (pk + 1e-9))
al = np.exp(-1 / (0.002 * SR))
g = np.minimum(signal.lfilter([1 - al], [1, -al], g), 0.9 / (pk + 1e-9))
mix = mix * g[:, None]
mix = mix / np.abs(mix).max() * 0.966
mix[-int(0.003 * SR):] *= np.linspace(1, 0, int(0.003 * SR))[:, None]

out = Path(__file__).with_name("song.wav")
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("wrote", out, f"{len(mix) / SR:.2f}s")
if shutil.which("ffmpeg"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-b:a", "320k",
                    str(out.with_suffix(".mp3"))], check=True)
    print("wrote", out.with_suffix(".mp3"))
