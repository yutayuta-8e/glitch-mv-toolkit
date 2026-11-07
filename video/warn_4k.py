"""注意書き 06（にじみ 2-B、静止）を、倍率を付けて描き直す。v7 の warn_2B.png（1920×816）と同じ配置・同じ加工。

文字の大きさ・位置・にじみのぼかし量（1.9px）を倍率どおりにする。しきい値（0.22〜0.58）はそのまま。
使い方: python -I warn_4k.py <「警告」のフォント> <本文のフォント> <出力.png> [倍率]
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TITLE_FONT, BODY_FONT, OUT = sys.argv[1:4]
S = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
W, H = int(1920 * S), int(816 * S)
JA = ["この映像には激しい光の点滅や", "色の急な変化が多く含まれます。", "光に敏感な方はご注意ください。"]


def ink_center(d, text, font, y):
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    probe = Image.new("L", (r - l + 40, b - t + 40))
    ImageDraw.Draw(probe).text((20 - l, 20 - t), text, font=font, fill=255)
    il, _, ir, _ = probe.getbbox()
    return (W - (ir - il)) / 2 - (il - 20 + l), y - t


def alpha(lines):
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    for text, path, size, y in lines:
        f = ImageFont.truetype(path, int(size * S))
        d.text(ink_center(d, text, f, y * S), text, font=f, fill=255)
    return np.asarray(img, np.float32) / 255


def bleed(a):
    b = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.9 * S)),
                   np.float32) / 255
    t = np.clip((b - 0.22) / (0.58 - 0.22), 0, 1)
    return t * t * (3 - 2 * t)


ta = bleed(alpha([("警告", TITLE_FONT, 230, 70)]))
ba = bleed(alpha([("PHOTOSENSITIVITY WARNING", BODY_FONT, 50, 368)] +
                 [(line, BODY_FONT, 58, 470 + i * 88) for i, line in enumerate(JA)]))
f = np.zeros((H, W, 3), np.float32)
f = f * (1 - ba[..., None]) + np.array([235, 235, 235]) * ba[..., None]
f = f * (1 - ta[..., None]) + np.array([179, 0, 27]) * ta[..., None]
Image.fromarray(f.astype(np.uint8)).save(OUT)
print("saved", OUT, W, H)
