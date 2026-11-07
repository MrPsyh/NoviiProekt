"""SOPHIE STYLE — an ORIGINAL 30-second track (own melody, beat, bassline, chords) played
on sounds sampled from two user-supplied SOPHIE tracks (user states they have permission):
a sustained tonal note becomes the melody sampler, the rubbery bass becomes the bass
sampler, isolated drum/metal hits become the kit. Nothing is a loop of the originals.

    python3 sophie_style.py PONY.m4a HARD.m4a
"""
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent))
import rubber_face_lib as syn  # noqa: E402

SR, BPM = 44100, 96
BEAT = 60 / BPM
BAR, S16 = 4 * BEAT, BEAT / 4      # 2.5 s bars -> 12 bars = 30 s
N, TAIL = int(30 * SR), 4 * SR
rng = np.random.default_rng(96)
adsr, tt = syn.adsr, syn.tt


def at(bar, step=0.0):
    return bar * BAR + step * S16


# ------------------------------------------------------------------ dsp
def sos(kind, f, o=2):
    return signal.butter(o, f, kind, fs=SR, output="sos")


def hp(x, f, o=2):
    return signal.sosfilt(sos("highpass", f, o), x, axis=0)


def lp(x, f, o=2):
    return signal.sosfilt(sos("lowpass", f, o), x, axis=0)


def repitch(x, semis):
    idx = np.arange(0, len(x) - 1, 2 ** (semis / 12))
    if x.ndim == 1:
        return np.interp(idx, np.arange(len(x)), x)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def stereo(x, pan=0.0):
    if x.ndim == 2:
        return x
    a = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1) * np.sqrt(2)


def widen(x, amt=1.5):
    m, s = (x[:, 0] + x[:, 1]) / 2, hp((x[:, 0] - x[:, 1]) / 2, 250) * amt
    return np.stack([m + s, m - s], 1)


_t = tt(2.5)
IR = lp(rng.standard_normal((len(_t), 2)) * np.exp(-_t * 2.6)[:, None], 7000)
IR = np.concatenate([np.zeros((int(0.025 * SR), 2)), IR])
IR /= np.sqrt((IR ** 2).sum(0))


def reverb(x):
    return np.stack([signal.fftconvolve(x[:, c], IR[:, c])[:len(x)] for c in (0, 1)], 1)


