#!/usr/bin/env bash
# 重い本番ファイルから、X（旧 Twitter）に投稿しやすい版を作る。H.264・2 パス・faststart・音はコピー。
# 2026-11 の実績：3840×1632・約 410Mbps・5.4GB の本番はパソコンのブラウザから投稿に失敗、
# 75Mbps・995MB の 4K 版は投稿できた（有料プラン）。X のヘルプでは無料は 140 秒・512MB まで。
# 使い方: bash tools/export_for_x.sh <本番.mp4> <出力フォルダ> [1080|4k|4k_grain|all]
#   1080     : 1920 幅に縮小、34Mbps（106 秒で約 450MB。無料アカウントの 512MB に収まる長さの目安は約 115 秒まで）
#   4k       : 解像度そのまま、75Mbps（106 秒で約 1GB）
#   4k_grain : 解像度そのまま、-tune grain、180Mbps（106 秒で約 2.4GB。粒子ノイズを残す。投稿できるかは未確認）
set -euo pipefail
IN=$1; OUTDIR=$2; WHICH=${3:-all}
mkdir -p "$OUTDIR"; BASE=$(basename "${IN%.*}")
LOG=$(mktemp -d)
enc() {  # 名前 縮小フィルタ ビットレート 最大 バッファ レベル 追加の設定
  local name=$1 vf=$2 b=$3 max=$4 buf=$5 lvl=$6 extra=${7:-}
  local out="$OUTDIR/${BASE}_X_${name}.mp4"
  [ -e "$out" ] && { echo "exists, skip: $out"; return; }
  ffmpeg -v error -y -i "$IN" -vf "$vf" -c:v libx264 -preset slow $extra -profile:v high -level "$lvl" \
    -b:v "$b" -maxrate "$max" -bufsize "$buf" -pass 1 -passlogfile "$LOG/p_$name" -an -f null -
  ffmpeg -v error -y -i "$IN" -vf "$vf" -c:v libx264 -preset slow $extra -profile:v high -level "$lvl" \
    -b:v "$b" -maxrate "$max" -bufsize "$buf" -pass 2 -passlogfile "$LOG/p_$name" -c:a copy -movflags +faststart "$out"
  ffprobe -v error -show_entries format=size,bit_rate:stream=width,height -of compact "$out"
}
case $WHICH in 1080|all) enc 1080 "scale=1920:-2:flags=lanczos,format=yuv420p" 34M 50M 68M 4.2 ;; esac
case $WHICH in 4k|all) enc 4k "format=yuv420p" 75M 110M 150M 5.1 ;; esac
case $WHICH in 4k_grain|all) enc 4k_grain "format=yuv420p" 180M 240M 360M 5.1 "-tune grain" ;; esac
rm -rf "$LOG"
