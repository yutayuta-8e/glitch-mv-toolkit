"""サムネ THUMB-01_1 を、動画（見てるよ v7）の質感に合わせて 10 通りに加工し、中央に小さく題名を入れる。

生成 AI は使わず Pillow / NumPy だけで加工する。元画像は読むだけで、別ファイルに書き出す。
どのパターンにも動画の仕上げ（走査線・RGB ずれ・周辺減光・粒子ノイズ）をかけ、そのうえで
パターンごとの効果（VHS のずれ、ネガ反転、二色化、ポスター化、鏡写し、ブロック化、二重露光など）を足す。
使い方: python -I thumb_fx.py <元画像> <動画のコマ.png> <出力フォルダ>
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC, VFRAME, OUT = sys.argv[1:4]
W, H = 1920, 1080
TITLE = "yuta - breakcore 2"
FD = os.environ.get("GLITCH_MV_FONTS", "fonts")  # いいフォントなどの書体を入れたフォルダ（書体ごとのサブフォルダ）
FONTS = {
    "nijimi": f"{FD}/maboroshi-nijimi-mincho/幻ノにじみ明朝.otf",
    "dust": f"{FD}/dustdevil-m/CHI_DustDevil_M-Heavy.ttf",
    "degobo": f"{FD}/degobogothic/degobogothic.ttf",
    "shitataru": f"{FD}/shitataru-mincho/ShitataruMinchoShogo-EB.ttf",
    "kurobara": f"{FD}/kurobara-cinderella/kurobara-cinderella.ttf",
    "haretsu": f"{FD}/haretsu-no-mincho/HaretsuNoMincho.ttf",
    "zomzi": f"{FD}/ankokuzonji/zomzi.TTF",
    "onryou": f"{FD}/onryou/onryou.TTF",
    "shinsyoku": f"{FD}/shinsyoku-mincho/ShinsyokuMincho-Regular.ttf",
    "fear": f"{FD}/feeling-of-fear/FeelingOfFear.ttf",
}
RNG = np.random.default_rng(7)


def arr(im):
    return np.asarray(im.convert("RGB"), np.float32)


def img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- 動画と同じ仕上げ
def finish(a, shift=4, grain=12.0):
    """ffmpeg の drawgrid（4px ごとの黒線 35%）、rgbashift（赤 -4・青 +4）、vignette、noise に相当。"""
    a = a.copy()
    a[::4] *= 0.65
    out = a.copy()
    out[:, :, 0] = np.roll(a[:, :, 0], -shift, axis=1)
    out[:, :, 2] = np.roll(a[:, :, 2], shift, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / np.sqrt(2)
    out *= (np.cos(np.clip(r, 0, 1) * np.pi / 4) ** 4)[..., None] * 1.12
    out += RNG.normal(0, grain, (H, W, 1))
    return out


# ---------------------------------------------------------------- 題名
def title(im, font, size, fill, stroke=0, stroke_fill=(0, 0, 0), outline_only=False, rgb_split=0, glow=None):
    """インクの外枠で画面の真ん中に置く。"""
    f = ImageFont.truetype(FONTS[font], size)
    probe = Image.new("L", (W, H))
    ImageDraw.Draw(probe).text((0, 0), TITLE, font=f, fill=255, stroke_width=stroke)
    l, t, r, b = probe.getbbox()
    pos = ((W - (r - l)) / 2 - l, (H - (b - t)) / 2 - t)
    mask = Image.new("L", (W, H))
    ImageDraw.Draw(mask).text(pos, TITLE, font=f, fill=255)
    if outline_only:
        mask = Image.fromarray(np.clip(np.asarray(mask, np.int16)
                                       - np.asarray(mask.filter(ImageFilter.MinFilter(5)), np.int16), 0, 255).astype(np.uint8))
    base = im.convert("RGB")
    if glow:
        g = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(14))
        base = Image.composite(Image.new("RGB", (W, H), glow), base, g.point(lambda v: v * 0.8))
    if stroke and not outline_only:
        sm = Image.new("L", (W, H))
        ImageDraw.Draw(sm).text(pos, TITLE, font=f, fill=255, stroke_width=stroke)
        base = Image.composite(Image.new("RGB", (W, H), stroke_fill), base, sm)
    if rgb_split:
        for col, dx in (((255, 0, 60), -rgb_split), ((0, 255, 238), rgb_split)):
            m = Image.new("L", (W, H))
            m.paste(mask, (dx, 0))
            base = Image.composite(Image.new("RGB", (W, H), col), base, m.point(lambda v: v * 0.85))
    return Image.composite(Image.new("RGB", (W, H), fill), base, mask)


# ---------------------------------------------------------------- 効果
def vhs(a):
    out = a.copy()
    y = 0
    while y < H:
        h = int(RNG.integers(6, 60))
        if RNG.random() < 0.35:
            out[y:y + h] = np.roll(a[y:y + h], int(RNG.integers(-50, 50)), axis=1)
        y += h
    ch = out.copy()
    ch[:, :, 0] = np.roll(out[:, :, 0], -12, axis=1)
    ch[:, :, 2] = np.roll(out[:, :, 2], 12, axis=1)
    blur = arr(img(ch).filter(ImageFilter.GaussianBlur(1.6)))
    return blur * 0.9 + 12


def duotone(a, dark, mid, light):
    lum = (a @ np.array([0.299, 0.587, 0.114], np.float32))[..., None] / 255
    d, m, li = (np.array(c, np.float32) for c in (dark, mid, light))
    lo = d + (m - d) * np.clip(lum * 2, 0, 1)
    hi = m + (li - m) * np.clip(lum * 2 - 1, 0, 1)
    return np.where(lum < 0.5, lo, hi)


def posterize_acid(a):
    q = np.floor(a / 256 * 4) * (255 / 3)
    hsv = np.asarray(img(q).convert("HSV"), np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + 70) % 256  # 色相を回して、ピンクを緑・黄寄りに
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.6, 0, 255)
    return arr(Image.fromarray(hsv.astype(np.uint8), "HSV"))


def mirror(a):
    """動画の鏡写しのカットと同じく、左上の4分の1を上下左右に折り返し、ずらした2枚目を色相を変えて重ねる。"""
    q = a[: H // 2, : W // 2]
    top = np.concatenate([q, q[:, ::-1]], 1)
    k = np.concatenate([top, top[::-1]], 0)
    sh = np.roll(k, W // 6, axis=1)
    hsv = np.asarray(img(sh).convert("HSV"), np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + 110) % 256
    alt = arr(Image.fromarray(hsv.astype(np.uint8), "HSV"))
    return np.maximum(k * 0.85, alt * 0.55)


def pixel_glitch(a):
    out = a.copy()
    y = 0
    while y < H:
        h = int(RNG.integers(20, 120))
        if RNG.random() < 0.45:
            b = int(RNG.choice([16, 24, 40]))
            band = img(a[y:y + h])
            small = band.resize((max(1, W // b), max(1, band.height // b)), Image.NEAREST)
            out[y:y + h] = arr(small.resize(band.size, Image.NEAREST))
            if RNG.random() < 0.5:
                out[y:y + h] = np.roll(out[y:y + h], int(RNG.integers(-120, 120)), axis=1)
        y += h
    for _ in range(14):  # ずれたブロック（データの崩れ風）
        bw, bh = int(RNG.integers(80, 300)), int(RNG.integers(20, 90))
        x0, y0 = int(RNG.integers(0, W - bw)), int(RNG.integers(0, H - bh))
        x1, y1 = int(RNG.integers(0, W - bw)), int(RNG.integers(0, H - bh))
        out[y0:y0 + bh, x0:x0 + bw] = a[y1:y1 + bh, x1:x1 + bw][:, :, [2, 0, 1]]
    return out


def double_exposure(a, b):
    screen = 255 - (255 - a) * (255 - b) / 255
    diff = np.abs(a - b)
    return screen * 0.55 + diff * 0.45


def ominous(a):
    lum = (a @ np.array([0.299, 0.587, 0.114], np.float32))[..., None] / 255
    dark = (lum ** 2.2) * np.array([255, 30, 60], np.float32) + a * 0.12
    return dark


def text_wall(a, font):
    words = ["見てるよ", "みつけた", "目", "眼", "瞳", "EYE", "I SEE YOU", "WATCHING", "DON'T BLINK", "まばたき禁止",
             "ここにいるよ", "MITERUYO", "FOUND YOU", "視線過多", "LOOK"]
    cols = [(255, 0, 204), (0, 255, 238), (255, 242, 0), (57, 255, 20), (255, 255, 255)]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(170):  # 1語ずつ1色。動画のスパートの文字の壁に寄せる
        f = ImageFont.truetype(FONTS[str(RNG.choice(list(FONTS)))], int(RNG.integers(40, 220)))
        w = str(RNG.choice(words))
        c = cols[int(RNG.integers(0, len(cols)))]
        d.text((int(RNG.integers(-200, W)), int(RNG.integers(-60, H))), w, font=f,
               fill=c + (int(RNG.integers(110, 200)),))
    out = img(a * 0.75)  # 文字の壁が見えるように、元の絵を少し沈める
    out.paste(layer, (0, 0), layer)
    return arr(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    base = Image.open(SRC).convert("RGB").resize((W, H), Image.LANCZOS)
    a = arr(base)
    vf = arr(Image.open(VFRAME).convert("RGB").resize((W, int(W * 816 / 1920)), Image.LANCZOS)
             .resize((W, H), Image.LANCZOS))
    v = [
        ("01_film_finish", finish(a), dict(font="nijimi", size=58, fill=(255, 255, 255), glow=(0, 0, 0))),
        ("02_vhs_tracking", finish(vhs(a), shift=6), dict(font="dust", size=54, fill=(255, 255, 255), rgb_split=4)),
        ("03_negative_flash", finish(255 - a), dict(font="degobo", size=56, fill=(0, 0, 0), stroke=3,
                                                      stroke_fill=(255, 242, 0))),
        ("04_magenta_duotone", finish(duotone(a, (10, 0, 20), (255, 0, 170), (255, 235, 250))),
         dict(font="shitataru", size=60, fill=(255, 255, 255), glow=(30, 0, 40))),
        ("05_acid_posterize", finish(posterize_acid(a)), dict(font="kurobara", size=60, fill=(0, 0, 0), stroke=4,
                                                            stroke_fill=(255, 255, 255))),
        ("06_mirror_kaleido", finish(mirror(a)), dict(font="haretsu", size=58, fill=(255, 255, 255), rgb_split=5,
                                                    glow=(0, 0, 0))),
        ("07_pixel_glitch", finish(pixel_glitch(a)), dict(font="zomzi", size=56, fill=(0, 255, 238), stroke=3,
                                                        stroke_fill=(0, 0, 0))),
        ("08_double_exposure", finish(double_exposure(a, vf)), dict(font="onryou", size=62, fill=(255, 255, 255),
                                                                  glow=(255, 0, 204))),
        ("09_ominous_red", finish(ominous(a), grain=16), dict(font="shinsyoku", size=72, fill=(255, 225, 230),
                                                            outline_only=True, glow=(0, 0, 0))),
        ("10_text_wall", finish(text_wall(a, "fear")), dict(font="fear", size=60, fill=(255, 242, 0), stroke=4,
                                                          stroke_fill=(0, 0, 0))),
    ]
    sheet = Image.new("RGB", (5 * 384, 2 * (216 + 28)), (20, 20, 20))
    sd = ImageDraw.Draw(sheet)
    lf = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 20)
    for k, (name, fx, t) in enumerate(v):
        out = title(img(fx), **t)
        out.save(os.path.join(OUT, f"THUMB-01_1_fx{name}.png"))
        x, y = (k % 5) * 384, (k // 5) * (216 + 28)
        sd.text((x + 6, y + 3), f"{name}  [{t['font']}]", font=lf, fill=(255, 220, 0))
        sheet.paste(out.resize((384, 216), Image.LANCZOS), (x, y + 28))
    sheet.save(os.path.join(OUT, "THUMB-01_1_fx-contact-sheet.jpg"), quality=92)
    print("done", OUT)


if __name__ == "__main__":
    main()
