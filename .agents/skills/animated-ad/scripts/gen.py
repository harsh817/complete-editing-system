#!/usr/bin/env python3
"""gen.py: scene sheet -> stills -> clips on kie.ai, with a quote before every paid step. Run from the ad folder.
Reads renders/_work/animated/scenes.json (the machine copy of the prompt sheet). Needs KIE_API_KEY, ffmpeg, Pillow,
and Skill 12 (gate.py). Paid commands without --approved print the quote and the cost tag, and stop.

  gen.py init                         write an example scenes.json
  gen.py check                        lint before any spend: ids, references, packshot, durations, dialogue lines
  gen.py stills ID ...|all|masters [--approved]
                                      masters (M#) and anchors (A#) get 2 variants, scene stills 1 -> renders/gen/stills/
  gen.py pick ID N                    keep variant N of a master or anchor (picks.json)
  gen.py repair ID "note" [ID "note" ...] [--approved]
                                      same prompt + "Revision request: <note>" -> ID-r1, ID-r2 ... (old files kept)
  gen.py contact [ID ...]             contact sheet of the latest version of each still -> renders/_work/animated/contact.png
  gen.py clips ID ...|all [--approved]
                                      clips from approved stills -> renders/gen/clips/ (cut to the row length)
  gen.py qa [ID ...]                  4 frames per clip in one grid -> renders/_work/animated/qa_clips.png
  gen.py status                       every job: submitted, done, failed

Prompts are composed here, so the style strings stay byte-identical in every prompt:
  still = style_block + " " + camera + " " + prompt + reference sentences + " " + style_closing
  clip  = prompt + " " + animation_closing"""

# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")

import json, os, re, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KIE = "https://api.kie.ai/api/v1"
UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
WORK = Path("renders/_work/animated")
SHEET = WORK / "scenes.json"
JOBS = WORK / "jobs"
STILLS = Path("renders/gen/stills")
CLIPS = Path("renders/gen/clips")
PACKSHOT = Path("refs/packshot.png")
OMNI = "google/gemini-omni-flash-1-1"
OMNI_TIERS = [4, 6, 8, 10]
LIMITS = {"kling-3.0/video": (3, 15), OMNI: (3, 10)}
REF_CAST = ("The supplied character reference images define each recurring character's identity: match face, "
            "proportions, construction, and palette exactly; pose, expression, and scene-appropriate variation follow "
            "this scene's description.")
REF_PRODUCT = ("The final supplied image is the real product photograph and is the only authority for the product: "
               "reproduce its packaging, label layout, lettering, and colors exactly, rendered in the established style, "
               "immediately recognizable, never redrawn or approximated.")
EXAMPLE = {
    "style": "pixar",
    "style_block": "3D Pixar-style animated.",
    "style_closing": "9:16 vertical format.",
    "animation_closing": "3D Pixar-style animated. Smooth natural motion. No morphing. No style change.",
    "image_model": "nano-banana-pro",
    "video_model": "kling-3.0/video",
    "resolution": "1K",
    "cast": {"M1": "MAYA, a woman in her 40s with shoulder-length curly brown hair, round glasses, a mustard cardigan"},
    "masters": [{"id": "M1", "prompt": "Full character sheet of MAYA, a woman in her 40s with shoulder-length curly brown "
                 "hair, round glasses, a mustard cardigan, standing front-facing in a neutral pose, arms relaxed, neutral "
                 "studio background, soft even studio lighting."}],
    "anchors": [{"id": "A1", "prompt": "Empty cozy kitchen at morning, window left, wooden table centre, plants on the sill, "
                 "warm light.", "camera": "Wide shot, eye level, 28mm."}],
    "stills": [{"id": "S01-a", "camera": "Low angle, medium close-up, 35mm.",
                "prompt": "MAYA, a woman in her 40s with shoulder-length curly brown hair, round glasses, a mustard "
                "cardigan, sits at the wooden table holding a mug, tired eyes, before sunrise.",
                "refs": ["M1", "A1"]},
               {"id": "S02-a", "camera": "Close-up, slight high angle, 50mm.",
                "prompt": "The product jar on the wooden table next to the mug, morning light.",
                "refs": ["A1", "PK"]}],
    "clips": [{"id": "S01", "dur": 5, "start": "S01-a", "end": None,
               "prompt": "Maya lifts the mug slowly and sighs, steam rises, slight push-in.", "line": None},
              {"id": "S02", "dur": 4, "start": "S02-a", "end": None,
               "prompt": "Static camera. Light shifts warmer across the jar, dust in the air.", "line": None}]
}


