"""Synth voices shared by rubber_face.py / sample_flip.py (auto-extracted from rubber_face.py)."""
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


