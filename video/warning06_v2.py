"""注意書き 06（drip_horror）の改訂版。

- 「警告」はしたたる明朝初号、本文（英語の見出しと日本語3行）はインクがにじむ明朝体「フィーリングオブフィア」。
- 各行は、字の実際のインクの幅を測って画面の真ん中に置く（ffmpeg の drawtext だと行末がそろって右寄せに見えたため）。
- 文字は PIL で透明 PNG に描き、ffmpeg で黒地に重ねて、ゆっくり寄る・周辺減光・フェードをかける。点滅はなし。
"""
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1920, 816, 24, 7
TITLE_FONT, BODY_FONT = sys.argv[1], sys.argv[2]
OUT_PNG, OUT_MP4 = sys.argv[3], sys.argv[4]

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)


def center_line(text, font, y, fill):
    """一度描いて実際のインク（不透明な画素）の範囲を測り、その中心を画面の中心に合わせる。
    全角の「。」などは字の幅に対してインクが片寄るため、字の枠ではなくインクで合わせる。"""
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    probe = Image.new("L", (r - l + 40, b - t + 40))
    ImageDraw.Draw(probe).text((20 - l, 20 - t), text, font=font, fill=255)
    il, _, ir, _ = probe.getbbox()
    ink_left = il - 20 + l
    ink_w = ir - il
    x = (W - ink_w) / 2 - ink_left
    d.text((x, y - t), text, font=font, fill=fill)
    return b - t


BLEED = len(sys.argv) > 5 and sys.argv[5] == "bleed"

title = ImageFont.truetype(TITLE_FONT, 230)
center_line("警告", title, 70, (179, 0, 27, 255))
title_layer = img.copy()

# 本文は別の層に描き、必要ならインクのにじみ加工をかける
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
en = ImageFont.truetype(BODY_FONT, 50)
center_line("PHOTOSENSITIVITY WARNING", en, 368, (225, 225, 225, 255))
body = ImageFont.truetype(BODY_FONT, 58)
for i, line in enumerate(["この映像には激しい光の点滅や", "色の急な変化が多く含まれます。", "光に敏感な方はご注意ください。"]):
    center_line(line, body, 470 + i * 88, (255, 255, 255, 255))

if BLEED:
    import numpy as np
    from PIL import ImageFilter
    a = np.asarray(img.getchannel("A"), np.float32) / 255
    # 1) ぼかしてから締め直す：角が丸くなり、線がにじんで少し太る
    soft = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.6)),
                      np.float32) / 255
    t = np.clip((soft - 0.18) / (0.55 - 0.18), 0, 1)
    core = t * t * (3 - 2 * t)
    # 2) 紙に染みたような細かいむら（決まった種のノイズ）
    rng = np.random.default_rng(7)
    grain = np.asarray(Image.fromarray((rng.random((H, W)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                       np.float32) / 255
    core = np.clip(core * (0.82 + 0.36 * grain), 0, 1)
    # 3) まわりにうっすら広がるインクの染み
    halo = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7)),
                      np.float32) / 255 * 0.45
    alpha = np.clip(np.maximum(core, halo), 0, 1)
    rgb = np.asarray(img.convert("RGB"), np.float32)
    rgb = np.where(alpha[..., None] > 0, np.maximum(rgb, 200), 0)  # 白〜薄い灰のインク
    img = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")

img.alpha_composite(title_layer)
img.save(OUT_PNG)

# 画面は固定（寄る動きはなし）。周辺減光とフェードだけ
vf = (f"[0:v][1:v]overlay=0:0,vignette=PI/3.5,"
      f"fade=t=in:st=0:d=0.5,fade=t=out:st={DUR - 0.5}:d=0.5,format=yuv420p[v]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={DUR}",
                "-loop", "1", "-t", str(DUR), "-i", OUT_PNG, "-filter_complex", vf, "-map", "[v]", "-r", str(FPS),
                "-t", str(DUR), "-c:v", "libx264", "-crf", "14", OUT_MP4], check=True)
print("done", OUT_MP4)
