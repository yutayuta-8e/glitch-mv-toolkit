"""ゆた×目：ピアノだけの方向違い5案（試聴用、各40〜50秒）。

音は breakcore_v2.py の合成ピアノ（piano_note）を使い、案ごとに作りと音色の加工を変える。
どの案も曲のキーの音（D# E F# G# A# B C#）だけで組む。旋律と和音はすべてオリジナル。
"""
import os
import sys

import numpy as np
from pedalboard import Chorus, Delay, HighpassFilter, Limiter, LowpassFilter, Pedalboard, Reverb
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakcore_v2 as b2  # noqa: E402

SR = b2.SR


class Score:
    def __init__(self, sec, bpm):
        self.buf = np.zeros(int(sec * SR))
        self.beat = 60.0 / bpm

    def note(self, beat, m, dur_beats, vel):
        t = beat * self.beat
        sig = b2.piano_note(m, dur_beats * self.beat, vel, None)
        i = int(t * SR)
        if i >= len(self.buf):
            return
        self.buf[i:i + len(sig)] += sig[: len(self.buf) - i]

    def chord(self, beat, ms, dur_beats, vel, roll=0.0):
        for k, m in enumerate(ms):
            self.note(beat + k * roll, m, dur_beats - k * roll, vel)


def finish(buf, board, path):
    st = np.stack([buf, buf * 0.98], 1).astype(np.float32)
    st = board(np.ascontiguousarray(st.T), SR).T
    st = Pedalboard([Limiter(threshold_db=-3)])(np.ascontiguousarray(st.T), SR).T
    st *= 10 ** (-1.5 / 20) / max(np.max(np.abs(st)), 1e-9)
    wavfile.write(path, SR, (st * 32767).astype(np.int16))


# ------------------------------------------------------------ 1 夜想曲（フェルトピアノ）
def nocturne(path):
    s = Score(50, 64)
    prog = [(39, [58, 63, 66]), (35, [54, 59, 63]), (32, [56, 59, 63]), (40, [56, 59, 64]),
            (39, [58, 63, 66]), (42, [58, 61, 66]), (40, [56, 59, 64]), (39, [58, 63, 64])]
    mel = [[(1, 2, 75), (3, 1, 73)], [(0, 3, 71), (3, 1, 73)], [(0, 1.5, 75), (1.5, 0.5, 78), (2, 2, 75)],
           [(0, 4, 71)], [(1, 1, 82), (2, 1, 80), (3, 1, 78)], [(0, 2, 78), (2, 1, 75), (3, 1, 73)],
           [(0, 3, 76), (3, 1, 75)], [(0, 4, 75)]]
    for rep in range(2):
        for i, (bass, ch) in enumerate(prog):
            b0 = (rep * 8 + i) * 4
            s.note(b0, bass, 4, 0.45)
            for k, m in enumerate([ch[0], ch[1], ch[2], ch[1]] * 2):  # 8分音符でゆっくり崩した和音
                s.note(b0 + k * 0.5, m, 4 - k * 0.5, 0.28)
            for bb, d, m in mel[i]:
                s.note(b0 + bb, m + 12 * (rep == 1 and i >= 4), d, 0.55)
                if rep == 1 and bb == 0:
                    s.note(b0 + bb - 0.12, m + 2 if m + 2 in (65, 77, 80, 82, 85) else m + 1, 0.12, 0.3)  # 装飾音
    finish(s.buf, Pedalboard([LowpassFilter(3200), HighpassFilter(40),
                              Reverb(room_size=0.7, damping=0.6, wet_level=0.28, dry_level=0.9)]), path)


# ------------------------------------------------------------ 2 ロマン派の大きな波（B メジャー）
def romantic(path):
    s = Score(48, 72)
    # B – G#m – E – F# – D#m – G#m – C#m – F#(sus) → B（曲と同じ音だけでできる B メジャー）
    prog = [(35, [59, 63, 66]), (44, [56, 59, 63]), (40, [56, 59, 64]), (42, [54, 58, 61]),
            (39, [54, 58, 63]), (44, [56, 59, 63]), (37, [56, 61, 64]), (42, [54, 59, 61])]
    mel = [[(0, 2, 71), (2, 1, 73), (3, 1, 75)], [(0, 3, 75), (3, 1, 73)], [(0, 1, 71), (1, 1, 76), (2, 2, 80)],
           [(0, 3, 78), (3, 1, 76)], [(0, 2, 75), (2, 1, 78), (3, 1, 82)], [(0, 3, 80), (3, 1, 78)],
           [(0, 1, 76), (1, 1, 75), (2, 1, 73), (3, 1, 76)], [(0, 4, 75)]]
    for rep in range(2):
        for i, (bass, ch) in enumerate(prog):
            b0 = (rep * 8 + i) * 4
            arp = [bass, bass + 7, bass + 12, ch[0], ch[1], ch[2], ch[2] + 12, ch[2], ch[1], ch[0], bass + 12, bass + 7]
            for k in range(24):  # 6連符で両手にまたがる大きな波
                s.note(b0 + k / 6, arp[k % 12], 4 - k / 6, 0.26 + 0.08 * (k % 6 == 0))
            for bb, d, m in mel[i]:
                for mm in ([m, m - 12] if rep == 1 else [m]):
                    s.note(b0 + bb, mm, d, 0.62 if mm == m else 0.4)
    finish(s.buf, Pedalboard([LowpassFilter(7000), HighpassFilter(35),
                              Reverb(room_size=0.85, damping=0.35, wet_level=0.33, dry_level=0.85)]), path)


