#!/usr/bin/env bash
# Original and edit next to each other at the same height, for the "only one thing changed" check. Free, local.
#   bash side_by_side.sh renders/gen/broll/stills/S03.png renders/gen/edits/S03_edit-light_v1.png [out.jpg]
# -> out.jpg, default renders/gen/edits/S03_edit-light_v1_compare.jpg
set -euo pipefail
A="$1"; B="$2"
OUT="${3:-${B%.*}_compare.jpg}"
ffmpeg -v error -y -i "$A" -i "$B" -filter_complex \
  "[0:v]scale=-2:1280,setsar=1[a];[1:v]scale=-2:1280,setsar=1[b];[a]pad=iw+16:ih:0:0:white[ap];[ap][b]hstack=inputs=2" \
  -frames:v 1 -q:v 3 "$OUT"
echo "$OUT"
