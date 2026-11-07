"""yuta-eye 見てるよ chaos-edit v3 (Fable version): text layer renderer.

Renders a transparent RGBA text layer per frame (PIL) on top of the v2 picture,
driven by chaos_v2/plan.json (segment timing + intensity + flash colour).

Usage:
  python -I render.py preview            -> contact sheet of 1 fps sampled frames (overlay on base video frames)
  python -I render.py pipe               -> composite full video to comp.mp4 (text over base.mp4)
  python -I render.py frame N out.png    -> single frame overlay (text only, on grey)
"""
import json
import math
import os
import random
import subprocess
import sys
import time
from multiprocessing import Pool

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glyphs import has_glyphs, missing  # noqa: E402

W, H = 1920, 816
FPS = 24
TOTAL = 2264
SEED = 20261106
# カオス編集の plan.json（Fable 版の全編描画で使う。スパートの層だけなら無くてよい）と、フォントのフォルダ。
# 環境変数で場所を変えられる（GLITCH_MV_PLAN、GLITCH_MV_FABLE_FONTS）。
_PLAN_PATH = os.environ.get('GLITCH_MV_PLAN', os.path.join(HERE, '..', 'chaos_v2', 'plan.json'))
PLAN = json.load(open(_PLAN_PATH, encoding='utf-8')) if os.path.exists(_PLAN_PATH) else []
FD = os.environ.get('GLITCH_MV_FABLE_FONTS', os.path.join(HERE, 'fonts2'))

# ---------------------------------------------------------------- fonts
# iifont (いいフォント) set + three local fonts allowed for Latin-only words.
F = {k: os.path.join(FD, v) for k, v in {
    'haretsu': 'HaretsuNoMincho.ttf',        # 破裂ノ明朝
    'degobo': 'degobogothic.ttf',            # でごぼゴシック
    'comic': 'g_comichorrorR_freeR.ttf',     # g_コミックホラー恐怖 (教育漢字のみ)
    'kuronuri': 'kuronuri-Regular.otf',      # クロヌリフォント (かなのみ, 黒塗り風)
    'zomzi': 'zomzi.TTF',                    # 暗黒ゾン字
    'onryou': 'onryou.TTF',                  # 怨霊フォント
    'kurobara': 'kurobara-cinderella.ttf',   # 黒薔薇シンデレラ
    'shitataru': 'ShitataruMinchoShogo-EB.ttf',  # したたる明朝初号
    'shinsyoku': 'ShinsyokuMincho-Regular.ttf',  # 侵食明朝
    'fear': 'FeelingOfFear.ttf',             # フィーリングオブフィア
    'dust': 'CHI_DustDevil_M-Heavy.ttf',     # ダストデビルM
    'kaibun': 'Kaibunsyo.ttf',               # 怪聞書 (ransom-note style)
    'kakinaguri': 'Kakinaguri-Regular.ttf',  # カキナグリ
    'gekifude': 'GEKIFUDE-SFX-Regular.ttf',  # 激筆SFX (かな・英字のみ)
    'dela': 'DelaGothicOne-Regular.ttf', 'dot': 'DotGothic16-Regular.ttf', 'zenmaru': 'ZenMaruGothic-Black.ttf',
}.items()}
LOCAL = ['dela', 'dot', 'zenmaru']                  # Latin-only words only
JP_HEAVY = ['haretsu', 'degobo', 'zomzi', 'kurobara', 'shitataru', 'dust', 'kaibun', 'gekifude']
BRUSH = ['onryou', 'haretsu', 'zomzi', 'comic', 'shinsyoku', 'fear', 'kakinaguri', 'gekifude']
JP_ALL = ['haretsu', 'degobo', 'comic', 'zomzi', 'onryou', 'kurobara', 'shitataru', 'shinsyoku', 'fear', 'dust',
          'kaibun', 'kakinaguri', 'gekifude']
ALL = JP_ALL + LOCAL
NUM_FONTS = ['dela', 'dot', 'zenmaru', 'degobo', 'haretsu', 'zomzi', 'onryou', 'kurobara', 'shitataru', 'dust', 'kaibun', 'gekifude', 'fear']
FALLBACK = 'degobo'


def is_latin(word):
    return all(ord(c) < 0x3000 or c.isspace() for c in word)


def allowed(word, fonts):
    """Local (Google) fonts only for Latin-only words; everything must pass the glyph check."""
    return [f for f in fonts if (f not in LOCAL or is_latin(word)) and has_glyphs(F[f], word)]

