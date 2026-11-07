"""ゆた×目：めちゃくちゃ編集 v2 を、解像度を変えて描き直す版（4K 用、2026-11-07）。

--plan で v2 の plan.json を読むと、カットの並び・効果・速さ・重ねる素材が v2 と同じになる。
--scale 2 で 3840×1632。ピクセルで決めている効果の量（色ずれ・ブロックの大きさ・揺れ・文字）も同じ倍率にする。

以下は v2 の説明。

v1 からの追加：カットをさらに細かく、効果を増やして重ね数も増やす、別の素材との二重露光、
拍ごとの色フラッシュ、一瞬だけ映る文字、走査線、冒頭3秒の光過敏の注意書き。
ffmpeg はフォントを相対パスで読むため、作業フォルダ（--tmp）を cwd にして動かす。
作業フォルダには warn.ttc（注意書き用）と dot.ttf（映り込む文字用）を置いておく。
"""
import argparse
import glob
import json
import os
import random
import subprocess

FPS = 24
BASE_W, BASE_H = 1920, 816
SCALE = 1
W, H = BASE_W, BASE_H
WARN_SEC = 3

# 曲の区間（秒）、1カットのコマ数の候補、同時にかける効果の数、オーバーレイ確率、色フラッシュ確率
SECTIONS = [
    (0.00, 2.83, [34, 34], 2, 0.3, 0.5),
    (2.83, 14.10, [18, 18, 9], 2, 0.4, 0.3),
    (14.10, 35.50, [4, 6, 9, 9], 4, 0.7, 0.6),
    (35.50, 51.00, [18, 9, 9, 4], 3, 0.5, 0.4),
    (51.00, 54.40, [2, 4], 4, 0.8, 0.8),
    (54.40, 58.00, [9, 18], 2, 0.3, 0.3),
    (58.00, 62.40, [2, 3, 4], 4, 0.9, 0.9),
    (62.40, 80.00, [4, 6, 9], 4, 0.7, 0.6),
    (80.00, 92.00, [2, 2, 3, 4], 5, 1.0, 1.0),
    (92.00, 94.32, [56], 0, 0.0, 0.0),
]
FLASH_COLORS = ["white", "black", "0xff00cc", "0x00ffee", "0xffff00", "red"]
TEXTS = ["見てるよ", "みつけた", "みてるよ", "目"]

def make_effects(k):
    """ピクセルで決めている量を k 倍にした効果の一覧。"""
    def px(v):
        return int(round(v * k))
    return {

    "rgb": f"rgbashift=rh=-{px(30)}:bh={px(30)}:rv={px(10)}:bv=-{px(10)}",
    "rgb2": f"rgbashift=gh={px(40)}:bh=-{px(40)}:gv=-{px(12)}",
    "neg": "negate",
    "hue": "hue=h=t*1440:s=2.5",
    "mirror2": "crop=iw/2:ih:0:0,split[ml][mr];[mr]hflip[mrf];[ml][mrf]hstack",
    "mirror4": "crop=iw/2:ih/2:0:0,split[qa][qb];[qb]hflip[qbf];[qa][qbf]hstack,split[qc][qd];[qd]vflip[qdf];[qc][qdf]vstack",
    "grid9": "scale=iw/3:ih/3,split=3[g1][g2][g3];[g1][g2][g3]hstack=3,split=3[h1][h2][h3];[h1][h2][h3]vstack=3",
    "edge": "edgedetect=mode=colormix:high=0.15:low=0.03",
    "poster": "lutrgb=r='bitand(val,192)':g='bitand(val,192)':b='bitand(val,192)'",
    "solar": "lutrgb=r='if(gt(val,128),255-val,val*2)':g='if(gt(val,128),255-val,val*2)':b='if(gt(val,128),255-val,val*2)'",
    "pixel": f"pixelize=w={px(36)}:h={px(36)}",
    "shuffle": f"shufflepixels=w={px(96)}:h={px(96)}:m=block",
    "trail": "lagfun=decay=0.96",
    "echo": "tmix=frames=8",
    "diff": "tblend=all_mode=difference,eq=brightness=0.1:contrast=2.5",
    "xor": "tblend=all_mode=xor",
    "stutter": "loop=loop=6:size=3:start=0",
    "zoom": f"scale=w='{W}*(1+1.6*t)':h=-2:eval=frame,crop={W}:{H}",
    "rotate": "rotate=a='t*9':fillcolor=black",
    "fisheye": "lenscorrection=k1=0.6:k2=0.6",
    "scroll": "scroll=h=0.04:v=0.01",
    "shake": f"pad=iw+{px(160)}:ih+{px(160)}:{px(80)}:{px(80)},crop={W}:{H}:x='{px(80)}+{px(75)}*sin(n*2.9)':y='{px(80)}+{px(75)}*cos(n*4.3)'",
    "strobe": "negate=enable='lt(mod(n,2),1)'",
    "noise": "noise=alls=90:allf=t+u",
    "burn": "eq=saturation=4:contrast=2:brightness=0.05",
    "thermal": "pseudocolor=preset=turbo",
    "swap": "colorchannelmixer=rr=0:rb=1:bb=0:br=1:gg=0.4:gr=0.6",
}


