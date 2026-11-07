"""ゆた×目：Suno「見てるよ」を素材に、楽器を足して加工した版を作る。

キーは D#（E♭）、80 BPM（1拍 0.75 秒）。足す音は NumPy で合成し、効果は pedalboard でかける。
区間（秒）は曲の音量とスペクトログラムから決めたもの。
"""
import argparse

import numpy as np
from pedalboard import (Bitcrush, Chorus, Compressor, Delay, Distortion, Gain, HighpassFilter, Limiter,
                        LowpassFilter, Pedalboard, PitchShift, Reverb)
from scipy.io import wavfile

SR = 48000
BEAT = 0.75
ROOT = 38.89  # D#1
# E♭ フリジアン（D# E F# G# A# B C#）の半音
SCALE = [0, 1, 3, 5, 7, 8, 10]
SEC = {"intro": (0, 2.83), "build": (2.83, 14.1), "noisy": (14.1, 35.5), "dark": (35.5, 51.0),
       "burst1": (51.0, 54.4), "calm": (54.4, 58.0), "burst2": (58.0, 62.4), "heavy": (62.4, 80.0),
       "climax": (80.0, 92.0), "end": (92.0, 94.32)}
HITS = [14.1, 35.5, 62.4, 80.0]


def note(semi, octave=0):
    return ROOT * 2 ** (octave + semi / 12)


def env_adsr(n, a, d, s, r):
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1)
    e = np.where(t > a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)), e)
    tail = int(r * SR)
    if tail and tail < n:
        e[-tail:] *= np.linspace(1, 0, tail)
    return e


def place(buf, sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= buf.shape[0]:
        return
    sig = sig[: buf.shape[0] - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(sig), 0] += sig * gain * l * 1.414
    buf[i:i + len(sig), 1] += sig * gain * r * 1.414


def kick(rng):
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    f = 45 + 130 * np.exp(-t * 28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5)
    s += 0.4 * rng.standard_normal(n) * np.exp(-t * 180)
    return np.tanh(s * 3.5) * 0.8


def hat(rng, length=0.05):
    n = int(length * SR)
    s = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 60)
    s = np.diff(s, prepend=0)  # 高域だけ残す
    return s * 0.5


def bell(freq, dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * freq * 3.51 * t) * 4 * np.exp(-t * 2)
    s = np.sin(2 * np.pi * freq * t + mod) * np.exp(-t * 1.6)
    s += 0.3 * np.sin(2 * np.pi * freq * 2.01 * t) * np.exp(-t * 3)
    return s * 0.6


