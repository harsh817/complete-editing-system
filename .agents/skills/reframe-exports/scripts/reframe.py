#!/usr/bin/env python3
"""reframe.py: reframe to 9:16 and 4:5, stitch every hook onto the body, render every hook x ratio, loudness-normalize.
Run from the ad folder. Needs ffmpeg + ffprobe. Face-aware crop needs opencv-python (optional).

  reframe.py probe FILE ...                         size, fps, duration, audio yes/no
  reframe.py reframe IN OUT --ratio 9x16|4x5 [--mode crop|pad|blur] [--x 0.5] [--face]
                                                    one file to one ratio (no stitch, no loudness pass)
  reframe.py faces IN                               horizontal face centre (0..1) sampled over the clip
  reframe.py plan                                   write an example renders/_work/plan.json
  reframe.py render [--plan P] [--only H1,H2] [--bump] [--final]
                                                    every hook x ratio: stitch hook + body, reframe, two-pass
                                                    loudnorm -> renders/<AD>_<HOOK>_<RATIO>_v#_clean.mp4
                                                    (--final: no _clean suffix, for ads with no burned text)
  reframe.py export [FILES ...] [--version v2]      copy final-named renders into exports/9x16/ and exports/4x5/,
                                                    name regex check, never overwrite, one measured row per file
  reframe.py loudness FILE ...                      integrated LUFS, true peak, LRA

Ratio tokens are 9x16 and 4x5 (1080x1920 and 1080x1350). Names: ACME_2610-S3_H1_9x16_v1.mp4.
Loudness target and true peak come from LOUDNESS_TARGET_LUFS and TRUE_PEAK_DBTP in AGENTS.md when set."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

SIZES = {"9x16": (1080, 1920), "4x5": (1080, 1350), "1x1": (1080, 1080)}
NAME_RE = r"^[A-Z]{3,4}_\d{4}-S\d+(-[A-Za-z0-9]+)?_(H\d+|BODY)_(9x16|4x5)_v\d+\.mp4$"
EXAMPLE_PLAN = {
    "name": "ACME_2610-S3", "version": 1,
    "hooks": {"H1": "footage/hook1.mp4", "H2": "footage/hook2.mp4"},
    "body": "footage/body.mp4",
    "endcard": None,
    "ratios": ["9x16", "4x5"],
    "mode": "crop",
    "x": 0.5,
    "face": False,
    "fps": 30,
    "lufs": -14.0, "tp": -1.0, "lra": 11.0,
    "crf": 18,
    "out_dir": "renders"
}
PLAN = "renders/_work/plan.json"


def house_var(name, default):
    """read NAME = value from the workspace AGENTS.md (two folders up from ads/<AD>/)"""
    for p in [Path.cwd(), *Path.cwd().parents]:
        f = p / "AGENTS.md"
        if f.exists():
            m = re.search(rf"{name}\s*=\s*(-?[0-9.]+)", f.read_text(encoding="utf-8"))
            if m:
                return float(m.group(1))
    return default


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def probe(f):
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
             "-of", "json", f])
    if r.returncode:
        raise SystemExit(f"ffprobe failed on {f}: {r.stderr.strip()[:200]}")
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = any(s["codec_type"] == "audio" for s in j["streams"])
    if not v:
        raise SystemExit(f"{f} has no video stream")
    n, d = v["r_frame_rate"].split("/")
    return dict(w=int(v["width"]), h=int(v["height"]), fps=round(float(n) / float(d or 1), 3),
                dur=float(j["format"]["duration"]), audio=a)


def face_x(f, samples=12):
    """median horizontal face centre (0..1) over sampled frames, or None when no face or no opencv"""
    try:
        import cv2
    except ImportError:
        print("  face-aware crop needs opencv-python (pip install opencv-python): using the fixed x instead")
        return None
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(f))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    xs = []
    for i in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (i + 0.5) / samples))
        ok, img = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cas.detectMultiScale(g, 1.1, 5, minSize=(g.shape[0] // 12, g.shape[0] // 12))
        if len(faces):
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / g.shape[1])
    cap.release()
    if not xs:
        return None
    xs.sort()
    return round(xs[len(xs) // 2], 3)


def frame_filter(ratio, mode, x, fps, tag="0"):
    """video filter chain: any input -> exact ratio size, square pixels, constant fps"""
    W, H = SIZES[ratio]
    x = min(max(float(x), 0.0), 1.0)
    if mode == "crop":
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}:(iw-{W})*{x}:(ih-{H})/2,setsar=1,fps={fps},format=yuv420p")
    if mode == "pad":
        return (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=yuv420p")
    if mode == "blur":
        return (f"split[a{tag}][b{tag}];[a{tag}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=30:3[bg{tag}];[b{tag}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{tag}];"
                f"[bg{tag}][fg{tag}]overlay=(W-w)/2:(H-h)/2,"
                f"setsar=1,fps={fps},format=yuv420p")
    raise SystemExit(f"mode must be crop, pad or blur, not {mode}")


def segment_graph(files, ratio, mode, xs, fps):
    """filter_complex that reframes every input and concatenates them. Inputs without audio get silence, so the
    concat filter always sees one video and one audio per segment (the concat demuxer breaks on mixed inputs)."""
    parts, labels = [], []
    for i, (f, x) in enumerate(zip(files, xs)):
        p = probe(f)
        parts.append(f"[{i}:v]{frame_filter(ratio, mode, x, fps, i)}[v{i}]")
        if p["audio"]:
            parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={p['dur']:.3f}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append("".join(labels) + f"concat=n={len(files)}:v=1:a=1[v][a]")
    return ";".join(parts)


def loudness(f, lufs=-14.0, tp=-1.0, lra=11.0):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-vn", "-af",
             f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"])
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise SystemExit(f"loudness measure failed on {f}: {r.stderr[-300:]}")
    return json.loads(m[-1])


def next_version(out_dir, stem_no_v, start, suf=""):
    v = start
    while (out_dir / f"{stem_no_v}_v{v}{suf}.mp4").exists() or any(Path("exports").glob(f"*/{stem_no_v}_v{v}.mp4")):
        v += 1
    return v


def render(plan_path=PLAN, only=None, bump=False, final=False):
    if not Path(plan_path).exists():
        raise SystemExit(f"{plan_path} not found: run  reframe.py plan  and edit it")
    P = {**EXAMPLE_PLAN, "lufs": house_var("LOUDNESS_TARGET_LUFS", -14.0), "tp": house_var("TRUE_PEAK_DBTP", -1.0),
         **json.loads(Path(plan_path).read_text(encoding="utf-8"))}
    out_dir = Path(P["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    body = [P["body"]] if P.get("body") else []
    tail = [P["endcard"]] if P.get("endcard") else []
    for f in list(P["hooks"].values()) + body + tail:
        if not Path(f).exists():
            raise SystemExit(f"missing input: {f}")
    face_cache = {}

    def xpos(f):
        if not P["face"] or P["mode"] != "crop":
            return P["x"]
        if f not in face_cache:
            face_cache[f] = face_x(f)
            print(f"  face centre {f}: {face_cache[f] if face_cache[f] is not None else 'none found, fixed x'}")
        return face_cache[f] if face_cache[f] is not None else P["x"]

    hooks = [h for h in P["hooks"] if not only or h in only]
    for hook in hooks:
        files = [P["hooks"][hook]] + body + tail
        for ratio in P["ratios"]:
            if ratio not in SIZES:
                raise SystemExit(f"unknown ratio {ratio}: use one of {', '.join(SIZES)}")
            stem = f"{P['name']}_{hook}_{ratio}"
            suf = "" if final else "_clean"
            v = int(P["version"])
            if (out_dir / f"{stem}_v{v}{suf}.mp4").exists():
                if not bump:
                    print(f"skip {stem}_v{v}{suf}.mp4: exists (use --bump for a new version, files are never overwritten)")
                    continue
                v = next_version(out_dir, stem, v, suf)
            out = out_dir / f"{stem}_v{v}{suf}.mp4"
            tmp = Path(tempfile.mkdtemp()) / "stitched.mp4"
            graph = segment_graph(files, ratio, P["mode"], [xpos(f) for f in files], P["fps"])
            args = ["ffmpeg", "-v", "error", "-y"]
            for f in files:
                args += ["-i", f]
            r = run(args + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
                            "-crf", P["crf"], "-c:a", "pcm_s16le", tmp.with_suffix(".mov")])
            if r.returncode:
                raise SystemExit(f"stitch failed for {stem}: {r.stderr[-400:]}")
            tmp = tmp.with_suffix(".mov")
            m = loudness(tmp, P["lufs"], P["tp"], P["lra"])
            af = (f"loudnorm=I={P['lufs']}:TP={P['tp']}:LRA={P['lra']}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                  f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
                  f"aresample=48000")
            r = run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", af,
                     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
            if r.returncode:
                raise SystemExit(f"loudness pass failed for {stem}: {r.stderr[-400:]}")
            after = loudness(out, P["lufs"], P["tp"], P["lra"])
            p = probe(out)
            print(f"{out.name}: {p['w']}x{p['h']} {p['fps']}fps {p['dur']:.2f}s | "
                  f"{float(m['input_i']):.1f} -> {float(after['input_i']):.1f} LUFS, TP {float(after['input_tp']):.1f} dBTP")


def export(files):
    """final-named files from renders/ -> exports/<ratio>/. Suffixed work files never go to exports/."""
    files = files or sorted(str(p) for p in Path("renders").glob("*.mp4") if re.match(NAME_RE, p.name))
    if not files:
        raise SystemExit("no final-named files in renders/ (work files with _clean, _rough or _review never export)")
    print("| file | ok | size | fps | s | LUFS | dBTP | MB |\n|---|---|---|---|---|---|---|---|")
    for f in files:
        name = Path(f).name
        if not re.match(NAME_RE, name):
            print(f"| {name} | NAME FAILS {NAME_RE} | | | | | | |")
            continue
        ratio = re.search(r"_(9x16|4x5)_", name).group(1)
        dst = Path("exports") / ratio / name
        if dst.exists():
            print(f"| {name} | EXISTS in exports/{ratio}/, not overwritten: render the next version | | | | | | |")
            continue
        p = probe(f)
        if (p["w"], p["h"]) != SIZES[ratio]:
            print(f"| {name} | SIZE {p['w']}x{p['h']} does not match {ratio}, not exported | | | | | | |")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        m = loudness(dst)
        print(f"| {name} | exported | {p['w']}x{p['h']} | {p['fps']} | {p['dur']:.2f} | {float(m['input_i']):.1f} | "
              f"{float(m['input_tp']):.1f} | {dst.stat().st_size / 1e6:.1f} |")
    print("NEXT: $ad-qa on this ad. Nothing is delivered before $ad-qa passes.")


def reframe_one(src, out, ratio="9x16", mode="crop", x=0.5, face=False):
    p = probe(src)
    if face and mode == "crop":
        fx = face_x(src)
        x = fx if fx is not None else x
        print(f"  crop centre x = {x}")
    r = run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", f"[0:v]{frame_filter(ratio, mode, x, round(p['fps']))}[v]",
             "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", 18, "-c:a", "aac", "-b:a", "192k", out])
    if r.returncode:
        raise SystemExit(r.stderr[-400:])
    q = probe(out)
    print(f"{out}: {q['w']}x{q['h']} {q['dur']:.2f}s")


def opt(a, name, default=None, flag=False):
    if name not in a:
        return default
    i = a.index(name)
    if flag:
        del a[i]
        return True
    v = a[i + 1]
    del a[i:i + 2]
    return v


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a.pop(0) if a else "help"
    if cmd == "probe":
        for f in a:
            print(f, probe(f))
    elif cmd == "faces":
        print(face_x(a[0]))
    elif cmd == "reframe":
        ratio, mode, x, face = opt(a, "--ratio", "9x16"), opt(a, "--mode", "crop"), opt(a, "--x", "0.5"), opt(a, "--face", False, True)
        reframe_one(a[0], a[1], ratio, mode, float(x), face)
    elif cmd == "plan":
        if Path(PLAN).exists():
            raise SystemExit(f"{PLAN} exists: edit it")
        Path(PLAN).parent.mkdir(parents=True, exist_ok=True)
        Path(PLAN).write_text(json.dumps({**EXAMPLE_PLAN, "name": Path.cwd().name}, indent=1))
        print(f"wrote {PLAN}: set hooks, body, end card, ratios")
    elif cmd == "render":
        plan, only = opt(a, "--plan", PLAN), opt(a, "--only")
        bump, final = opt(a, "--bump", False, True), opt(a, "--final", False, True)
        render(plan, set(only.split(",")) if only else None, bump, final)
    elif cmd == "export":
        export(a)
    elif cmd == "loudness":
        for f in a:
            m = loudness(f)
            print(f"{f}: {float(m['input_i']):.1f} LUFS integrated, TP {float(m['input_tp']):.1f} dBTP, LRA {float(m['input_lra']):.1f} LU")
    else:
        raise SystemExit(__doc__)
