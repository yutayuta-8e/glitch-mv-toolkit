"""音量の推移（区間ごとの RMS）と、全体の LUFS・トゥルーピークを出す。聴けない AI が音を確かめる用。

区間の頭・ラストの壊れ方・余韻の消え方・無音のはずの所が本当に無音か、を数字で見る。
使い方: python -I tools/loudness_curve.py <音か動画> [--step 0.5] [--start 0] [--end 末尾]
"""
import argparse
import os
import re
import subprocess
import tempfile

import numpy as np
from scipy.io import wavfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vn", "-ac", "2", "-ar", "48000", wav], check=True)
        sr, x = wavfile.read(wav)
    x = x.astype(np.float64) / 32768
    end = len(x) / sr if a.end is None else a.end
    t = a.start
    rows = []
    while t < end - 1e-6:
        s = x[int(t * sr):int(min(t + a.step, end) * sr)]
        rows.append(f"{t:7.2f}s {20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12):6.1f} dB")
        t += a.step
    print("\n".join(rows))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.src, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    print(f"integrated {lufs[-1] if lufs else '?'} LUFS, true peak {peak[-1] if peak else '?'} dBTP")


if __name__ == "__main__":
    main()
