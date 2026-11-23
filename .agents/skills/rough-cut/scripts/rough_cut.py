#!/usr/bin/env python3
"""Rough cut from the take map: best take per line, in script order, dead air and fillers removed.

  python3 rough_cut.py renders/_work/takes.json --hook H1              # -> renders/rough_v1.mp4 + .edl + .csv
  python3 rough_cut.py renders/_work/takes.json --hook H2 --ratio 4:5 --name ACME_2610-S3
                                       # -> renders/ACME_2610-S3_H2_4x5_v1_rough.mp4
  python3 rough_cut.py renders/_work/takes.json --hook H1 --plan-only  # print the cut list, render nothing

Order: the chosen hook, then every line that is not a hook (B1, B2..., CTA) in script order.
Inside each line, pauses longer than --max-pause (measured with ffmpeg silencedetect) are cut out,
and filler words (um, uh) are cut when --cut-fillers is set.
Outputs: the video, a CMX3600 EDL (imports into Premiere Pro, DaVinci Resolve, Avid) and a CSV cut list.
Free, local. Needs ffmpeg. Input = takes.json from take_diff.py.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys

FILLERS = {"um", "uh", "er", "erm", "ah", "hmm", "mm", "uhm"}
SIZES = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}


def silences(path, noise_db, min_d):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_d}",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    if len(ends) < len(starts):
        ends.append(1e9)
    return list(zip(starts, ends))


def source_tc_offset(path, fps):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=timecode:stream_tags=timecode",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout.split()
    if not out:
        return 0.0
    h, m, s, f = [int(x) for x in re.split(r"[:;]", out[0])]
    return h * 3600 + m * 60 + s + f / fps


def split_segment(seg, sil, max_pause, keep, words, cut_fillers):
    """Cut the inside of one line at long silences and (optionally) at filler words."""
    holes = []
    for s, e in sil:
        if e - s > max_pause and s > seg[0] and e < seg[1]:
            holes.append((s + keep, e - keep))
    if cut_fillers:
        for i, w in enumerate(words):
            if re.sub(r"[^\w]", "", w["text"].lower()) in FILLERS:
                a = words[i - 1]["end"] + 0.02 if i > 0 else w["start"]
                b = words[i + 1]["start"] - 0.02 if i + 1 < len(words) else w["end"]
                holes.append((a, b))
    holes = sorted(h for h in holes if h[1] > h[0])
    parts, cur = [], seg[0]
    for a, b in holes:
        if a > cur:
            parts.append((cur, a))
        cur = max(cur, b)
    if seg[1] > cur:
        parts.append((cur, seg[1]))
    return [p for p in parts if p[1] - p[0] >= 0.12]


def tc(t, fps):
    f = int(round(t * fps))
    return f"{f // (3600 * fps):02d}:{f // (60 * fps) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def next_version(base, suffix=""):
    v = 1
    while os.path.exists(f"{base}_v{v}{suffix}.mp4"):
        v += 1
    return f"{base}_v{v}{suffix}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("takes")
    ap.add_argument("--hook", default="H1")
    ap.add_argument("--ratio", default="9:16", choices=list(SIZES))
    ap.add_argument("--name", default=None, help="the ad name (BRAND_CONCEPT), used in the file name")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--max-pause", type=float, default=0.35, help="cut any pause inside a line longer than this")
    ap.add_argument("--keep", type=float, default=0.06, help="seconds of pause kept on each side of a cut")
    ap.add_argument("--noise", type=float, default=-35, help="silence threshold in dB; raise to -30 in noisy rooms")
    ap.add_argument("--cut-fillers", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()

    data = json.load(open(a.takes, encoding="utf-8"))
    lines = data["lines"]
    hook = [l for l in lines if l["id"] == a.hook.upper()]
    if not hook:
        sys.exit(f"No line {a.hook} in {a.takes}. Hooks found: {', '.join(l['id'] for l in lines if l['id'].startswith('H'))}")
    order = hook + [l for l in lines if not re.match(r"^H\d+$", l["id"])]
    missing = [l["id"] for l in order if not l["best"]]
    if missing:
        print(f"WARNING: no take for {', '.join(missing)}. They are left out of the cut.")
    order = [l for l in order if l["best"]]

    sil_cache, cuts = {}, []
    for l in order:
        b = l["best"]
        if b["file"] not in sil_cache:
            sil_cache[b["file"]] = silences(b["file"], a.noise, a.max_pause)
        for s, e in split_segment((b["in"], b["out"]), sil_cache[b["file"]], a.max_pause, a.keep,
                                  b.get("words", []), a.cut_fillers):
            cuts.append({"line": l["id"], "file": b["file"], "in": round(s, 3), "out": round(e, 3)})

    rec = 0.0
    for c in cuts:
        c["rec_in"], c["rec_out"] = rec, rec + (c["out"] - c["in"])
        rec = c["rec_out"]
    print(f"{len(cuts)} cuts from {len(order)} lines, {rec:.2f} s total")
    for i, c in enumerate(cuts, 1):
        print(f"{i:03d} {c['line']:<5} {os.path.basename(c['file']):<28} {c['in']:8.3f} -> {c['out']:8.3f}")
    if a.plan_only:
        return

    os.makedirs("renders", exist_ok=True)
    ratio_tag = a.ratio.replace(":", "x")
    base = (next_version(os.path.join("renders", f"{a.name}_{a.hook.upper()}_{ratio_tag}"), "_rough") if a.name
            else next_version(os.path.join("renders", "rough")))
    W, H = SIZES[a.ratio]
    cmd, fc = ["ffmpeg", "-v", "error", "-y"], []
    for i, c in enumerate(cuts):
        d = c["out"] - c["in"]
        cmd += ["-ss", f"{c['in']:.3f}", "-t", f"{d:.3f}", "-i", c["file"]]
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={a.fps},"
                  f"format=yuv420p[v{i}]")
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.01,"
                  f"afade=t=out:st={max(d - 0.01, 0):.3f}:d=0.01[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", base + ".mp4"]
    subprocess.run(cmd, check=True)

    offsets = {f: source_tc_offset(f, a.fps) for f in sil_cache}
    with open(base + ".edl", "w") as f:   # whole frames, so source and record durations always match
        f.write(f"TITLE: {os.path.basename(base)}\nFCM: NON-DROP FRAME\n\n")
        rec_f = 3600 * a.fps
        for i, c in enumerate(cuts, 1):
            src_f = round((c["in"] + offsets[c["file"]]) * a.fps)
            dur_f = max(1, round((c["out"] - c["in"]) * a.fps))
            f.write(f"{i:03d}  AX       AA/V  C        {tc(src_f / a.fps, a.fps)} {tc((src_f + dur_f) / a.fps, a.fps)} "
                    f"{tc(rec_f / a.fps, a.fps)} {tc((rec_f + dur_f) / a.fps, a.fps)}\n")
            rec_f += dur_f
            f.write(f"* FROM CLIP NAME: {os.path.basename(c['file'])}\n* COMMENT: {c['line']}\n\n")
    with open(base + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "line", "file", "src_in_s", "src_out_s", "rec_in_s", "rec_out_s", "dur_s"])
        for i, c in enumerate(cuts, 1):
            w.writerow([i, c["line"], c["file"], f"{c['in']:.3f}", f"{c['out']:.3f}", f"{c['rec_in']:.3f}",
                        f"{c['rec_out']:.3f}", f"{c['out'] - c['in']:.3f}"])
    print(f"-> {base}.mp4, {base}.edl, {base}.csv")


if __name__ == "__main__":
    main()
