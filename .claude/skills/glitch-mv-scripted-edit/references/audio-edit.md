# 音の編集

読むタイミング：Suno 曲をブレイクコア／DnB にする、ピアノを重ねる、ドラムを足す／壊す、セリフを入れる、余韻を延ばすとき。AI は音を聴けないので、結果は実測値と試聴用ファイルで渡す。

## 1. 素材の段（`remix_audio.py`、`breakcore_audio.py`）

- `remix_audio.py <suno.wav> <out.wav> --stems <フォルダ>`：曲（D#、80 BPM、1 拍 0.75 秒）を土台に、ドラム・ベース・ベル・クワイア・FX・心音を NumPy で合成して重ねる。楽器ごとの WAV も出る（02_bass … 06_heart）。ブレイクコアの段はこの stems を読む。
- `breakcore_audio.py`：アーメン風のブレイクを合成する（サンプルの引用はしない）。曲の 2 拍 = ドラム 1 小節、160 BPM、1 小節 1.5 秒。区間の計画は `PLAN`：none / half（ローパス）/ full / chaos（ビットクラッシュ）/ roll。刻み方は `chop_bar`、ベースはリース（`reese`）。

## 2. 本体（`breakcore_v2.py`）

v7 で使った実際のコマンド（パスは作品に合わせて直す。2026-11-07 に、最終版で使う音だけを `音源/見てるよ_最終版_v7/` にまとめ、ほかは Safe Trash に退避した。下のパスは移動前のもの）：

```bash
python -I breakcore_v2.py 音源/見てるよ_suno.wav 音源/見てるよ_remix_v1_stems 音源/見てるよ_breakcore_v6_longtail.wav --piano-wav 音源/piano_salamander_ambient_glass.wav --piano-gain 0.9 --more-drums --wreck --voice 音源/voice/miteruyo_CLIP-01_v2_7.06-8.02.wav --tail-extend 4.5 --stems-out 音源/見てるよ_breakcore_v6_longtail_stems
```

- 加速：62.4〜92 秒（`RAMP_A, RAMP_B`）で、ピアノは 80 → 105 BPM、ドラムは 160 → 210 BPM。ドラム 1 小節 = `2*60/bpm_at(t)`。速くなった分は各スライスの後ろを切って詰める（音程は変えない）。Suno の元の音は加速させず、後ろに敷いたまま。
- `--piano-wav`：合成ピアノの代わりに、外のピアノ WAV を使う（曲と同じ長さ・48kHz・ステレオ）。
- `--more-drums`：2 つ目のブレイク（K=[0,3,6,10,11]、S=[4,12,14]、高めのスネア、左右に振る）、サブキック（D#1＝38.89Hz、1 拍目と 3 拍目）、ライド（8 分）、シェイカー（16 分）、区間の頭の直前のスネアロール（16 分 → 32 分）、区間の頭のクラッシュ。加速に追従する。
- `--wreck`：62.4〜92 秒で、後ろほど激しく壊す（`wreck_level = p**1.5`）。
  - 8 分ごとに確率 0.15+0.7p で、連打（2〜16 分割）・逆再生・音程の上下（0.5〜2 倍）・ぶつ切りのどれかにする。
  - 歪み（tanh、ドライブ 1→6）と、粗い音（11kHz・6bit）を p に合わせて混ぜる。
  - 80 秒と 92 秒の直前でテープストップ。
  - 84 秒からは、32 分 → 64 分の連打を上に重ね、音程を上げていく。
- `--voice`：セリフの WAV を決まった秒数に置く（`voice_events`）。
  - 置き方：遠い残響、真ん中にそのまま、−7 半音の低い声、+7 半音の高い声、「み・み・み・みてるよ」の連打、逆再生。
  - 声の大きさの包絡でほかの音を最大 55% 下げる（ダッキング）。
- `--tail-extend 秒`：92 秒からの余韻を延ばす。外のピアノ WAV は曲の長さで切れるので、最後の和音（92.4〜93.6 秒）を 0.3 秒の粒にして 0.05 秒ごとに重ね続け、音を引き延ばす。深い残響（room 0.95）を足し、`-45 dB * u**2.5` の形で小さくして、最後の 1 秒で無音にする。最後のひと言は静かになってから（94.4 秒）。
- 仕上げ：ハイパス 28Hz → コンプ → リミッター -3dB → サンプルのピークを -3 dBFS にそろえる（v7：-11.0 LUFS、トゥルーピーク -0.4 dBTP）。

## 3. ピアノ（Salamander Grand Piano V3、CC BY 3.0）

- 場所：`<Salamander Grand Piano V3 の SFZ のフォルダ>`。クレジット `Piano: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0)`。
- `sfz_piano.py <sfz> <out.wav>`：SFZ の小さなサンプラー。演奏データは `musio_piano.build_events`（「3 番：アンビエントのガラス」系統、494 音）。
  - `<group>` の設定を `<region>` に引き継ぐ。
  - `trigger=release`（離鍵音）と、ペダル（hikey=-1）の group は読み飛ばす（そうしないと 641 リージョンになって音が濁る。正しくは 480）。
  - 強さの効き方は amp_veltrack、離鍵後の消え方は ampeg_release に従う。
- `piano_ideas.py`：ピアノだけの 5 案（40〜50 秒）。依頼者は合成ピアノを「ちょっと違う」として、音色を Salamander に替えた。
- Musio（Musio Connect / REAPER）は、プラグイン画面がクリックを受け付けず使えなかった。

## 4. セリフの切り出し

- H3 の動画の音を書き出し、`showspectrumpic`（log、0〜8kHz）で、声の倍音が縦に並ぶ帯を探す。ささやきの指定でも、実際は有声の声で入っていた。
- サンプル精度で切る：`atrim=start=7.06:end=8.02,asetpts=PTS-STARTPTS,highpass=f=160,afade=t=in:d=0.01,afade=t=out:st=0.88:d=0.08`。予備のテイクも残す（`音源/voice/`）。
- Suno の MCP 接続は不要（曲は公式ダウンロード済みの WAV、セリフは H3 の音）。

## 5. 確認のしかた

- 0.5 秒ごとの RMS（dB）で、区間の頭・ラストの壊れ方・余韻の消え方を見る。v6 の初版は、余韻が 96.5 秒まで -12 dB のまま 97 秒でストンと落ちていたので作り直した。
- `ebur128=peak=true` で LUFS とトゥルーピーク。前後の版のスペクトログラムを縦に並べて比べる。
- 注意書きの間（0〜6.9 秒）が -91 dB 前後（無音）かを `volumedetect` で見る。
