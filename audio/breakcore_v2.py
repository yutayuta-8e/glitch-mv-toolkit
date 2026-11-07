"""ゆた×目：breakcore_v1 に、ロマン派風のピアノと、終盤の加速を足した版。

- ピアノは合成（倍音の不調和・弦の唸り・ハンマー音・ペダルの響き）。旋律と和音はオリジナルで、
  リスト「愛の夢」の雰囲気（歌う旋律、大きく波打つアルペジオ）を目指したもの。曲そのものは引用しない。
- 和音は曲のキー D# フリジアン（D# E F# G# A# B C#）の音だけで組む。
- 62.4 秒から 92 秒にかけて、ドラムは 160 → 210 BPM、ピアノは 80 → 105 BPM に加速する。
  Suno の元の音は加速させない（雰囲気の土台として後ろに置いたまま）。
breakcore_audio.py の部品（ドラム合成、刻み、リース・ベースなど）を使う。
"""
import argparse
import os
import sys

import numpy as np
from pedalboard import Compressor, Gain, HighpassFilter, Limiter, LowpassFilter, Pedalboard, Reverb
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakcore_audio as bc  # noqa: E402

SR = bc.SR
RAMP_A, RAMP_B = 62.4, 92.0
BPM0, BPM1 = 80.0, 105.0  # ピアノ（拍）の速さ。ドラムはこの倍


def bpm_at(t):
    if t < RAMP_A:
        return BPM0
    if t > RAMP_B:
        return BPM1
    p = (t - RAMP_A) / (RAMP_B - RAMP_A)
    return BPM0 + (BPM1 - BPM0) * p ** 1.4


def beat_times(total_sec):
    """拍の位置（秒）の一覧。加速を積分して求める。"""
    out, t = [0.0], 0.0
    while t < total_sec:
        t += 60.0 / bpm_at(t)
        out.append(t)
    return np.array(out)


# ------------------------------------------------------------ ピアノの合成
def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


_CACHE = {}


def piano_note(m, dur, vel, rng):
    """1音。dur はペダルを含めて鳴らす長さ（秒）。vel は 0〜1。
    同じ音高・長さ・強さ（丸めたもの）は作り置きを使い回す。"""
    key = (m, round(dur, 1), round(vel * 20) / 20)
    if key not in _CACHE:
        _CACHE[key] = _piano_note(m, key[1], key[2], np.random.default_rng(hash(key) & 0xFFFFFFFF))
    return _CACHE[key]


def _piano_note(m, dur, vel, rng):
    f0 = midi_hz(m)
    ring = min(dur + 0.25, 7.0)
    n = int(ring * SR)
    t = np.arange(n) / SR
    B = 0.00015 * (f0 / 261.6) ** 0.8  # 弦の硬さによる倍音のずれ
    t0 = np.clip(5.5 * (261.6 / f0) ** 0.6, 0.6, 9.0)  # 低い音ほど長く響く
    bright = 0.35 + 0.65 * vel
    sig = np.zeros(n)
    kmax = int(min(14, 11000 / f0))
    for k in range(1, kmax + 1):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        amp = (1.0 / k ** 1.15) * np.exp(-(k - 1) * (1.2 - bright) * 0.45)
        tau = t0 / (1 + 0.35 * (k - 1))
        env = 0.65 * np.exp(-t / (tau * 0.25)) + 0.35 * np.exp(-t / tau)  # 速い減衰と長い余韻
        dets = (-0.6, 0.0, 0.7) if k <= 4 else (0.0,)  # 低い倍音だけ3本の弦のずれ（唸り）
        for det in dets:
            ph = rng.uniform(0, 2 * np.pi)
            sig += amp * env * np.sin(2 * np.pi * fk * (1 + det / 1e4 * k ** 0.5) * t + ph) / len(dets)
    att = int(0.004 * SR)
    sig[:att] *= np.linspace(0, 1, att)
    hammer = rng.standard_normal(int(0.012 * SR)) * np.exp(-np.arange(int(0.012 * SR)) / SR * 400)
    sig[: len(hammer)] += hammer * 0.04 * vel
    rel = int(0.25 * SR)
    end = int(dur * SR)
    if end + rel < n:
        sig[end:end + rel] *= np.linspace(1, 0, rel) ** 2
        sig[end + rel:] = 0
    return sig * vel * 0.18


