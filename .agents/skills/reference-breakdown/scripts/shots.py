#!/usr/bin/env python3
"""Cut detection, one frame per shot and a labelled contact sheet for a reference ad. Free, local.

  python3 shots.py refs/ref1.mp4                     # -> renders/_work/ref1/shots.json, frames/, contact.jpg
  python3 shots.py refs/ref1.mp4 --threshold 0.10    # lower = more cuts found (use on soft cuts, punch-ins)
  python3 shots.py frames refs/ref1.mp4 --start 1.2 --end 3.0 --step 0.1
                                                     # dense frames to time on-screen text on and off

Run from the ad folder. Needs ffmpeg and Pillow (pip install pillow).
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Install Pillow first: pip install pillow")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                         capture_output=True, text=True).stdout
    p = json.loads(out)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    num, den = v.get("avg_frame_rate", "30/1").split("/")
    return {"duration": float(p["format"]["duration"]), "width": int(v["width"]), "height": int(v["height"]),
            "fps": round(float(num) / float(den or 1), 3), "has_audio": any(s["codec_type"] == "audio" for s in p["streams"])}


def detect_cuts(path, threshold, min_gap):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-an", "-vf", f"select='gt(scene,{threshold})',showinfo",
                        "-f", "null", "-"], capture_output=True, text=True)
    times = [float(t) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    cuts, last = [], 0.0
    for t in times:
        if t - last >= min_gap:
            cuts.append(round(t, 3))
            last = t
    return cuts


def grab(path, t, out, width=360):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                    "-vf", f"scale={width}:-2", "-q:v", "3", out], check=True)


def font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def contact_sheet(shots, out, cols=6, thumb_w=240):
    thumbs = [Image.open(s["frame"]).convert("RGB") for s in shots]
    th = int(thumbs[0].height * thumb_w / thumbs[0].width)
    label_h = 26
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (th + label_h)), "white")
    d, f = ImageDraw.Draw(sheet), font(16)
    for i, (s, im) in enumerate(zip(shots, thumbs)):
        x, y = (i % cols) * thumb_w, (i // cols) * (th + label_h)
        sheet.paste(im.resize((thumb_w, th)), (x, y + label_h))
        d.text((x + 4, y + 4), f"#{s['n']:02d}  {s['start']:.2f}-{s['end']:.2f}s", fill="black", font=f)
    sheet.save(out, quality=88)


def breakdown(a):
    info = probe(a.video)
    name = os.path.splitext(os.path.basename(a.video))[0]
    out_dir = a.out_dir or os.path.join("renders", "_work", name)
    frames = os.path.join(out_dir, "frames")
    os.makedirs(frames, exist_ok=True)
    cuts = detect_cuts(a.video, a.threshold, a.min_gap)
    edges = [0.0] + cuts + [info["duration"]]
    shots = []
    for i in range(len(edges) - 1):
        s, e = edges[i], edges[i + 1]
        if e - s < 0.04:
            continue
        n = len(shots) + 1
        fr = os.path.join(frames, f"shot_{n:02d}.jpg")
        grab(a.video, s + (e - s) / 2, fr)
        shots.append({"n": n, "start": round(s, 3), "end": round(e, 3), "dur": round(e - s, 3), "frame": fr})
    sheet = os.path.join(out_dir, "contact.jpg")
    contact_sheet(shots, sheet)
    durs = [s["dur"] for s in shots]
    longest = max(shots, key=lambda s: s["dur"])
    data = {"source": a.video, "threshold": a.threshold, **info, "cuts": cuts, "shots": shots,
            "avg_shot_s": round(sum(durs) / len(durs), 3), "longest_shot": longest["n"]}
    with open(os.path.join(out_dir, "shots.json"), "w") as f:
        json.dump(data, f, indent=1)
    print(f"{a.video}: {info['width']}x{info['height']} {info['fps']} fps, {info['duration']:.2f} s, "
          f"audio: {'yes' if info['has_audio'] else 'no'}")
    print(f"{len(shots)} shots, average {data['avg_shot_s']:.2f} s, longest #{longest['n']} ({longest['dur']:.2f} s)")
    print(f"-> {out_dir}/shots.json, {sheet}, {frames}/")


def dense(a):
    name = os.path.splitext(os.path.basename(a.video))[0]
    out_dir = os.path.join(a.out_dir or os.path.join("renders", "_work", name), "dense")
    os.makedirs(out_dir, exist_ok=True)
    t, shots = a.start, []
    while t <= a.end + 1e-6:
        fr = os.path.join(out_dir, f"t_{t:07.3f}.jpg")
        grab(a.video, t, fr, width=480)
        shots.append({"n": len(shots) + 1, "start": round(t, 3), "end": round(t + a.step, 3), "frame": fr})
        t += a.step
    sheet = os.path.join(out_dir, f"dense_{a.start:.2f}-{a.end:.2f}.jpg")
    contact_sheet(shots, sheet, cols=5, thumb_w=288)
    print(f"{len(shots)} frames -> {sheet}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd")
        ap.add_argument("video")
        ap.add_argument("--start", type=float, required=True)
        ap.add_argument("--end", type=float, required=True)
        ap.add_argument("--step", type=float, default=0.1)
        ap.add_argument("--out-dir", default=None)
        dense(ap.parse_args())
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--threshold", type=float, default=0.15)
    ap.add_argument("--min-gap", type=float, default=0.3, help="ignore a cut closer than this to the previous one")
    ap.add_argument("--out-dir", default=None)
    breakdown(ap.parse_args())


if __name__ == "__main__":
    main()
