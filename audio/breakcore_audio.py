"""ゆた×目：Suno「見てるよ」を、ブレイクコア風に作り直す。

曲は 80 BPM なので、ドラムは倍の 160 BPM（1小節 = 1.5 秒 = 元の2拍）で刻む。
ドラムは既存サンプル（アーメン・ブレイク等）を使わず、すべて合成する（商用利用のため）。
アーメン風のパターンで1小節のブレイクを作り、小節ごとに並べ替え・逆再生・ロール・ピッチ上げをかける。
上物は Suno の元の音と、remix_v1 で合成したドローン・ベル・合唱・心臓の音（stems）を使う。
"""
import argparse
import os

import numpy as np
from pedalboard import (Bitcrush, Compressor, Distortion, Gain, HighpassFilter, Limiter, LowpassFilter,
                        Pedalboard, Reverb)
from scipy.io import wavfile

SR = 48000
BAR = 1.5            # 160 BPM の1小節
STEP = BAR / 16      # 16分音符
ROOT = 38.89         # D#1

# 区間（秒）と、その区間のドラムの扱い
#   none: ドラムなし / half: ローパスでこもった半分の密度 / full: 刻み / chaos: 激しく刻む / roll: ロールで加速
PLAN = [
    (0.00, 2.83, "none"),
    (2.83, 8.83, "none"),
    (8.83, 14.10, "half"),
    (14.10, 35.50, "full"),
    (35.50, 51.00, "none"),
    (51.00, 54.40, "chaos"),
    (54.40, 58.00, "none"),
    (58.00, 62.40, "roll"),
    (62.40, 80.00, "full"),
    (80.00, 92.00, "chaos"),
    (92.00, 94.32, "none"),
]


def kick(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 35)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    s[:240] += rng.standard_normal(240) * np.linspace(0.6, 0, 240)
    return np.tanh(s * 2.5)


def snare(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25) * 0.7
    noise = rng.standard_normal(n) * np.exp(-t * 14)
    noise = Pedalboard([HighpassFilter(1200), LowpassFilter(9000)])(noise.astype(np.float32), SR)
    return np.tanh((body + noise * 0.9) * 2)


