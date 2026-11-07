"""中が抜けた本物のアウトライン文字の比較。使い方: python -I outline_variants.py <bg.png> <font> <out_dir>"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BG, FONT, OUT = sys.argv[1:4]
TEXT = "めめめ LOOK"


def glyph(size, w, h):
    m = Image.new("L", (w, h), 0)
    f = ImageFont.truetype(FONT, size)
    d = ImageDraw.Draw(m)
    l, t, r, b = d.textbbox((0, 0), TEXT, font=f)
    d.text(((w - (r - l)) / 2 - l, (h - (b - t)) / 2 - t), TEXT, font=f, fill=255)
    return m


def ring(m, width):  # 輪郭線だけ（内側に width px）
    k = width * 2 + 1
    return np.clip(np.asarray(m, np.float32) - np.asarray(m.filter(ImageFilter.MinFilter(k)), np.float32), 0, 255) / 255


def over(bg, a, rgb):
    out = np.asarray(bg, np.float32).copy()
    return out * (1 - a[..., None]) + np.array(rgb, np.float32) * a[..., None]


bg = Image.open(BG).convert("RGB")
W, H = bg.size
m = glyph(330, W, H)
a = np.asarray(m, np.float32) / 255
fat = np.asarray(m.filter(ImageFilter.MaxFilter(17)), np.float32) / 255
cyan = (0, 255, 230)
v = {
    "1_now_filled": over(bg, fat, cyan),
    "2_hairline_3px": over(bg, ring(m, 3), cyan),
    "3_line_6px": over(bg, ring(m, 6), cyan),
    "4_line_12px": over(bg, ring(m, 12), cyan),
    "5_double_line": over(over(bg, ring(m, 4), cyan),
                          ring(Image.fromarray((np.clip(fat, 0, 1) * 255).astype(np.uint8)), 3), (255, 40, 120)),
    "6_line_6px_glow": None,
}
glow = np.asarray(Image.fromarray((ring(m, 6) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)), np.float32) / 255
v["6_line_6px_glow"] = over(over(bg, np.clip(glow * 1.6, 0, 1) * 0.7, cyan), ring(m, 5), (230, 255, 250))
os.makedirs(OUT, exist_ok=True)
sheet = Image.new("RGB", (2 * 960, 3 * (408 + 34)), (20, 20, 20))
sd = ImageDraw.Draw(sheet)
lf = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 26)
for k, (name, arr) in enumerate(v.items()):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    im.save(os.path.join(OUT, f"OUTLINE-{name}.png"))
    x, y = (k % 2) * 960, (k // 2) * (408 + 34)
    sd.text((x + 10, y + 3), f"OUTLINE-{name}", font=lf, fill=(255, 220, 0))
    sheet.paste(im.resize((960, 408), Image.LANCZOS), (x, y + 34))
sheet.save(os.path.join(OUT, "OUTLINE-contact-sheet.jpg"), quality=92)
print("done")
