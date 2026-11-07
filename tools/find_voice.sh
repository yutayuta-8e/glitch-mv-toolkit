#!/usr/bin/env bash
# 生成動画の音から、セリフの場所を探すためのスペクトログラム（0〜8kHz、時間の目盛り付き）。
# 声は、倍音が横縞の束になって並ぶ帯として見える。見つけたら atrim でサンプル単位で切り出す：
#   ffmpeg -i <動画> -vn -af "atrim=start=<秒>:end=<秒>,asetpts=PTS-STARTPTS,highpass=f=160,afade=t=in:d=0.01,afade=t=out:st=<長さ-0.08>:d=0.08" -ar 48000 -ac 2 voice.wav
# 使い方: bash tools/find_voice.sh <動画か音> <開始の秒> <長さの秒> <出力.png>
set -euo pipefail
IN=$1; SS=$2; DUR=$3; OUT=$4
ffmpeg -v error -y -ss "$SS" -t "$DUR" -i "$IN" -vn -ac 1 \
  -lavfi "showspectrumpic=s=1300x360:legend=1:scale=log:stop=8000" "$OUT"
echo "$OUT"