EFFECTS = make_effects(1)
BLEND_MODES = ["difference", "screen", "addition", "xor", "phoenix", "negation", "hardlight"]


def run(cmd, cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd)


def src_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def build_plan(rng, clips, alphas, total_frames):
    plan = []
    f = 0
    for start, end, lens, power, p_ov, p_flash in SECTIONS:
        sec_end = min(round(end * FPS), total_frames)
        while f < sec_end:
            n = min(rng.choice(lens), sec_end - f)
            if power == 0:
                plan.append({"start": f, "frames": n, "black": True})
                f += n
                continue
            plan.append({
                "start": f,
                "frames": n,
                "src": rng.choice(clips),
                "speed": rng.choice([1, 0.5, 2, 3, 4]),
                "reverse": rng.random() < 0.35,
                "fx": rng.sample(list(EFFECTS), power),
                "overlay": rng.choice(alphas) if rng.random() < p_ov else None,
                "blend": ({"src": rng.choice(clips), "mode": rng.choice(BLEND_MODES)}
                          if rng.random() < p_ov * 0.6 else None),
                "flash": rng.choice(FLASH_COLORS) if rng.random() < p_flash else None,
                "text": rng.choice(TEXTS) if rng.random() < p_flash * 0.25 else None,
            })
            f += n
    return plan


def clip_input(src, need, durs, seed):
    dur = durs[src]
    ss = 0 if dur <= need else random.Random(seed).uniform(0, dur - need)
    return ["-stream_loop", "-1", "-ss", f"{ss:.3f}", "-i", src]


def render_segment(i, seg, tmp, durs):
    out = f"seg{i:04d}.mp4"
    n = seg["frames"]
    if seg.get("black"):
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}",
             "-frames:v", str(n), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out], cwd=tmp)
        return out
    need = n / FPS * seg["speed"] + 0.3
    norm = f"fps={FPS},scale={W}:{H}:flags=lanczos,setsar=1"
    chain = [f"trim=duration={need:.3f}", "setpts=PTS-STARTPTS"]
    if seg["reverse"]:
        chain.append("reverse")
    chain += [f"setpts=PTS/{seg['speed']}", norm]
    fx = ",".join(EFFECTS[k] for k in seg["fx"])
    inputs = clip_input(seg["src"], need, durs, i)
    graph = f"[0:v]{','.join(chain)},{fx},{norm}[b]"
    last = "b"
    k = 1
    if seg["blend"]:
        inputs += clip_input(seg["blend"]["src"], n / FPS + 0.3, durs, i + 7)
        graph += (f";[{k}:v]{norm},format=gbrp[x{k}];[{last}]format=gbrp[y{k}];"
                  f"[y{k}][x{k}]blend=all_mode={seg['blend']['mode']},{norm}[bl]")
        last = "bl"
        k += 1
    if seg["overlay"]:
        inputs += ["-stream_loop", "-1", "-i", seg["overlay"]]
        graph += f";[{k}:v]fps={FPS},scale={W}:{H},format=yuva420p[o];[{last}][o]overlay=format=auto[ov]"
        last = "ov"
        k += 1
    if seg["flash"]:
        graph += f";[{last}]drawbox=c={seg['flash']}:t=fill:enable='lt(n,1)'[fl]"
        last = "fl"
    if seg["text"]:
        graph += (f";[{last}]drawtext=fontfile=dot.ttf:text='{seg['text']}':fontsize={int(260 * SCALE)}:fontcolor=white:"
                  f"borderw={int(6 * SCALE)}:bordercolor=black:x=(w-tw)/2:y=(h-th)/2:enable='between(n,1,2)'[tx]")
        last = "tx"
    graph += f";[{last}]format=yuv420p[v]"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
         "-frames:v", str(n), "-an", "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", out], cwd=tmp)
    return out


