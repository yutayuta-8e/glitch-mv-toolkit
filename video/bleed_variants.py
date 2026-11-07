"""注意書き06の本文の、インクのにじみ加工10パターンを静止画で並べる。

フォントはどれも 幻ノにじみ明朝。「警告」（したたる明朝初号）はそのまま。
使い方: python -I bleed_variants.py <title_font> <body_font> <out_dir>
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 816
TITLE_FONT, BODY_FONT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
JA = ["この映像には激しい光の点滅や", "色の急な変化が多く含まれます。", "光に敏感な方はご注意ください。"]


def ink_center(d, text, font, y):
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    probe = Image.new("L", (r - l + 40, b - t + 40))
    ImageDraw.Draw(probe).text((20 - l, 20 - t), text, font=font, fill=255)
    il, _, ir, _ = probe.getbbox()
    return (W - (ir - il)) / 2 - (il - 20 + l), y - t


def body_alpha():
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    en = ImageFont.truetype(BODY_FONT, 50)
    d.text(ink_center(d, "PHOTOSENSITIVITY WARNING", en, 368), "PHOTOSENSITIVITY WARNING", font=en, fill=255)
    body = ImageFont.truetype(BODY_FONT, 58)
    for i, line in enumerate(JA):
        d.text(ink_center(d, line, body, 470 + i * 88), line, font=body, fill=255)
    return np.asarray(img, np.float32) / 255


def title_layer():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(TITLE_FONT, 230)
    d.text(ink_center(d, "警告", f, 70), "警告", font=f, fill=(179, 0, 27, 255))
    return img


def blur(a, r):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                      np.float32) / 255


def smooth(a, lo, hi):
    t = np.clip((a - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


RNG = np.random.default_rng(7)
NOISE = RNG.random((H, W)).astype(np.float32)


def noise(r):
    return blur(NOISE, r)


def v01(a):  # フォントだけ
    return a


def v02(a):  # 弱
    return smooth(blur(a, 1.4), 0.25, 0.6)


def v03(a):  # 中（いまの版）
    core = smooth(blur(a, 2.6), 0.18, 0.55) * (0.82 + 0.36 * noise(1.2))
    return np.maximum(np.clip(core, 0, 1), blur(a, 7) * 0.45)


def v04(a):  # 強
    core = smooth(blur(a, 4.0), 0.12, 0.45) * (0.8 + 0.4 * noise(1.5))
    return np.maximum(np.clip(core, 0, 1), blur(a, 10) * 0.5)


def v05(a):  # 輪郭のにじみだけ
    return smooth(blur(a, 3.4), 0.15, 0.5)


def v06(a):  # デコボコ（ノイズで閾値をゆらす）
    n = noise(2.0)
    return smooth(blur(a, 2.8) + (n - 0.5) * 0.5, 0.2, 0.5)


def v07(a):  # 墨だまり：太らせて、線の重なりや角に濃いたまり
    fat = smooth(blur(a, 3.0), 0.08, 0.35)
    pool = smooth(blur(a, 6.0), 0.55, 0.85)
    return np.clip(fat * 0.8 + pool * 0.4, 0, 1)


def v08(a):  # にじみ＋かすれ：横に伸びたノイズで欠けさせる
    streak = np.asarray(Image.fromarray((NOISE * 255).astype(np.uint8)).resize((W // 24, H)).resize((W, H), Image.BILINEAR),
                        np.float32) / 255
    core = smooth(blur(a, 2.2), 0.2, 0.55)
    return np.clip(core * smooth(streak + noise(0.8) * 0.4, 0.35, 0.7), 0, 1)


def v09(a):  # 毛羽立ち：縁から細い繊維状に走る
    fibers = np.asarray(Image.fromarray((NOISE * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)), np.float32) / 255
    edge = smooth(blur(a, 5.0), 0.05, 0.35) - smooth(blur(a, 1.0), 0.3, 0.6)
    hair = np.clip(edge, 0, 1) * (fibers > 0.55) * 0.85
    return np.clip(np.maximum(smooth(blur(a, 1.6), 0.25, 0.6), hair), 0, 1)


def v10(a):  # 濡れた紙：広く柔らかい染み＋強いむら
    core = smooth(blur(a, 2.4), 0.2, 0.55) * (0.7 + 0.6 * noise(2.5))
    wet = blur(a, 16) * 0.75 * (0.6 + 0.8 * noise(6))
    return np.clip(np.maximum(core, wet), 0, 1)


VARIANTS = [("01_font_only", v01), ("02_weak", v02), ("03_medium_current", v03), ("04_strong", v04),
            ("05_edge_only", v05), ("06_organic_edge", v06), ("07_ink_pool", v07), ("08_bleed_dry", v08),
            ("09_fiber", v09), ("10_wet_paper", v10)]


def main():
    os.makedirs(OUT, exist_ok=True)
    a = body_alpha()
    title = title_layer()
    sheet = Image.new("RGB", (2 * 960, 5 * (408 + 150 + 30)), (25, 25, 25))
    sd = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 26)
    for k, (name, fn) in enumerate(VARIANTS):
        alpha = np.clip(fn(a), 0, 1)
        rgb = np.full((H, W, 3), 235, np.float32)
        layer = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        frame.alpha_composite(layer)
        frame.alpha_composite(title)
        frame = frame.convert("RGB")
        frame.save(os.path.join(OUT, f"BLEED-{name}.png"))
        x, y = (k % 2) * 960, (k // 2) * (408 + 150 + 30)
        sd.text((x + 10, y + 2), f"BLEED-{name}", font=label_font, fill=(255, 220, 0))
        sheet.paste(frame.resize((960, 408), Image.LANCZOS), (x, y + 30))
        crop = frame.crop((560, 455, 1360, 545)).resize((960, 108), Image.LANCZOS)
        sheet.paste(crop, (x, y + 30 + 408 + 20))
    sheet.save(os.path.join(OUT, "BLEED-contact-sheet.png"))
    print("done", OUT)


if __name__ == "__main__":
    main()
