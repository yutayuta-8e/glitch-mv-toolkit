"""にじみ加工2（ぼかして締め直す）の強さ3段階を、画面全体の文字にかけた静止画。
使い方: python -I bleed_v2_strength.py <title_font> <body_font> <out_dir>"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.argv = sys.argv[:4]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bleed_variants as bv  # noqa: E402
import bleed_fullframe as bf  # noqa: E402

LEVELS = [("2A_light", 1.0), ("2B_medium", 1.9), ("2C_strong", 2.8)]


def weak(a, r):
    return bv.smooth(bv.blur(a, r), 0.22, 0.58)


def main():
    out = sys.argv[3]
    ta, ba = bf.title_alpha(), bv.body_alpha()
    W, H = bv.W, bv.H
    sheet = Image.new("RGB", (960, 3 * (408 + 190 + 30)), (25, 25, 25))
    sd = ImageDraw.Draw(sheet)
    lf = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 26)
    for k, (name, r) in enumerate(LEVELS):
        t, b = weak(ta, r), weak(ba, r)
        f = np.zeros((H, W, 3), np.float32)
        f = f * (1 - b[..., None]) + np.array([235, 235, 235]) * b[..., None]
        f = f * (1 - t[..., None]) + np.array([179, 0, 27]) * t[..., None]
        im = Image.fromarray(f.astype(np.uint8))
        im.save(os.path.join(out, f"BLEED-FULL-{name}_r{r}.png"))
        y = k * (408 + 190 + 30)
        sd.text((10, y + 2), f"BLEED-FULL-{name} (blur {r})", font=lf, fill=(255, 220, 0))
        sheet.paste(im.resize((960, 408), Image.LANCZOS), (0, y + 30))
        sheet.paste(im.crop((700, 60, 1220, 300)).resize((390, 180), Image.LANCZOS), (0, y + 30 + 408 + 5))
        sheet.paste(im.crop((560, 455, 1060, 545)).resize((570, 103), Image.LANCZOS), (390, y + 30 + 408 + 45))
    sheet.save(os.path.join(out, "BLEED-FULL-2-strength-sheet.png"))
    print("done")


if __name__ == "__main__":
    main()
