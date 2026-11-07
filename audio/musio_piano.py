"""ゆた×目：Musio のピアノで「3番（アンビエントのガラス）系統」を曲の全長ぶん演奏して書き出す。

使い方:
  python -I musio_piano.py choose <state.bin>
      Musio の画面を開く。依頼者がピアノを選んで画面を閉じると、その設定を state.bin に保存する。
  python -I musio_piano.py render <state.bin> <out.wav>
      保存した設定で、MIDI を Musio に流して 94.32 秒のピアノを書き出す（ディレイと残響つき）。

旋律と和音はオリジナル。キーの音（D# E F# G# A# B C#）だけを使う。
テンポは breakcore_v2.py と同じ（80 BPM、62.4〜92 秒で 105 BPM まで加速）。
"""
import os
import sys

import mido
import numpy as np
from pedalboard import Delay, HighpassFilter, Limiter, Pedalboard, Reverb, load_plugin
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakcore_v2 as b2  # noqa: E402

PLUGIN = "C:/Program Files/Common Files/VST3/Musio.vst3"
SR = 48000
TOTAL = 94.32

# 2小節ごとに変わる3音のセルと低音（3番の案を全長に広げたもの）
CELLS = [([75, 82, 78], 27), ([75, 82, 80], 23), ([73, 80, 76], 28), ([71, 78, 75], 30)]
# 暗い区間に浮かべる旋律のかけら（拍, 長さ, 音）
FRAG = [(0, 3, 87), (3, 1, 85), (4, 4, 82), (8, 2, 87), (10, 2, 90), (12, 4, 87)]


def density(t):
    """区間ごとの刻みの細かさ（1拍あたりの音数）と強さ。"""
    if t < 2.83:
        return 0, 0
    if t < 14.1:
        return 2, 48
    if t < 35.5:
        return 4, 62
    if t < 51.0:
        return 1, 44
    if t < 62.4:
        return 4, 60
    if t < 80.0:
        return 4, 72
    if t < 92.0:
        return 6, 88
    return 0, 0


def build_events():
    beats = b2.beat_times(TOTAL + 5)
    ev = []  # (秒, 'on'/'off', 音, 強さ)

    def bt(b):
        i = int(np.floor(b))
        return beats[i] + (b - i) * (beats[i + 1] - beats[i])

    def add(b0, length, m, vel):
        t0, t1 = bt(b0), bt(b0 + length)
        if t0 >= 92.0:
            return
        ev.append((t0, 'on', m, vel))
        ev.append((min(t1, 93.5), 'off', m, 0))

    nb = 0
    while bt(nb) < 92.0:
        t = bt(nb)
        bar = nb // 4
        cell, bass = CELLS[(bar // 2) % 4]
        if nb % 8 == 0 and t >= 2.83:
            add(nb, 8, bass, 50)
            add(nb, 8, bass + 12, 40)
        div, vel = density(t)
        for k in range(div):
            step = nb * div + k
            m = cell[step % 3]
            if t >= 62.4 and k % 2 == 1:
                m += 12  # 終盤はオクターブ上を混ぜてきらめかせる
            add(nb + k / div, 1.0, m, int(vel + (8 if k == 0 else 0)))
        nb += 1
    # 暗い区間（35.5〜51 秒）には旋律のかけらを2回浮かべる
    b_dark = int(np.searchsorted(beats, 36.0))
    for rep in range(2):
        for b, length, m in FRAG:
            add(b_dark + rep * 16 + b, length, m, 70)
    # 最後の和音（92 秒）
    for m in [27, 39, 51, 58, 63, 70, 75, 82, 87]:
        ev.append((92.0, 'on', m, 80))
        ev.append((94.2, 'off', m, 0))
    ev.sort(key=lambda e: (e[0], e[1] == 'on'))
    return ev


def to_midi(ev):
    msgs = []
    for t, kind, m, vel in ev:
        if kind == 'on':
            msgs.append(mido.Message('note_on', note=m, velocity=max(1, min(127, vel)), time=t))
        else:
            msgs.append(mido.Message('note_off', note=m, velocity=0, time=t))
    msgs.insert(0, mido.Message('control_change', control=64, value=0, time=0.0))
    return msgs


def main():
    mode = sys.argv[1]
    plug = load_plugin(PLUGIN)
    if mode == 'choose':
        print("Musio の画面でピアノを選んで、画面を閉じてください。", flush=True)
        plug.show_editor()
        with open(sys.argv[2], 'wb') as f:
            f.write(plug.raw_state)
        print("saved", sys.argv[2], len(plug.raw_state), "bytes")
        return
    with open(sys.argv[2], 'rb') as f:
        plug.raw_state = f.read()
    msgs = to_midi(build_events())
    print("notes", sum(1 for m in msgs if m.type == 'note_on'), flush=True)
    audio = plug(msgs, duration=TOTAL, sample_rate=SR, num_channels=2, buffer_size=512, reset=True)
    print("raw peak", float(np.max(np.abs(audio))), flush=True)
    audio = Pedalboard([HighpassFilter(50), Delay(delay_seconds=0.5625, feedback=0.4, mix=0.3),
                        Reverb(room_size=0.95, damping=0.25, wet_level=0.45, dry_level=0.7),
                        Limiter(threshold_db=-3)])(audio, SR)
    peak = max(float(np.max(np.abs(audio))), 1e-9)
    audio = audio * (10 ** (-1.5 / 20) / peak)
    wavfile.write(sys.argv[3], SR, (np.clip(audio.T, -1, 1) * 32767).astype(np.int16))
    print("done", sys.argv[3])


if __name__ == '__main__':
    main()
