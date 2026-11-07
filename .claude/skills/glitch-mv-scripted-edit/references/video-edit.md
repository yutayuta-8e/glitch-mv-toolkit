# 映像の編集

読むタイミング：カオス編集・文字の層・スパート・注意書き・仕上げ・組み立てを作る／直すとき。

## 1. カオス編集（`video/chaos_edit_v2.py（4K 対応の後継 video/chaos_edit_v3.py）`）

```bash
python -I chaos_edit_v2.py --cuts <カットのフォルダ> --audio <曲.wav> --out <出力.mp4> --tmp <作業フォルダ> --seed 66
```

- 作業フォルダに `warn.ttc`（注意書き用）と `dot.ttf`（一瞬の文字用）を置く。ffmpeg はフォントを相対パスで読むので、作業フォルダを cwd にして動かす。
- `SECTIONS`：曲の区間ごとに、1 カットのコマ数の候補・同時にかける効果の数・オーバーレイ確率・色フラッシュ確率を決める。静かな区間は 18〜34 コマ、山場は 2〜4 コマ。最後の区間は黒。
- `EFFECTS`：rgbashift、negate、hue 回転、鏡写し（2 分割・4 分割）、9 分割、edgedetect、ポスター化、ソラリゼーション、pixelize、shufflepixels、lagfun、tmix、tblend（difference / xor）、stutter、zoom、rotate、魚眼、scroll、shake、strobe、noise、焼き込み、pseudocolor、チャンネル入れ替え。
- カットごとに速さ（0.5〜4 倍）・逆再生 35%・別カットとの blend（difference / screen / phoenix など）・透過オーバーレイ・頭 1 コマの色フラッシュ・2 コマだけの文字を乗せる。
- 出力は作業フォルダの `seg0000.mp4…` と `plan.json`。文字の層とスパートの層は、この plan を読む。

## 2. 文字の層（`video/chaos_text_v4.py（4K 対応の後継 video/chaos_text_v5.py）`）

```bash
python -I chaos_text_v4.py --v2tmp <chaos_edit の作業フォルダ> --fonts <フォントのフォルダ> --audio x --out x --tmp <新しい作業フォルダ> --seed 7 --preview
```

- `--preview`：カットを ultrafast で書き出して終わる。`--segments-only`：本番の画質（CRF14）でカットだけ書き出す。どちらも付けないと、最後に仕上げ付きの確認用 mp4 まで作る（遅い）。
- 作業フォルダに `warn.ttc` を置く。出力は `tseg*.mp4`、`list.txt`（1 行目が注意書き）、`text_log.json`（言葉・フォント・アウトラインか・フィルタ）。
- 同じ seed なら同じ配置になる。プレビューと本番で text_log の言葉とフォントが一致するのを確かめる。
- フォント：フォルダごとに ttf を 1 つ（無ければ otf）。除外は `SKIP_FONTS`（怪文書）、アウトラインに使わないのは `NO_OUTLINE_FONTS`（クロヌリ。塗り 70% で使う）。
- 豆腐チェック：`Coverage` クラス。文字を描いた結果を、無い字（U+E000）の描画と比べる。さらに、めったに使わない漢字 2 つ（龘・驫）が同じ形に描かれるならそれを「無い字の形」とみなす。
- スパート前（曲の 62.4 秒より前、`CALM_UNTIL_FRAME`）は控えめにする：文字の数を減らす（`COUNT_CALM`）、小さめ、アウトライン 80%、塗りは半透明。
- **アウトライン**は drawtext ではなく、PIL で「文字 − 内側に 6px 削った文字」（`scipy.ndimage.minimum_filter`）の輪郭を PNG にして、`overlay` で重ねる。drawtext の位置の式は overlay の式に読み替える（`tw,th → w,h`、`w,h → W,H`）。enable の点滅もそのまま移す。
- **縦書き**は1文字ずつ textfile を分けて描き、y をずらして積む。縦の列が画面の高さの 1.15 倍に収まる大きさにする。

## 3. 終盤スパートの文字の層（`video/spurt_layer_v2.py`）

```bash
python -I spurt_layer.py video/fable_render <出力.mov>
```