# D# フリジアンの和音（MIDI）。左手の低音、和音の音
CHORDS = [
    ("D#m", 39, [63, 66, 70]),        # D#2 / D#4 F#4 A#4
    ("Bmaj7", 35, [63, 66, 70, 71]),  # B1 / D# F# A# B
    ("G#m7", 32, [63, 66, 68, 71]),   # G#1
    ("Emaj7", 40, [63, 64, 68, 71]),  # E2
    ("B/D#", 39, [63, 66, 71]),       # D#2
    ("F#6", 42, [61, 63, 66, 70]),    # F#2
    ("Emaj7#11", 40, [64, 68, 70, 71]),
    ("D#m(add b9)", 39, [63, 64, 66, 70]),  # E を短9度の色として使う（フリジアン）
]

# 旋律（8小節、各4拍）。(小節内の拍, 長さ[拍], MIDI)
MELODY = [
    [(0, 2, 70), (2, 1, 73), (3, 1, 75)],
    [(0, 3, 78), (3, 0.5, 76), (3.5, 0.5, 75)],
    [(0, 2, 75), (2, 1, 71), (3, 1, 73)],
    [(0, 2.5, 71), (2.5, 0.5, 68), (3, 1, 70)],
    [(0, 1.5, 75), (1.5, 0.5, 78), (2, 2, 82)],
    [(0, 1, 80), (1, 1, 78), (2, 1, 75), (3, 1, 73)],
    [(0, 2, 76), (2, 1, 75), (3, 1, 71)],
    [(0, 4, 75)],
]


def dyn_at(t):
    """区間ごとの強さ（0〜1）。"""
    for a, b, v in [(0, 14.1, 0.45), (14.1, 35.5, 0.62), (35.5, 51.0, 0.7), (51.0, 62.4, 0.6),
                    (62.4, 80.0, 0.72), (80.0, 92.0, 0.9), (92.0, 999, 0.8)]:
        if a <= t < b:
            return v
    return 0.6


