"""にじみ加工 2・8・9・10 を、「警告」も含めた画面全体の文字にかけた静止画。

8（かすれ）と9（毛羽立ち）は前回の効きが弱かったので強めた。
使い方: python -I bleed_fullframe.py <title_font> <body_font> <out_dir>
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.argv = sys.argv[:4]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bleed_variants as bv  # noqa: E402  （同じ文字配置と部品を使う）

W, H = bv.W, bv.H
OUT = sys.argv[3]


def title_alpha():
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(bv.TITLE_FONT, 230)
    d.text(bv.ink_center(d, "警告", f, 70), "警告", font=f, fill=255)
    return np.asarray(img, np.float32) / 255


def v02(a):
    return bv.v02(a)


def v08_strong(a):  # にじみ＋かすれ（強め）：横に流れる筋で欠けさせ、縁はにじませる
    streak = np.asarray(Image.fromarray((bv.NOISE * 255).astype(np.uint8)).resize((W // 40, H // 2))
                        .resize((W, H), Image.BILINEAR), np.float32) / 255
    core = bv.smooth(bv.blur(a, 2.4), 0.18, 0.5)
    dry = bv.smooth(streak * 0.7 + bv.noise(0.7) * 0.6, 0.38, 0.62)
    return np.clip(core * (0.25 + 0.75 * dry), 0, 1)


def v09_strong(a):  # 毛羽立ち（強め）：縁から細い繊維が外へ走る
    rng = np.random.default_rng(11)
    fib = np.zeros((H, W), np.float32)
    ys, xs = np.nonzero(bv.blur(a, 1.0) > 0.4)
    pick = rng.choice(len(xs), size=min(len(xs), 26000), replace=False)
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    for k in pick:
        ang = rng.uniform(0, 2 * np.pi)
        ln = rng.uniform(3, 11)
        x0, y0 = xs[k], ys[k]
        d.line([(x0, y0), (x0 + np.cos(ang) * ln, y0 + np.sin(ang) * ln)], fill=int(rng.uniform(120, 230)), width=1)
    fib = np.asarray(img, np.float32) / 255
    base = bv.smooth(bv.blur(a, 1.8), 0.22, 0.58)
    return np.clip(np.maximum(base, fib * 0.85), 0, 1)


def v10(a):
    return bv.v10(a)


VARIANTS = [("02_weak", v02), ("08_bleed_dry_strong", v08_strong), ("09_fiber_strong", v09_strong),
            ("10_wet_paper", v10)]


def main():
    os.makedirs(OUT, exist_ok=True)
    ta, ba = title_alpha(), bv.body_alpha()
    sheet = Image.new("RGB", (2 * 960, 2 * (408 + 150 + 30)), (25, 25, 25))
    sd = ImageDraw.Draw(sheet)
    lf = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 26)
    for k, (name, fn) in enumerate(VARIANTS):
        t = np.clip(fn(ta), 0, 1)
        b = np.clip(fn(ba), 0, 1)
        frame = np.zeros((H, W, 3), np.float32)
        frame = frame * (1 - b[..., None]) + np.array([235, 235, 235]) * b[..., None]
        frame = frame * (1 - t[..., None]) + np.array([179, 0, 27]) * t[..., None]
        im = Image.fromarray(frame.astype(np.uint8))
        im.save(os.path.join(OUT, f"BLEED-FULL-{name}.png"))
        x, y = (k % 2) * 960, (k // 2) * (408 + 150 + 30)
        sd.text((x + 10, y + 2), f"BLEED-FULL-{name}", font=lf, fill=(255, 220, 0))
        sheet.paste(im.resize((960, 408), Image.LANCZOS), (x, y + 30))
        sheet.paste(im.crop((700, 60, 1220, 300)).resize((325, 150), Image.LANCZOS), (x, y + 30 + 408 + 20))
        sheet.paste(im.crop((560, 455, 1360, 545)).resize((635, 71), Image.LANCZOS), (x + 325, y + 30 + 408 + 60))
    sheet.save(os.path.join(OUT, "BLEED-FULL-contact-sheet.png"))
    print("done")


if __name__ == "__main__":
    main()