def load_gate():
    import importlib.util
    here = Path(__file__).resolve()
    cands = [os.environ.get("GATED_PY")]
    cands += [str(p / ".agents/skills/gated-generation/scripts/gate.py") for p in [Path.cwd(), *Path.cwd().parents]]
    cands += [str(here.parents[2] / "gated-generation/scripts/gate.py"),
              str(Path.home() / ".agents/skills/gated-generation/scripts/gate.py")]
    for c in cands:
        if c and Path(c).exists():
            spec = importlib.util.spec_from_file_location("gate", c)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise SystemExit("gate.py not found: install Skill 12 (gated-generation) first")


def sheet():
    if not SHEET.exists():
        raise SystemExit(f"{SHEET} not found: run  gen.py init  and fill it from the approved prompt sheet")
    return json.loads(SHEET.read_text(encoding="utf-8"))


def key():
    k = os.environ.get("KIE_API_KEY", "").strip()
    if not k:
        raise SystemExit("KIE_API_KEY is not set. Export it in your shell profile. Never paste it in the chat.")
    return k


def api(path, body=None):
    req = urllib.request.Request(KIE + path, method="POST" if body else "GET", data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def upload(path):
    """public URL, cached 20 h (kie deletes uploads after 24 h)"""
    cache_f = JOBS / "_uploads.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    hit = cache.get(str(path))
    if hit and hit["mtime"] == os.path.getmtime(path) and time.time() - hit["at"] < 20 * 3600:
        return hit["url"]
    r = subprocess.run(["curl", "-sS", "-X", "POST", UPLOAD, "-H", f"Authorization: Bearer {key()}", "-F", f"file=@{path}",
                        "-F", "uploadPath=animated-ad"], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout).get("data") or {}
    url = d.get("downloadUrl") or d.get("fileUrl")
    if not url:
        raise SystemExit(f"upload of {path} failed: {r.stdout[:300]}")
    cache[str(path)] = {"url": url, "at": time.time(), "mtime": os.path.getmtime(path)}
    JOBS.mkdir(parents=True, exist_ok=True)
    cache_f.write_text(json.dumps(cache, indent=1))
    return url


def picks():
    f = WORK / "picks.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def latest(sid):
    """latest revision id of a still: S01-a-r2 beats S01-a-r1 beats S01-a"""
    revs = sorted((int(m.group(1)), p.stem) for p in STILLS.glob(f"{sid}-r*.png")
                  if (m := re.fullmatch(re.escape(sid) + r"-r(\d+)(?:-v\d+)?", p.stem)))
    return f"{sid}-r{revs[-1][0]}" if revs else sid


def still_file(sid):
    job = latest(sid)
    v = picks().get(sid)
    if v:
        f = STILLS / f"{job}-v{v}.png"
        if f.exists():
            return f
    for f in (STILLS / f"{job}.png", STILLS / f"{job}-v1.png"):
        if f.exists():
            return f
    return None


def all_stills(S):
    return {x["id"]: x for x in S.get("masters", []) + S.get("anchors", []) + S.get("stills", [])}


def compose_still(S, x):
    refs = x.get("refs", [])
    sent = []
    if any(r != "PK" for r in refs):
        sent.append(REF_CAST)
    if "PK" in refs:
        sent.append(REF_PRODUCT)
    parts = [S["style_block"], x.get("camera", ""), x["prompt"], " ".join(sent), x.get("note", ""), S["style_closing"]]
    return " ".join(p.strip() for p in parts if p and p.strip())


def ref_files(refs):
    """local files for the references, packshot always last. Raises before any spend when one is missing."""
    files = []
    for r in [r for r in refs if r != "PK"] + (["PK"] if "PK" in refs else []):
        if r == "PK":
            if not PACKSHOT.exists():
                raise SystemExit("PK is referenced but refs/packshot.png is missing")
            files.append(PACKSHOT)
            continue
        if re.fullmatch(r"[MA]\d+", r) and r not in picks() and any(STILLS.glob(f"{latest(r)}-v*.png")):
            raise SystemExit(f"{r} has variants and no pick: show the contact sheet, then  gen.py pick {r} <N>")
        f = still_file(r)
        if not f:
            raise SystemExit(f"reference {r} has no approved still yet: generate and pick it first")
        files.append(f)
    return files


def ref_urls(refs):
    return [upload(f) for f in ref_files(refs)]


def on_disk(job):
    return any(re.fullmatch(re.escape(job) + r"(-v\d+)?", p.stem) for p in STILLS.glob("*.png"))


def submit(model, inp, job):
    JOBS.mkdir(parents=True, exist_ok=True)
    st = JOBS / f"{job}.json"
    if st.exists():
        return json.loads(st.read_text(encoding="utf-8"))["task"]
    r = api("/jobs/createTask", {"model": model, "input": inp})
    tid = (r.get("data") or {}).get("taskId")
    if not tid:
        raise RuntimeError(f"{job}: {model} refused: {r.get('msg') or r}")
    st.write_text(json.dumps({"task": tid, "model": model, "input": inp, "at": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    return tid


def wait(job, tid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = api(f"/jobs/recordInfo?taskId={tid}").get("data") or {}
        if d.get("state") == "fail":
            (JOBS / f"{job}.error.json").write_text(json.dumps(d, indent=1))
            raise RuntimeError(f"{job} failed: {d.get('failMsg')} (content filter false positives are common: rephrase, "
                               "then repair under a new revision)")
        if d.get("state") == "success":
            return json.loads(d["resultJson"]).get("resultUrls") or []
        time.sleep(10)
    raise RuntimeError(f"{job} still running after {timeout}s: run the same command again, nothing is submitted twice")


def fetch(url, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dst) + ".part")
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dst)


def image_input(S, prompt, urls):
    if S["image_model"].startswith("gpt-image-2"):
        p = {"prompt": prompt, "aspect_ratio": "9:16", "resolution": S.get("resolution", "1K")}
        if urls:
            p["input_urls"] = urls
        return ("gpt-image-2-image-to-image" if urls else "gpt-image-2-text-to-image"), p
    p = {"prompt": prompt, "aspect_ratio": "9:16", "resolution": S.get("resolution", "1K"), "output_format": "png"}
    if urls:
        p["image_input"] = urls[:8]
    return S["image_model"], p


def run_stills(items, approved):
    """items = [(job_id, still_dict, prompt, variants)]"""
    S = sheet()
    todo = [it for it in items if not on_disk(it[0])]
    skipped = [it[0] for it in items if it not in todo]
    if skipped:
        print("already on disk, not paid again:", " ".join(skipped))
    if not todo:
        return
    for job, x, _, _ in todo:
        ref_files(x.get("refs", []))
    g = load_gate()
    g.gate([(S["image_model"], sum(v for *_, v in todo), "image")], approved, step="stills")

    def one(it):
        job, x, prompt, variants = it
        urls = ref_urls(x.get("refs", []))
        m, inp = image_input(S, prompt, urls)
        outs = []
        for v in range(1, variants + 1):
            name = f"{job}-v{v}" if variants > 1 else job
            tid = submit(m, inp, name)
            res = wait(name, tid)
            fetch(res[0], STILLS / f"{name}.png")
            outs.append(f"{name}.png")
        return f"{job}: " + ", ".join(outs)

    with ThreadPoolExecutor(6) as ex:
        for it, fut in [(it, ex.submit(one, it)) for it in todo]:
            try:
                print(fut.result(), flush=True)
            except Exception as e:
                print("FAILED", it[0], str(e)[:300], flush=True)
    print("Next: gen.py contact, then the user approves, picks or asks for repairs.")


def stills(ids, approved):
    S = sheet()
    every = all_stills(S)
    if ids == ["all"]:
        ids = list(every)
    elif ids == ["masters"]:
        ids = [i for i in every if re.fullmatch(r"[MA]\d+", i)]
    bad = [i for i in ids if i not in every]
    if bad:
        raise SystemExit("not in scenes.json: " + " ".join(bad))
    run_stills([(i, every[i], compose_still(S, every[i]), 2 if re.fullmatch(r"[MA]\d+", i) else 1) for i in ids], approved)


def repair(pairs, approved):
    S = sheet()
    every = all_stills(S)
    items = []
    for sid, note in pairs:
        if sid not in every:
            raise SystemExit(f"{sid} not in scenes.json")
        n = 1
        while any(STILLS.glob(f"{sid}-r{n}*.png")) or (JOBS / f"{sid}-r{n}.json").exists():
            n += 1
        x = dict(every[sid], note=f"Revision request: {note}")
        items.append((f"{sid}-r{n}", x, compose_still(S, x), 1))
    run_stills(items, approved)


def omni_len(d):
    return min(t for t in OMNI_TIERS if t >= d)


def clip_price_key(S, c):
    m = S["video_model"]
    if m == OMNI:
        return f"{m}:{omni_len(c['dur'])}", 1, "clip"
    sound = bool(c.get("line")) if c.get("audio") is None else bool(c.get("audio"))
    return (f"{m}:sound" if sound else m), c["dur"], "second"


def clips(ids, approved):
    S = sheet()
    rows = {c["id"]: c for c in S["clips"]}
    ids = list(rows) if ids == ["all"] else ids
    bad = [i for i in ids if i not in rows]
    if bad:
        raise SystemExit("not in scenes.json: " + " ".join(bad))
    todo = [rows[i] for i in ids if not (CLIPS / f"{i}.mp4").exists()]
    if len(todo) < len(ids):
        print("already on disk, not paid again:", " ".join(i for i in ids if (CLIPS / f"{i}.mp4").exists()))
    if not todo:
        return
    for c in todo:
        for sid in [c["start"]] + ([c["end"]] if c.get("end") else []):
            if not still_file(sid):
                raise SystemExit(f"clip {c['id']} needs still {sid}, which is not generated and approved yet")
    keys = [clip_price_key(S, c) for c in todo]
    g = load_gate()
    g.gate(keys, approved, step="clips")

    def one(c):
        m = S["video_model"]
        prompt = f"{c['prompt'].strip()} {S['animation_closing']}"
        if m == OMNI:
            inp = {"prompt": prompt, "first_frame_url": upload(still_file(c["start"])), "duration": str(omni_len(c["dur"])),
                   "aspect_ratio": "9:16", "resolution": "720p"}
            if c.get("end"):
                inp["last_frame_url"] = upload(still_file(c["end"]))
        else:
            inp = {"prompt": prompt, "image_urls": [upload(still_file(c["start"]))] +
                   ([upload(still_file(c["end"]))] if c.get("end") else []),
                   "duration": str(c["dur"]), "sound": clip_price_key(S, c)[0].endswith(":sound"), "mode": "pro",
                   "multi_shots": False}
        job = f"clip-{c['id']}"
        res = wait(job, submit(m, inp, job))
        full = CLIPS / "_full" / f"{c['id']}.mp4"
        fetch(res[0], full)
        got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(full)],
                                   capture_output=True, text=True).stdout or 0)
        dst = CLIPS / f"{c['id']}.mp4"
        if got > c["dur"] + 0.1:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(full), "-t", str(c["dur"]), "-c:v", "libx264", "-crf", "16",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dst)], check=True)
        else:
            os.replace(full, dst)
        return f"{c['id']}: {got:.1f}s take" + (f", cut to its {c['dur']}s row (full take in {full})" if got > c["dur"] + 0.1 else "")

    with ThreadPoolExecutor(6) as ex:
        for c, fut in [(c, ex.submit(one, c)) for c in todo]:
            try:
                print(fut.result(), flush=True)
            except Exception as e:
                print("FAILED", c["id"], str(e)[:300], flush=True)
    print("Next: gen.py qa, then the user reviews; a bad clip is redone only after its own quote.")


