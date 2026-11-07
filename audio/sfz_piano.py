"""SFZ のピアノ音源（Salamander Grand Piano V3）を、演奏データどおりに鳴らして書き出す小さなサンプラー。

- SFZ の <region> から sample / lokey / hikey / lovel / hivel / pitch_keycenter を読み、
  音高と強さに合う録音を選ぶ。録音のない音高は近い録音の音程を少しずらして使う。
- 強さによる音量は SFZ の amp_veltrack（73%）にならう。離鍵後は ampeg_release（1 秒）で消す。
- 演奏データは musio_piano.py の build_events()（3番系統、曲の全長）を使う。

使い方: python -I sfz_piano.py <SalamanderGrandPianoV3.sfz> <out.wav>
"""
import os
import re
import sys

import numpy as np
from pedalboard import Delay, HighpassFilter, Limiter, Pedalboard, Reverb
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import musio_piano as mp  # noqa: E402

SR = 48000
TOTAL = mp.TOTAL
VELTRACK = 0.73
RELEASE = 1.0


def parse_sfz(path):
    base = os.path.dirname(path)
    regions = []
    group = {}
    text = open(path, encoding="utf-8", errors="replace").read()
    for line in text.splitlines():
        if line.startswith("<group>"):
            group = dict(re.findall(r"(\w+)=(\S+)", line))
            continue
        if not line.startswith("<region>"):
            continue
        kv = {**group, **dict(re.findall(r"(\w+)=(\S+)", line))}
        # 離鍵音（trigger=release）とペダル音（hikey=-1 のグループ）は使わない
        if "sample" not in kv or kv.get("trigger") == "release" or group.get("hikey") == "-1":
            continue
        regions.append({
            "sample": os.path.join(base, kv["sample"].replace("\\", os.sep)),
            "lokey": int(kv.get("lokey", 0)), "hikey": int(kv.get("hikey", 127)),
            "lovel": int(kv.get("lovel", 1)), "hivel": int(kv.get("hivel", 127)),
            "center": int(kv.get("pitch_keycenter", kv.get("lokey", 60))),
            "release": float(kv.get("ampeg_release", RELEASE)),
            "veltrack": float(kv.get("amp_veltrack", VELTRACK * 100)) / 100,
        })
    return regions


_WAV = {}


def load(path):
    if path not in _WAV:
        sr, x = wavfile.read(path)
        x = x.astype(np.float32) / 32768.0
        if x.ndim == 1:
            x = np.stack([x, x], 1)
        _WAV[path] = (sr, x)
    return _WAV[path]


def render_note(regions, m, vel, dur):
    cand = [r for r in regions if r["lokey"] <= m <= r["hikey"] and r["lovel"] <= vel <= r["hivel"]]
    if not cand:
        cand = sorted(regions, key=lambda r: (abs(r["center"] - m), abs((r["lovel"] + r["hivel"]) / 2 - vel)))[:1]
    r = cand[0]
    sr, x = load(r["sample"])
    ratio = 2 ** ((m - r["center"]) / 12) * sr / SR  # 1 出力サンプルあたりに進む元のサンプル数
    rel = r["release"]
    length = min(int((dur + rel) * SR), int((len(x) - 1) / ratio))
    pos = np.arange(length) * ratio
    y = np.stack([np.interp(pos, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    rel_start = int(dur * SR)
    if rel_start < length:
        k = length - rel_start
        y[rel_start:] *= np.exp(-np.arange(k) / SR * 5.0 / rel)[:, None]
    vt = r["veltrack"]
    gain = (1 - vt) + vt * (vel / 127) ** 2
    return y * gain


def main():
    sfz, out = sys.argv[1], sys.argv[2]
    regions = parse_sfz(sfz)
    print("regions", len(regions), flush=True)
    ev = mp.build_events()
    ons = {}
    buf = np.zeros((int((TOTAL + 2) * SR), 2), np.float32)
    count = 0
    for t, kind, m, vel in ev:
        if kind == "on":
            ons.setdefault(m, []).append((t, vel))
        else:
            if not ons.get(m):
                continue
            t0, v = ons[m].pop(0)
            y = render_note(regions, m, v, max(0.05, t - t0))
            i = int(t0 * SR)
            n = min(len(y), len(buf) - i)
            buf[i:i + n] += y[:n]
            count += 1
    buf = buf[: int(TOTAL * SR)]
    print("notes rendered", count, "raw peak", float(np.max(np.abs(buf))), flush=True)
    wet = Pedalboard([HighpassFilter(40), Delay(delay_seconds=0.5625, feedback=0.4, mix=0.28),
                      Reverb(room_size=0.93, damping=0.3, wet_level=0.4, dry_level=0.75),
                      Limiter(threshold_db=-3)])(np.ascontiguousarray(buf.T), SR).T
    wet *= 10 ** (-1.5 / 20) / max(float(np.max(np.abs(wet))), 1e-9)
    wavfile.write(out, SR, (np.clip(wet, -1, 1) * 32767).astype(np.int16))
    print("done", out)


if __name__ == "__main__":
    main()
