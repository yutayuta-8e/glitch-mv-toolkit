"""サムネの組み合わせ版：04 の背景（黒・マゼンタ・白の三色化）に、05 の題名（黒薔薇シンデレラ、黒字＋白の縁）を
2 倍の大きさ（60 → 120、縁 4 → 8）でのせる（2026-11-07 依頼者の指定）。部品は thumb_fx.py をそのまま使う。
使い方: python -I thumb_fx_combo.py <元画像> <出力.png>
"""
import os
import sys

src, out = sys.argv[1:3]
sys.argv = [sys.argv[0], src, "unused", os.path.dirname(out)]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_fx as fx  # noqa: E402
from PIL import Image  # noqa: E402

a = fx.arr(Image.open(src).convert("RGB").resize((fx.W, fx.H), Image.LANCZOS))
bg = fx.finish(fx.duotone(a, (10, 0, 20), (255, 0, 170), (255, 235, 250)))
fx.title(fx.img(bg), font="kurobara", size=120, fill=(0, 0, 0), stroke=8, stroke_fill=(255, 255, 255)).save(out)
print("done", out)
