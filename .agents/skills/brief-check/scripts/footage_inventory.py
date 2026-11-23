#!/usr/bin/env python3
"""List every media file in a folder with what an editor needs to know before the first cut.

  python3 footage_inventory.py footage/                 # prints a Markdown table
  python3 footage_inventory.py footage/ --csv renders/_work/inventory.csv

Columns: file, duration, size as displayed (rotation applied), ratio, fps, codec, audio, flags.
Flags: ROTATED (phone metadata turns it), VFR (variable frame rate, conform before editing),
LOW_RES (short side under 1080), NO_AUDIO, SHORT (under 1 s).
"""
import argparse
import csv
import json
import os
import subprocess
from fractions import Fraction

MEDIA = {".mp4", ".mov", ".m4v", ".mkv", ".mxf", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".aac",
         ".png", ".jpg", ".jpeg", ".webp", ".heic"}
RATIOS = {"9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1.0, "16:9": 16 / 9, "3:4": 3 / 4, "2:3": 2 / 3}


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                         capture_output=True, text=True).stdout
    return json.loads(out or "{}")


def rotation(v):
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(float(sd["rotation"]))
    return int(v.get("tags", {}).get("rotate", 0) or 0)


def nearest_ratio(w, h):
    r = w / h
    name, val = min(RATIOS.items(), key=lambda kv: abs(kv[1] - r))
    return name if abs(val - r) < 0.02 else f"{w}:{h}"


def row(path):
    p = probe(path)
    streams = p.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(p.get("format", {}).get("duration", 0) or 0)
    flags = []
    size = ratio = fps = codec = "-"
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rot = rotation(v)
        if abs(rot) in (90, 270):
            w, h = h, w
            flags.append("ROTATED")
        size, codec = f"{w}x{h}", v.get("codec_name", "?")
        ratio = nearest_ratio(w, h) if w and h else "-"
        rf, af = v.get("r_frame_rate", "0/1"), v.get("avg_frame_rate", "0/1")
        try:
            rfv, afv = float(Fraction(rf)), float(Fraction(af))
            fps = f"{afv:.3f}".rstrip("0").rstrip(".")
            if dur > 1 and afv and abs(rfv - afv) > 0.5:
                flags.append("VFR")
        except (ZeroDivisionError, ValueError):
            pass
        if min(w, h) < 1080 and dur > 0:
            flags.append("LOW_RES")
    if not a and dur > 0:
        flags.append("NO_AUDIO")
    if 0 < dur < 1:
        flags.append("SHORT")
    return {"file": os.path.relpath(path), "duration_s": f"{dur:.2f}" if dur else "-", "size": size, "ratio": ratio,
            "fps": fps, "codec": codec, "audio": "yes" if a else "no", "flags": " ".join(flags)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    files = sorted(os.path.join(d, f) for d, _, fs in os.walk(a.folder) for f in fs
                   if os.path.splitext(f)[1].lower() in MEDIA and not f.startswith("."))
    rows = [row(f) for f in files]
    cols = ["file", "duration_s", "size", "ratio", "fps", "codec", "audio", "flags"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")
    total = sum(float(r["duration_s"]) for r in rows if r["duration_s"] != "-")
    print(f"\n{len(rows)} files, {total:.1f} s of media")
    if a.csv:
        os.makedirs(os.path.dirname(os.path.abspath(a.csv)), exist_ok=True)
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"-> {a.csv}")


if __name__ == "__main__":
    main()
