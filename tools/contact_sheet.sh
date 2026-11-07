#!/usr/bin/env bash
# 動画の N 秒ごとのコマを並べた一覧（AI が画像で中身を確かめる用）。
# 使い方: bash tools/contact_sheet.sh <動画> <出力.jpg> [間隔の秒=5] [開始の秒=0] [列x行=5x4]
set -euo pipefail
IN=$1; OUT=$2; EVERY=${3:-5}; START=${4:-0}; GRID=${5:-5x4}
ffmpeg -v error -y -ss "$START" -i "$IN" -vf "fps=1/$EVERY,scale=320:-1,tile=$GRID" -frames:v 1 "$OUT"
echo "$OUT"