def hat(rng, open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    s = rng.standard_normal(n) * np.exp(-t * (12 if open_ else 70))
    return Pedalboard([HighpassFilter(6500)])(s.astype(np.float32), SR) * 0.5


def place(buf, sig, i, g=1.0):
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig * g


def make_break(rng):
    """アーメン風の16分パターンで1小節（1.5秒）のブレイクを作る。"""
    n = int(BAR * SR)
    b = np.zeros(n + int(0.4 * SR), np.float32)
    K = [0, 2, 10, 11]
    S = [4, 7, 9, 12, 15]
    ghost = [6, 14]
    for st in range(16):
        i = int(st * STEP * SR + (0.012 * SR if st % 2 else 0))  # 少しハネさせる
        if st in K:
            place(b, kick(rng), i, 1.0)
        if st in S:
            place(b, snare(rng), i, 0.9)
        if st in ghost:
            place(b, snare(rng), i, 0.35)
        place(b, hat(rng, open_=(st == 14)), i, 0.6 if st % 2 == 0 else 0.4)
    b = Pedalboard([Compressor(threshold_db=-14, ratio=4, attack_ms=3, release_ms=60), Distortion(drive_db=6),
                    LowpassFilter(11000), Gain(-3)])(b, SR)
    return b[:n]


def slices(brk):
    m = len(brk) // 16
    return [brk[k * m:(k + 1) * m] for k in range(16)]


def pitch(sl, ratio):
    idx = np.arange(0, len(sl), ratio)
    out = np.interp(idx, np.arange(len(sl)), sl)
    return out[: len(sl)] if len(out) >= len(sl) else np.pad(out, (0, len(sl) - len(out)))


def chop_bar(sl, rng, mode, progress=0.0):
    """1小節ぶんのスライスを並べ替える。progress は roll 区間の進み具合（0〜1）。"""
    m = len(sl[0])
    out = []
    st = 0
    while st < 16:
        if mode == "roll":
            div = 1 if progress < 0.3 else 2 if progress < 0.6 else 4 if progress < 0.85 else 8
            src = sl[4 if st % 4 else 0]
            piece = src[: m // div]
            seg = np.tile(piece, div) * (0.5 + 0.5 * progress)
            seg = pitch(seg, 1 + progress * 0.8)
            out.append(seg)
            st += 1
            continue
        pick = st
        if mode in ("full", "chaos") and st not in (0, 8) and rng.random() < (0.35 if mode == "full" else 0.6):
            pick = rng.integers(16)
        seg = sl[pick].copy()
        r = rng.random()
        if mode == "chaos" and r < 0.15:
            seg = seg[::-1]
        elif mode == "chaos" and r < 0.35:
            div = rng.choice([2, 4, 8])
            seg = np.tile(seg[: m // div], div)
        elif mode == "full" and r < 0.08:
            seg = seg[::-1]
        elif mode == "full" and r < 0.16:
            seg = np.tile(seg[: m // 2], 2)
        if mode == "chaos" and rng.random() < 0.2:
            seg = pitch(seg, rng.choice([1.5, 2.0, 0.75]))
        out.append(seg)
        st += 1
    bar = np.concatenate(out)
    # 小節の最後で一瞬止める（ブレイクコアらしい間）
    if mode in ("full", "chaos") and rng.random() < 0.15:
        bar[int(len(bar) * 0.875):] *= 0.0
    return bar


def build_drums(n, rng):
    brk = make_break(rng)
    sl = slices(brk)
    out = np.zeros(n, np.float32)
    for a, b, mode in PLAN:
        if mode == "none":
            continue
        t = a
        while t < b - 0.05:
            progress = (t - a) / max(b - a, 1e-6)
            bar = chop_bar(sl, rng, "full" if mode == "half" else mode, progress)
            if mode == "half":
                bar = bar * 0.5
            i = int(t * SR)
            seg = bar[: int((b - t) * SR)]
            place(out, seg, i)
            t += BAR
        if mode == "half":
            i0, i1 = int(a * SR), int(b * SR)
            out[i0:i1] = Pedalboard([LowpassFilter(900)])(out[i0:i1].copy(), SR)
        if mode == "chaos":
            i0, i1 = int(a * SR), int(b * SR)
            out[i0:i1] = Pedalboard([Bitcrush(bit_depth=8)])(out[i0:i1].copy(), SR) * 0.6 + out[i0:i1] * 0.6
    return out


def reese(n, rng):
    """うねる低音：少しずらしたのこぎり波を重ねてローパス。D# と E を行き来する。"""
    t = np.arange(n) / SR
    notes = np.where((t // (BAR * 4)) % 4 == 3, ROOT * 2 ** (1 / 12), ROOT) * 2
    ph1 = np.cumsum(notes * 1.003) / SR
    ph2 = np.cumsum(notes * 0.997) / SR
    s = (2 * (ph1 % 1) - 1) + (2 * (ph2 % 1) - 1) + 0.6 * np.sin(2 * np.pi * np.cumsum(notes / 2) / SR)
    s = Pedalboard([LowpassFilter(420), Distortion(drive_db=10), LowpassFilter(900), Gain(-10)])(s.astype(np.float32), SR)
    return s


def mask(n, modes, fade=0.05):
    g = np.zeros(n, np.float32)
    for a, b, mode in PLAN:
        if mode in modes:
            g[int(a * SR):int(b * SR)] = 1
    k = int(fade * SR)
    return np.convolve(g, np.ones(k) / k, mode="same")


def read(path):
    sr, x = wavfile.read(path)
    assert sr == SR
    return x.astype(np.float32) / 32768


def fx(board, arr):
    return board(np.ascontiguousarray(arr.T, dtype=np.float32), SR).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suno")
    ap.add_argument("stems", help="remix_v1 の stems フォルダ")
    ap.add_argument("out")
    ap.add_argument("--stems-out")
    ap.add_argument("--seed", type=int, default=160)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    suno = read(a.suno)
    n = suno.shape[0]
    st = {k: read(os.path.join(a.stems, f)) for k, f in
          [("bass", "02_bass.wav"), ("bell", "03_bell.wav"), ("choir", "04_choir.wav"), ("fx", "05_fx.wav"),
           ("heart", "06_heart.wav")]}

    drums = build_drums(n, rng)
    drum_on = mask(n, ("full", "chaos", "roll"))
    bass = reese(n, rng) * mask(n, ("full", "chaos"), fade=0.3)

    # Suno の音：ドラムが鳴る区間は沈ませて残響を足し、上物として後ろに置く
    bed = fx(Pedalboard([HighpassFilter(120), Reverb(room_size=0.85, wet_level=0.35, dry_level=0.8)]), suno)
    duck = 1 - 0.3 * drum_on
    bed *= duck[:, None]

    # ドラムのサイドチェイン：キックが鳴る小節頭で上物とベースを少し沈ませる
    drums_st = np.stack([drums, drums], 1)
    mix = (bed * 0.8 + st["bell"] * 0.9 + st["choir"] * 0.8 + st["fx"] * 0.9 + st["heart"] * 0.9
           + st["bass"] * 0.5 * (1 - 0.5 * drum_on)[:, None]
           + np.stack([bass, bass], 1) * 0.9 + drums_st * 0.85)
    end = int(92.0 * SR)
    mix[end:] *= np.linspace(1, 0, n - end)[:, None] ** 2
    mix = fx(Pedalboard([HighpassFilter(28), Compressor(threshold_db=-16, ratio=3, attack_ms=5, release_ms=120),
                         Limiter(threshold_db=-3.0, release_ms=60)]), mix)
    mix *= 10 ** (-1.5 / 20) / np.max(np.abs(mix))
    wavfile.write(a.out, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    if a.stems_out:
        os.makedirs(a.stems_out, exist_ok=True)
        for name, arr in [("01_breaks", drums_st), ("02_reese", np.stack([bass, bass], 1)), ("03_suno_bed", bed)]:
            peak = max(np.max(np.abs(arr)), 1e-9)
            wavfile.write(os.path.join(a.stems_out, f"{name}.wav"), SR,
                          (np.clip(arr / max(peak, 1.0), -1, 1) * 32767).astype(np.int16))
    print("done", a.out)


if __name__ == "__main__":
    main()