# ------------------------------------------------------------------ sources -> instruments
def load(path):
    with tempfile.TemporaryDirectory() as d:
        o = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "2", str(o)],
                       check=True)
        with wave.open(str(o)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768


PONY, HARD = load(sys.argv[1]), load(sys.argv[2])


def grab(src, t, d, a=0.002, r=0.03):
    x = src[int(t * SR):int((t + d) * SR)].copy()
    x *= adsr(len(x), a, r)[:, None]
    return x / (np.abs(x).max() + 1e-9)


# melody sampler: sustained clean note (E5, MIDI 76.2) from Ponyboy's outro
MEL = grab(PONY, 183.92, 1.30, 0.01, 0.15)
MEL = hp(MEL, 250)
MEL_REF = 76.2
# bass sampler: rubbery bass note (G1, MIDI 31.3) from HARD, low-passed to strip the drums
BAS = lp(grab(HARD, 15.80, 0.45, 0.002, 0.08), 380, 4)
BAS /= np.abs(BAS).max()
BAS_REF = 31.3
# squeak sampler: high tonal blip (F6, MIDI 88.8) from HARD, high-passed
SQK = hp(grab(HARD, 123.62, 0.22, 0.002, 0.04), 600, 4)
SQK /= np.abs(SQK).max()
SQK_REF = 88.8
# kit
KICK_S = grab(HARD, 60.017, 0.40)
SNR_S = grab(HARD, 63.053, 0.30)
MET1 = grab(HARD, 137.516, 0.32)
MET2 = grab(HARD, 135.734, 0.30)
MET3 = grab(HARD, 138.590, 0.30)
HI1 = hp(grab(PONY, 70.757, 0.15), 3000)
HI2 = hp(grab(HARD, 39.307, 0.12), 2500)


def kick():
    t = tt(0.4)
    body = np.tanh(2.6 * np.sin(syn.ph(46 + 160 * np.exp(-t * 32))) * np.exp(-t * 5.5))
    k = stereo(body) * 0.7
    k[:len(KICK_S)] += KICK_S * 0.55
    return k


def snare():
    t = tt(0.4)
    nz = rng.standard_normal(len(t))
    env = sum(np.where(t >= o, np.exp(-(t - o) * 170), 0) for o in (0, 0.009, 0.018))
    env = env + np.where(t >= 0.018, np.exp(-(t - 0.018) * 18) * 0.5, 0)
    clap = signal.sosfilt(signal.butter(2, [900, 6000], "bandpass", fs=SR, output="sos"), nz * env)
    s = stereo(np.tanh(2 * clap)) * 0.5
    s[:len(SNR_S)] += SNR_S * 0.6
    s[:len(MET1)] += MET1 * 0.45
    return s


KICK, SNARE = kick(), snare()


def hat():
    t = tt(0.04)
    return hp(rng.standard_normal(len(t)), 8000) * np.exp(-t * 90) * 0.5


HAT = hat()


def mel_note(note, d, vib=True):
    """melody sampler: repitch the Ponyboy note, loop-free (sample is long enough), gate to length"""
    x = repitch(MEL, note - MEL_REF)
    n = int(d * SR)
    if len(x) < n:
        x = np.pad(x, ((0, n - len(x)), (0, 0)))
    x = x[:n] * adsr(n, 0.006, min(0.06, d / 3))[:, None]
    if vib and d > 0.3:
        t = np.arange(n) / SR
        x = x * (1 + 0.08 * np.clip((t - 0.15) * 4, 0, 1) * np.sin(2 * np.pi * 6 * t))[:, None]
    return x


def bass_note(note, d):
    x = repitch(BAS, note - BAS_REF)
    n = int(d * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * syn.mtof(note) * t) * 0.55 * adsr(n, 0.004, 0.05)
    out = stereo(sub)
    m = min(n, len(x))
    out[:m] += x[:m] * 0.9 * adsr(m, 0.001, 0.03)[:, None]
    return np.tanh(1.4 * out)


def squeak(note, d=None):
    x = repitch(SQK, note - SQK_REF)
    return x if d is None else x[:int(d * SR)]


# ------------------------------------------------------------------ composition (original)
# chord loop, one chord per bar: Em - C - G - D
CHORDS = [[64, 67, 71, 76], [60, 64, 67, 72], [55, 59, 62, 67], [62, 66, 69, 74]]
ROOTS = [28, 36, 31, 38]           # bass: E1, C2, G1, D2

# hook: (step, midi, len in 16ths), one list per bar of the 4-bar loop
HOOK = [
    [(0, 76, 2), (2, 79, 1), (3, 81, 3), (6, 83, 2), (8, 81, 1), (9, 79, 1), (10, 76, 4), (14, 74, 2)],
    [(0, 76, 2), (2, 79, 1), (3, 81, 3), (6, 86, 4), (10, 83, 2), (12, 81, 4)],
    [(0, 76, 2), (2, 79, 1), (3, 81, 3), (6, 83, 2), (8, 88, 6), (14, 86, 2)],
    [(0, 83, 3), (3, 81, 3), (6, 79, 2), (8, 76, 8)],
]
# bassline rhythm: (step, len, octave-up?)
BASS_RHY = [(0, 3, 0), (3, 2, 0), (6, 1, 1), (7, 3, 0), (10, 2, 0), (13, 3, 1)]
KICKS = [0, 7, 10]


class Bus:
    def __init__(self):
        self.x = np.zeros((N + TAIL, 2))

    def add(self, sig, t, gain=1.0, pan=0.0):
        sig = stereo(sig, pan)
        if pan and sig.ndim == 2:
            sig = sig * np.array([min(1, 1 - pan), min(1, 1 + pan)])
        i = int(round(t * SR))
        n = min(len(sig), len(self.x) - i)
        if n > 0:
            self.x[i:i + n] += sig[:n] * gain


drums, bass, mel, music, send = (Bus() for _ in range(5))
kick_times = []


def play_hook(bar, ci, octave=0, gain=0.55, rev=0.2):
    for s, n, ln in HOOK[ci]:
        x = mel_note(n + octave, ln * S16 * 0.95)
        mel.add(x, at(bar, s), gain)
        send.add(x, at(bar, s), rev)


def groove(bar, ci, full=True):
    for s in KICKS + ([14] if full and ci == 3 else []):
        drums.add(KICK, at(bar, s), 1.0 if s == 0 else 0.85)
        kick_times.append(at(bar, s))
    drums.add(SNARE, at(bar, 8), 0.85)
    send.add(SNARE, at(bar, 8), 0.2)
    drums.add(MET2, at(bar, 3), 0.35, pan=-0.4)
    drums.add(repitch(MET3, -3), at(bar, 11), 0.3, pan=0.4)
    drums.add(HI1, at(bar, 4), 0.35, pan=0.2)
    drums.add(HI1, at(bar, 12), 0.35, pan=-0.2)
    for s in range(0, 16, 1 if full else 2):
        drums.add(HAT, at(bar, s), (0.3 if s % 2 == 0 else 0.16) * (1 if full else 0.8), pan=0.3 * (-1) ** s)
    if full:
        drums.add(HI2, at(bar, 6), 0.3, pan=0.5)
        drums.add(HI2, at(bar, 14), 0.3, pan=-0.5)
    r = ROOTS[ci]
    for s, ln, up in BASS_RHY:
        bass.add(bass_note(r + 12 * up, ln * S16), at(bar, s), 0.85)


# bars 0-1: intro — hook alone on the sampler, light metal ticks, reverb
for b in range(2):
    play_hook(b, b, gain=0.5, rev=0.4)
    for s in (0, 6, 10):
        drums.add(MET2, at(b, s), 0.25, pan=0.4 * (-1) ** s)
    drums.add(HI1, at(b, 12), 0.25)
bass.add(bass_note(ROOTS[1], BAR * 0.9), at(1), 0.4)

# bars 2-5: verse groove + hook
for i, b in enumerate(range(2, 6)):
    groove(b, i, full=False)
    play_hook(b, i)
    # squeak answers in the hook's gaps
    drums.add(squeak(CHORDS[i][2] + 12), at(b, 14), 0.25, pan=0.5)

# bars 6-7: break — no kick, pads + sampler melody sustained an octave up, rubber bass pulses
for i, b in enumerate(range(6, 8)):
    ci = i * 2  # Em then G
    pad = syn.supersaw([n + 12 for n in CHORDS[ci]], BAR, bright=(4, 9), attack=0.3,
                       voices=(-0.15, -0.07, 0, 0.07, 0.15))
    music.add(widen(stereo(pad)), at(b), 0.32)
    send.add(stereo(pad), at(b), 0.3)
    for s in (0, 8):
        bass.add(bass_note(ROOTS[ci], 6 * S16), at(b, s), 0.6)
    drums.add(SNARE, at(b, 8), 0.5)
    send.add(SNARE, at(b, 8), 0.35)
    for s in range(0, 16, 2):
        drums.add(HAT, at(b, s), 0.12)
for b, line in ((6, [(0, 88, 6), (6, 86, 2), (8, 83, 8)]), (7, [(0, 88, 4), (4, 91, 4), (8, 86, 8)])):
    for s, n, ln in line:
        x = mel_note(n, ln * S16 * 0.95)
        mel.add(x, at(b, s), 0.45)
        send.add(x, at(b, s), 0.45)
drums.add(syn.riser(BAR * 0.5), at(7, 8), 0.4)
for i in range(8):  # snare build in the last half-bar
    drums.add(repitch(SNARE, i * 0.6), at(7, 8 + i), 0.15 + 0.04 * i)

# bars 8-11: full groove, hook doubled an octave up, squeaks, then the cut
for i, b in enumerate(range(8, 12)):
    groove(b, i, full=True)
    play_hook(b, i, gain=0.55)
    play_hook(b, i, octave=12, gain=0.22, rev=0.15)
    for s in (5, 13):
        drums.add(squeak(CHORDS[i][(s // 4) % 4] + 12), at(b, s), 0.22, pan=0.5 * (-1) ** s)
drums.add(MET1, at(8), 0.6)

# ------------------------------------------------------------------ mix
tg = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for k in kick_times:
    i = int(k * SR)
    j = min(len(duck), i + int(0.5 * SR))
    duck[i:j] = np.minimum(duck[i:j], 1 - 0.55 * np.exp(-(tg[i:j] - k) / 0.1))
d = duck[:, None]

dl = int(3 * S16 * SR)
src = mel.x.mean(1)
dly = np.zeros_like(mel.x)
for tap in range(1, 5):
    dly[dl * tap:, tap % 2] += src[:-dl * tap] * 0.38 ** tap
dly = lp(hp(dly, 400), 6000)
wet = reverb(hp(send.x, 300))

mix = (drums.x + hp(bass.x, 28) * (0.55 + 0.45 * d) + mel.x * (0.8 + 0.2 * d)
       + music.x * d + dly * 0.3 + wet * 0.4)[:N].copy()

# glitch into the cut: last half-beat chopped into rising 32nds
a, sl = int(at(11, 14) * SR), int(S16 / 2 * SR)
piece = mix[a:a + sl].copy()
out = []
for r in range(4):
    p = repitch(piece, 3 * r) * adsr(len(repitch(piece, 3 * r)), 0.001, 0.002)[:, None]
    out.append(p)
seq = np.concatenate(out)
while len(seq) < 2 * int(S16 * SR):
    seq = np.concatenate([seq, out[-1]])
mix[a:a + 2 * int(S16 * SR)] = seq[:2 * int(S16 * SR)]

# master
mix = hp(mix, 25, 4)
mix = np.tanh(1.15 * mix / np.percentile(np.abs(mix), 99.95))
mix = mix / np.abs(mix).max() * 0.966
mix[-int(0.003 * SR):] *= np.linspace(1, 0, int(0.003 * SR))[:, None]

dst = Path(__file__).with_name("sophie_style.wav")
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
