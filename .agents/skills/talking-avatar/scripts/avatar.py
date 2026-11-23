#!/usr/bin/env python3
"""Talking-avatar helper: split the voiceover, write the kie jobs file, assemble the finished clips.

Run from the ad folder.
  python3 avatar.py split  audio/vo/BRAND_CONCEPT_BODY_VO_v1.wav [--max 15]     # free: chunks at pauses, <= max s each
  python3 avatar.py jobs   --still renders/gen/avatar/still.png --name BRAND_CONCEPT [--prompt "..."] [--resolution 720p]
                                                       # free: writes renders/_work/avatar/avatar_jobs.json for kie.py
  python3 avatar.py finish --name BRAND_CONCEPT [--ratio 9:16]                # free: remux + one video per hook

Inputs it looks for (from the voiceover skill, run with --parts):
  audio/vo/<name>_H<n>_HOOKONLY_VO_v<k>.wav   one per hook (latest version wins)
  audio/vo/<name>_BODY_VO_v<k>.wav            the body, split into renders/_work/avatar/audio/BODY_01.mp3, BODY_02.mp3...
Outputs:
  renders/gen/avatar/clips/<chunk>.mp4                 from kie.py (one lip-synced clip per audio chunk)
  renders/<name>_H<n>_<ratio>_v<k>_avatar.mp4   hook + body, with the clean voiceover audio put back
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

SIZES = {"9:16": (1080, 1920), "4:5": (1080, 1350)}
DEFAULT_PROMPT = ("A person talking straight to the camera in a natural, relaxed way. Small natural head movements "
                  "and blinks, subtle hand gestures, mouth movements match the speech exactly. Phone camera look, "
                  "static framing, the background stays exactly as in the image.")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip())


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=lambda f: int(re.search(r"_v(\d+)\.wav$", f).group(1))) if files else None


def to_mp3(src, dst, start=None, end=None):
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}", "-to", f"{end:.3f}"]
    cmd += ["-i", src, "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", dst]
    subprocess.run(cmd, check=True)


def split(a):
    total = dur(a.audio)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.audio, "-af", "silencedetect=noise=-40dB:d=0.2", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    mids = [(s + e) / 2 for s, e in zip(st, en) if 0.3 < (s + e) / 2 < total - 0.3]
    os.makedirs("renders/_work/avatar/audio", exist_ok=True)
    for old in glob.glob("renders/_work/avatar/audio/BODY_*.mp3"):
        os.remove(old)
    start, n = 0.0, 0
    while start < total - 0.05:
        limit = start + a.max
        if limit >= total:
            end = total
        else:
            fits = [m for m in mids if start + 1.0 < m <= limit]
            end = fits[-1] if fits else limit
            if not fits:
                print(f"WARNING: no pause between {start:.2f} and {limit:.2f} s, hard cut at {end:.2f} s. "
                      "Check the join, or lower --max.")
        n += 1
        out = f"renders/_work/avatar/audio/BODY_{n:02d}.mp3"
        to_mp3(a.audio, out, start, end)
        print(f"{out}: {start:.2f} -> {end:.2f} s ({end - start:.2f} s)")
        start = end


def jobs(a):
    os.makedirs("renders/_work/avatar/audio", exist_ok=True)
    hooks = sorted({re.search(r"_(H\d+)_HOOKONLY_VO_v\d+\.wav$", f).group(1)
                    for f in glob.glob(f"audio/vo/{a.name}_H*_HOOKONLY_VO_v*.wav")})
    if not hooks:
        sys.exit(f"No hook files like audio/vo/{a.name}_H1_HOOKONLY_VO_v1.wav. Run the voiceover skill with --parts first.")
    chunks = []
    for h in hooks:
        out = f"renders/_work/avatar/audio/{h}.mp3"
        to_mp3(latest(f"audio/vo/{a.name}_{h}_HOOKONLY_VO_v*.wav"), out)
        chunks.append((h, out))
    body = sorted(glob.glob("renders/_work/avatar/audio/BODY_*.mp3"))
    if not body:
        sys.exit("No body chunks. Run: python3 avatar.py split audio/vo/<name>_BODY_VO_v1.wav")
    chunks += [(os.path.splitext(os.path.basename(b))[0], b) for b in body]
    spec = {"skill": "talking-avatar", "step": "avatar", "jobs": []}
    for cid, audio in chunks:
        if os.path.getsize(audio) > 10 * 1024 * 1024:
            sys.exit(f"{audio} is over 10 MB. Split it smaller.")
        spec["jobs"].append({"id": cid, "model": a.model, "out": f"renders/gen/avatar/clips/{cid}.mp4",
                             "input": {"prompt": a.prompt, "resolution": a.resolution},
                             "files": {"image_url": a.still, "audio_url": audio}})
    with open("renders/_work/avatar/avatar_jobs.json", "w") as f:
        json.dump(spec, f, indent=1)
    secs = sum(dur(c[1]) for c in chunks)
    print(f"{len(chunks)} clips ({', '.join(c[0] for c in chunks)}), {secs:.1f} s of audio -> renders/_work/avatar/avatar_jobs.json")
    print("Next: python3 <skill-dir>/scripts/kie.py quote renders/_work/avatar/avatar_jobs.json")


def fit(src, audio, out, W, H):
    """Scale the clip to the delivery size and put the clean voiceover chunk back as its only audio."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", out], check=True)


