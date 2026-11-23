#!/usr/bin/env python3
"""qa.py: QA every export before it leaves. Run from the ad folder. Needs ffmpeg, ffprobe, Pillow.

  qa.py init                       write an example renders/qa/qa.json (names, specs, loudness, banned text, zones)
  qa.py run [FILES ...]            check every file (default: exports/*/*.mp4)
                                   -> renders/qa/qa-<YYYYMMDD-HHMM>.md + renders/qa/<name>_sheet.png
  qa.py sheet FILE [--every 1.0]   contact sheet only, with the zones drawn

Automatic checks: file name, resolution vs ratio token, fps, video and audio codec, pixel format, duration,
audio vs video length, integrated loudness and true peak, black frames, frozen frames, long silences, caption
boxes inside the house zone and caption text against banned patterns (both from
renders/_work/captions/<name>.layout.json), file in the exports/ folder of its own ratio.
Visual check (Codex reads the contact sheet): watermarks, phone numbers, URLs, wrong brand names, text outside
the green box, cut-off text. The report keeps that column PENDING until it is filled.
Exit code 1 when any automatic check fails. This script never writes renders/qa/LAST_PASS: only $ad-qa does,
after every blocking check passed."""
import glob, json, re, subprocess, sys, time
from pathlib import Path

CFG_FILE = Path("renders/qa/qa.json")
QA = Path("renders/qa")
META_BOTTOM = 0.65
EXAMPLE = {
    "name_pattern": r"^[A-Z]{3,4}_\d{4}-S\d+(-[A-Za-z0-9]+)?_(H\d+|BODY)_(9x16|4x5)_v\d+\.mp4$",
    "sizes": {"9x16": [1080, 1920], "4x5": [1080, 1350]},
    "fps": [23.976, 24, 25, 29.97, 30],
    "video_codecs": ["h264"],
    "audio_codecs": ["aac"],
    "pix_fmt": ["yuv420p"],
    "min_s": 5,
    "max_s": 180,
    "av_tolerance_s": 0.1,
    "lufs": -14.0,
    "lufs_tolerance": 1.0,
    "max_true_peak": -1.0,
    "black_min_s": 0.1,
    "freeze_min_s": 0.5,
    "freeze_ignore_last_s": 3.5,
    "silence_min_s": 1.5,
    "silence_db": -45,
    "banned_patterns": [r"https?://", r"www\.", r"\b\w+\.(com|net|org|io|co)\b", r"\+?\d[\d\s().-]{7,}\d", r"@\w{3,}"],
    "wrong_names": ["OldBrandName", "CompetitorName"],
    "safe_zone": {"9x16": [0.0602, 0.1484, 0.9398, 0.8516], "4x5": [0.06, 0.05, 0.94, 0.95]},
    "sheet_every_s": 1.0,
    "sheet_cols": 6
}


def house_var(name):
    for p in [Path.cwd(), *Path.cwd().parents]:
        f = p / "AGENTS.md"
        if f.exists():
            m = re.search(rf"{name}\s*=\s*(-?[0-9.]+)", f.read_text(encoding="utf-8"))
            return float(m.group(1)) if m else None
    return None


def cfg():
    c = dict(EXAMPLE)
    for k, var in (("lufs", "LOUDNESS_TARGET_LUFS"), ("max_true_peak", "TRUE_PEAK_DBTP")):
        v = house_var(var)
        if v is not None:
            c[k] = v
    if CFG_FILE.exists():
        c.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
    return c


def run(cmd):
    return subprocess.run([str(x) for x in cmd], capture_output=True, text=True)


def ffprobe(f):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,duration,sample_rate:format=duration",
             "-of", "json", f])
    return json.loads(r.stdout) if r.returncode == 0 else None


def rate(s):
    n, d = (s or "0/1").split("/")
    return float(n) / float(d) if float(d) else 0.0


def detect(f, c):
    """one decode pass: blackdetect + freezedetect on video, ebur128 + silencedetect on audio"""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", f,
             "-filter_complex",
             f"[0:v]blackdetect=d={c['black_min_s']}:pix_th=0.10,freezedetect=n=0.003:d={c['freeze_min_s']}[v];"
             f"[0:a]ebur128=peak=true,silencedetect=n={c['silence_db']}dB:d={c['silence_min_s']}[a]",
             "-map", "[v]", "-map", "[a]", "-f", "null", "-"])
    e = r.stderr
    black = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", e)]
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", e)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", e)]
    freeze = [(s, fe[i] if i < len(fe) else None) for i, s in enumerate(fs)]
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    silence = [(max(0.0, s), se[i] if i < len(se) else None) for i, s in enumerate(ss)]
    summ = e[e.rfind("Summary:"):] if "Summary:" in e else ""
    I = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    P = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summ)
    return dict(black=black, freeze=freeze, silence=silence,
                lufs=float(I.group(1)) if I else None,
                tp=(float(P.group(1)) if P and P.group(1) != "-inf" else None),
                error=None if r.returncode == 0 else e[-300:])


