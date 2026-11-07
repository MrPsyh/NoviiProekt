"""HYPERPOP MAX — 30-second maximalist hyperpop fragment.

160 BPM, 20 bars. Everything at once: distorted 808 glides, 7-voice supersaw lead with
portamento, chipmunk formant vocal chops, chiptune arps, hat rolls, claps, laser zaps,
resonant filter sweeps, tape-start / tape-stop, bitcrush, stutters, reverb, sidechain,
impacts, master limiter — plus one-shots chopped from two user-supplied source tracks
(the user states they have permission; source audio is not stored in the repo).

    python3 hyperpop_max.py PONY.m4a HARD.m4a
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
BAR, S16 = 4 * BEAT, BEAT / 4     # 1.5 s bars -> 20 bars == 30 s
DUR = 30.0
N, TAIL = int(SR * DUR), SR * 4
rng = np.random.default_rng(160)
adsr, tt, ph, mtof = syn.adsr, syn.tt, syn.ph, syn.mtof


def at(bar, step=0.0):
    return bar * BAR + step * S16


# ================================================================ DSP toolbox
def biquad_lp(f, q):
    w = 2 * np.pi * np.clip(f, 20, SR * 0.45) / SR
    al = np.sin(w) / (2 * q)
    c = np.cos(w)
    b = np.array([(1 - c) / 2, 1 - c, (1 - c) / 2])
    a = np.array([1 + al, -2 * c, 1 - al])
    return b / a[0], a / a[0]


def sweep_lp(x, f0, f1, q=4.0, curve=2.0, block=256):
    """time-varying resonant low-pass (works on mono or stereo)"""
    st = x.ndim == 2
    y = np.zeros_like(x)
    chans = [x[:, 0], x[:, 1]] if st else [x]
    nb = int(np.ceil(len(x) / block))
    for ci, ch in enumerate(chans):
        zi = np.zeros(2)
        out = y[:, ci] if st else y
        for i in range(nb):
            pos = (i / max(1, nb - 1)) ** curve
            f = f0 * (f1 / f0) ** pos
            b, a = biquad_lp(f, q)
            seg = ch[i * block:(i + 1) * block]
            out[i * block:i * block + len(seg)], zi = signal.lfilter(b, a, seg, zi=zi)
    return y


def bandpass(x, lo, hi):
    sos = signal.butter(2, [lo, hi], "bandpass", fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def highpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x, axis=0)


def lowpass(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "lowpass", fs=SR, output="sos"), x, axis=0)


def make_ir(d=2.4, decay=2.6, pre=0.018):
    t = tt(d)
    ir = rng.standard_normal((len(t), 2)) * np.exp(-t * decay)[:, None]
    ir = lowpass(ir, 7000)
    ir = np.concatenate([np.zeros((int(pre * SR), 2)), ir])
    return ir / np.sqrt((ir ** 2).sum(0))


IR = make_ir()


def reverb(x):
    return np.stack([signal.fftconvolve(x[:, c], IR[:, c])[:len(x)] for c in (0, 1)], 1)


def crush(x, bits=6, hold=3):
    q = 2 ** bits
    return np.repeat(np.round(x[::hold] * q) / q, hold, axis=0)[:len(x)]


def tape(x, start, dur, direction="stop"):
    """tape stop (speed 1->0) or tape start (0->1) over [start, start+dur)"""
    a, n = int(start * SR), int(dur * SR)
    seg = x[a:a + 4 * n].copy()
    u = np.linspace(0, 1, n)
    speed = (1 - u) ** 1.5 if direction == "stop" else u ** 1.5
    pos = np.cumsum(speed)
    pos = pos - pos[0]
    if direction == "start":
        pos = pos + (len(seg) // 4 - pos[-1]) * 0  # starts at the region head
    for c in (0, 1):
        x[a:a + n, c] = np.interp(pos, np.arange(len(seg)), seg[:, c])


def stutter(x, start, dur, slice_len, pitch_up=0.0):
    a, n, s = int(start * SR), int(dur * SR), int(slice_len * SR)
    piece = x[a:a + s] * adsr(s, 0.001, 0.002)[:, None]
    out, filled = [], 0
    while filled < n:  # pitched-up slices get shorter, so keep looping until the gap is full
        p = piece if not pitch_up else repitch(piece, pitch_up * filled / n)
        p = p * adsr(len(p), 0.001, 0.002)[:, None]
        out.append(p)
        filled += len(p)
    x[a:a + n] = np.concatenate(out)[:n]


def widen(x, amt=1.4):
    m, s = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    s = highpass(s, 200) * amt
    return np.stack([m + s, m - s], 1)


def repitch(x, semis):
    r = 2 ** (semis / 12)
    idx = np.arange(0, len(x) - 1, r)
    if x.ndim == 1:
        return np.interp(idx, np.arange(len(x)), x)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


def stereo(sig, pan=0.0):
    if sig.ndim == 2:
        return sig
    a = (pan + 1) * np.pi / 4
    return np.stack([sig * np.cos(a), sig * np.sin(a)], 1) * np.sqrt(2)


# ================================================================ sources
def load(path):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ar", str(SR), "-ac", "2", str(out)],
                       check=True)
        with wave.open(str(out)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2)
    return x.astype(np.float64) / 32768


PONY, HARD = load(sys.argv[1]), load(sys.argv[2])


def cut(src, t, d, pre=0.004, fade=0.03):
    a = max(0, int((t - pre) * SR))
    x = src[a:a + int(d * SR)].copy()
    env = np.ones(len(x))
    env[:int(pre * SR)] = np.linspace(0, 1, int(pre * SR))
    env[-int(fade * SR):] *= np.linspace(1, 0, int(fade * SR))
    x = x * env[:, None]
    return x / (np.abs(x).max() + 1e-9)


def fit(x, d):
    idx = np.linspace(0, len(x) - 1, int(d * SR))
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)


SMP = {
    "h_low": cut(HARD, 31.428, 0.5), "h_low2": cut(HARD, 25.716, 0.4),
    "h_mid": cut(HARD, 137.497, 0.35), "h_mid2": cut(HARD, 74.641, 0.3),
    "h_hi": cut(HARD, 4.853, 0.25), "h_hi2": cut(HARD, 75.743, 0.25), "h_hi3": cut(HARD, 62.044, 0.3),
    "p_low": cut(PONY, 2.682, 0.5), "p_low2": cut(PONY, 96.015, 0.45),
    "p_hi": cut(PONY, 0.151, 0.3), "p_hi2": cut(PONY, 70.74, 0.25), "p_hi3": cut(PONY, 41.854, 0.35),
}
SMP["p_loop"] = fit(cut(PONY, 96.015, 4 * 60 / 103.4, fade=0.01), 4 * BEAT)
SMP["h_loop"] = fit(cut(HARD, 31.428, 4 * 60 / 84.7, fade=0.01), 4 * BEAT)
MID_REF = 68.0  # reference pitch for the tuned HARD mid-hit sampler


# ================================================================ new instruments
def saw_osc(freq, oversample=2):
    """naive saw at 2x, decimated: bright, slightly gritty — very hyperpop"""
    fu = np.repeat(freq, oversample)
    p = np.cumsum(fu) / (SR * oversample) + rng.uniform()
    s = 2 * (p % 1.0) - 1
    return signal.resample_poly(s, 1, oversample)


def glide_curve(notes, d_total, glide=0.035):
    """notes: list of (start_s, midi). returns per-sample frequency with portamento"""
    n = int(d_total * SR)
    m = np.zeros(n)
    for i, (s, note) in enumerate(notes):
        m[int(s * SR):] = note
    a = np.exp(-1 / (glide * SR))
    m = signal.lfilter([1 - a], [1, -a], m, zi=[m[0] * a])[0]
    return mtof(m)


def supersaw_lead(notes, d_total, gates, detune=0.22, voices=7, cutoff=(9000, 2500)):
    f = glide_curve(notes, d_total)
    n = len(f)
    L, R = np.zeros(n), np.zeros(n)
    for v in range(voices):
        dt = detune * (v / (voices - 1) * 2 - 1)
        x = saw_osc(f * 2 ** (dt / 12))[:n]
        if v % 2:
            L += x
        else:
            R += x
        if v == voices // 2:
            L += x * 0.5
            R += x * 0.5
    x = np.stack([L, R], 1) / voices
    vib = 1  # noqa
    env = np.zeros(n)
    for s, e in gates:
        a, b = int(s * SR), min(n, int(e * SR))
        seg = np.ones(b - a)
        k = min(len(seg), int(0.006 * SR))
        seg[:k] = np.linspace(0, 1, k)
        r = min(len(seg), int(0.03 * SR))
        seg[-r:] *= np.linspace(1, 0, r)
        env[a:b] = np.maximum(env[a:b], seg)
    x = sweep_lp(x, cutoff[0], cutoff[1], q=1.6, curve=1.0, block=512)
    x = np.tanh(2.2 * x) * env[:, None]
    return widen(x, 1.6)


def saw808(note_from, note_to, d, glide_at=0.0, glide_t=0.08, drive=5.0):
    t = tt(d)
    m = np.where(t < glide_at, note_from,
                 note_from + (note_to - note_from) * np.clip((t - glide_at) / glide_t, 0, 1))
    f = mtof(m) * (1 + 0.9 * np.exp(-t * 60))
    body = np.sin(ph(f))
    x = np.tanh(drive * body) * 0.55 + body * 0.6
    x += rng.standard_normal(len(t)) * np.exp(-t * 500) * 0.3
    return x * adsr(len(t), 0.001, 0.03) * (0.65 + 0.35 * np.exp(-t * 3))


def chip_arp(note, d, duty=0.25):
    t = tt(d)
    p = (mtof(note) * t) % 1.0
    x = np.where(p < duty, 1.0, -1.0) * 0.5
    x = crush(x[:, None], 4, 2)[:, 0]
    return x * np.exp(-t * 9) * adsr(len(t), 0.001, 0.01)


def clap(d=0.35):
    t = tt(d)
    nz = rng.standard_normal(len(t))
    env = np.zeros(len(t))
    for o in (0, 0.009, 0.019, 0.03):
        env += np.where(t >= o, np.exp(-(t - o) * 180), 0)
    env += np.where(t >= 0.03, np.exp(-(t - 0.03) * 14) * 0.5, 0)
    return np.tanh(2 * bandpass(nz * env, 900, 5000)) * adsr(len(t), 0.0005, 0.02)


def laser(d=0.22, f0=4000, f1=90):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * 26)
    return np.sin(ph(f) + 2.5 * np.sin(ph(f * 1.5))) * np.exp(-t * 9) * adsr(len(t), 0.001, 0.02)


def impact(d=2.0):
    t = tt(d)
    boom = np.sin(ph(30 + 90 * np.exp(-t * 8))) * np.exp(-t * 2.2)
    nz = rng.standard_normal(len(t))
    return np.tanh(2.5 * boom) + highpass(nz, 3000) * np.exp(-t * 3) * 0.5


def chipmunk(note, d, v1="a", v2=None, glide=0.0):
    return syn.voice(note, d, v1, v2, glide, shift=1.75, breath=0.25)


def blip(note, d=0.09):
    t = tt(d)
    return (np.sin(2 * np.pi * mtof(note) * t) + 0.3 * np.sin(4 * np.pi * mtof(note) * t)) * np.exp(-t * 40)


# ================================================================ buses
class Bus:
    def __init__(self):
        self.x = np.zeros((N + TAIL, 2))

    def add(self, sig, start, pan=0.0, gain=1.0):
        sig = stereo(sig, pan)
        if sig is not None and pan and sig.ndim == 2 and sig.shape[1] == 2:
            pass
        i = int(round(start * SR))
        n = min(len(sig), len(self.x) - i)
        if n > 0:
            self.x[i:i + n] += sig[:n] * gain


drums, bass, music, lead, vox, verb_send, dly_send = (Bus() for _ in range(7))
kicks = []


def smp(name, bar, s, gain=0.8, pan=0.0, semis=0.0, bus=None):
    x = SMP[name] if not semis else repitch(SMP[name], semis)
    if pan:
        x = x * np.array([min(1, 1 - pan), min(1, 1 + pan)])
    (bus or drums).add(x, at(bar, s), 0, gain)


def kick(bar, s, gain=1.0, src="p_low"):
    smp(src, bar, s, gain * 0.7)
    drums.add(syn.kick(0.35, 3.0), at(bar, s), gain=gain * 0.6)
    kicks.append(at(bar, s))


def snare(bar, s, gain=0.8, flavor="h_hi"):
    drums.add(clap(), at(bar, s), gain=gain * 0.7)
    smp(flavor, bar, s, gain * 0.55)
    verb_send.add(clap(), at(bar, s), gain=gain * 0.25)


def hats(bar, steps, gain=0.4, roll_at=None):
    for s in steps:
        drums.add(syn.hat(0.04), at(bar, s), pan=0.35 * np.sin(s * 2.1), gain=gain)
    if roll_at is not None:  # hyperpop hat roll: 32nd-note triplets, rising
        for i in range(6):
            x = repitch(syn.hat(0.035), i * 1.5)
            drums.add(x, at(bar, roll_at) + i * S16 * 2 / 6, pan=-0.4 + 0.16 * i, gain=gain * 0.9)


def bass808(bar, s, note, ln, to=None, glide_at=None):
    x = saw808(note, to if to is not None else note, ln * S16, (glide_at or ln * 0.6) * S16)
    bass.add(x, at(bar, s), gain=0.75)


def keyhit(bar, s, note, ln, gain=0.3, pan=0.0, rev=0.15, dly=0.15):
    x = repitch(SMP["h_mid"], note - MID_REF)
    n = min(len(x), int(ln * S16 * SR))
    x = x[:n] * adsr(n, 0.001, 0.015)[:, None]
    music.add(x * np.array([min(1, 1 - pan), min(1, 1 + pan)]), at(bar, s), gain=gain)
    verb_send.add(x, at(bar, s), gain=rev)
    dly_send.add(x, at(bar, s), gain=dly)


def vchop(bar, s, note, ln, v1="a", v2=None, glide=0.0, gain=0.4, pan=0.0, rev=0.2, dly=0.12):
    x = chipmunk(note, ln * S16 * 0.92, v1, v2, glide)
    vox.add(x, at(bar, s), pan, gain)
    verb_send.add(x, at(bar, s), pan, rev)
    dly_send.add(x, at(bar, s), pan, dly)


CH = {"Db": [61, 65, 68, 72], "Eb": [63, 67, 70, 75], "Fm": [65, 68, 72, 75], "Ab": [63, 68, 72, 75]}
ROOT = {"Db": 37, "Eb": 39, "Fm": 41, "Ab": 44}
ORDER = ["Db", "Eb", "Fm", "Ab"]


def chord(bar):
    return ORDER[bar % 4]


# ================================================================ ARRANGEMENT
# --- A  bars 0-1 (0-3 s): filtered intro, chipmunk vocal, bells, crushed
intro = np.zeros((int(2 * BAR * SR), 2))
for b in range(2):
    c = CH[chord(b)]
    pad = syn.supersaw([n + 12 for n in c], BAR, bright=(3, 9), attack=0.05)
    intro[int(b * BAR * SR):int(b * BAR * SR) + len(pad)] += stereo(pad) * 0.5
intro = sweep_lp(intro, 350, 6000, q=6, curve=2.2)
music.add(crush(intro, 7, 2), 0, gain=0.9)
verb_send.add(intro, 0, gain=0.3)
for b in range(2):
    for s in range(0, 16, 2):
        keyhit(b, s, CH[chord(b)][(s // 2) % 4] + 12, 2, gain=0.14, pan=0.5 * (-1) ** s, rev=0.25)
for s, n, ln, v in ((0, 84, 3, "a"), (4, 84, 1, "a"), (5, 87, 1, "e"), (6, 89, 4, "o"), (12, 87, 4, "a")):
    vchop(0, s, n, ln, v, "i" if v == "o" else None, gain=0.38)
for s, n, ln, v in ((0, 84, 2, "a"), (2, 84, 2, "a"), (4, 91, 6, "a"), (12, 89, 2, "e"), (14, 87, 2, "o")):
    vchop(1, s, n, ln, v, "u" if v == "o" else None, glide=0.08 if ln > 4 else 0, gain=0.38)
drums.add(laser(0.3, 6000, 200), at(1, 14), pan=0.5, gain=0.4)

# --- B  bars 2-5 (3-9 s): half-time bounce on HARD one-shots, 808 glides, squeaks
for b in range(2, 6):
    c, r = chord(b), ROOT[chord(b)]
    kick(b, 0, src="h_low")
    kick(b, 6, 0.85, src="h_low2")
    if b % 2:
        kick(b, 11, 0.75, src="h_low")
    snare(b, 8)
    hats(b, range(0, 16, 2), 0.35, roll_at=14 if b % 2 else None)
    bass808(b, 0, r, 6)
    bass808(b, 6, r, 4, to=r + 12, glide_at=2)
    bass808(b, 11, r + 12, 5, to=r, glide_at=3)
    for s, ln in ((3, 2), (13, 2)):
        x = syn.latex_squeak(c and CH[c][3] + 12, ln * S16, up=0.8)
        music.add(x, at(b, s), pan=-0.4 if s < 8 else 0.4, gain=0.22)
        dly_send.add(x, at(b, s), gain=0.2)
    smp("h_mid2", b, 10, 0.35, semis=7, pan=0.4)
    drums.add(syn.plastic_pop(2600), at(b, 5), pan=0.6, gain=0.35)
    if b in (3, 5):
        for i, s in enumerate((12, 12.5, 13, 13.5)):
            vchop(b, s, 86 + (i == 3) * 3, 0.5, "a", gain=0.32, pan=0.3 * (-1) ** i)
        vchop(b, 14, 91, 2, "o", "u", glide=-0.5, gain=0.3)
    else:
        for s in range(0, 16, 4):
            music.add(chip_arp(CH[c][(s // 4) % 4] + 24, S16 * 1.5), at(b, s + 2), pan=0.6, gain=0.12)

# --- C  bars 6-7 (9-12 s): build — snare roll, riser, everything filtered upward
build = Bus()
for b in (6, 7):
    c = CH[chord(b)]
    pad = syn.supersaw([n + 12 for n in c], BAR, bright=(6, 14), attack=0.02)
    build.add(pad, at(b) - at(6), gain=0.45)
    for s in range(0, 16, 2):
        build.add(chip_arp(c[(s // 2) % 4] + 24, S16 * 1.2), at(b, s) - at(6), pan=0.5 * (-1) ** s, gain=0.15)
music.add(sweep_lp(build.x[:int(2 * BAR * SR)], 300, 14000, q=7, curve=1.6), at(6), gain=1.0)
roll = [(6, s) for s in range(0, 16, 4)] + [(6, s) for s in range(8, 16, 2)] + \
       [(7, s) for s in range(0, 8, 1)] + [(7, 8 + s / 2) for s in range(8)]
for i, (b, s) in enumerate(sorted(set(roll))):
    x = repitch(clap(0.15), i * 0.35)
    drums.add(x, at(b, s), gain=0.2 + 0.018 * i, pan=0.15 * np.sin(i))
for b in (6, 7):
    kick(b, 0, 0.8)
    bass808(b, 0, ROOT[chord(b)], 8)
    hats(b, range(16) if b == 7 else range(0, 16, 2), 0.3)
drums.add(syn.riser(BAR * 1.75), at(6, 4), gain=0.5)
verb_send.add(syn.riser(BAR * 1.75), at(6, 4), gain=0.25)
vchop(7, 14, 96, 2, "a", "i", glide=0.6, gain=0.4, rev=0.4)  # pitched-up "ya!" in the gap

# --- D  bars 8-13 (12-21 s): DROP 1
HOOK = [(0, 77, 3), (3, 80, 3), (6, 84, 4), (10, 82, 2), (12, 80, 2), (14, 79, 2),
        (16, 80, 3), (19, 84, 3), (22, 87, 4), (26, 85, 2), (28, 84, 4)]


def lead_phrase(bar0, bars, transpose=0, cutoff=(11000, 3500)):
    notes, gates = [], []
    for rep in range(bars // 2):
        for s, n, ln in HOOK:
            st = (rep * 32 + s) * S16
            notes.append((st, n + transpose))
            gates.append((st, st + ln * S16 * 0.92))
    d = bars * BAR
    x = supersaw_lead(notes, d + 0.1, gates, cutoff=cutoff)
    lead.add(x, at(bar0), gain=0.42)
    verb_send.add(x, at(bar0), gain=0.15)
    dly_send.add(x, at(bar0), gain=0.1)


drums.add(impact(), at(8), gain=0.7)
verb_send.add(impact(), at(8), gain=0.3)
lead_phrase(8, 6)
for b in range(8, 14):
    c, r = chord(b), ROOT[chord(b)]
    for s in (0, 6, 10):
        kick(b, s, 1.0, src="p_low" if s == 0 else "p_low2")
    if b % 2:
        kick(b, 14, 0.7)
    snare(b, 4, 0.85, "p_hi3")
    snare(b, 12, 0.85, "h_hi")
    hats(b, range(0, 16, 1), 0.28, roll_at=14 if b % 2 == 0 else None)
    smp("p_loop", b, 0, 0.22)
    smp("p_hi", b, 15, 0.4, pan=0.5 * (-1) ** b)
    bass808(b, 0, r, 6)
    bass808(b, 6, r, 4)
    bass808(b, 10, r + 7, 3, to=r + 12, glide_at=1.5)
    bass808(b, 13, r + 12, 3, to=r, glide_at=1.5)
    for s in (2, 7, 10, 15):  # supersaw stabs
        x = syn.supersaw(CH[c], S16 * 1.6, bright=(18, 2.5), voices=(-0.15, -0.05, 0, 0.05, 0.15), pluck=True)
        music.add(widen(stereo(x), 1.5), at(b, s), gain=0.28)
    for s in range(16):  # chiptune 16th arp, two octaves up
        n = CH[c][[0, 2, 1, 3][s % 4]] + 24 + (12 if s % 8 == 7 else 0)
        music.add(chip_arp(n, S16 * 0.9), at(b, s), pan=0.55 * (-1) ** s, gain=0.09)
    if b % 2 == 1:
        for i, s in enumerate((8, 8.5, 9, 9.5)):
            vchop(b, s, 89 + 3 * (i % 2), 0.5, "a" if i < 3 else "o", gain=0.3, pan=0.4 * (-1) ** i)
    drums.add(laser(0.25, 5000, 150), at(b, 11), pan=-0.5, gain=0.25)
    keyhit(b, 3, CH[c][3] + 12, 2, gain=0.25, pan=-0.3)

# --- E  bars 14-15 (21-24 s): sweet switch — big reverb pad, bells, chipmunk hook
for b in (14, 15):
    c = CH[["Db", "Ab"][b - 14]] if True else None
    pad = syn.supersaw([n + 12 for n in c] + [c[0] + 24], BAR, bright=(5, 18), attack=0.1)
    music.add(widen(stereo(pad), 1.8), at(b), gain=0.4)
    verb_send.add(pad, at(b), gain=0.5)
    bass.add(syn.sub(ROOT[["Db", "Ab"][b - 14]] - 12 + 12, BAR), at(b), gain=0.4)
    for s in range(16):
        n = c[(s * 3) % 4] + 24
        x = syn.glass_bell(n, 0.4)
        music.add(x, at(b, s), pan=0.7 * np.sin(s * 1.3), gain=0.12)
        verb_send.add(x, at(b, s), gain=0.15)
        dly_send.add(x, at(b, s), gain=0.08)
    hats(b, range(1, 16, 2), 0.18)
for s, n, ln, v in ((0, 89, 4, "a"), (4, 91, 2, "e"), (6, 92, 6, "a"), (12, 91, 4, "o")):
    vchop(14, s, n, ln, v, "i" if v == "o" else None, glide=0.05, gain=0.42, rev=0.45)
for s, n, ln, v in ((0, 89, 2, "a"), (2, 87, 2, "a"), (4, 84, 4, "o"), (8, 96, 4, "a")):
    vchop(15, s, n, ln, v, "u" if v == "o" else None, gain=0.42, rev=0.45)
rc = syn.riser(BAR * 0.5)
drums.add(rc, at(15, 8), gain=0.6)
rev_crash = impact(1.0)[::-1] * np.linspace(0, 1, int(1.0 * SR)) ** 3
drums.add(highpass(rev_crash, 1500), at(15, 16) - 1.0, gain=0.4)

# --- F  bars 16-19 (24-30 s): DROP 2 — octave up, harder, double-time chaos, hard cut
drums.add(impact(), at(16), gain=0.75)
lead_phrase(16, 4, transpose=12, cutoff=(14000, 5000))
for b in range(16, 20):
    c, r = chord(b), ROOT[chord(b)]
    for s in (0, 3, 6, 8, 10, 11, 14):
        kick(b, s, 1.0, src="p_low" if s % 2 == 0 else "h_low")
    if b == 19:  # machine-gun kicks into the cut
        for s in range(12, 16):
            for h in (0, 0.5):
                kick(b, s + h, 0.7, src="p_low2")
    for s in (4, 12):
        snare(b, s, 0.9, "p_hi3" if b % 2 else "h_hi")
        drums.add(syn.metal_clang(160, 0.4, drive=4), at(b, s), gain=0.35)
    hats(b, range(16), 0.3, roll_at=6 if b % 2 else 14)
    smp("h_loop" if b % 2 else "p_loop", b, 0, 0.25)
    smp("p_hi2", b, 7, 0.4, pan=-0.5)
    drums.add(syn.whip(), at(b, 15), pan=0.5, gain=0.4)
    for s, ln in ((0, 3), (3, 3), (6, 2), (8, 2), (10, 1), (11, 2), (13, 3)):
        bass808(b, s, r + (12 if s in (10, 13) else 0), ln, to=r if s == 13 else None, glide_at=1)
    for s in (2, 5, 7, 10, 13, 15):
        x = syn.supersaw(CH[c], S16 * 1.4, bright=(20, 3), voices=(-0.15, -0.05, 0, 0.05, 0.15), pluck=True)
        music.add(widen(stereo(x), 1.6), at(b, s), gain=0.26)
    for s in range(0, 16):
        n = CH[c][[0, 3, 2, 1][s % 4]] + 24 + 12 * (s % 4 == 3)
        music.add(chip_arp(n, S16 * 0.8, duty=0.125), at(b, s), pan=0.6 * (-1) ** s, gain=0.08)
    for i, s in enumerate((12, 12.5, 13, 13.5, 14, 14.5)):
        vchop(b, s, 91 + (i % 3) * 2 + (b % 2) * 3, 0.5, "aeiaeo"[i], gain=0.3, pan=0.5 * (-1) ** i)
    keyhit(b, 0, CH[c][0] + 24, 3, gain=0.3, pan=0.3)
    drums.add(laser(0.2, 7000, 300), at(b, 9), pan=0.5, gain=0.25)
vchop(19, 15, 98, 3, "a", "i", glide=1.0, gain=0.45, rev=0.3)  # scream cut off by the stop

# ================================================================ MIX
t_all = np.arange(N + TAIL) / SR
duck = np.ones(N + TAIL)
for kt in kicks:
    i = int(kt * SR)
    j = min(len(duck), i + int(0.5 * SR))
    duck[i:j] = np.minimum(duck[i:j], 1 - 0.8 * np.exp(-(t_all[i:j] - kt) / 0.09))
dk = duck[:, None]

dl = int(S16 * 3 * SR)
src = dly_send.x.mean(1)
dly = np.zeros((N + TAIL, 2))
for tap in range(1, 7):
    dly[dl * tap:, tap % 2] += src[:-dl * tap] * 0.55 ** tap
dly = lowpass(highpass(dly, 300), 6000)

wet = reverb(highpass(verb_send.x, 250))

mix = (drums.x * 1.0
       + bass.x * (0.35 + 0.65 * dk)
       + music.x * dk
       + lead.x * (0.25 + 0.75 * dk)
       + vox.x * (0.6 + 0.4 * dk)
       + dly * 0.5 * dk
       + wet * 0.55 * dk)[:N].copy()

# tape-start into the track, tape-stop at end of drop 1, glitches everywhere
tape(mix, at(13, 12), BEAT, "stop")
for (b, s, d, sl, pu) in ((3, 14, 2, 0.5, 0), (5, 12, 4, 0.25, 12), (9, 14, 2, 0.5, 0),
                          (11, 12, 2, 0.25, 7), (12, 14, 2, 1 / 3, 0), (17, 14, 2, 0.5, 5),
                          (18, 8, 2, 0.25, 0), (18, 14, 2, 0.125, 12)):
    stutter(mix, at(b, s), S16 * d, S16 * sl, pu)
for (b, s, d) in ((7, 12, 4), (19, 8, 4)):  # bitcrush bursts
    a, n = int(at(b, s) * SR), int(d * S16 * SR)
    mix[a:a + n] = crush(mix[a:a + n], 5, 5)
fade_in = int(0.35 * SR)
mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None] ** 2

# master: HPF -> glue saturation -> lookahead limiter -> hard cut at 30.0 s
mix = highpass(mix, 28, 4)
mix = np.tanh(1.4 * mix / np.percentile(np.abs(mix), 99.9))
look = int(0.004 * SR)
pk = maximum_filter1d(np.abs(mix).max(1), size=2 * look + 1)
g = np.minimum(1.0, 0.89 / (pk + 1e-9))
g = signal.lfilter([1 - np.exp(-1 / (0.0015 * SR))], [1, -np.exp(-1 / (0.0015 * SR))], g)
g = np.minimum(g, 0.89 / (pk + 1e-9))
mix = mix * g[:, None]
mix = mix / np.abs(mix).max() * 0.966  # -0.3 dBFS
nd = int(0.003 * SR)
mix[-nd:] *= np.linspace(1, 0, nd)[:, None]

out = Path(__file__).with_name("hyperpop_max.wav")
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