def finish(a):
    W, H = SIZES[a.ratio]
    tmp = "renders/_work/avatar/_fit"
    os.makedirs(tmp, exist_ok=True)
    os.makedirs("renders", exist_ok=True)
    body = sorted(glob.glob("renders/_work/avatar/audio/BODY_*.mp3"))
    hooks = sorted(glob.glob("renders/_work/avatar/audio/H*.mp3"))
    fitted = {}
    for audio in hooks + body:
        cid = os.path.splitext(os.path.basename(audio))[0]
        clip = f"renders/gen/avatar/clips/{cid}.mp4"
        if not os.path.exists(clip):
            sys.exit(f"Missing {clip}. Run kie.py run renders/_work/avatar/avatar_jobs.json first (after the OK).")
        drift = dur(clip) - dur(audio)
        if abs(drift) > 0.2:
            print(f"WARNING: {cid} video is {drift:+.2f} s off its audio. Check the lip sync at the end of the clip.")
        fitted[cid] = f"{tmp}/{cid}.mp4"
        fit(clip, audio, fitted[cid], W, H)
    for h in hooks:
        hid = os.path.splitext(os.path.basename(h))[0]
        parts = [fitted[hid]] + [fitted[os.path.splitext(os.path.basename(b))[0]] for b in body]
        lst = f"{tmp}/{hid}_list.txt"
        with open(lst, "w") as f:
            f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
        v = 1
        while os.path.exists(f"renders/{a.name}_{hid}_{a.ratio.replace(':', 'x')}_v{v}_avatar.mp4"):
            v += 1
        out = f"renders/{a.name}_{hid}_{a.ratio.replace(':', 'x')}_v{v}_avatar.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        "-movflags", "+faststart", out], check=True)
        print(f"{out} ({dur(out):.2f} s)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("audio")
    s.add_argument("--max", type=float, default=15.0, help="longest chunk in seconds; check the model's limit")
    j = sub.add_parser("jobs")
    j.add_argument("--still", required=True)
    j.add_argument("--name", required=True)
    j.add_argument("--model", default="infinitalk/from-audio")
    j.add_argument("--prompt", default=DEFAULT_PROMPT)
    j.add_argument("--resolution", default="720p")
    f = sub.add_parser("finish")
    f.add_argument("--name", required=True)
    f.add_argument("--ratio", default="9:16", choices=list(SIZES))
    a = ap.parse_args()
    {"split": split, "jobs": jobs, "finish": finish}[a.cmd](a)


if __name__ == "__main__":
    main()
