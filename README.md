# glitch-mv-toolkit

生成 AI のカットと曲から、フラッシュ注意レベルのグリッチ／サイケ MV を FFmpeg と Python だけで組み立てるためのスクリプト集。音は Suno の曲を土台に、ブレイクコアを合成して作る。作例は「ゆた×目／見てるよ」（約 106 秒、21:9、24fps、1920×816 と 3840×1632）。

読み手は Claude Code などの AI エージェントを想定している。全体の手順と値は [docs/HOWTO-glitch-mv.md](docs/HOWTO-glitch-mv.md)、作業のときの進め方は Claude Code のスキル [.claude/skills/glitch-mv-scripted-edit/](.claude/skills/glitch-mv-scripted-edit/SKILL.md) にある。このリポジトリを開いた Claude Code は、スキルを自動で読み込む。

## 中身

```text
docs/HOWTO-glitch-mv.md        全体の手順・数値・詰まった点・権利の注意（最初に読む）
.claude/skills/glitch-mv-scripted-edit/
  SKILL.md                     進め方と守ること（Claude Code のスキル）
  references/                  映像・音・サムネ・つまずき・版の上げ方の詳細
video/                         カオス編集、文字の層、終盤スパート、注意書き、黒の透過
  fable_render/                スパートの層が使う描画部品（言葉・フォント・豆腐チェック）
audio/                         Suno 曲＋合成のリミックス、ブレイクコア、加速、ドラム追加、壊し、セリフ、余韻、SFZ ピアノ
thumbnail/                     動画と同じ質感でサムネを 10 通りに加工、組み合わせ
tools/                         確認用の小道具（コマ一覧、音量の推移、版の比較、セリフ探し、X 向けの書き出し）
examples/build_example.sh      素材 → カット → 文字 → スパート → 組み立てまでの流れ（プレビュー／本番／4K）
```

ファイル名の `_v2`・`_v3` などは、作品を直していったときの版。新しい方が上位互換になっている（`chaos_edit_v3`、`chaos_text_v5`、`spurt_layer_v2`）。古い版は、何を変えたかを追えるように残してある。各スクリプトの冒頭の docstring に、使い方と、その版で変えたことが書いてある。

## 必要なもの

- FFmpeg（libx264、prores_ks、drawtext、showspectrumpic が使えるビルド）
- Python 3.12 と `pip install -r requirements.txt`（Pillow、NumPy、SciPy、pedalboard）
- 動作確認は Windows 11（Git Bash）。シェルスクリプトは bash、Python は `python -I` で動かす前提

## 作例の素材

最終版に実際に使った素材と、完成版（X 投稿用の 4K）を置いてある。

- 画像：`media/images/`（世界観の基準 `MOOD-02_1`、サムネの元画像、サムネの完成版）
- カット（40 本、約 1.2GB）と音（最終ミックス・stems・作り直しに要る素材、13 ファイル、約 210MB）：[リリース media-v1](https://github.com/yutayuta-8e/glitch-mv-toolkit/releases/tag/media-v1) の ZIP。容量が大きいので Git ではなくリリースに置いた。SHA-256 は同じリリースの `SHA256SUMS.txt`
- 完成版：同じリリースの `miteruyo_v7_X_4k.mp4`（3840×1632、105.83 秒、H.264 75Mbps、約 995MB）。元の 4K 本番（約 5.4GB）は 1 ファイル 2GB の上限を超えるので置いていない
- クレジット：映像と画像は TapNow で生成（MiniMax H3、Midjourney）、キャラクターは作者のもの。曲は Suno（作者が有料プランで生成）。ピアノは `Piano: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0)`
- 映像には激しい点滅が多く含まれる

## 入っていないもの（自分で用意する）

- **フォント**：配布の規約上、このリポジトリには入れていない。作例は「いいフォント」掲載の OFL などの書体（破裂ノ明朝、でごぼゴシック、したたる明朝、侵食明朝、フィーリングオブフィア、ダストデビル、幻ノにじみ明朝、カキナグリ、暗黒ゾン字、怨霊フォント、黒薔薇シンデレラ、g_コミックホラー、激筆SFX、クロヌリ）と、Google Fonts の Dela Gothic One・DotGothic16・Zen Maru Gothic。書体ごとのサブフォルダに入れて、`--fonts` か環境変数で場所を渡す
- **自分の作品の素材**：作例以外の曲・映像は、自分で用意する
- **ピアノの音源**：Salamander Grand Piano V3（CC BY 3.0）の SFZ とサンプルは、配布元から取ってくる。使ったらクレジットを書く

## 環境変数

| 変数 | 使うスクリプト | 中身 |
|---|---|---|
| `GLITCH_MV_FONTS` | `thumbnail/thumb_fx.py` | 書体のフォルダ（書体ごとのサブフォルダ） |
| `GLITCH_MV_FABLE_FONTS` | `video/fable_render/render.py`（スパートの層） | スパートの層の書体を平らに置いたフォルダ（ファイル名は render.py の `F` を参照） |
| `GLITCH_MV_PLAN` | `video/fable_render/render.py` | カオス編集の plan.json（スパートの層だけなら不要） |

## 曲に合わせて直すところ

区間の秒数は「見てるよ」（94.32 秒、80 BPM、D# フリジアン）に合わせてある。別の曲では次を直す。

- `video/chaos_edit_v3.py` の `SECTIONS`（区間ごとのカット長・効果数・確率）
- `video/chaos_text_v5.py` の `CALM_UNTIL_FRAME`（ここまでは文字を控えめに）
- `video/spurt_layer_v2.py` の `F0, F1`（スパートの区間）
- `audio/breakcore_audio.py` の `PLAN`、`audio/breakcore_v2.py` の `RAMP_A, RAMP_B`・`SECTION_HITS`・`ROLL_INTO`・`voice_events`
- `examples/build_example.sh` の `SPURT_START`・`WARN_SEC`・`TAIL`

## 使い方の例

```bash
# 黒背景の動画を透過にする
python -I video/black_to_alpha.py overlay.mp4 overlay_alpha.mov --lo 10 --hi 48

# 曲（Suno の WAV と、remix_audio.py の stems から）
python -I audio/remix_audio.py song.wav remix.wav --stems remix_stems
python -I audio/breakcore_v2.py song.wav remix_stems mix.wav --piano-wav piano.wav --piano-gain 0.9 --more-drums --wreck --voice voice.wav --tail-extend 4.5

# 映像（変数はスクリプトの頭で設定する）
MODE=preview SCALE=1 bash examples/build_example.sh
MODE=final SCALE=2 bash examples/build_example.sh

# 確認
bash tools/contact_sheet.sh out.mp4 sheet.jpg 5
python -I tools/loudness_curve.py mix.wav --step 0.5
python -I tools/compare_versions.py video a.mp4 b.mp4
bash tools/export_for_x.sh out.mp4 x_out all
```

## 権利

- コードと文書（`*.py`、`*.sh`、`*.md`、`.claude/` など）：[MIT License](LICENSE)（範囲は [NOTICE](NOTICE)）
- 素材（`media/images/` の画像、リリースのカット・音・完成版の動画）：MIT の対象外。キャラクターを含め、すべての権利は作者（yutayuta-8e）が持つ。使いたいときは作者に確認すること
- フォント：多くは「フォントのファイルの再配布・販売」だけを禁止している。文字を描き込んだ動画の加工・拡大は問題ない。書体ごとに同梱の規約を読む
- Suno の曲を商用に使う条件は、有料プランでの生成と公式ダウンロード
- Salamander Grand Piano V3 は CC BY 3.0（`Piano: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0)`）
