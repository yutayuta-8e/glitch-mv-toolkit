"""黒背景の動画を、黒が透明な ProRes 4444 の MOV に変換する。

アルファは各画素の RGB の最大値から作る（lo 以下は完全透明、hi 以上は不透明、間はなめらか）。
半透明の画素は色を alpha で割り戻し、ふちに黒いにじみが残らないようにする。
"""
import argparse
import subprocess

import numpy as np


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout.strip().split(",")
    return int(out[0]), int(out[1]), out[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--lo", type=float, default=10)
    ap.add_argument("--hi", type=float, default=48)
    ap.add_argument("--q", type=int, default=None, help="prores_ks qscale (larger = smaller file)")
    a = ap.parse_args()

    w, h, fps = probe(a.src)
    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", a.src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
         "-r", fps, "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
         "-alpha_bits", "16", "-vendor", "apl0"]
        + (["-qscale:v", str(a.q)] if a.q else []) + [a.out],
        stdin=subprocess.PIPE)
    size = w * h * 3
    n = 0
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        rgb = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32)
        t = np.clip((rgb.max(axis=2) - a.lo) / (a.hi - a.lo), 0, 1)
        alpha = t * t * (3 - 2 * t)
        safe = np.maximum(alpha, 1e-3)[..., None]
        col = np.clip(rgb / safe, 0, 255)
        col[alpha == 0] = 0
        rgba = np.dstack([col, alpha * 255]).round().astype(np.uint8)
        enc.stdin.write(rgba.tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print(a.out, "frames", n)


if __name__ == "__main__":
    main()