def check_file(f, c):
    name = Path(f).name
    res, notes = {}, []
    m = re.match(c["name_pattern"], name)
    res["name"] = bool(m)
    if not m:
        notes.append("name does not match BRAND_YYMM-S#_H#_RATIO_v#.mp4 (e.g. ACME_2610-S3_H1_9x16_v1.mp4)")
    ratio = (re.search(r"_(9x16|4x5|1x1)[_.]", name) or [None, None])[1]
    folder = Path(f).parent.name
    if folder in ("9x16", "4x5") and ratio and folder != ratio:
        res["name"] = False
        notes.append(f"a {ratio} file sits in exports/{folder}/")
    j = ffprobe(f)
    if not j:
        return dict(file=name, res={"probe": False}, notes=["ffprobe could not read the file"], specs="", dur=0)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    w, h = v.get("width"), v.get("height")
    fps = rate(v.get("avg_frame_rate"))
    dur = float(j["format"]["duration"])
    exp = c["sizes"].get(ratio)
    ok_size = exp is not None and [w, h] == exp
    ok_fps = any(abs(fps - x) < 0.05 for x in c["fps"])
    ok_codec = v.get("codec_name") in c["video_codecs"] and v.get("pix_fmt") in c["pix_fmt"]
    ok_audio = a is not None and a.get("codec_name") in c["audio_codecs"]
    res["specs"] = ok_size and ok_fps and ok_codec and ok_audio
    if not ok_size:
        notes.append(f"size {w}x{h}, expected {exp} for ratio {ratio}")
    if not ok_fps:
        notes.append(f"fps {fps:.3f} not in {c['fps']}")
    if not ok_codec:
        notes.append(f"video {v.get('codec_name')} {v.get('pix_fmt')}")
    if not ok_audio:
        notes.append("no audio stream" if a is None else f"audio codec {a.get('codec_name')}")
    vd = float(v.get("duration") or dur)
    ad = float(a.get("duration") or dur) if a else 0.0
    res["duration"] = c["min_s"] <= dur <= c["max_s"] and (a is None or abs(vd - ad) <= c["av_tolerance_s"])
    if not c["min_s"] <= dur <= c["max_s"]:
        notes.append(f"duration {dur:.2f}s outside {c['min_s']}-{c['max_s']}s")
    if a is not None and abs(vd - ad) > c["av_tolerance_s"]:
        notes.append(f"audio {ad:.2f}s vs video {vd:.2f}s")
    d = detect(f, c) if a is not None else dict(black=[], freeze=[], silence=[], lufs=None, tp=None, error="no audio")
    if d["lufs"] is None:
        res["loudness"] = False
        notes.append("loudness not measured")
    else:
        res["loudness"] = abs(d["lufs"] - c["lufs"]) <= c["lufs_tolerance"] and (d["tp"] is None or d["tp"] <= c["max_true_peak"] + 0.05)
        if not res["loudness"]:
            notes.append(f"{d['lufs']:.1f} LUFS (target {c['lufs']}), true peak {d['tp']} dBTP (max {c['max_true_peak']})")
    res["black"] = not d["black"]
    for s, e in d["black"]:
        notes.append(f"black {s:.2f}-{e:.2f}s")
    frozen = [(s, e) for s, e in d["freeze"] if s < dur - c["freeze_ignore_last_s"]]
    res["frozen"] = not frozen
    for s, e in frozen:
        notes.append(f"frozen from {s:.2f}s" + (f" to {e:.2f}s" if e else " to the end"))
    for s, e in d["silence"]:
        notes.append(f"WARN silence {s:.2f}-{e if e else dur:.2f}s")
    lay = Path("renders/_work/captions") / f"{Path(f).stem}.layout.json"
    if lay.exists():
        L = json.loads(lay.read_text(encoding="utf-8"))
        W, H = L["size"]
        z = c["safe_zone"].get(ratio, L["safe_zone"])
        out = [e for e in L["events"] if not (e["box"][0] >= z[0] * W - 1 and e["box"][1] >= z[1] * H - 1 and
                                             e["box"][0] + e["box"][2] <= z[2] * W + 1 and e["box"][1] + e["box"][3] <= z[3] * H + 1)]
        res["safe_zone"] = not out
        for e in out:
            notes.append(f"{e['kind']} at {e['start']}s outside the house zone: box {e['box']}")
        low = [e for e in L["events"] if ratio == "9x16" and e["box"][1] + e["box"][3] > META_BOTTOM * H]
        if low:
            notes.append(f"WARN {len(low)} text block(s) in Meta's Reels bottom 35 % (house caption line): "
                         "check the placement preview in Ads Manager")
        text = " ".join(" ".join(e["lines"]) for e in L["events"]).replace("*", "")
        bad = [p for p in c["banned_patterns"] if re.search(p, text, re.I)]
        bad += [n for n in c["wrong_names"] if re.search(r"\b" + re.escape(n) + r"\b", text, re.I)]
        res["caption_text"] = not bad
        for p in bad:
            notes.append(f"caption text matches banned '{p}'")
    else:
        res["safe_zone"] = None
        res["caption_text"] = None
        notes.append(f"no {lay}: caption zone and text not checked (text burned elsewhere = check it on the sheet)")
    if d.get("error") and d["error"] != "no audio":
        notes.append("ffmpeg detect pass error: " + d["error"].strip().splitlines()[-1])
    sheet(f, c)
    specs = f"{w}x{h} {fps:.2f}fps {v.get('codec_name')}/{a.get('codec_name') if a else '-'} {dur:.2f}s"
    loud = f"{d['lufs']:.1f} LUFS / {d['tp']} dBTP" if d["lufs"] is not None else "-"
    return dict(file=name, res=res, notes=notes, specs=specs, loud=loud, dur=dur)