# ---------------------------------------------------------------- words
JP_WORDS = ['見てるよ', 'みつけた', '目', '眼', '瞳', '視線', '凝視', '監視中', '瞬き禁止', '覗く', '見ないで', '見ろ', '後ろ',
            '誰？', 'おまえ', '全部知ってる', '逃げても', '白目', '黒目', '瞳孔', '網膜', '虹彩', '瞼', '鏡', '夢', '闇', '嘘',
            '開眼', '君', '貴方', '顔', '光', 'ずっと', 'ほら', 'ね', 'みてる', 'みえてる', 'まばたき', 'めだま', '瞬', '瞥',
            '見た', '見えた', '隠れても', 'そこ', 'ここ', '視', '監']
JP_NONSENSE = ['ミテルヨ', 'ギョロギョロ', 'ジロジロ', 'ジーッ', 'パチパチ', 'チカチカ', 'グルグル', 'ぬるぬる', 'メメメメメ',
               '目目目目目', 'ァァァァ', 'ンンンン', 'ヴェエエ', 'ギョロン', 'オクルス', 'メダマ', 'ミラレテル', 'バレテル',
               'ミタ？', 'ミタネ', 'ゾロゾロ', 'ピカーン', 'ギラギラ', 'ドロドロ', 'ぱちくり', 'めめめ', '目ガ目ガ', 'ミミミミ',
               'ヨヨヨ', 'ギョッ', 'ジッ', 'ぬっ', 'のぞく', 'ぎょろり', 'メヂカラ', 'ミエミエ', 'ウラメ', 'ギョロメ',
               'ピカピカ', 'ジロリ', 'キョロキョロ', 'ボーッ', 'ヌルッ', 'ズブズブ', 'ガン見', 'まばたき禁止']
EN_WORDS = ['WATCHING', 'I SEE YOU', 'FOUND YOU', "DON'T BLINK", 'EYE', 'EYES', 'BLINK', 'STARE', 'GAZE', 'LOOK',
            'SEEN', 'OBSERVED', 'PUPIL', 'RETINA', 'IRIS', 'SCLERA', 'OPTIC', 'VOYEUR', 'PEEP', 'WATCH ME',
            'LOOK AT ME', 'BEHIND YOU', 'NOWHERE TO HIDE', 'REC', 'LIVE', 'WATCHER', 'EYEBALL', 'MITERUYO',
            'MITSUKETA', 'NO ESCAPE', '1000 EYES']
EN_NONSENSE = ['GLORBO', 'EYEYEYEYE', 'OKULOKULO', 'BLINKBLINK', 'ZZZT', 'OPTIKKK', 'MIMIMIMI', 'OGLE', 'OOOOO',
               'EEEEEE', 'SEEEEEN', 'LQQK', 'O_O', '@_@', '0_0', 'WATCH3R', 'EYEBALLZ', 'BLINK404', 'GOGGLE', 'OCULOX',
               'VIZZZ', 'PEEPEEP', 'ZOOMZOOM', 'ERR_EYE', 'IRIZZ', 'GLANCEEE', 'OPTOPTOPT', 'BLNK', 'EYEYE', 'SEE SEE SEE',
               'OO OO OO', 'LOOKLOOKLOOK', 'OBSERV3D', 'PUPILPUPIL']
KANJI1 = ['目', '眼', '瞳', '見', '視', '覗', '瞼', '瞥', '瞬', '監', '凝']
KANA_POOL = 'ギョロジッパチメミテルヨヴァンヌルズブゾロキラ'
LATIN_POOL = 'EYEOBLNKZOOSEEW'

NEON = [(255, 255, 255), (255, 0, 204), (0, 255, 238), (255, 255, 0), (255, 40, 40), (120, 255, 0)]
FLASH_RGB = {'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 40, 40), '0xff00cc': (255, 0, 204),
             '0xffff00': (255, 255, 0), '0x00ffee': (0, 255, 238)}


def section(n):
    s = n / FPS
    if s < 35.5:
        return 'A'
    if s < 51:
        return 'B'
    if s < 54:
        return 'C'
    if s < 58:
        return 'D'
    if s < 62:
        return 'C'
    if s < 80:
        return 'E'
    if s < 92:
        return 'F'
    return 'G'


# ---------------------------------------------------------------- text rendering
_FONTS = {}
_LAYERS = {}
FALLBACK_COUNT = [0]


