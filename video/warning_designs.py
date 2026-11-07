"""ゆた×目：冒頭7秒の光過敏の注意書き、デザイン違い10案。

どの案も同じ文面（PHOTOSENSITIVITY WARNING＋日本語3行）を読める大きさで載せる。
注意書きなので、点滅・急な明暗の切り替えは入れない（動きはゆっくりしたものだけ）。
作業フォルダ（cwd）にフォントと eye.png を置き、ffmpeg からは相対パスで読む。
"""
import os
import subprocess
import sys

W, H, FPS, DUR = 1920, 816, 24, 7
EN = "PHOTOSENSITIVITY WARNING"
JA = ["この映像には激しい光の点滅や", "色の急な変化が多く含まれます。", "光に敏感な方はご注意ください。"]
FADE = f"fade=t=in:st=0:d=0.5,fade=t=out:st={DUR - 0.5}:d=0.5"


def dt(font, text, size, color, x="(w-tw)/2", y="(h-th)/2", extra=""):
    return f"drawtext=fontfile={font}:text='{text}':fontsize={size}:fontcolor={color}:x={x}:y={y}{extra}"


def body(font, size, color, y0, gap, x="(w-tw)/2", extra=""):
    return ",".join(dt(font, t, size, color, x, f"{y0 + i * gap}", extra) for i, t in enumerate(JA))


def color_src(c):
    return ["-f", "lavfi", "-i", f"color=c={c}:s={W}x{H}:r={FPS}:d={DUR}"]


DESIGNS = {}


def design(name):
    def deco(fn):
        DESIGNS[name] = fn
        return fn
    return deco


@design("01_hazard")
def hazard():
    # 黄色と黒の斜めストライプの枠。ストライプはゆっくり横に流れる
    stripes = (f"geq=lum='if(lt(mod(X+Y+T*40\\,120)\\,60)\\,210\\,15)':cb=128:cr=128,"
               f"format=yuv420p,colorchannelmixer=rr=1:rg=0:rb=0:gr=0.85:gg=0.15:gb=0:br=0:bg=0:bb=0.05")
    g = (f"[0:v]{stripes}[s];[1:v][s]overlay=0:0[bg];"
         f"[bg]drawbox=x=90:y=80:w={W - 180}:h={H - 160}:c=black:t=fill,"
         f"drawbox=x=90:y=80:w={W - 180}:h={H - 160}:c=0xffd400:t=6,"
         + dt("dela.ttf", "▲ CAUTION ▲", 70, "0xffd400", y="140") + ","
         + dt("gothic.ttc", EN, 56, "white", y="250") + ","
         + body("gothic.ttc", 54, "white", 370, 88) + f",{FADE}[v]")
    return color_src("black") + color_src("black"), g


@design("02_eye_glass")
def eye_glass():
    # MOOD-02_1 をぼかして暗くした背景に、半透明のガラス板。ゆっくりズーム
    g = (f"[0:v]scale={W * 1.15:.0f}:-1,zoompan=z='1+0.0006*on':d=1:s={W}x{H}:fps={FPS},"
         f"gblur=sigma=18,eq=brightness=-0.25:saturation=1.3[bg];"
         f"[bg]drawbox=x=360:y=150:w=1200:h=520:c=black@0.55:t=fill,"
         f"drawbox=x=360:y=150:w=1200:h=520:c=0xff7ad9@0.9:t=3,"
         + dt("gothic.ttc", EN, 54, "0xffd6f2", y="210") + ","
         + body("gothic.ttc", 52, "white", 330, 84) + ","
         + dt("dot.ttf", "%{eif\\:7.999-t\\:d}", 44, "0xff7ad9", x="1560-tw-30", y="620") + f",{FADE}[v]")
    return ["-loop", "1", "-t", str(DUR), "-i", "eye.png"], g


@design("03_vhs_blue")
def vhs_blue():
    # ビデオの青画面。走査線と弱いノイズ、右上にタイムコード
    g = (f"[0:v]noise=alls=6:allf=t,drawgrid=w=iw:h=4:t=1:c=black@0.25,"
         + dt("dot.ttf", "■ WARNING ■", 80, "white", y="110") + ","
         + dt("dot.ttf", EN, 54, "white", y="230") + ","
         + body("dot.ttf", 56, "white", 360, 90) + ","
         + dt("dot.ttf", "PLAY", 44, "white", x="90", y="60") + ","
         + dt("dot.ttf", "%{pts\\:hms}", 44, "white", x="w-tw-90", y="60") + f",{FADE}[v]")
    return color_src("0x0b22b8"), g


@design("04_redacted")
def redacted():
    # 白い書類。黒塗りの行と赤い「警告」のはんこ
    g = (f"[0:v]noise=alls=4:allf=t,"
         f"drawbox=x=300:y=60:w=1320:h=700:c=0xf3f0e8:t=fill,"
         + dt("mincho.ttc", "機密文書　第六号", 34, "0x444444", x="360", y="100") + ","
         + "drawbox=x=360:y=160:w=560:h=30:c=black:t=fill,drawbox=x=950:y=160:w=300:h=30:c=black:t=fill,"
         + dt("mincho.ttc", EN, 50, "black", y="240") + ","
         + body("mincho.ttc", 52, "black", 340, 84) + ","
         + "drawbox=x=360:y=620:w=420:h=30:c=black:t=fill,drawbox=x=820:y=620:w=640:h=30:c=black:t=fill,"
         + "drawbox=x=1300:y=80:w=270:h=150:c=0xd11a2a:t=8,"
         + dt("erode.ttf", "警告", 100, "0xd11a2a", x="1322", y="98") + f",{FADE}[v]")
    return color_src("0x1a1a1a"), g


