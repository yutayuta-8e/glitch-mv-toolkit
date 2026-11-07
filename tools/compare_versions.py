"""2 つの版がどれくらい同じかを測る。解像度が違っても、b を a の大きさに合わせて比べる。

- 映像：N コマごとの SSIM（1 が完全一致）。粒子ノイズを全体にかけた映像は、圧縮でノイズが消えるだけで下がる。
- 文字の記録：chaos_text の text_log.json を 2 つ渡すと、言葉・フォント・アウトラインかが一致するかを数える。
使い方:
  python -I tools/compare_versions.py video <a.mp4> <b.mp4> [--every 12]
  python -I tools/compare_versions.py textlog <a/text_log.json> <b/text_log.json>
"""
import argparse
import json
import re
import subprocess


def video(a, b, every):
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", a], capture_output=True, text=True, check=True).stdout.strip().split(",")
    graph = (f"[0:v]select='not(mod(n\\,{every}))',setpts=N/TB[x];"
             f"[1:v]select='not(mod(n\\,{every}))',setpts=N/TB,scale={w}:{h}:flags=lanczos[y];[x][y]ssim")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", a, "-i", b, "-lavfi", graph, "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.findall(r"SSIM Y:([\d.]+).*All:([\d.]+)", r)
    print(f"SSIM Y {m[-1][0]}  All {m[-1][1]}  (every {every} frames, compared at {w}x{h})" if m else r[-800:])


def textlog(a, b):
    x = json.load(open(a, encoding="utf-8"))["texts"]
    y = json.load(open(b, encoding="utf-8"))["texts"]
    keys = ("word", "font", "outline_only")
    same = sum(all(p.get(k) == q.get(k) for k in keys) for p, q in zip(x, y))
    print(f"{len(x)} vs {len(y)} texts, identical (word/font/outline) {same}/{min(len(x), len(y))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["video", "textlog"])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--every", type=int, default=12)
    a = ap.parse_args()
    video(a.a, a.b, a.every) if a.kind == "video" else textlog(a.a, a.b)


if __name__ == "__main__":
    main()