def choir(freqs, dur, rng):
    """のこぎり波を重ねて、母音「あ」に近い帯域だけを持ち上げた合唱っぽいパッド。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det in (-0.3, 0, 0.27):
            ph = rng.uniform(0, 1)
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t + ph * 6)
            s += 2 * ((f * (1 + det / 100) * vib * t + ph) % 1) - 1
    spec = np.fft.rfft(s)
    fr = np.fft.rfftfreq(n, 1 / SR)
    shape = sum(g * np.exp(-((fr - c) / w) ** 2) for c, w, g in [(730, 120, 1), (1090, 140, 0.6), (2440, 300, 0.3)])
    s = np.fft.irfft(spec * (shape + 0.02), n)
    s /= np.max(np.abs(s)) + 1e-9
    return s * env_adsr(n, 1.5, 2, 0.8, 1.5) * 0.5


def heartbeat():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 18)
    out = thump.copy()
    j = int(0.18 * SR)
    out[j:] += 0.7 * thump[: n - j]
    return out * 0.9


def riser(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 3800 * (t / dur) ** 2) / SR)
    s = noise * 0.4 + sweep * 0.5
    s = Pedalboard([HighpassFilter(300)])(s.astype(np.float32), SR)
    return s * (t / dur) ** 2.5


def impact(rng):
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 90 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.4)
    crash = rng.standard_normal(n) * np.exp(-t * 2.5) * 0.4
    return np.tanh((boom + crash) * 2) * 0.9


def drone(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * ROOT * t) + 0.5 * np.sin(2 * np.pi * ROOT * 2 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t))
    s += 0.25 * np.sin(2 * np.pi * note(1, 1) * t)  # 半音上の E を薄く重ねて不穏に
    return np.tanh(s * 1.5) * env_adsr(n, 2, 1, 1, 2) * 0.5


def seg(x, a, b):
    return x[int(a * SR):int(b * SR)]


def fx(board, arr):
    """(サンプル数, 2) の配列に効果をかけて、同じ向きで返す。"""
    return board(np.ascontiguousarray(arr.T, dtype=np.float32), SR).T


def process_original(x, rng):
    """Suno の元の音に、区間ごとの加工をかける。"""
    y = x.copy()
    # 騒がしい区間：歪ませて少しつぶす
    a, b = SEC["noisy"]
    y[int(a * SR):int(b * SR)] = fx(Pedalboard([Distortion(drive_db=8), Gain(-4)]), seg(x, a, b))
    # テープストップ：35.5 秒の直前 0.6 秒で音程を落としながら止める
    a, b = 34.9, 35.5
    s = seg(x, a, b)
    n = s.shape[0]
    pos = np.cumsum(np.linspace(1, 0.05, n))
    pos = np.clip(pos, 0, n - 1)
    y[int(a * SR):int(b * SR)] = np.stack([np.interp(pos, np.arange(n), s[:, c]) for c in range(2)], 1) * \
        np.linspace(1, 0.2, n)[:, None]
    # ビートリピート：連打区間で 1/8〜1/16 拍を繰り返す
    for name, step in [("burst1", BEAT / 4), ("burst2", BEAT / 4), ("climax", BEAT / 2)]:
        a, b = SEC[name]
        t = a
        while t < b - step:
            if rng.random() < 0.55:
                sl = int(rng.choice([step / 2, step / 4]) * SR)
                src = y[int(t * SR):int(t * SR) + sl].copy()
                reps = int(step * SR) // sl
                y[int(t * SR):int(t * SR) + sl * reps] = np.tile(src, (reps, 1))
            t += step
    # ビットクラッシュ：連打区間に薄く
    for name in ("burst2", "climax"):
        a, b = SEC[name]
        y[int(a * SR):int(b * SR)] = fx(Pedalboard([Bitcrush(bit_depth=6)]), seg(y, a, b)) * 0.7 + seg(y, a, b) * 0.5
    # 逆再生の吸い込み：区間の頭の直前に、その頭 1.5 秒を逆再生して重ねる
    rev = np.zeros_like(y)
    for h in HITS:
        s = seg(x, h, h + 1.5)[::-1] * np.linspace(0, 1, int(1.5 * SR))[:, None] ** 2
        s = fx(Pedalboard([Reverb(room_size=0.9, wet_level=0.6, dry_level=0.4)]), s)
        i = int((h - 1.5) * SR)
        rev[i:i + s.shape[0]] += s[: rev.shape[0] - i] * 0.6
    return y + rev


def build_layers(n, rng):
    L = {k: np.zeros((n, 2), np.float32) for k in ("drum", "bass", "bell", "choir", "fx", "heart")}
    k = kick(rng)
    # キック：騒がしい区間は2拍ごと、重い区間と山は毎拍、山の後半は半拍
    for name, every in [("noisy", 2 * BEAT), ("heavy", BEAT), ("climax", BEAT)]:
        a, b = SEC[name]
        t = a
        while t < b - 0.05:
            place(L["drum"], k, t, 0.9)
            if name == "climax" and t > 86 and rng.random() < 0.6:
                place(L["drum"], k, t + BEAT / 2, 0.6)
            t += every
    # ハイハットとグリッチ：重い区間は 1/8、山は 1/16 と細かい連打
    for name, step in [("heavy", BEAT / 2), ("climax", BEAT / 4), ("burst1", BEAT / 4), ("burst2", BEAT / 8)]:
        a, b = SEC[name]
        t = a
        while t < b - 0.02:
            if rng.random() < 0.8:
                place(L["drum"], hat(rng, rng.choice([0.03, 0.05, 0.12])), t, 0.5, rng.uniform(-0.7, 0.7))
            t += step
    # 低音ドローン：暗い区間と重い区間と山
    for name in ("build", "dark", "heavy", "climax"):
        a, b = SEC[name]
        place(L["bass"], drone(b - a), a, 0.6 if name != "build" else 0.3)
    # ベル：暗い区間と静かな区間に、まばらに不穏なメロディ
    for name, dens in [("dark", 0.45), ("calm", 0.6), ("build", 0.2)]:
        a, b = SEC[name]
        t = a
        while t < b - 1:
            if rng.random() < dens:
                semi = SCALE[rng.integers(len(SCALE))]
                place(L["bell"], bell(note(semi, rng.choice([4, 5])), 3.0, rng), t, 0.35, rng.uniform(-0.8, 0.8))
            t += BEAT * rng.choice([1, 2])
    # 合唱パッド：重い区間と山で、D#・E・A# の不穏な和音
    for name in ("heavy", "climax"):
        a, b = SEC[name]
        place(L["choir"], choir([note(0, 3), note(1, 3), note(7, 3), note(0, 4)], b - a, rng), a, 0.35)
    # 心臓の音：暗い区間で毎拍
    a, b = SEC["dark"]
    t = a + 0.5
    while t < b:
        place(L["heart"], heartbeat(), t, 0.8)
        t += BEAT
    # ライザーと衝撃音
    for h in HITS:
        place(L["fx"], riser(3.0, rng), h - 3.0, 0.35)
        place(L["fx"], impact(rng), h, 0.7)
    return L


def fx_layers(L):
    L["drum"] = fx(Pedalboard([Compressor(threshold_db=-12, ratio=4), Distortion(drive_db=4)]), L["drum"])
    L["bell"] = fx(Pedalboard([Chorus(), Delay(delay_seconds=BEAT * 0.75, feedback=0.45, mix=0.35),
                               Reverb(room_size=0.95, wet_level=0.5, dry_level=0.6)]), L["bell"])
    L["choir"] = fx(Pedalboard([Reverb(room_size=0.9, wet_level=0.45, dry_level=0.7), LowpassFilter(6000)]), L["choir"])
    L["fx"] = fx(Pedalboard([Reverb(room_size=0.8, wet_level=0.3, dry_level=0.8)]), L["fx"])
    L["heart"] = fx(Pedalboard([LowpassFilter(400), Gain(2)]), L["heart"])
    return L


def sidechain(y, n):
    """キックの拍で元の音を少し沈ませる。"""
    g = np.ones(n, np.float32)
    duck = 1 - 0.35 * np.exp(-np.arange(int(0.3 * SR)) / SR * 12)
    for name, every in [("heavy", BEAT), ("climax", BEAT)]:
        a, b = SEC[name]
        t = a
        while t < b:
            i = int(t * SR)
            g[i:i + len(duck)] = np.minimum(g[i:i + len(duck)], duck[: n - i])
            t += every
    return y * g[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--stems", help="folder to write each layer as WAV")
    ap.add_argument("--seed", type=int, default=6)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    sr, x = wavfile.read(a.src)
    assert sr == SR
    x = x.astype(np.float32) / 32768
    n = x.shape[0]
    orig = sidechain(process_original(x, rng), n)
    L = fx_layers(build_layers(n, rng))
    mix = orig * 0.85 + sum(L.values())
    end = int(SEC["end"][0] * SR)
    mix[end:] *= np.linspace(1, 0, n - end)[:, None] ** 3
    mix = fx(Pedalboard([HighpassFilter(25), Compressor(threshold_db=-14, ratio=2.5, attack_ms=10, release_ms=150),
                         Limiter(threshold_db=-3.0, release_ms=80)]), mix)
    mix *= 10 ** (-1.5 / 20) / np.max(np.abs(mix))  # 最後にピークを -1.5 dBFS へ
    wavfile.write(a.out, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    if a.stems:
        import os
        os.makedirs(a.stems, exist_ok=True)
        wavfile.write(os.path.join(a.stems, "00_suno_processed.wav"), SR, (np.clip(orig, -1, 1) * 32767).astype(np.int16))
        for i, (k, v) in enumerate(L.items(), 1):
            wavfile.write(os.path.join(a.stems, f"{i:02d}_{k}.wav"), SR, (np.clip(v, -1, 1) * 32767).astype(np.int16))
    print("done", a.out)


if __name__ == "__main__":
    main()