- `video/fable_render/render.py` の部品（言葉・フォント・豆腐チェック・text_layer）を使う。`render.py` は `環境変数 GLITCH_MV_PLAN の plan.json（スパートの層だけなら不要）` と `環境変数 GLITCH_MV_FABLE_FONTS のフォルダ（既定は video/fable_render/fonts2/）`（いいフォントと DelaGothicOne・DotGothic16・ZenMaruGothic）を読むので、この並びに置く。
- 曲の 62.4〜92 秒（710 コマ）を描く。文字の量は進み具合 p の累乗で増やす：流れる帯 `int(6*p**3.2)`、p>0.75 で文字の壁、p≥0.95 で塗りの壁、ばらまき `2+110*p**3.6`。画面の覆われ方は 30% 地点で 4%、50% で 20%、70% で 56%、90% で 92%、最後は 99.8%。
- 怪文書（'kaibun'）はモジュールの読み込み直後に候補から外している。10 プロセスで描いて ProRes 4444（アルファ付き）にする。v7 は 2 分 44 秒、約 1GB。
- 組み立てでは `-itsoffset 69.416667`（注意書き 7 秒＋曲の 62.4 秒、24fps のコマ境界）で重ねる。

## 4. 光過敏の注意書き

- `warning_designs.py`：10 案（黄黒ストライプ、ガラス、ビデオの青画面、黒塗り文書、ターミナル、したたる明朝、パステル、カウントダウン、監視カメラ、白黒分割）。依頼者の採用は 06（したたる明朝の赤い「警告」）。
- `warning06_v2.py <題名フォント> <本文フォント> <out.png> <out.mp4> [bleed]`：文字はインクの外枠（getbbox）で中央にそろえる。全角の句読点があると、文字の箱で中央にすると左右にずれるため。
- にじみ加工 2-B：`smooth(blur(a, 1.9), 0.22, 0.58)`（ガウスぼかし → smoothstep で締め直す）。角が丸くインクで膨らんだ見た目になる。「警告」も本文も同じ加工。比較は `bleed_variants.py`（10 案）、`bleed_v2_strength.py`（強さ 3 段階）。
- 書体：「警告」はしたたる明朝初号、本文と英語の見出しは幻ノにじみ明朝。
- 動きは付けない（依頼者「固定で大丈夫」）。7 秒の静止画の動画にする：

```bash
ffmpeg -loop 1 -framerate 24 -t 7 -i warn.png -vf "vignette=PI/3.5,fade=t=in:st=0:d=0.5,fade=t=out:st=6.5:d=0.5,format=yuv420p" -c:v libx264 -crf 14 warn.mp4
```

- 曲は注意書きの後から始める（`adelay=7000|7000`）。

## 5. 仕上げと組み立て（`examples/build_example.sh`）

- 並べる：`list.txt` の 1 行目（古い注意書き）を採用版の注意書きに差し替え、concat demuxer の `-c copy` でつなぐ。
- 余韻のぶん黒を足す：`tpad=stop_mode=add:stop_duration=4.5:color=black`。
- 仕上げのチェーン（全編共通）：

```text
[1:v]format=yuva444p10le[sp];[0:v]tpad=...[bv];[bv][sp]overlay=eof_action=pass:format=auto,drawgrid=w=iw:h=4:t=1:c=black@0.35,rgbashift=rh=-4:bh=4,vignette=PI/4,noise=alls=12:allf=t,format=yuv420p[v]
```

- プレビューは、このあとに `scale=1280:-2` を足して CRF23 veryfast・AAC 192k。本番は CRF18 slow・AAC 320k。`-shortest` で曲の長さに合わせる。

## 6. 4K で描き直す（2026-11-07）

依頼者が「最終版をアップスケールしたい」と言ったときは、AI アップスケールより描き直しを勧めた。小さな文字・走査線・粒子を AI が描き直して崩しやすく、外部サービスへの送信も要るため。素材の H3 カットは 2944×1248 あるので、絵も 1920 より細かい。

- カット：`chaos_edit_v3.py --plan <v2 の plan.json> --scale 2 --segments-only`（並びは v2 と同じ。色ずれ・ブロック・揺れ・一瞬の文字も 2 倍、縮小は lanczos）
- 文字：`chaos_text_v5.py --scale 2 --segments-only --seed 7`（乱数の引き方は v4 と同じ。大きさ・縁・アウトラインの線 6→12px・速さ・震えを 2 倍）
- スパート：`spurt_layer_v2.py video/fable_render <out.mov> 2`（並列 4、文字のキャッシュ 80 で、メモリ 14GB の PC でも動く）
- 注意書き：`warn_4k.py <したたる明朝> <幻ノにじみ明朝> <out.png> 2`（倍率 1 で v7 の画像と画素まで一致）
- 組み立て：`examples/build_example.sh`（SCALE=2）（走査線 8px・太さ 2、RGB ずれ 8px）
- かかった時間（v7、14GB RAM の PC）：カット＋文字 22 分、スパート 12 分（並行）、組み立て 23 分。出力 3840×1632、約 5.4GB
- 確認：text_log の言葉・フォント・アウトラインが 1920 版と全一致、カットを縮めた差の平均 0.1〜2.8、スパートの覆われ方の割合が 1920 版と ±1% 以内
