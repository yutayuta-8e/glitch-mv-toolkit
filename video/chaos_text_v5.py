"""ゆた×目：めちゃくちゃ編集の各カットに、大きな文字をたくさん乗せる（v4 に --scale を足した 4K 用、2026-11-07）。

--scale 2 で、文字の大きさ・縁の太さ・アウトラインの線（6→12px）・流れる速さ・震えの幅を 2 倍にする。
乱数の引き方は v4 と同じなので、同じ seed なら言葉・フォント・動き・点滅の選び方は v4 と同じになる。

以下は v4 の説明。

v3 との違い：アウトラインの文字を、本当に線だけ（中が透明、線の太さ 6px）にした。
ffmpeg の drawtext の縁取りは、文字を太らせた形を縁の色で塗りつぶすため、塗りを透明にしても
中まで埋まる。そこでアウトラインの文字だけ PIL で「文字 − 内側に 6px 削った文字」の輪郭を PNG にし、
overlay で同じ位置・動き・点滅に置く（2026-11-06 依頼者の指摘）。

v2 の作業フォルダ（seg0000.mp4…、plan.json、warning.mp4）をそのまま使い、映像は変えずに文字だけ足す。
文字は複数のフォント・塗り／アウトラインのみ・巨大・流れる・震える・点滅をランダムに組み合わせる。
フォントに無い字があると豆腐になるので、言葉ごとに全文字がそのフォントにあるか先に調べる。
ffmpeg はフォントと文字のファイルを相対パスで読むため、出力先の作業フォルダを cwd にして動かす。
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
from scipy.ndimage import minimum_filter

FPS = 24
OUTLINE_PX = 6  # アウトラインの線の太さ（依頼者の選んだ見本 3）。--scale で倍にする
SCALE = 1.0
# 文字の周りに四角い枠が出るので使わない（2026-11-06 依頼者の指摘）：怪文書は1文字ずつ四角い紙に入った字形
SKIP_FONTS = {"kaibunsyo.ttf"}
# 字が黒い棒なので、線だけにすると四角い枠になる：アウトラインにはせず塗りで使う
NO_OUTLINE_FONTS = {"kuronuri-regular.otf"}
BASE_W, BASE_H = 1920, 816
W, H = BASE_W, BASE_H
WARN_SEC = 7

WORDS_JA = [
    "見てるよ", "みつけた", "みてるよ", "目", "眼", "瞳", "視", "覗", "睨", "瞬", "めめめめめ", "目目目目目目",
    "まばたき禁止", "瞳孔ひらく", "まぶたの裏で会おう", "目が合ったね", "ずっといたよ", "うしろ", "もっと見て",
    "見ルナ", "目ヲ閉ジナイデ", "眼球ノ森", "視線過多", "ひとみしり", "めだまやき", "カワイイ監視",
    "見つめ返して", "ないしょの眼", "ゆた見てる", "ぱちぱちぱち", "ぬぽん", "らりるれ眼", "黒目しりとり",
    "目薬がたりない", "一億の目", "あ", "おはよう眼球", "みてみてみて", "眼が溶ける", "ぐるぐる瞳孔",
    "見えてる？", "しーっ", "ここにいるよ", "目隠しごっこ", "まぶた営業中", "ひらけ", "とじるな",
]
WORDS_EN = [
    "EYE", "I SEE YOU", "WATCHING", "DON'T BLINK", "OPEN", "PUPIL.EXE", "LOOK", "MITERUYO", "FOUND YOU",
    "BLINK BLINK", "EYE EYE EYE", "1000000 EYES", "OVERWATCHED", "NO SLEEP", "IRIS", "STARE", "YUTA SEES",
]
COLORS = ["white", "black", "0xff1a6b", "0xff00cc", "0x00ffee", "0xfff200", "0x39ff14", "0xff3300", "0x8a2bff"]

# 文字の多さ：v2 の区間の強さ（同時にかけた効果の数）ごとの、1カットに乗せる文字数の候補
COUNT_BY_POWER = {2: [1, 1, 2], 3: [1, 2, 2], 4: [2, 2, 3], 5: [2, 3, 4]}
# 後半のスパート（曲の 62.4 秒）より前は控えめに：数を減らし、小さく、アウトライン多め（2026-11-06 依頼者の修正）
CALM_UNTIL_FRAME = round(62.4 * FPS)
COUNT_CALM = {2: [0, 1, 1], 3: [1, 1, 2], 4: [1, 2, 2], 5: [2, 2, 3]}


class Coverage:
    """フォントに字があるかを、存在しない字（私用領域）の描画結果と比べて判定する。"""

    def __init__(self, path):
        self.font = ImageFont.truetype(path, 64)
        self.missing = self._raster("")
        # 無い漢字をまとめて同じ四角の字形で描くフォントがある（激筆SFX）。めったに使わない漢字2つが
        # 同じ形に描かれるなら、それを「無い字」の形とみなす
        a, b = self._raster("龘"), self._raster("驫")
        self.placeholder = a if a.any() and np.array_equal(a, b) else None
        self.cache = {}

    def _raster(self, ch):
        img = Image.new("L", (96, 96))
        ImageDraw.Draw(img).text((8, 8), ch, font=self.font, fill=255)
        return np.asarray(img)

    def has(self, ch):
        if ch == " ":
            return True
        if ch not in self.cache:
            r = self._raster(ch)
            self.cache[ch] = (r.any() and not np.array_equal(r, self.missing)
                              and not (self.placeholder is not None and np.array_equal(r, self.placeholder)))
        return self.cache[ch]

    def covers(self, text):
        return all(self.has(c) for c in text if c != "\n")


def pick_text(rng, fonts):
    """フォントと、そのフォントで全字が出る言葉を選ぶ。"""
    for _ in range(30):
        name, cov = rng.choice(fonts)
        word = rng.choice(WORDS_JA + WORDS_EN)
        if rng.random() < 0.2 and len(word) <= 6 and word.isascii() is False:
            word = "\n".join(word)  # 縦書き風
        if cov.covers(word):
            return name, word
    return fonts[0][0], "EYE"


def drawtext(rng, i, k, font, tmp, frames, word, calm=False):
    word_file = f"t{i:04d}_{k}.txt"
    return word_file, _style(rng, font, word_file, frames, word, calm)


def _style(rng, font, word_file, frames, word, calm=False):
    longest = max(len(line) for line in word.split("\n"))
    if longest == 1:
        size = rng.choice([560, 680, 820] if calm else [1000, 1200, 1400])  # 1文字は大きく
    elif longest <= 4:
        size = rng.choice([300, 380, 480] if calm else [480, 640, 820])
    else:
        size = rng.choice([220, 280, 360] if calm else [360, 480, 640])
    size = int(size * SCALE)
    color = rng.choice(COLORS)
    edge = rng.choice(COLORS)
    outline = rng.random() < (0.8 if calm else 0.5)
    if outline:
        fill = f"{color}@0"
        border = f"borderw={int(rng.choice([5, 8, 12] if calm else [8, 14, 20, 28]) * SCALE)}:bordercolor={edge}"
    elif calm:
        fill = f"{color}@{rng.choice([0.55, 0.7])}"
        border = f"borderw={int(rng.choice([0, 4, 8]) * SCALE)}:bordercolor={edge}"
    else:
        fill = color if rng.random() < 0.8 else f"{color}@0.75"
        border = f"borderw={int(rng.choice([0, 4, 10]) * SCALE)}:bordercolor={edge}"
    motion =rng.choice(["center", "center", "random", "scroll", "scroll_rev", "jitter", "fall"])
    speed = int(rng.choice([40, 80, 140]) * SCALE)
    if motion == "center":
        x, y = "(w-tw)/2", "(h-th)/2"
    elif motion == "random":
        x, y = f"{rng.uniform(-0.3, 0.9):.2f}*w", f"{rng.uniform(-0.2, 0.8):.2f}*h"
    elif motion == "scroll":
        x, y = f"w-mod(n*{speed}\\,w+tw)", f"{rng.uniform(0, 0.7):.2f}*h"
    elif motion == "scroll_rev":
        x, y = f"mod(n*{speed}\\,w+tw)-tw", f"{rng.uniform(0, 0.7):.2f}*h"
    elif motion == "jitter":
        x, y = (f"(w-tw)/2+random(1)*{int(120 * SCALE)}-{int(60 * SCALE)}", f"(h-th)/2+random(2)*{int(80 * SCALE)}-{int(40 * SCALE)}")
    else:
        x, y = "(w-tw)/2", f"mod(n*{speed}\\,h+th)-th"
    blink = rng.random() < 0.3
    enable = ":enable='lt(mod(n,2),1)'" if blink else ""
    if frames > 6 and not blink and rng.random() < 0.3:
        a, b = sorted(rng.sample(range(frames), 2))
        enable = f":enable='between(n,{a},{b})'"
    return (f"drawtext=fontfile={font}:textfile=%WORDFILE%:fontsize={size}:fontcolor={fill}:{border}:"
            f"line_spacing=-{size // 6}:x={x}:y={y}{enable}")


def is_outline(filt):
    return re.search(r"fontcolor=[^:]+@0:", filt) is not None


def _overlay_expr(expr):
    """drawtext の式（w,h=画面、tw,th=文字）を overlay の式（W,H=画面、w,h=重ねる画像）に読み替える。"""
    return re.sub(r"\b(tw|th|w|h)\b", lambda m: {"tw": "w", "th": "h", "w": "W", "h": "H"}[m.group(1)], expr)


def outline_overlay(filt, text, png, tmp):
    """drawtext の設定から、線だけの文字の PNG を作り、同じ位置・動き・点滅の overlay の設定を返す。"""
    font = re.search(r"fontfile=(.+?):textfile=", filt).group(1)
    size = int(re.search(r"fontsize=(\d+)", filt).group(1))
    color = re.search(r"bordercolor=([^:]+)", filt).group(1)
    x = re.search(r":x=(.+?):y=", filt).group(1)
    y = re.search(r":y=(.+?)(?=:enable=|$)", filt).group(1)
    en = re.search(r":enable=('[^']*')", filt)
    f = ImageFont.truetype(os.path.join(tmp, font), size)
    l, t, r, b = f.getbbox(text)
    pad = OUTLINE_PX + 2
    m = Image.new("L", (max(1, r - l + 2 * pad), max(1, b - t + 2 * pad)), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), text, font=f, fill=255)
    a = np.asarray(m, np.float32)
    ring = np.clip(a - minimum_filter(a, size=2 * OUTLINE_PX + 1), 0, 255).astype(np.uint8)
    img = Image.new("RGBA", m.size, ImageColor.getrgb(color.replace("0x", "#")) + (0,))
    img.putalpha(Image.fromarray(ring))
    img.save(os.path.join(tmp, png))
    opt = f"overlay=x={_overlay_expr(x)}:y={_overlay_expr(y)}"
    return png, opt + (f":enable={en.group(1)}" if en else "")


def render_warning(tmp):
    """光過敏の注意書き（WARN_SEC 秒）。作業フォルダに warn.ttc（BIZ UDゴシック B）を置いておく。"""
    out = "warning.mp4"
    lines = [
        ("PHOTOSENSITIVITY WARNING", 64, -170),
        ("この映像には激しい光の点滅や", 58, -40),
        ("色の急な変化が多く含まれます。", 58, 40),
        ("光に敏感な方はご注意ください。", 58, 120),
    ]
    draws = ",".join(
        f"drawtext=fontfile=warn.ttc:text='{t}':fontsize={s}:fontcolor=white:x=(w-tw)/2:y=(h-th)/2+{dy}"
        for t, s, dy in lines)
    vf = f"{draws},drawbox=x=(iw-1300)/2:y=(ih-560)/2:w=1300:h=560:c=0xff2255:t=6,fade=t=out:st={WARN_SEC - 0.4}:d=0.4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={WARN_SEC}",
                    "-vf", vf, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out], check=True, cwd=tmp)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2tmp", required=True, help="v2 の作業フォルダ（segNNNN.mp4、plan.json、warning.mp4）")
    ap.add_argument("--fonts", required=True, help="フォントのフォルダ（下の階層の .ttf をすべて使う）")
    ap.add_argument("--extra-fonts", nargs="*", default=[])
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--seed", type=int, default=666)
    ap.add_argument("--limit", type=int, default=None, help="test: only the first N segments")
    ap.add_argument("--preview", action="store_true", help="確認用：カットを速い設定で書き出し、最後の仕上げは作らない")
    ap.add_argument("--scale", type=float, default=1.0, help="1920×816 に対する倍率（2 で 3840×1632）")
    ap.add_argument("--segments-only", action="store_true", help="本番用の画質でカットだけ書き出し、最後の仕上げは作らない（build_v7.sh final 用）")
    a = ap.parse_args()
    global SCALE, W, H, OUTLINE_PX
    SCALE = a.scale
    W, H = int(BASE_W * SCALE), int(BASE_H * SCALE)
    OUTLINE_PX = int(round(6 * SCALE))

    os.makedirs(a.tmp, exist_ok=True)
    rng = random.Random(a.seed)
    fonts = []
    paths = []
    for r, _, fs in os.walk(a.fonts):
        ttf = [f for f in fs if f.lower().endswith(".ttf")]
        otf = [f for f in fs if f.lower().endswith(".otf")]
        # 同じ書体の ttf と otf が両方あるときは ttf だけ、B1 などの別版は1つに絞る
        chosen = ttf[:1] or otf[:1]
        paths += [os.path.join(r, f) for f in chosen if f.lower() not in SKIP_FONTS]
    for j, p in enumerate(sorted(paths) + a.extra_fonts):
        name = f"f{j:02d}{os.path.splitext(p)[1].lower()}"
        shutil.copy(p, os.path.join(a.tmp, name))
        fonts.append((name, Coverage(p)))
    no_outline = {name for name, p in zip([f for f, _ in fonts], sorted(paths) + a.extra_fonts)
                  if os.path.basename(p).lower() in NO_OUTLINE_FONTS}
    with open(os.path.join(a.v2tmp, "plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    if a.limit:
        plan = plan[: a.limit]

    log = []
    segs = [os.path.join(a.tmp, render_warning(a.tmp))]
    for i, seg in enumerate(plan):
        src = os.path.join(a.v2tmp, f"seg{i:04d}.mp4")
        if seg.get("black"):
            segs.append(src)
            continue
        calm = seg["start"] < CALM_UNTIL_FRAME
        count = rng.choice((COUNT_CALM if calm else COUNT_BY_POWER)[len(seg["fx"])])
        if count == 0:
            segs.append(src)
            continue
        chain = []
        overlays = []  # (PNG, overlay の設定)：線だけの文字
        for k in range(count):
            font, word = pick_text(rng, fonts)
            word_file, filt = drawtext(rng, i, k, font, a.tmp, seg["frames"], word, calm)
            if font in no_outline and is_outline(filt):
                # 塗りに戻す（半透明の塗り、縁取りなし）
                filt = re.sub(r"fontcolor=([^:@]+)@0:borderw=\d+", r"fontcolor=\1@0.7:borderw=0", filt)
            if "\n" in word:
                # 縦書き：drawtext は改行を「字が無い」記号として描くことがあるため、1文字ずつ別に描いて縦に積む
                chars = word.split("\n")
                size = int(re.search(r"fontsize=(\d+)", filt).group(1))
                size_v = int(min(size, H * 1.15 / len(chars)))  # 縦の列が画面の高さくらいに収まる大きさ
                filt = filt.replace(f"fontsize={size}", f"fontsize={size_v}", 1)
                step = size_v * 1.05
                y_expr = re.search(r":y=(.+?)(?=:enable=|$)", filt).group(1)
                parts = []
                for j, ch in enumerate(chars):
                    cf = f"{word_file[:-4]}_{j}.txt"
                    with open(os.path.join(a.tmp, cf), "w", encoding="utf-8", newline="\n") as fh:
                        fh.write(ch)
                    one = filt.replace("%WORDFILE%", cf).replace(
                        f":y={y_expr}", f":y=({y_expr})+{(j - (len(chars) - 1) / 2) * step:.0f}", 1)
                    if is_outline(one):
                        overlays.append(outline_overlay(one, ch, f"o{i:04d}_{k}_{j}.png", a.tmp))
                        parts.append(overlays[-1][1])
                    else:
                        chain.append(one)
                        parts.append(one)
                log.append({"seg": i, "font": font, "word": word, "outline_only": is_outline(filt),
                            "filter": " | ".join(parts)})
                continue
            with open(os.path.join(a.tmp, word_file), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(word)
            one = filt.replace("%WORDFILE%", word_file)
            if is_outline(one):
                overlays.append(outline_overlay(one, word, f"o{i:04d}_{k}.png", a.tmp))
                log.append({"seg": i, "font": font, "word": word, "outline_only": True, "filter": overlays[-1][1]})
            else:
                chain.append(one)
                log.append({"seg": i, "font": font, "word": word, "outline_only": False, "filter": one})
        out = f"tseg{i:04d}.mp4"
        graph = f"[0:v]{','.join(chain) if chain else 'null'}[b0]"
        for q, (_, opt) in enumerate(overlays):
            graph += f";[b{q}][{q + 1}:v]{opt}[b{q + 1}]"
        graph += f";[b{len(overlays)}]format=yuv420p[v]"
        inputs = ["-i", src]
        for png, _ in overlays:
            inputs += ["-i", png]
        enc = ["-crf", "20", "-preset", "ultrafast"] if a.preview else ["-crf", "14", "-preset", "veryfast"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
                        "-an", "-c:v", "libx264", *enc, out], check=True, cwd=a.tmp)
        segs.append(os.path.join(a.tmp, out))
        if i % 50 == 0:
            print(f"segment {i + 1}/{len(plan)}", flush=True)
    with open(os.path.join(a.tmp, "text_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"fonts": [f for f, _ in fonts], "font_sources": sorted(paths) + a.extra_fonts, "texts": log},
                  fh, ensure_ascii=False, indent=1)
    with open(os.path.join(a.tmp, "list.txt"), "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{s}'\n" for s in segs)
    if a.preview or a.segments_only:
        print("done (segments only)", "texts", len(log))
        return
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy",
                    "joined.mp4"], check=True, cwd=a.tmp)
    vf = "drawgrid=w=iw:h=4:t=1:c=black@0.35,rgbashift=rh=-4:bh=4,vignette=PI/4,noise=alls=12:allf=t"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(a.tmp, "joined.mp4"), "-i", a.audio,
                    "-vf", vf, "-af", f"adelay={WARN_SEC * 1000}|{WARN_SEC * 1000},apad",
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-shortest", a.out], check=True)
    print("done", a.out, "texts", len(log))


if __name__ == "__main__":
    main()