def build_piano(total_sec, rng):
    n = int(total_sec * SR)
    out = np.zeros(n)
    beats = beat_times(total_sec + 5)
    nbars = (len(beats) - 1) // 4

    def bt(b):  # 拍番号（小数可）→ 秒
        i = int(np.floor(b))
        if i + 1 >= len(beats):
            return beats[-1]
        return beats[i] + (b - i) * (beats[i + 1] - beats[i])

    for bar in range(nbars):
        t_bar = bt(bar * 4)
        if t_bar >= 92.0:
            break
        name, bass, tones = CHORDS[bar % 8]
        phrase = (bar // 8)
        v = dyn_at(t_bar)
        bar_end = bt(bar * 4 + 4)
        # 左手：低音と、6連符で上がって下がるアルペジオ（ペダルで小節の終わりまで響かせる）
        arp_up = [bass, bass + 7, bass + 12, tones[0], tones[1], tones[2]]
        arp = arp_up + arp_up[::-1]
        for beat in range(4):
            for k in range(6):
                bpos = bar * 4 + beat + k / 6
                t = bt(bpos)
                m = arp[(beat % 2) * 6 + k]
                vel = v * (0.55 if k else 0.75) * (1.0 + 0.04 * rng.standard_normal())
                note = piano_note(m, bar_end - t, vel * 0.8, rng)
                i = int(t * SR)
                out[i:i + len(note)] += note[: max(0, n - i)]
        # 右手：旋律。後半の繰り返しは1オクターブ上を重ねる
        for b0, dur, m in MELODY[bar % 8]:
            if phrase == 0 and t_bar < 2.83:
                continue
            t = bt(bar * 4 + b0 + 0.03 * rng.standard_normal())  # わずかなルバート
            d = bt(bar * 4 + b0 + dur) - t
            vel = min(1.0, v * 1.1)
            for mm in ([m, m + 12] if t >= 62.4 or phrase % 2 == 1 and t > 35.5 else [m]):
                note = piano_note(mm, d * 1.05, vel * (0.7 if mm != m else 1.0), rng)
                i = int(t * SR)
                out[i:i + len(note)] += note[: max(0, n - i)]
    # 最後の和音：92 秒で D#m(add b9) を大きく鳴らして余韻を残す
    for m in [27, 39, 51, 58, 63, 64, 66, 70, 75, 82]:
        note = piano_note(m, 2.3, 0.85, rng)
        i = int(92.0 * SR)
        out[i:i + len(note)] += note[: max(0, n - i)]
    st = np.stack([out, out], 1).astype(np.float32)
    st[:, 0] *= 0.97
    return bc.fx(Pedalboard([HighpassFilter(35), Reverb(room_size=0.82, damping=0.35, wet_level=0.32, dry_level=0.85,
                                                            width=1.0)]), st)


# ------------------------------------------------------------ 加速するドラム
def build_drums_accel(n, rng):
    brk = bc.make_break(rng)
    sl = bc.slices(brk)
    out = np.zeros(n, np.float32)
    for a, b, mode in bc.PLAN:
        if mode == "none":
            continue
        t = a
        while t < b - 0.05:
            bar_len = 2 * 60.0 / bpm_at(t)  # ドラム1小節 = ピアノ2拍（80 BPM で 1.5 秒）
            progress = (t - a) / max(b - a, 1e-6)
            bar = bc.chop_bar(sl, rng, "full" if mode == "half" else mode, progress)
            if mode == "half":
                bar = bar * 0.5
            if bar_len < bc.BAR - 1e-3:  # 速くなった分、各スライスの後ろを切って詰める（音程は変えない）
                m_old = len(bar) // 16
                m_new = int(bar_len * SR / 16)
                fade = np.linspace(1, 0, min(120, m_new))
                pieces = []
                for k in range(16):
                    p = bar[k * m_old:k * m_old + m_new].copy()
                    p[-len(fade):] *= fade
                    pieces.append(p)
                bar = np.concatenate(pieces)
            i = int(t * SR)
            seg = bar[: int((b - t) * SR)]
            bc.place(out, seg, i)
            t += bar_len
        i0, i1 = int(a * SR), int(b * SR)
        if mode == "half":
            out[i0:i1] = Pedalboard([LowpassFilter(900)])(out[i0:i1].copy(), SR)
        if mode == "chaos":
            from pedalboard import Bitcrush
            out[i0:i1] = Pedalboard([Bitcrush(bit_depth=8)])(out[i0:i1].copy(), SR) * 0.6 + out[i0:i1] * 0.6
    return out


# ------------------------------------------------------------ 重ねるドラム（--more-drums）
SECTION_HITS = [14.1, 51.0, 58.0, 62.4, 80.0]   # クラッシュを入れる区間の頭
ROLL_INTO = [14.1, 35.5, 62.4, 80.0, 92.0]       # 直前にスネアのロールを入れる区間の頭


def snare_tight(rng):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 240 * t) * np.exp(-t * 40) * 0.6
    noise = rng.standard_normal(n) * np.exp(-t * 22)
    noise = Pedalboard([HighpassFilter(2500)])(noise.astype(np.float32), SR)
    return np.tanh((body + noise) * 2.2) * 0.8


def sub_kick():
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    f = 38.89 + 90 * np.exp(-t * 30)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 2.0)


def ride(rng):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    s = sum(np.sign(np.sin(2 * np.pi * f * t + rng.uniform(0, 6))) for f in (3180, 4570, 5930, 7420)) / 4
    s = Pedalboard([HighpassFilter(5000)])((s * np.exp(-t * 9)).astype(np.float32), SR)
    return s * 0.35


def shaker(rng):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    s = rng.standard_normal(n) * np.sin(np.pi * t / (n / SR))
    return Pedalboard([HighpassFilter(7000)])(s.astype(np.float32), SR) * 0.25


def crash(rng):
    n = int(2.5 * SR)
    t = np.arange(n) / SR
    s = rng.standard_normal(n) * np.exp(-t * 1.6)
    s += 0.5 * sum(np.sin(2 * np.pi * f * t) for f in (3390, 4760, 6110, 8230)) / 4 * np.exp(-t * 2.2)
    return Pedalboard([HighpassFilter(3000)])(s.astype(np.float32), SR) * 0.6


def mode_at(t):
    for a, b, mode in bc.PLAN:
        if a <= t < b:
            return mode
    return "none"