def render_warning(tmp):
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
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={WARN_SEC}",
         "-vf", vf, "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out], cwd=tmp)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--seed", type=int, default=66)
    ap.add_argument("--only", nargs="*", help="test: render only these effect names")
    ap.add_argument("--plan", help="既存の plan.json を使う（並びを v2 と同じにする）")
    ap.add_argument("--scale", type=float, default=1.0, help="1920×816 に対する倍率（2 で 3840×1632）")
    ap.add_argument("--limit", type=int, default=None, help="test: 最初の N カットだけ")
    ap.add_argument("--segments-only", action="store_true", help="カット（seg*.mp4、list.txt）まで作って終わる。仕上げは組み立てでかける")
    a = ap.parse_args()
    global SCALE, W, H, EFFECTS
    SCALE = a.scale
    W, H = int(BASE_W * SCALE), int(BASE_H * SCALE)
    EFFECTS = make_effects(SCALE)

    rng = random.Random(a.seed)
    clips = sorted(glob.glob(f"{a.cuts}/*.mp4"))
    alphas = sorted(glob.glob(f"{a.cuts}/*_alpha.mov"))
    durs = {p: src_duration(p) for p in clips}

    if a.only is not None:
        for i, name in enumerate(a.only or EFFECTS):
            seg = {"frames": 9, "src": clips[i % len(clips)], "speed": 2, "reverse": i % 2 == 0, "fx": [name],
                   "overlay": alphas[0] if i == 0 else None,
                   "blend": {"src": clips[3], "mode": BLEND_MODES[i % len(BLEND_MODES)]} if i % 3 == 0 else None,
                   "flash": FLASH_COLORS[i % len(FLASH_COLORS)], "text": TEXTS[i % len(TEXTS)]}
            try:
                render_segment(i, seg, a.tmp, durs)
                print("OK ", name)
            except subprocess.CalledProcessError:
                print("ERR", name)
        render_warning(a.tmp)
        print("warning OK")
        return

    if a.plan:
        with open(a.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
        durs.update({s["blend"]["src"]: src_duration(s["blend"]["src"]) for s in plan if s.get("blend")})
        durs.update({s["src"]: src_duration(s["src"]) for s in plan if s.get("src") and s["src"] not in durs})
    else:
        total = round(src_duration(a.audio) * FPS)
        plan = build_plan(rng, clips, alphas, total)
    if a.limit:
        plan = plan[: a.limit]
    with open(f"{a.tmp}/plan.json", "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    segs = [render_warning(a.tmp)]
    for i, seg in enumerate(plan):
        segs.append(render_segment(i, seg, a.tmp, durs))
        if i % 50 == 0:
            print(f"segment {i + 1}/{len(plan)}", flush=True)
    with open(f"{a.tmp}/list.txt", "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{s}'\n" for s in segs)
    if a.segments_only:
        print("done (segments only)", "segments", len(plan))
        return
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"],
        cwd=a.tmp)
    # 全体の仕上げ：走査線、色ずれ、周辺減光、粒子。音は注意書きの3秒ぶん遅らせる
    vf = ("drawgrid=w=iw:h=4:t=1:c=black@0.35,rgbashift=rh=-4:bh=4,vignette=PI/4,noise=alls=12:allf=t")
    run(["ffmpeg", "-v", "error", "-y", "-i", f"{a.tmp}/joined.mp4", "-i", a.audio,
         "-vf", vf, "-af", f"adelay={WARN_SEC * 1000}|{WARN_SEC * 1000},apad",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "320k", "-shortest", a.out])
    print("done", a.out, "segments", len(plan))


if __name__ == "__main__":
    main()