def grid(cells, out, cols, tw=240, th=427):
    from PIL import Image, ImageDraw
    per = max(len(c[1]) for c in cells)
    cw, lh = per * tw + 10, 26
    rows = -(-len(cells) // cols)
    img = Image.new("RGB", (cols * cw, rows * (th + lh)), "white")
    d = ImageDraw.Draw(img)
    for i, (label, pngs) in enumerate(cells):
        x0, y0 = (i % cols) * cw, (i // cols) * (th + lh)
        d.text((x0 + 6, y0 + 6), label, fill="black")
        for j, p in enumerate(pngs):
            if p and Path(p).exists():
                img.paste(Image.open(p).convert("RGB").resize((tw, th)), (x0 + j * tw, y0 + lh))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"-> {out}")


def contact(ids):
    S = sheet()
    every = all_stills(S)
    ids = ids or [i for i in every if on_disk(i) or on_disk(latest(i))]
    cells = []
    for i in ids:
        job = latest(i)
        vs = sorted(STILLS.glob(f"{job}-v*.png"))
        cells.append((f"{i} ({job})", [str(p) for p in vs] if vs and i not in picks() else [str(still_file(i))]))
    grid(cells, WORK / "contact.png", cols=6)


def qa(ids):
    files = [CLIPS / f"{i}.mp4" for i in ids] if ids else sorted(CLIPS.glob("*.mp4"))
    tmp = WORK / "qa_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    cells = []
    for f in files:
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                 capture_output=True, text=True).stdout)
        pngs = []
        for k, p in enumerate((0.1, 0.4, 0.7, 0.97)):
            o = tmp / f"{f.stem}_{k}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{d * p:.2f}", "-i", str(f), "-frames:v", "1", "-vf",
                            "scale=240:-2", str(o)])
            pngs.append(str(o))
        cells.append((f"{f.stem} {d:.1f}s", pngs))
    if cells:
        grid(cells, WORK / "qa_clips.png", cols=2, tw=180, th=320)


