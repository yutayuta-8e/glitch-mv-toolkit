#!/usr/bin/env bash
# 素材 → カット → 文字の層 → 終盤スパート → 注意書き → 組み立て、までの流れの例。
# 「見てるよ」（106 秒、21:9）で使った手順を、パスを変数にして書き直したもの。
# 使い方: MODE=preview|final SCALE=1|2 bash examples/build_example.sh
#   preview : 1280 幅・速い設定で確認用（全体で数分）
#   final   : CRF18 slow の本番。SCALE=2 で 3840×1632（4K）に描き直す
# 曲の区間（秒）は video/chaos_edit_v3.py の SECTIONS と、下の SPURT_START に入っている。別の曲では直す。
set -euo pipefail

MODE=${MODE:-preview}
SCALE=${SCALE:-1}
TOOLKIT=${TOOLKIT:-$(cd "$(dirname "$0")/.." && pwd)}

# ---- ここを自分の環境に合わせる ---------------------------------------------
WORK=${WORK:-$TOOLKIT/_work}                # 一時ファイル（数 GB になる）
CUTS=${CUTS:-$WORK/cuts}                    # カット（*.mp4）と透過オーバーレイ（*_alpha.mov）
SONG_SRC=${SONG_SRC:-$WORK/song_src.wav}    # 元の曲（長さを決めるのに使う）
MIX=${MIX:-$WORK/mix.wav}                   # 完成した曲（audio/breakcore_v2.py の出力）
FONTS=${FONTS:-$TOOLKIT/fonts}              # 文字の層に使う書体（書体ごとのサブフォルダ）
FABLE_FONTS=${FABLE_FONTS:-$TOOLKIT/fonts_fable}  # スパートの層の書体（video/fable_render/render.py の F の名前）
UI_FONT=${UI_FONT:-C:/Windows/Fonts/BIZ-UDGothicB.ttc}  # 古い注意書き・一瞬の文字の書体（ゴシック）
WARN_TITLE_FONT=${WARN_TITLE_FONT:-$FONTS/shitataru-mincho/ShitataruMinchoShogo-EB.ttf}
WARN_BODY_FONT=${WARN_BODY_FONT:-$FONTS/maboroshi-nijimi-mincho/幻ノにじみ明朝.otf}
PLAN=${PLAN:-}                               # 既存の plan.json を使うとき（並びを固定する）
OUT=${OUT:-$WORK/out_${MODE}_x${SCALE}.mp4}
WARN_SEC=7          # 冒頭の注意書きの秒数
SPURT_START=62.4    # 終盤スパートの始まり（曲の秒）
TAIL=4.5            # 最後に足す黒の秒数（曲の余韻に合わせる）
# ------------------------------------------------------------------------------

S=$SCALE
W=$(python -c "print(int(1920*$S))"); H=$(python -c "print(int(816*$S))")
E="$WORK/edit_x$S"; T="$WORK/text_x$S"; mkdir -p "$E" "$T"
cp "$UI_FONT" "$E/warn.ttc"; cp "$UI_FONT" "$E/dot.ttf"; cp "$UI_FONT" "$T/warn.ttc"

# 1) 注意書き（静止、にじみ明朝）
python -I "$TOOLKIT/video/warn_4k.py" "$WARN_TITLE_FONT" "$WARN_BODY_FONT" "$WORK/warn_x$S.png" "$S"
ffmpeg -v error -y -loop 1 -framerate 24 -t $WARN_SEC -i "$WORK/warn_x$S.png" \
  -vf "vignette=PI/3.5,fade=t=in:st=0:d=0.5,fade=t=out:st=$(python -c "print($WARN_SEC-0.5)"):d=0.5,format=yuv420p" \
  -r 24 -c:v libx264 -crf 14 "$WORK/warn_x$S.mp4"

# 2) カオス編集のカット
python -I "$TOOLKIT/video/chaos_edit_v3.py" --cuts "$CUTS" --audio "$SONG_SRC" --out unused --tmp "$E" \
  --scale "$S" --segments-only ${PLAN:+--plan "$PLAN"}

# 3) 文字の層
FLAG=$([ "$MODE" = preview ] && echo --preview || echo --segments-only)
python -I "$TOOLKIT/video/chaos_text_v5.py" --v2tmp "$E" --fonts "$FONTS" --audio unused --out unused --tmp "$T" \
  --seed 7 --scale "$S" $FLAG

# 4) 終盤スパートの文字の層（透明 MOV）
GLITCH_MV_FABLE_FONTS="$FABLE_FONTS" python -I "$TOOLKIT/video/spurt_layer_v2.py" "$TOOLKIT/video/fable_render" "$WORK/spurt_x$S.mov" "$S"

# 5) 並べて、スパートを重ね、仕上げをかけ、曲を付ける
python -I - "$T" "$WORK/warn_x$S.mp4" <<'PYEOF'
import sys, os
T, warn = sys.argv[1:3]
lines = open(os.path.join(T, "list.txt"), encoding="utf-8").read().splitlines()
open(os.path.join(T, "list_final.txt"), "w", encoding="utf-8", newline="\n").write(
    "\n".join([f"file '{warn}'"] + lines[1:]) + "\n")  # 1 行目（古い注意書き）を差し替える
PYEOF
ffmpeg -v error -y -f concat -safe 0 -i "$T/list_final.txt" -c copy "$T/base.mp4"
OFFSET=$(python -c "print(round($WARN_SEC + round($SPURT_START*24)/24, 6))")
G=$(python -c "print(int(4*$S))"); GT=$(python -c "print(max(1,int($S)))"); SH=$(python -c "print(int(4*$S))")
FIN="drawgrid=w=iw:h=$G:t=$GT:c=black@0.35,rgbashift=rh=-$SH:bh=$SH,vignette=PI/4,noise=alls=12:allf=t"
if [ "$MODE" = preview ]; then POST=",scale=1280:-2"; ENC="-c:v libx264 -crf 23 -preset veryfast -c:a aac -b:a 192k"
else POST=""; ENC="-c:v libx264 -crf 18 -preset slow -c:a aac -b:a 320k"; fi
ffmpeg -v error -y -i "$T/base.mp4" -itsoffset "$OFFSET" -i "$WORK/spurt_x$S.mov" -i "$MIX" \
  -filter_complex "[1:v]format=yuva444p10le[sp];[0:v]tpad=stop_mode=add:stop_duration=$TAIL:color=black[bv];[bv][sp]overlay=eof_action=pass:format=auto,$FIN$POST,format=yuv420p[v];[2:a]adelay=${WARN_SEC}000|${WARN_SEC}000,apad[a]" \
  -map "[v]" -map "[a]" $ENC -shortest "$OUT"
echo "done $OUT ($W x $H source)"