# ------------------------------------------------------------ 3 アンビエントの反復（ガラスの高音）
def ambient(path):
    s = Score(46, 80)
    cells = [[75, 82, 78], [75, 82, 80], [73, 80, 76], [71, 78, 75]]
    basses = [27, 23, 28, 30]
    for bar in range(14):
        cell = cells[(bar // 2) % 4]
        b0 = bar * 4
        if bar % 2 == 0:
            s.note(b0, basses[(bar // 2) % 4], 8, 0.4)
            s.note(b0, basses[(bar // 2) % 4] + 12, 8, 0.3)
        for k in range(16):
            m = cell[k % 3] + (12 if bar >= 8 and k % 4 == 3 else 0)
            s.note(b0 + k * 0.25, m, 1.0, 0.18 + 0.06 * (k % 3 == 0))
    finish(s.buf, Pedalboard([HighpassFilter(60), Delay(delay_seconds=0.5625, feedback=0.45, mix=0.35),
                              Reverb(room_size=0.97, damping=0.2, wet_level=0.55, dry_level=0.6)]), path)


# ------------------------------------------------------------ 4 暗いトレモロ（ホラー寄り）
def dark(path):
    s = Score(44, 70)
    for bar in range(12):
        b0 = bar * 4
        low = [27, 39] if bar % 4 != 3 else [28, 40]
        for k in range(32):  # 低音のトレモロ
            s.note(b0 + k / 8, low[k % 2], 0.2, 0.3 + 0.25 * (bar / 12))
        if bar % 2 == 1:
            s.chord(b0 + 2, [51, 52, 58, 63, 64], 2, 0.55)  # D# E A# の不協和な塊
    # 下がっていく旋律（半音でにじり寄る）
    line = [82, 80, 78, 76, 75, 76, 75, 71, 70, 71, 70, 66, 64, 63]
    for k, m in enumerate(line):
        s.note(4 + k * 3, m, 3, 0.5)
        s.note(4 + k * 3, m - 12, 3, 0.35)
    finish(s.buf, Pedalboard([LowpassFilter(5000), Reverb(room_size=0.9, damping=0.5, wet_level=0.4, dry_level=0.8)]),
           path)


# ------------------------------------------------------------ 5 ローファイのアップライト（子守唄）
def lofi(path):
    s = Score(46, 76)
    prog = [[51, 58, 63, 66], [47, 59, 63, 66], [44, 56, 59, 63], [52, 56, 59, 64]]
    mel = [(0, 1, 82), (1, 1, 80), (2, 2, 78), (4, 1, 75), (5, 1, 78), (6, 2, 80),
           (8, 1, 82), (9, 1, 85), (10, 2, 82), (12, 1, 80), (13, 1, 78), (14, 2, 75)]
    for rep in range(3):
        for i, ch in enumerate(prog):
            b0 = (rep * 4 + i) * 4
            s.note(b0, ch[0] - 12, 4, 0.35)
            for k in (1, 2, 3):
                s.chord(b0 + k, ch[1:], 0.9, 0.22, roll=0.02)
        for bb, d, m in mel:
            s.note(rep * 16 + bb, m, d, 0.5)
    buf = s.buf
    # テープのよれ：ゆっくり揺れる読み出し位置で音程を揺らす
    n = len(buf)
    t = np.arange(n) / SR
    pos = np.arange(n) + 0.0025 * SR * np.sin(2 * np.pi * 0.6 * t) + 0.0008 * SR * np.sin(2 * np.pi * 5.1 * t)
    buf = np.interp(np.clip(pos, 0, n - 1), np.arange(n), buf)
    buf += np.random.default_rng(5).standard_normal(n) * 0.0025  # ヒス
    finish(buf, Pedalboard([HighpassFilter(120), LowpassFilter(5200), Chorus(rate_hz=0.4, depth=0.15, mix=0.3),
                            Reverb(room_size=0.5, damping=0.7, wet_level=0.2, dry_level=0.9)]), path)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, fn in [("PIANO-01_nocturne", nocturne), ("PIANO-02_romantic_B_major", romantic),
                     ("PIANO-03_ambient_glass", ambient), ("PIANO-04_dark_tremolo", dark),
                     ("PIANO-05_lofi_upright", lofi)]:
        fn(os.path.join(out, name + ".wav"))
        print("ok", name, flush=True)


if __name__ == "__main__":
    main()