def check():
    S = sheet()
    errs, warns = [], []
    every = all_stills(S)
    ids = [x["id"] for x in S.get("masters", []) + S.get("anchors", []) + S.get("stills", [])]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        errs.append(f"still {i} defined twice")
    for i, x in every.items():
        for r in x.get("refs", []):
            if r == "PK":
                if not PACKSHOT.exists():
                    warns.append(f"{i} uses PK but refs/packshot.png is missing")
            elif r not in every:
                errs.append(f"{i} references {r}, which is not in the sheet")
            elif r == i:
                errs.append(f"{i} references itself")
        if "PK" in x.get("refs", []) and x["refs"][-1] != "PK":
            warns.append(f"{i}: the packshot goes last in refs (the script reorders it, fix the sheet too)")
        for name, clause in S.get("cast", {}).items():
            if name in x.get("refs", []) and clause not in x["prompt"]:
                warns.append(f"{i} attaches {name} but the prompt lacks its cast clause verbatim")
        if len(x.get("refs", [])) > 8 and S["image_model"] == "nano-banana-pro":
            errs.append(f"{i}: more than 8 references")
    lo, hi = LIMITS.get(S["video_model"], (3, 15))
    for c in S.get("clips", []):
        if not lo <= c["dur"] <= hi:
            errs.append(f"clip {c['id']}: {c['dur']}s is outside {lo}-{hi}s for {S['video_model']}")
        for sid in [c["start"]] + ([c["end"]] if c.get("end") else []):
            if sid not in every:
                errs.append(f"clip {c['id']} uses still {sid}, which is not in the sheet")
        if c.get("line") and c["line"] not in c["prompt"]:
            errs.append(f"clip {c['id']} has a spoken line that is not in its prompt verbatim (lip sync needs it)")
        if S["video_model"] == OMNI and "Audio:" not in c["prompt"]:
            warns.append(f"clip {c['id']}: this model always renders audio, end the prompt with an 'Audio:' line")
        n = len(c["prompt"].split())
        if n > 80:
            warns.append(f"clip {c['id']}: {n} words, keep animation prompts at 30-80 words, one action")
    for e in errs:
        print("ERROR", e)
    for w in warns:
        print("WARN ", w)
    print(f"check: {len(every)} stills, {len(S.get('clips', []))} clips, {len(errs)} errors, {len(warns)} warnings")
    if errs:
        sys.exit(1)