@design("05_terminal")
def terminal():
    # 黒い端末に緑の文字が一字ずつ出る（タイプライター）。カーソルはゆっくり点く
    lines = ["> SYSTEM ALERT / " + EN] + ["> " + t for t in JA]
    parts = []
    t0 = 0.4
    for li, line in enumerate(lines):
        y = 180 + li * 110
        for k in range(1, len(line) + 1):
            start = t0 + k * 0.045
            end = t0 + (k + 1) * 0.045 if k < len(line) else DUR
            parts.append(dt("dot.ttf", line[:k].replace("'", ""), 50, "0x39ff6a", x="160", y=str(y),
                            extra=f":enable='between(t,{start:.3f},{end:.3f})'"))
        t0 += len(line) * 0.045 + 0.25
    g = f"[0:v]drawgrid=w=iw:h=3:t=1:c=black@0.3,{','.join(parts)},{FADE}[v]"
    return color_src("0x050805"), g


@design("06_drip_horror")
def drip_horror():
    # ホラー映画のタイトル風。垂れる明朝の赤い「警告」、ゆっくり寄る
    g = (f"[0:v]"
         + dt("drip.ttf", "警告", 230, "0xb3001b", y="60") + ","
         + dt("gothic.ttc", EN, 46, "0xdddddd", y="360") + ","
         + body("gothic.ttc", 50, "white", 460, 80) + ","
         + f"scale=w='{W}*(1+0.012*t)':h=-2:eval=frame,crop={W}:{H},vignette=PI/3.5,{FADE}[v]")
    return color_src("black"), g


@design("07_pink_kawaii")
def pink_kawaii():
    # パステルピンクに丸い吹き出し。かわいいのに不穏
    g = (f"[0:v]drawbox=x=310:y=110:w=1300:h=600:c=white:t=fill,"
         f"drawbox=x=310:y=110:w=1300:h=600:c=0xff5fa8:t=10,"
         + dt("maru.ttf", "● ちゅうい ●", 64, "0xff5fa8", y="160") + ","
         + dt("maru.ttf", EN, 46, "0x7a2c55", y="265") + ","
         + body("maru.ttf", 54, "0x4a1f38", 360, 86) + ","
         + dt("maru.ttf", "…みてるよ", 36, "0xff9ccc", x="1610-tw-40", y="650") + f",{FADE}[v]")
    return color_src("0xffd6ea"), g


@design("08_countdown")
def countdown():
    # 中央に大きなカウントダウン（輪郭だけ）。注意文は下に
    g = (f"[0:v]"
         + dt("dela.ttf", "%{eif\\:7.999-t\\:d}", 380, "white@0", y="20",
              extra=":borderw=6:bordercolor=0xff2255") + ","
         + dt("gothic.ttc", EN, 48, "0xff2255", y="470") + ","
         + body("gothic.ttc", 46, "white", 560, 70) + f",{FADE}[v]")
    return color_src("black"), g


@design("09_surveillance")
def surveillance():
    # 監視カメラの画面。四隅のブラケット、REC、時刻
    br = []
    for x, y, dx, dy in [(60, 60, 1, 1), (W - 60, 60, -1, 1), (60, H - 60, 1, -1), (W - 60, H - 60, -1, -1)]:
        br.append(f"drawbox=x={min(x, x + dx * 110)}:y={y if dy > 0 else y - 6}:w=110:h=6:c=white:t=fill")
        br.append(f"drawbox=x={x if dx > 0 else x - 6}:y={min(y, y + dy * 110)}:w=6:h=110:c=white:t=fill")
    g = (f"[0:v]noise=alls=10:allf=t,eq=saturation=0,"
         + ",".join(br) + ","
         + dt("dot.ttf", "● REC", 46, "0xff2a2a", x="120", y="100") + ","
         + dt("dot.ttf", "CAM 06  SUBJECT\\: YOU", 40, "white", x="w-tw-120", y="100") + ","
         + dt("dot.ttf", "2026-11-06  %{pts\\:hms}", 40, "white", x="120", y="h-140") + ","
         + dt("gothic.ttc", EN, 52, "white", y="250") + ","
         + body("gothic.ttc", 50, "white", 350, 82) + f",{FADE}[v]")
    return color_src("0x1c1f1c"), g


@design("10_split")
def split():
    # 白と黒の真ん中で割れた画面。左に日本語、右に英語
    g = (f"[0:v]drawbox=x={W // 2}:y=0:w={W // 2}:h={H}:c=white:t=fill,"
         + dt("erode.ttf", "⚠", 160, "0xff2255", x=f"{W // 4}-tw/2", y="90") + ","
         + body("gothic.ttc", 48, "white", 330, 80, x=f"{W // 4}-tw/2") + ","
         + dt("dela.ttf", "PHOTO-", 92, "black", x=f"{W * 3 // 4}-tw/2", y="200") + ","
         + dt("dela.ttf", "SENSITIVITY", 92, "black", x=f"{W * 3 // 4}-tw/2", y="320") + ","
         + dt("dela.ttf", "WARNING", 92, "0xff2255", x=f"{W * 3 // 4}-tw/2", y="440") + ","
         + f"drawbox=x={W // 2 - 3}:y=0:w=6:h={H}:c=0xff2255:t=fill,{FADE}[v]")
    return color_src("black"), g


def main():
    cwd, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in DESIGNS.items():
        inputs, graph = fn()
        out = os.path.join(out_dir, f"WARN-{name}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
                        "-t", str(DUR), "-r", str(FPS), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out],
                       check=True, cwd=cwd)
        print("ok", name)


if __name__ == "__main__":
    main()