def make_break2(rng):
    """2つ目のブレイク：違うパターンと高めの締まったスネア。"""
    n = int(bc.BAR * SR)
    b = np.zeros(n + int(0.4 * SR), np.float32)
    K = [0, 3, 6, 10, 11]
    S = [4, 12, 14]
    ghost = [2, 7, 9, 15]
    for st in range(16):
        i = int(st * bc.STEP * SR + (0.008 * SR if st % 2 else 0))
        if st in K:
            bc.place(b, bc.kick(rng), i, 0.8)
        if st in S:
            bc.place(b, snare_tight(rng), i, 0.9)
        if st in ghost:
            bc.place(b, snare_tight(rng), i, 0.3)
    b = Pedalboard([Compressor(threshold_db=-12, ratio=5, attack_ms=2, release_ms=50), Gain(-2)])(b, SR)
    return b[:n]


def build_more_drums(n, rng):
    """2つ目のブレイク、サブキック、ライド、シェイカー、ロール、クラッシュを重ねる（左右2ch）。"""
    out = np.zeros((n, 2), np.float32)
    sl2 = bc.slices(make_break2(rng))
    sk, rd = sub_kick(), ride(rng)
    t = 0.0
    while t < 92.0:
        bar_len = 2 * 60.0 / bpm_at(t)
        mode = mode_at(t)
        i = int(t * SR)
        if mode in ("full", "chaos", "roll", "half"):
            # 2つ目のブレイク（左右に少し振る）
            if mode != "half":
                bar = bc.chop_bar(sl2, rng, "full" if mode == "roll" else mode, 0.0)
                m_old, m_new = len(bar) // 16, int(bar_len * SR / 16)
                if m_new < m_old:
                    bar = np.concatenate([bar[k * m_old:k * m_old + m_new] for k in range(16)])
                seg = bar[: max(0, n - i)]
                out[i:i + len(seg), 0] += seg * 0.75
                out[i:i + len(seg), 1] += seg * 0.55
            # サブキック：小節の1拍目と3拍目
            if mode in ("full", "chaos"):
                for q in (0, 0.5):
                    j = int((t + q * bar_len) * SR)
                    seg = sk[: max(0, n - j)]
                    out[j:j + len(seg)] += seg[:, None] * 0.55
            # ライド（8分）とシェイカー（16分）
            for k in range(16):
                j = int((t + k * bar_len / 16) * SR)
                if k % 2 == 0:
                    seg = rd[: max(0, n - j)]
                    out[j:j + len(seg), 0] += seg * (0.5 if k % 4 else 0.7)
                    out[j:j + len(seg), 1] += seg * 0.4
                sh = shaker(rng)[: max(0, n - j)]
                out[j:j + len(sh), 1] += sh * (0.9 if k % 2 else 0.5)
                out[j:j + len(sh), 0] += sh * 0.3
        t += bar_len
    # スネアのロール：区間の頭の直前 1 小節で、16分 → 32分に細かく、だんだん大きく
    for h in ROLL_INTO:
        bar_len = 2 * 60.0 / bpm_at(h - 1.0)
        start = h - bar_len
        k, tt = 0, start
        while tt < h - 0.01:
            p = (tt - start) / bar_len
            step = bar_len / (16 if p < 0.5 else 32)
            j = int(tt * SR)
            seg = snare_tight(rng)[: max(0, n - j)]
            out[j:j + len(seg)] += seg[:, None] * (0.25 + 0.6 * p)
            tt += step
            k += 1
    # クラッシュ：区間の頭
    for h in SECTION_HITS:
        j = int(h * SR)
        seg = crash(rng)[: max(0, n - j)]
        out[j:j + len(seg), 0] += seg * 0.7
        out[j:j + len(seg), 1] += seg * 0.8
    return bc.fx(Pedalboard([Compressor(threshold_db=-14, ratio=3, attack_ms=3, release_ms=80)]), out)


# ------------------------------------------------------------ ラストに向けて壊す（--wreck）
def wreck_level(t):
    """62.4 秒から 92 秒へ、0 → 1 に上がる壊し具合（後ろほど急に）。"""
    return float(np.clip((t - RAMP_A) / (RAMP_B - RAMP_A), 0, 1)) ** 1.5


def resample(seg, ratio):
    """ratio 倍の速さで読む（音程も変わる）。長さは元のまま、足りない分は無音。"""
    n = len(seg)
    idx = np.arange(n) * ratio
    idx = idx[idx < n - 1]
    out = np.zeros_like(seg)
    for c in range(seg.shape[1]):
        out[: len(idx), c] = np.interp(idx, np.arange(n), seg[:, c])
    return out


