"""v4 の終盤スパート用の文字の層（透明 MOV）を作る。

Fable 版 v3 の描画部品（fable_v3/render.py の言葉・フォント・豆腐チェック・text_layer）を借り、
曲の 62.4 秒から 92 秒にかけて文字をだんだん増やし、最後は画面一面を文字で埋める。
出力は ProRes 4444（アルファ付き）。曲の時間で 62.4 秒のコマから始まる。

使い方: python -I spurt_layer_v2.py <fable_v3 フォルダ> <出力.mov> [倍率]

v2（2026-11-07）：倍率（2 で 3840×1632）を足した。大きさ・位置・速さ・揺れを倍率どおりにし、
乱数の引き方は変えないので、同じ配置のまま解像度だけ上がる。
"""
import os
import random
import subprocess
import sys
from multiprocessing import Pool

FABLE = sys.argv[1]
sys.path.insert(0, FABLE)
import render as fr  # noqa: E402  (Fable の描画部品)

from PIL import Image  # noqa: E402

# 怪文書（1文字ずつ四角い紙に入った字形）は文字の周りに四角い枠が出るので使わない（2026-11-06 依頼者の指摘）
for _lst in (fr.JP_HEAVY, fr.JP_ALL, fr.ALL, fr.NUM_FONTS, fr.BRUSH):
    while 'kaibun' in _lst:
        _lst.remove('kaibun')

S = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0  # Windows の子プロセスも同じ引数で読み直す
fr.W, fr.H = int(1920 * S), int(816 * S)  # fr.blit の切り抜きもこの大きさを使う
W, H, FPS = fr.W, fr.H, fr.FPS

# 4K では文字の画像が 4 倍の大きさになるので、描いた文字の使い回し（キャッシュ）を小さく保つ
_orig_text_layer = fr.text_layer


def _text_layer_small_cache(*args, **kw):
    if len(fr._LAYERS) > (600 if S <= 1 else 80):
        fr._LAYERS.clear()
    return _orig_text_layer(*args, **kw)


fr.text_layer = _text_layer_small_cache
F0, F1 = round(62.4 * FPS), round(92.0 * FPS)  # 曲のコマ番号
POOLS = [fr.JP_WORDS, fr.JP_NONSENSE, fr.EN_WORDS, fr.EN_NONSENSE, 'gen', fr.KANJI1]
COLORS = fr.NEON + [(0, 0, 0)]


def progress(n):
    return (n - F0) / (F1 - F0)


def scatter(c, rr, count, big_share):
    for _ in range(count):
        word, fk = fr.pick(rr, POOLS, fr.ALL)
        big = rr.random() < big_share
        size = int((rr.uniform(160, 560) if big else rr.uniform(60, 240)) * S)
        col = rr.choice(COLORS)
        outline = rr.random() < 0.45
        ang = rr.choice([0, 0, 0, rr.uniform(-30, 30), 90, -90, rr.uniform(-180, 180)])
        img = fr.text_layer(word, fk, size, None if outline else col, max(2, size // 16) if outline else rr.choice([0, size // 22]),
                            col if outline else rr.choice(fr.NEON), ang)
        fr.blit_c(c, img, rr.uniform(-80 * S, W + 80 * S), rr.uniform(-60 * S, H + 60 * S))


def marquee(c, rr, n, k):
    word, fk = fr.pick(random.Random(k * 977), POOLS[:4], fr.ALL)
    size = int(random.Random(k * 31).uniform(110, 300) * S)
    col = fr.NEON[k % len(fr.NEON)]
    unit = fr.text_layer(word + '  ', fk, size, col if k % 2 else None, max(3, size // 14), col)
    uw, uh = unit.size
    speed = (60 + 25 * k) * (1 if k % 2 else -1) * S
    y = random.Random(k * 53).uniform(40 * S, H - 40 * S)
    off = (n * speed) % uw
    x = -off - uw
    while x < W + uw:
        fr.blit(c, unit, x, y - uh / 2)
        x += uw


def wall(c, rr, rows, flicker, seed, fill_all=False):
    r0 = random.Random(seed)
    word, _ = fr.pick(r0, POOLS[:4], fr.ALL)
    size = int(H / rows * 1.02)
    y = 0
    for i in range(rows):
        _, fk = fr.pick(r0, [[word]], fr.ALL)
        col = r0.choice(fr.NEON + [(0, 0, 0)])
        outline = (not fill_all) and i % 2 == 1
        unit = fr.text_layer(word + ' ', fk, size, None if outline else col, max(3, size // 14) if outline else 0, col)
        uw, uh = unit.size
        off = (rr.uniform(0, uw))
        x = -off
        while x < W:
            if rr.random() > flicker:
                fr.blit(c, unit, x + rr.uniform(-8, 8) * S, y + rr.uniform(-6, 6) * S)
            x += uw
        y += H / rows


def render_frame(n):
    p = progress(n)
    c = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    period = 3 if p < 0.3 else 2 if p < 0.6 else 1
    rr = random.Random(20261106 + (n // period) * 7919)
    # 1) 流れるテロップ帯：後半ほど本数が増える
    for k in range(int(6 * p ** 3.2)):
        marquee(c, rr, n, k)
    # 2) 文字の壁：終盤（75%）から。最後の約 1.5 秒は塗りつぶしの壁を何枚も重ねて画面を埋める
    if p > 0.75:
        fill_all = p >= 0.95
        layers = 1 if p < 0.88 else 2 if not fill_all else 4
        for L in range(layers):
            rows = rr.choice([4, 5, 6, 7, 8, 10, 12])
            flicker = 0.0 if fill_all else 0.85 - (p - 0.75) * 3.0
            wall(c, rr, rows, flicker, seed=(n // max(1, period)) * 13 + L, fill_all=fill_all)
    # 3) ばらまき：数をゆっくり、終盤で一気に増やす
    count = int(2 + 110 * p ** 3.6)
    scatter(c, rr, count, big_share=0.06 + 0.35 * p ** 3)
    return c


def frame_bytes(n):
    return render_frame(n).tobytes()


def init():
    pass


def main():
    out = sys.argv[2]
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', 'pipe:0', '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16',
           '-vendor', 'apl0', out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = list(range(F0, F1))
    with Pool(10 if S <= 1 else 4) as pool:  # 4K はメモリが足りなくなるので並列を減らす
        for b0 in range(0, len(frames), 40):
            for data in pool.map(frame_bytes, frames[b0:b0 + 40], chunksize=2):
                ff.stdin.write(data)
            print(f'frames {min(b0 + 40, len(frames))}/{len(frames)}', flush=True)
    ff.stdin.close()
    ff.wait()
    print('done', out, 'fallbacks', fr.FALLBACK_COUNT[0])


if __name__ == '__main__':
    main()