def font(fkey, size):
    size = max(8, int(size))
    k = (fkey, size)
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(F[fkey], size, layout_engine=ImageFont.Layout.BASIC)
    return _FONTS[k]


def safe_font(fkey, text):
    """Guarantee every glyph exists; swap font or drop chars rather than ship tofu."""
    if has_glyphs(F[fkey], text) and (fkey not in LOCAL or is_latin(text)):
        return fkey, text
    FALLBACK_COUNT[0] += 1
    print('FALLBACK', fkey, repr(text), file=sys.stderr)
    if has_glyphs(F[FALLBACK], text):
        return FALLBACK, text
    bad = set(missing(F[FALLBACK], text))
    return FALLBACK, ''.join(c for c in text if c not in bad) or '目'


def text_layer(text, fkey, size, fill=None, sw=0, scol=(255, 255, 255), angle=0, mirror=False, alpha=255):
    key = (text, fkey, int(size), fill, sw, scol, angle, mirror, alpha)
    if key in _LAYERS:
        return _LAYERS[key]
    fkey, text = safe_font(fkey, text)
    f = font(fkey, size)
    l, t, r, b = f.getbbox(text, stroke_width=sw)
    pad = 6
    wd, hd = max(1, r - l + 2 * pad), max(1, b - t + 2 * pad)
    img = Image.new('RGBA', (wd, hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pos = (pad - l, pad - t)
    if sw > 0:
        sc = tuple(scol) + (255,)
        d.text(pos, text, font=f, fill=sc, stroke_width=sw, stroke_fill=sc)
        if fill is None:
            inner = Image.new('L', (wd, hd), 0)
            ImageDraw.Draw(inner).text(pos, text, font=f, fill=255)
            img.putalpha(ImageChops.subtract(img.getchannel('A'), inner))
        else:
            d.text(pos, text, font=f, fill=tuple(fill) + (255,))
    else:
        d.text(pos, text, font=f, fill=tuple(fill or (255, 255, 255)) + (255,))
    if alpha < 255:
        img.putalpha(img.getchannel('A').point(lambda v: v * alpha // 255))
    if mirror:
        img = ImageOps.mirror(img)
    if angle:
        img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
    if len(_LAYERS) > 600:
        _LAYERS.clear()
    _LAYERS[key] = img
    return img


def blit(canvas, img, x, y):
    iw, ih = img.size
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + iw, W), min(y + ih, H)
    if x1 <= x0 or y1 <= y0:
        return
    part = img.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    canvas.alpha_composite(part, (x0, y0))


def blit_c(canvas, img, cx, cy):
    blit(canvas, img, cx - img.size[0] / 2, cy - img.size[1] / 2)


def units(word):
    return sum(0.62 if ord(c) < 0x3000 else 1.0 for c in word) or 1


def rnd_nonsense(r):
    if r.random() < 0.5:
        return ''.join(r.choice(KANA_POOL) for _ in range(r.randint(3, 6)))
    return ''.join(r.choice(LATIN_POOL) for _ in range(r.randint(3, 8)))


def pick(r, pools, fonts):
    """Pick (word, font) with full glyph coverage."""
    for _ in range(40):
        pool = r.choice(pools)
        word = rnd_nonsense(r) if pool == 'gen' else r.choice(pool)
        ok = allowed(word, fonts)
        if ok:
            return word, r.choice(ok)
    return '目', 'degobo'


def color_pair(r, flash):
    base = FLASH_RGB.get(flash) if flash else None
    c1 = r.choice(NEON)
    if base and r.random() < 0.6:
        c2 = (0, 0, 0) if base == (255, 255, 255) else (255, 255, 255)
    else:
        c2 = r.choice(NEON + [(0, 0, 0)])
    return c1, c2


# ---------------------------------------------------------------- program (per segment style specs)
def build_program():
    prog = []
    for i, seg in enumerate(PLAN):
        r = random.Random(SEED * 7919 + i)
        n0, fr = seg['start'], seg['frames']
        sec = section(n0)
        inten = len(seg.get('fx', []))
        flash = seg.get('flash')
        styles = []
        if seg.get('black'):
            styles.append({'k': 'ending'})
            prog.append(styles)
            continue
        if sec == 'A':
            count = {0: 1, 2: 1, 3: 2, 4: 2, 5: 3}[inten]
            menu = ['giant', 'giant', 'marquee', 'wall', 'scatter', 'stack', 'counter', 'glitchword', 'tate']
            if r.random() < 0.7:
                styles.append({'k': 'hud'})
        elif sec == 'B':
            count = 1
            menu = ['giant_dark', 'tate', 'whisper', 'giant_dark']
        elif sec == 'C':
            count = r.randint(3, 4)
            menu = ['giant', 'wall', 'scatter', 'marquee', 'stack', 'counter']
            styles.append({'k': 'hud'})
        elif sec == 'D':
            count = 1
            menu = ['giant_dark', 'whisper', 'tate']
        elif sec == 'E':
            count = {0: 2, 2: 2, 3: 2, 4: 3, 5: 4}[inten]
            menu = ['giant', 'giant', 'marquee', 'wall', 'scatter', 'stack', 'counter', 'glitchword', 'tate', 'marquee']
            if r.random() < 0.6:
                styles.append({'k': 'hud'})
        else:  # F climax
            count = r.randint(3, 4)
            menu = ['giant', 'scatter', 'wall', 'marquee', 'stack', 'counter', 'giant', 'glitchword']
            styles.append({'k': 'hud'})
        if flash and sec in 'ACEF':
            styles.append({'k': 'blink', 'flash': flash})
        chosen = []
        for _ in range(count):
            k = r.choice(menu)
            if k in chosen and k not in ('giant', 'scatter', 'marquee'):
                k = r.choice(menu)
            chosen.append(k)
        for k in chosen:
            styles.append(make_style(r, k, seg, sec, inten, flash, fr))
        prog.append(styles)
    return prog


def make_style(r, k, seg, sec, inten, flash, fr):
    s = {'k': k}
    v2text = seg.get('text')
    if k in ('giant', 'giant_dark'):
        if v2text and r.random() < 0.4:
            word = v2text
            fk = r.choice(allowed(word, JP_HEAVY + BRUSH) or ['degobo'])
        else:
            pools = [KANJI1, KANJI1, JP_WORDS, JP_NONSENSE, EN_WORDS, EN_NONSENSE] if k == 'giant' else [KANJI1, JP_WORDS, JP_WORDS, EN_WORDS]
            word, fk = pick(r, pools, ALL if k == 'giant' else JP_HEAVY + BRUSH)
        u = units(word)
        target_w = W * r.uniform(0.9, 1.7)
        size = min(1700, target_w / u)
        if u <= 1.1:
            size = H * r.uniform(0.9, 1.6)
        s.update(word=word, font=fk, size=int(size), sw=int(r.uniform(0.012, 0.03) * size) + 4,
                 outline=r.random() < (0.75 if k == 'giant' else 0.6), angle=r.choice([0, 0, 0, r.uniform(-14, 14), 90, -90]) if k == 'giant' else r.uniform(-6, 6),
                 cx=W / 2 + r.uniform(-250, 250), cy=H / 2 + r.uniform(-120, 120),
                 motion=r.choice(['zoom', 'slam', 'drift', 'shake', 'zoom', 'none']) if k == 'giant' else r.choice(['zoom', 'drift']),
                 colors=color_pair(r, flash), flip=r.choice([1, 1, 2, 3, 0]) if k == 'giant' else 0,
                 mirror=r.random() < 0.25, alpha=255 if k == 'giant' else int(r.uniform(110, 190)),
                 drift=r.uniform(-18, 18))
    elif k == 'marquee':
        if r.random() < 0.15:  # redacted-looking kana band (クロヌリ: kana drawn as black-out bars, by design)
            word, fk = pick(r, [['ミテルヨ', 'みつけた', 'ギョロギョロ', 'バレテル', 'ミラレテル']], ['kuronuri'])
        else:
            word, fk = pick(r, [JP_WORDS, JP_NONSENSE, EN_WORDS, EN_NONSENSE, 'gen'], ALL)
        s.update(word=word, font=fk, size=int(r.uniform(110, 330)), outline=r.random() < 0.5,
                 color=r.choice(NEON), sw=r.randint(4, 14), speed=r.choice([-1, 1]) * r.uniform(40, 150),
                 y=r.uniform(60, H - 60), angle=r.choice([0, 0, r.uniform(-10, 10), r.uniform(80, 100)]),
                 sep=r.choice([x for x in ['  ', ' ● ', ' ◆ ', ' ▲ ', ' / ', ' !! ', ' ?? ', '　'] if has_glyphs(F[fk], word + x)] or ['  ']),
                 phase=r.uniform(0, 4000))
    elif k == 'wall':
        word, fk = pick(r, [JP_WORDS, JP_NONSENSE, EN_WORDS, EN_NONSENSE], ALL)
        rows = r.randint(3, 6)
        fonts = []
        for _ in range(rows):
            w2, f2 = pick(r, [[word]], ALL)
            fonts.append(f2)
        s.update(word=word, rows=rows, fonts=fonts, color=r.choice(NEON), color2=r.choice(NEON),
                 jitter=r.uniform(0, 30), flicker=r.uniform(0.1, 0.6), scroll=r.uniform(-30, 30), alt=r.random() < 0.7)
    elif k == 'scatter':
        s.update(count=r.randint(8, 20) if sec != 'F' else r.randint(12, 24),
                 period=1 if sec == 'F' or inten >= 5 else r.choice([1, 2, 3, 4]),
                 big=r.random() < 0.4)
    elif k == 'stack':
        word, fk = pick(r, [JP_WORDS, JP_NONSENSE, EN_WORDS, EN_NONSENSE], ALL)
        lines = r.randint(4, 7)
        fonts = [pick(r, [[word]], ALL)[1] for _ in range(lines)]
        s.update(word=word, lines=lines, fonts=fonts, color=r.choice(NEON), color2=r.choice(NEON + [(0, 0, 0)]),
                 speed=r.uniform(6, 40), sw=r.randint(4, 12))
    elif k == 'counter':
        s.update(font=r.choice(NUM_FONTS),
                 digits=r.randint(3, 6), size=int(r.uniform(420, 900)), outline=r.random() < 0.5,
                 color=r.choice(NEON), mode=r.choice(['random', 'count', 'count']), x=r.uniform(0.25, 0.75), y=r.uniform(0.3, 0.7),
                 sw=r.randint(6, 20), prefix=r.choice(['', '', '#', 'NO.', 'ID ', 'EYE ']))
    elif k == 'glitchword':
        word, fk = pick(r, [JP_WORDS, JP_NONSENSE, EN_WORDS], JP_HEAVY + ['dot', 'onryou'])
        s.update(word=word, font=fk, size=int(min(620, W * 0.9 / units(word))), color=r.choice(NEON),
                 outline=r.random() < 0.4, sw=r.randint(6, 16), y=r.uniform(0.3, 0.7))
    elif k == 'tate':
        word, fk = pick(r, [JP_WORDS, JP_NONSENSE], BRUSH + ['degobo', 'kurobara', 'shitataru', 'kaibun'])
        s.update(word=word, font=fk, size=int(r.uniform(90, 200)), color=r.choice([(255, 255, 255), (255, 40, 40), (255, 255, 255), r.choice(NEON)]),
                 cols=r.randint(1, 3), speed=r.uniform(-14, 14), outline=r.random() < 0.4, sw=r.randint(3, 8),
                 xs=[r.uniform(0.04, 0.96) for _ in range(3)], alpha=255 if sec in 'ACEF' else int(r.uniform(120, 200)))
    elif k == 'whisper':
        word, fk = pick(r, [JP_WORDS, JP_NONSENSE, EN_WORDS], ['onryou', 'haretsu', 'comic', 'kurobara', 'shinsyoku', 'fear', 'kakinaguri', 'dot'])
        s.update(word=word, font=fk, size=int(r.uniform(40, 110)), x=r.uniform(0.05, 0.9), y=r.uniform(0.08, 0.92),
                 alpha=int(r.uniform(120, 220)), color=r.choice([(255, 255, 255), (255, 40, 40), (200, 200, 255)]),
                 appear=r.randint(0, max(0, fr // 3)), n=r.randint(1, 3))
    return s


# ---------------------------------------------------------------- style drawing
def draw_giant(c, s, t, n, seg, r):
    fr = seg['frames']
    col = s['colors'][0]
    if s['flip'] and t < 8:
        col = s['colors'][(t // s['flip']) % 2]
    elif s['flip'] == 0 and s['motion'] == 'shake':
        col = s['colors'][(t // 3) % 2]
    scale = 1.0
    dx = dy = 0
    m = s['motion']
    if m == 'zoom':
        scale = 1.0 + 0.35 * t / max(1, fr)
    elif m == 'slam':
        scale = 1.0 + max(0, 0.9 - 0.3 * t)
    elif m == 'drift':
        dx = s['drift'] * t
    elif m == 'shake':
        dx, dy = r.uniform(-25, 25), r.uniform(-25, 25)
    img = text_layer(s['word'], s['font'], s['size'], None if s['outline'] else col, s['sw'], col, s['angle'], False, s['alpha'])
    if scale != 1.0:
        img = img.resize((max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))), Image.BILINEAR)
    blit_c(c, img, s['cx'] + dx, s['cy'] + dy)
    if s['mirror']:
        col2 = s['colors'][1]
        img2 = text_layer(s['word'], s['font'], s['size'], None, s['sw'], col2, -s['angle'], True, 170)
        blit_c(c, img2, s['cx'] + dx + 40, s['cy'] + dy + 30)


def draw_marquee(c, s, t, n, seg, r):
    unit = text_layer(s['word'] + s['sep'], s['font'], s['size'], None if s['outline'] else s['color'], s['sw'], s['color'])
    uw, uh = unit.size
    period = uw
    off = (s['phase'] + t * s['speed']) % period
    ang = s['angle']
    if ang == 0:
        x = -off - period
        while x < W + period:
            blit(c, unit, x, s['y'] - uh / 2)
            x += period
    else:
        L = int(math.hypot(W, H)) + 2 * period
        strip = Image.new('RGBA', (L, uh), (0, 0, 0, 0))
        x = -off
        while x < L:
            strip.alpha_composite(unit, (int(x), 0)) if 0 <= x < L - uw else blit_any(strip, unit, x, 0, L, uh)
            x += period
        strip = strip.rotate(ang, expand=True, resample=Image.BILINEAR)
        blit_c(c, strip, W / 2 if abs(ang) > 45 else W / 2, s['y'] if abs(ang) < 45 else H / 2)


def blit_any(dst, img, x, y, dw, dh):
    iw, ih = img.size
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + iw, dw), min(y + ih, dh)
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(img.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def draw_wall(c, s, t, n, seg, r):
    rows = s['rows']
    size = int(H / rows * 0.95)
    y = 0
    for i in range(rows):
        fk = s['fonts'][i]
        outline = s['alt'] and i % 2 == 1
        col = s['color'] if i % 2 == 0 else s['color2']
        unit = text_layer(s['word'] + '  ', fk, size, None if outline else col, max(3, size // 14) if outline else 0, col)
        uw, uh = unit.size
        off = (s['scroll'] * t * (1 if i % 2 == 0 else -1) + i * uw / 3) % uw
        jx, jy = r.uniform(-s['jitter'], s['jitter']), r.uniform(-s['jitter'], s['jitter'])
        x = -off - uw
        while x < W + uw:
            if r.random() > s['flicker']:
                blit(c, unit, x + jx, y + jy)
            x += uw
        y += H / rows


def draw_scatter(c, s, t, n, seg, r):
    rr = random.Random(SEED + seg['start'] * 31 + (t // s['period']) * 7 + 11)
    for i in range(s['count']):
        word, fk = pick(rr, [JP_WORDS, JP_NONSENSE, EN_WORDS, EN_NONSENSE, 'gen', KANJI1], ALL)
        size = int(rr.uniform(70, 260)) if not s['big'] else int(rr.uniform(120, 520))
        col = rr.choice(NEON + [(0, 0, 0)])
        outline = rr.random() < 0.5
        ang = rr.choice([0, 0, rr.uniform(-35, 35), 90, -90, rr.uniform(-180, 180)])
        img = text_layer(word, fk, size, None if outline else col, max(2, size // 16) if outline else rr.choice([0, 0, size // 20]), col if outline else rr.choice(NEON), ang)
        blit_c(c, img, rr.uniform(-60, W + 60), rr.uniform(-40, H + 40))


def draw_stack(c, s, t, n, seg, r):
    lines = s['lines']
    size = int(H / lines * 1.25)
    for i in range(lines):
        fk = s['fonts'][i]
        outline = i % 2 == 1
        col = s['color'] if i % 2 == 0 else s['color2']
        img = text_layer(s['word'], fk, size, None if outline else col, s['sw'] if outline else 0, col)
        dx = s['speed'] * t * (1 if i % 2 == 0 else -1)
        blit_c(c, img, W / 2 + dx, (i + 0.5) * H / lines)


def draw_counter(c, s, t, n, seg, r):
    rr = random.Random(SEED + n * 3)
    if s['mode'] == 'random':
        num = ''.join(rr.choice('0123456789') for _ in range(s['digits']))
    else:
        num = str((n * 37 + seg['start']) % (10 ** s['digits'])).zfill(s['digits'])
    txt = s['prefix'] + num
    img = text_layer(txt, s['font'], s['size'], None if s['outline'] else s['color'], s['sw'] if s['outline'] else 0, s['color'])
    blit_c(c, img, s['x'] * W, s['y'] * H)


def draw_glitchword(c, s, t, n, seg, r):
    fr = seg['frames']
    word = s['word']
    rr = random.Random(SEED + n)
    resolved = int(len(word) * min(1.0, t / max(1, fr * 0.7)) + 0.5)
    out = []
    for i, ch in enumerate(word):
        if i < resolved or rr.random() < 0.2:
            out.append(ch)
        else:
            out.append(rr.choice(KANA_POOL if ord(ch) >= 0x3000 else LATIN_POOL))
    txt = ''.join(out)
    img = text_layer(txt, s['font'], s['size'], None if s['outline'] else s['color'], s['sw'], s['color'])
    blit_c(c, img, W / 2 + rr.uniform(-12, 12), s['y'] * H)


def draw_tate(c, s, t, n, seg, r):
    word = s['word']
    size = s['size']
    for ci in range(s['cols']):
        x = s['xs'][ci] * W
        col_h = len(word) * size * 1.05
        off = (t * s['speed'] * (1 if ci % 2 == 0 else -1)) % col_h
        y = -col_h + off
        while y < H + col_h:
            for j, ch in enumerate(word):
                img = text_layer(ch, s['font'], size, None if s['outline'] else s['color'], s['sw'] if s['outline'] else 0, s['color'], 0, False, s['alpha'])
                blit_c(c, img, x, y + j * size * 1.05)
            y += col_h


def draw_whisper(c, s, t, n, seg, r):
    if t < s['appear']:
        return
    a = min(1.0, (t - s['appear']) / 6.0)
    img = text_layer(s['word'], s['font'], s['size'], s['color'], 0, s['color'], 0, False, int(s['alpha'] * a))
    for i in range(s['n']):
        blit_c(c, img, s['x'] * W + i * 37, s['y'] * H + i * 31)


HUD_LINES = ['TRACKING', 'LOCKED', '視線追跡中', '瞬き検出', 'SUBJECT: YOU', 'NO BLINK DETECTED', 'ANALYZING', '監視中',
             '逃げられない', 'DISTANCE 0.00m', 'EYE CONTACT', 'まだ見てる', 'FOCUS', '瞳孔拡大', 'RETINA SCAN']


def draw_hud(c, s, t, n, seg, r):
    rr = random.Random(SEED + n // 6)
    col = (255, 255, 255) if (n // 48) % 2 else (120, 255, 0)
    sz = 44
    tc = '%02d:%02d:%02d:%02d' % (0, (n // FPS) // 60, (n // FPS) % 60, n % FPS)
    rec = 'REC ' + ('●' if (n // 12) % 2 == 0 else '　')
    hexid = 'ID 0x%04X' % rr.randint(0, 0xFFFF)
    items = [(rec, 40, 30), (tc, W - 420, 30), ('SUBJECT: YOU  ' + hexid, 40, H - 80),
             ('瞳孔 %.1fmm  BLINK %d' % (rr.uniform(4.0, 8.9), rr.randint(0, 3)), W - 640, H - 80),
             (rr.choice(HUD_LINES) + ('…' if (n // 8) % 2 else ''), W / 2 - 200, H - 140)]
    for txt, x, y in items:
        if r.random() < 0.08:
            continue
        img = text_layer(txt, 'dot' if is_latin(txt) else 'degobo', sz, col, 0, col, 0, False, 230)
        blit(c, img, x, y)
    d = ImageDraw.Draw(c)
    m, L = 70 + (n % 7) * 2, 80
    for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        d.line([(x, y), (x + sx * L, y)], fill=col + (200,), width=4)
        d.line([(x, y), (x, y + sy * L)], fill=col + (200,), width=4)


def draw_blink(c, s, t, n, seg, r):
    if t not in (0, 1):
        return
    rr = random.Random(SEED + seg['start'])
    word, fk = pick(rr, [KANJI1, JP_WORDS, EN_WORDS, JP_NONSENSE], ALL)
    base = FLASH_RGB.get(s['flash'], (255, 255, 255))
    col = (0, 0, 0) if sum(base) > 380 else (255, 255, 255)
    u = units(word)
    size = min(1500, W * 1.1 / u) if u > 1.1 else H * 1.3
    img = text_layer(word, fk, int(size), col, 0, col, rr.choice([0, 0, 90]))
    blit_c(c, img, W / 2, H / 2)


def draw_ending(c, s, t, n, seg, r):
    if 8 <= t < 40:
        a = min(1.0, (t - 8) / 10.0)
        img = text_layer('まだ見てるよ', 'shinsyoku', 80, (255, 255, 255), 0, (255, 255, 255), 0, False, int(210 * a))
        blit_c(c, img, W / 2, H / 2)
    elif t in (47, 48):
        img = text_layer('●', 'dot', 40, (255, 255, 255))
        blit_c(c, img, W / 2, H / 2)


DRAW = {'giant': draw_giant, 'giant_dark': draw_giant, 'marquee': draw_marquee, 'wall': draw_wall, 'scatter': draw_scatter,
        'stack': draw_stack, 'counter': draw_counter, 'glitchword': draw_glitchword, 'tate': draw_tate, 'whisper': draw_whisper,
        'hud': draw_hud, 'blink': draw_blink, 'ending': draw_ending}

PROG = None
SEG_OF = None


def init():
    global PROG, SEG_OF
    PROG = build_program()
    SEG_OF = []
    for i, seg in enumerate(PLAN):
        SEG_OF.extend([i] * seg['frames'])
    assert len(SEG_OF) == TOTAL, len(SEG_OF)


def render_frame(n):
    if PROG is None:
        init()
    i = SEG_OF[n]
    seg = PLAN[i]
    t = n - seg['start']
    c = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    r = random.Random(SEED * 13 + n)
    styles = PROG[i]
    # draw order: blink first (under), then others, hud last (on top)
    order = sorted(styles, key=lambda s: {'blink': 0, 'hud': 9}.get(s['k'], 5))
    for s in order:
        DRAW[s['k']](c, s, t, n, seg, r)
    return c


def frame_bytes(n):
    return render_frame(n).tobytes()


# ---------------------------------------------------------------- entry points
def main():
    mode = sys.argv[1]
    if mode == 'frame':
        n = int(sys.argv[2])
        img = render_frame(n)
        bg = Image.new('RGBA', (W, H), (90, 90, 90, 255))
        bg.alpha_composite(img)
        bg.convert('RGB').save(sys.argv[3])
        print('fallbacks', FALLBACK_COUNT[0])
        return
    if mode == 'preview':
        init()
        frames = list(range(0, TOTAL, 24))
        cols, tw, th = 8, 480, 204
        rows = math.ceil(len(frames) / cols)
        sheet = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0))
        for k, n in enumerate(frames):
            # basefr/NNN.png = base.mp4 frames at 1 fps (ffmpeg select=not(mod(n,24)), 1-based numbering)
            bg = Image.open(os.path.join(HERE, 'basefr', '%03d.png' % (k + 1))).convert('RGBA')
            bg.alpha_composite(render_frame(n))
            sheet.paste(bg.convert('RGB').resize((tw, th), Image.BILINEAR), ((k % cols) * tw, (k // cols) * th))
        sheet.save(os.path.join(HERE, 'contact_sheet.png'))
        print('fallbacks', FALLBACK_COUNT[0])
        return
    if mode == 'pipe':
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'comp.mp4')
        cmd = ['ffmpeg', '-y', '-v', 'error', '-stats', '-i', 'base.mp4',
               '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', 'pipe:0',
               '-filter_complex', '[0:v]format=rgb24[b];[b][1:v]overlay=format=auto:shortest=1[v]', '-map', '[v]',
               '-c:v', 'libx264', '-crf', '12', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', out]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=HERE)
        t0 = time.time()
        with Pool(10, initializer=init) as pool:
            batch = 60
            for b0 in range(0, TOTAL, batch):
                idx = list(range(b0, min(TOTAL, b0 + batch)))
                for data in pool.map(frame_bytes, idx, chunksize=3):
                    ff.stdin.write(data)
                print('frames %d/%d  %.0fs' % (idx[-1] + 1, TOTAL, time.time() - t0), file=sys.stderr)
        ff.stdin.close()
        ff.wait()
        print('done', ff.returncode, '%.0fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