def tape_stop(seg):
    """テープを止めたように、だんだん遅く・低くなって止まる。"""
    n = len(seg)
    speed = np.linspace(1, 0, n) ** 1.3
    pos = np.cumsum(speed)
    pos = pos[pos < n - 1]
    out = np.zeros_like(seg)
    for c in range(seg.shape[1]):
        out[: len(pos), c] = np.interp(pos, np.arange(n), seg[:, c])
    return out


def wreck(bus, rng):
    """ドラムを 8分ごとに刻み、後ろほど高い確率で、連打・逆再生・音程の上下・ぶつ切りにする。
    あわせて歪みとビットの粗さを上げ、80 秒と 92 秒の直前はテープストップ。"""
    from pedalboard import Bitcrush, Resample
    out = bus.copy()
    t = RAMP_A
    while t < RAMP_B - 0.02:
        unit = 2 * 60.0 / bpm_at(t) / 8
        p = wreck_level(t)
        i0, i1 = int(t * SR), int(min(t + unit, RAMP_B) * SR)
        chunk = bus[i0:i1]
        m = len(chunk)
        if m > 64 and rng.random() < 0.15 + 0.7 * p:
            op = rng.choice(["stutter", "stutter", "stutter_fine", "reverse", "pitch", "gate"])
            if op in ("stutter", "stutter_fine"):
                div = rng.choice([2, 4] if op == "stutter" else ([8, 16] if p > 0.5 else [4, 8]))
                piece = chunk[: m // div].copy()
                piece[-min(60, len(piece)):] *= np.linspace(1, 0, min(60, len(piece)))[:, None]
                rep = np.concatenate([piece * (1 - 0.3 * k / div) for k in range(div)])
                new = np.zeros_like(chunk)
                new[: min(m, len(rep))] = rep[:m]
            elif op == "reverse":
                new = chunk[::-1].copy()
            elif op == "pitch":
                new = resample(chunk, rng.choice([0.5, 0.7, 1.5, 2.0]))
            else:
                g = (np.arange(m) // max(1, m // 8)) % 2 == 0
                new = chunk * g[:, None]
            out[i0:i1] = new
        t += unit
    # 歪みとビットの粗さ：壊し具合に合わせて上げる
    a, b = int(RAMP_A * SR), int(RAMP_B * SR)
    lv = np.array([wreck_level(i / SR) for i in range(a, b, 480)], np.float32)
    lv = np.repeat(lv, 480)[: b - a][:, None]
    seg = out[a:b]
    crushed = Pedalboard([Resample(target_sample_rate=11025), Bitcrush(bit_depth=6)])(seg.copy(), SR)
    drive = 1 + 5 * lv
    dist = np.tanh(seg * drive) / np.tanh(drive)
    out[a:b] = seg * (1 - lv) + (dist * 0.65 + crushed[: len(seg)] * 0.35) * lv * 1.1
    # 区間の頭の直前でテープストップ
    for h, d in ((80.0, 0.45), (RAMP_B, 0.8)):
        i0, i1 = int((h - d) * SR), int(h * SR)
        out[i0:i1] = tape_stop(out[i0:i1])
    # 84 秒からは 32分 → 64分の連打を上に重ね、音程をだんだん上げる
    sl = bc.slices(bc.make_break(rng))
    t = 84.0
    while t < RAMP_B - 0.8:
        p = (t - 84.0) / (RAMP_B - 0.8 - 84.0)
        step = 2 * 60.0 / bpm_at(t) / (32 if p < 0.6 else 64)
        s = sl[rng.choice([4, 12])] if rng.random() < 0.7 else sl[0]
        s = s[: int(step * SR)]
        s = resample(np.stack([s, s], 1), 1.0 + 0.8 * p)
        j = int(t * SR)
        out[j:j + len(s)] += s * (0.25 + 0.45 * p)
        t += step
    return out


# ------------------------------------------------------------ セリフ「見てるよ」（--voice）
def voice_events(v, rng, last_at=92.6):
    """(秒, 音) の並び。v は H3 の動画から切り出した「みてるよ。」（ステレオ）。"""
    from pedalboard import PitchShift
    v = v / max(np.max(np.abs(v)), 1e-9) * 0.9
    tail = np.zeros((int(1.6 * SR), 2), np.float32)
    padded = np.concatenate([v, tail])
    verb = Pedalboard([Reverb(room_size=0.95, wet_level=0.6, dry_level=0.55)])(padded.copy(), SR)
    low = Pedalboard([PitchShift(semitones=-7), Reverb(room_size=0.7, wet_level=0.3, dry_level=0.9)])(padded.copy(), SR)
    high = Pedalboard([PitchShift(semitones=7)])(v.copy(), SR)
    mi = v[: int(0.16 * SR)].copy()
    mi[-200:] *= np.linspace(1, 0, 200)[:, None]

    def stutter(k, gap):
        out = np.zeros((int((k * gap + len(v) / SR + 0.1) * SR), 2), np.float32)
        for q in range(k):
            out[int(q * gap * SR):int(q * gap * SR) + len(mi)] += mi
        out[int(k * gap * SR):int(k * gap * SR) + len(v)] += v
        return out

    return [
        (5.2, verb * 0.55),          # 静かな頭で、遠くから
        (33.9, verb * 0.8),          # 1回目の山の終わり
        (61.3, v * 1.0),             # スパートの直前、ドラムを下げて真ん中に
        (70.0, low * 0.9),           # 低い声
        (78.9, stutter(4, 0.12)),    # み・み・み・み・みてるよ → 80 秒の頭へ
        (84.2, v * 0.9),
        (86.4, high * 0.7),
        (88.0, stutter(6, 0.07)),
        (89.6, v[::-1] * 0.8),       # 逆再生
        (90.3, stutter(8, 0.045)),
        (last_at, verb * 0.9),       # ぜんぶ止まったあとに、最後のひと言
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suno")
    ap.add_argument("stems", help="remix_v1 の stems フォルダ")
    ap.add_argument("out")
    ap.add_argument("--stems-out")
    ap.add_argument("--seed", type=int, default=160)
    ap.add_argument("--piano-wav", help="合成ピアノの代わりに使うピアノの WAV（48kHz ステレオ、曲と同じ長さ）")
    ap.add_argument("--piano-gain", type=float, default=1.0)
    ap.add_argument("--more-drums", action="store_true", help="2つ目のブレイク、サブキック、ライド等を重ねる")
    ap.add_argument("--wreck", action="store_true", help="62.4〜92 秒のドラムを、後ろほど激しく壊す")
    ap.add_argument("--voice", help="セリフ「みてるよ。」の WAV（48kHz）。決まった場所に差し込み、その間はほかを下げる")
    ap.add_argument("--tail-extend", type=float, default=0.0,
                    help="曲の終わりを何秒延ばすか。92 秒からの余韻を、深い残響でゆっくり消えるようにする")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    suno = bc.read(a.suno)
    n = suno.shape[0]
    st = {k: bc.read(os.path.join(a.stems, f)) for k, f in
          [("bass", "02_bass.wav"), ("bell", "03_bell.wav"), ("choir", "04_choir.wav"), ("fx", "05_fx.wav"),
           ("heart", "06_heart.wav")]}
    drums = build_drums_accel(n, rng)
    drum_on = bc.mask(n, ("full", "chaos", "roll"))
    bass = bc.reese(n, rng) * bc.mask(n, ("full", "chaos"), fade=0.3)
    if a.piano_wav:
        p = bc.read(a.piano_wav)[:n]
        piano = np.zeros((n, 2), np.float32)
        piano[: len(p)] = p * a.piano_gain
    else:
        piano = build_piano(n / SR, np.random.default_rng(a.seed + 1))[:n]

    bed = bc.fx(Pedalboard([HighpassFilter(120), Reverb(room_size=0.85, wet_level=0.35, dry_level=0.8)]), suno)
    bed *= (1 - 0.35 * drum_on)[:, None]
    drums_st = np.stack([drums, drums], 1) * 0.85
    if a.more_drums:
        drums_st = drums_st + build_more_drums(n, np.random.default_rng(a.seed + 7)) * 0.8
    if a.wreck:
        drums_st = wreck(drums_st, np.random.default_rng(a.seed + 13))
    mix = (bed * 0.7 + st["bell"] * 0.55 + st["choir"] * 0.7 + st["fx"] * 0.9 + st["heart"] * 0.9
           + st["bass"] * 0.5 * (1 - 0.5 * drum_on)[:, None]
           + np.stack([bass, bass], 1) * 0.9 + drums_st + piano * 1.0)
    end = int(92.0 * SR)
    ext = int(a.tail_extend * SR)
    if ext:
        mix = np.concatenate([mix, np.zeros((ext, 2), np.float32)])
        piano = np.concatenate([piano, np.zeros((ext, 2), np.float32)])
        n = len(mix)
    tail = np.linspace(1, 0, n - end) ** 1.5
    # 92 秒以降はドラムなどを止め、ピアノの最後の和音と残響だけを残す
    rest = mix[end:] - piano[end:]
    if ext:
        # 延ばした分：ドラムなどは早めに引き、ピアノはゆっくり。深い残響を重ねて最後まで尾を引かせる
        L = n - end
        k = np.linspace(1, 0, L)
        tt = np.arange(L) / SR
        dry = rest * (k ** 6)[:, None] + piano[end:]
        # ピアノの音源は曲の長さ（94.32 秒）で切れるので、最後の和音（92.4〜93.6 秒）を細かい粒にして
        # 重ね続け、音を引き延ばす。はじめはゆっくり、終わりに向けて小さく（終わりで約 -45 dB）
        src = piano[int(92.4 * SR):int(93.6 * SR)]
        grain, hop = int(0.30 * SR), int(0.05 * SR)
        win = np.hanning(grain)[:, None].astype(np.float32)
        rng_f = np.random.default_rng(a.seed + 31)
        freeze = np.zeros((L + grain, 2), np.float32)
        for j in range(0, L, hop):
            s0 = rng_f.integers(0, len(src) - grain)
            freeze[j:j + grain] += src[s0:s0 + grain] * win
        freeze = freeze[:L]
        freeze *= np.sqrt(np.mean(src ** 2)) / max(np.sqrt(np.mean(freeze[: int(1.0 * SR)] ** 2)), 1e-9)
        rise = np.clip((tt - 1.2) / 1.6, 0, 1)  # 元のピアノが消えていくのと入れ替わりに出てくる
        fall = 10 ** (-45 * (tt / tt[-1]) ** 2.5 / 20)
        dry = dry + freeze * (rise * fall * 0.9)[:, None]
        wash = Pedalboard([Reverb(room_size=0.95, damping=0.4, wet_level=1.0, dry_level=0.0, width=1.0)])(
            dry.copy(), SR)
        mix[end:] = (dry + wash * 0.45) * np.minimum(1, k * 7)[:, None]  # 最後の 1 秒で完全に無音へ
    else:
        mix[end:] = rest * (np.linspace(1, 0, n - end) ** 3)[:, None] + piano[end:] * tail[:, None]
    voice = np.zeros_like(mix)
    if a.voice:
        last_at = 94.4 if ext else 92.6  # 余韻を延ばしたときは、最後のひと言を静かになってから
        for at, sig in voice_events(bc.read(a.voice), np.random.default_rng(a.seed + 21), last_at):
            j = int(at * SR)
            seg = sig[: max(0, n - j)]
            voice[j:j + len(seg)] += seg
        # セリフの間はほかを下げる（声の大きさをなめらかにした分だけ）
        env = np.abs(voice).max(1)
        k = int(0.08 * SR)
        env = np.convolve(env, np.ones(k) / k, mode="same")
        env = np.clip(env / max(env.max(), 1e-9) * 2.5, 0, 1)
        mix *= (1 - 0.55 * env)[:, None]
        mix += voice * 1.6
    mix = bc.fx(Pedalboard([HighpassFilter(28), Compressor(threshold_db=-16, ratio=3, attack_ms=5, release_ms=120),
                            Limiter(threshold_db=-3.0, release_ms=60)]), mix)
    mix *= 10 ** (-3.0 / 20) / np.max(np.abs(mix))  # 歪みで音の山の間が 0 dB を超えやすいので、少し余裕を残す
    wavfile.write(a.out, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    if a.stems_out:
        os.makedirs(a.stems_out, exist_ok=True)
        for name, arr in [("01_breaks_accel", drums_st), ("02_reese", np.stack([bass, bass], 1)), ("03_suno_bed", bed),
                          ("04_piano", piano)]:
            peak = max(np.max(np.abs(arr)), 1e-9)
            wavfile.write(os.path.join(a.stems_out, f"{name}.wav"), SR,
                          (np.clip(arr / max(peak, 1.0), -1, 1) * 32767).astype(np.int16))
    print("done", a.out)


if __name__ == "__main__":
    main()