def sheet(f, c, every=None):
    """contact sheet, one frame every N s, timestamp + safe zone on each tile"""
    from PIL import Image, ImageDraw
    every = float(every or c["sheet_every_s"])
    QA.mkdir(parents=True, exist_ok=True)
    j = ffprobe(f)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    W, H, dur = int(v["width"]), int(v["height"]), float(j["format"]["duration"])
    ratio = (re.search(r"_(9x16|4x5|1x1)[_.]", Path(f).name) or [None, None])[1]
    z = c["safe_zone"].get(ratio)
    tw = 270
    th = int(H * tw / W)
    times = [round(t * every, 2) for t in range(int(dur / every) + 1) if t * every < dur - 0.05]
    times = times[:48]
    cols = int(c["sheet_cols"])
    rows = -(-len(times) // cols)
    out = Image.new("RGB", (cols * (tw + 6), rows * (th + 26)), "white")
    d = ImageDraw.Draw(out)
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vf", f"fps=1/{every},scale={tw}:{th}", "-frames:v",
                           str(len(times)), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(data) // (tw * th * 3)
    for i in range(min(n, len(times))):
        img = Image.frombytes("RGB", (tw, th), data[i * tw * th * 3:(i + 1) * tw * th * 3])
        x0, y0 = (i % cols) * (tw + 6), (i // cols) * (th + 26)
        out.paste(img, (x0, y0 + 22))
        d.text((x0 + 4, y0 + 4), f"{times[i]:.1f}s", fill="black")
        if z:
            d.rectangle([x0 + z[0] * tw, y0 + 22 + z[1] * th, x0 + z[2] * tw, y0 + 22 + z[3] * th], outline=(0, 200, 0), width=2)
    p = QA / f"{Path(f).stem}_sheet.png"
    out.save(p)
    return p


def mark(v):
    return "PASS" if v is True else "FAIL" if v is False else "n/a"


def report(results):
    cols = ["name", "specs", "duration", "loudness", "black", "frozen", "safe_zone", "caption_text"]
    lines = ["# QA report", "", "| file | " + " | ".join(cols) + " | visual | result |",
             "|" + "---|" * (len(cols) + 3)]
    any_fail = False
    for r in results:
        fail = any(v is False for v in r["res"].values())
        any_fail |= fail
        lines.append(f"| {r['file']} | " + " | ".join(mark(r['res'].get(k)) for k in cols) +
                     f" | PENDING | {'FAIL' if fail else 'PASS (auto), visual pending'} |")
    lines += ["", "## Details", ""]
    for r in results:
        lines.append(f"**{r['file']}**: {r['specs']} | {r.get('loud', '-')} | sheet: renders/qa/{Path(r['file']).stem}_sheet.png")
        for n in r["notes"]:
            lines.append(f"- {n}")
        lines.append("")
    QA.mkdir(parents=True, exist_ok=True)
    out = QA / f"qa-{time.strftime('%Y%m%d-%H%M')}.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines[:len(results) + 4]))
    print(f"\n-> {out} ({sum(1 for r in results if not any(v is False for v in r['res'].values()))}/{len(results)} pass the automatic checks)")
    return any_fail


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a.pop(0) if a else "help"
    if cmd == "init":
        if CFG_FILE.exists():
            raise SystemExit("qa.json exists: edit it")
        CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps(EXAMPLE, indent=1))
        print("wrote renders/qa/qa.json: set wrong_names, durations and loudness target for this ad")
    elif cmd == "run":
        files = a or sorted(glob.glob("exports/*/*.mp4"))
        if not files:
            raise SystemExit("no files: pass them, or run $ad-final so exports/9x16/ and exports/4x5/ hold them")
        c = cfg()
        sys.exit(1 if report([check_file(f, c) for f in files]) else 0)
    elif cmd == "sheet":
        every = None
        if "--every" in a:
            i = a.index("--every")
            every = a[i + 1]
            del a[i:i + 2]
        print("->", sheet(a[0], cfg(), every))
    else:
        raise SystemExit(__doc__)