def status():
    for j in sorted(JOBS.glob("*.json")):
        if j.name.startswith("_") or j.name.endswith(".error.json"):
            continue
        state = "FAILED" if (JOBS / f"{j.stem}.error.json").exists() else (
            "done" if any(STILLS.glob(f"{j.stem}.png")) or (CLIPS / f"{j.stem[5:]}.mp4").exists() else "submitted")
        print(f"{j.stem}: {state}")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a.pop(0) if a else "help"
    ok = "--approved" in a
    a = [x for x in a if x != "--approved"]
    if cmd == "init":
        if SHEET.exists():
            raise SystemExit(f"{SHEET} exists: edit it")
        WORK.mkdir(parents=True, exist_ok=True)
        SHEET.write_text(json.dumps(EXAMPLE, indent=1, ensure_ascii=False))
        print(f"wrote {SHEET}")
    elif cmd == "check":
        check()
    elif cmd == "stills":
        stills(a, ok)
    elif cmd == "pick":
        p = picks()
        p[a[0]] = int(a[1])
        (WORK / "picks.json").write_text(json.dumps(p, indent=1))
        print(f"{a[0]} = variant {a[1]}")
    elif cmd == "repair":
        repair(list(zip(a[0::2], a[1::2])), ok)
    elif cmd == "contact":
        contact(a)
    elif cmd == "clips":
        clips(a, ok)
    elif cmd == "qa":
        qa(a)
    elif cmd == "status":
        status()
    else:
        raise SystemExit(__doc__)
