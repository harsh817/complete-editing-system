#!/usr/bin/env python3
"""actorswap.py: recreate a winning ad with a new AI actor from its raw footage, same cuts, same timing.
Run from the ad folder that holds project.json. Needs ffmpeg, numpy. Paid commands need KIE_API_KEY and Skill 12
(gate.py): without --approved they print the quote and stop.

Mode A, recreate a winner from the raw it was cut from
  map                       find every piece of winner audio in the raw (log spectra + Viterbi) -> renders/_work/swap/mapping.csv
  cut                       used raw ranges, shared body cut once, min..max s -> renders/_work/swap/clips/*.mp4
  ref SRC AVATAR [--out F]  the new actor placed into the first frame of SRC -> renders/gen/ref/   [paid]
  swap CLIP ...|all [--model seedance|kling]   model output -> renders/gen/swap/, remuxed -> renders/_work/swap/swapped/   [paid]
  edit                      winner timeline rebuilt from the swapped clips, audio from the raw -> renders/_work/swap/edits/<H>.mp4
Mode B, restyle clips with no winner: set "clips_dir" in project.json, then  ref, swap --src clips_dir
Both
  quote [--src clips]       what swap would cost for every clip not yet generated
  compare A B OUT           side-by-side review video (left A, right B, audio of B)
  qa FILE ...               double cuts (1-3 frame flashes), frozen frames, audio vs video length
  speechcheck H FILE        spoken parts of FILE that differ from winner H (clipped word endings, wrong take)

Captions, zooms, B-roll and exports come after this: Skills 14 (captions-headlines) and 15 (reframe-exports)."""

# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")

import csv, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

P = Path.cwd()
CFG = json.loads((P / "project.json").read_text(encoding="utf-8")) if (P / "project.json").exists() else {}
W_ = P / "renders" / "_work" / "swap"   # mapping, clips, remuxed swaps, edits
GEN = P / "renders" / "gen" / "swap"    # paid model output, never overwritten
KIE = "https://api.kie.ai/api/v1"
UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
MODELS = {"seedance": "bytedance/seedance-2-5", "kling": "kling-3.0/motion-control", "ref": "nano-banana-pro"}
SR = 8000
REF_PROMPT = ("Replace the person in the first image with the person in the second image: face, head, hair, facial hair, "
              "glasses and skin tone come from the second image. Keep everything else from the first image exactly: "
              "framing, camera angle, background, lighting, clothing, pose, hands and every object. Eyes open. "
              "Photorealistic, same photo quality as the first image.")


def cfg(key, default=None):
    v = CFG
    for k in key.split("."):
        if not isinstance(v, dict) or k not in v:
            return default
        v = v[k]
    return v


def pth(x):
    x = Path(os.path.expanduser(str(x)))
    return x if x.is_absolute() else P / x


FPS = cfg("fps", 30)
W, H = cfg("size", [720, 1280])
ADS = list(cfg("winners", {}))


def load_gate():
    import importlib.util
    here = Path(__file__).resolve()
    cands = [os.environ.get("GATED_PY")]
    cands += [str(p / ".agents/skills/gated-generation/scripts/gate.py") for p in [P, *P.parents]]
    cands += [str(here.parents[2] / "gated-generation/scripts/gate.py"),
              str(Path.home() / ".agents/skills/gated-generation/scripts/gate.py")]
    for c in cands:
        if c and Path(c).exists():
            spec = importlib.util.spec_from_file_location("gate", c)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise SystemExit("gate.py not found: install Skill 12 (gated-generation) first")


def ff(*args):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg failed: {r.stderr[-400:]}")


def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True).stdout)


def key():
    k = os.environ.get("KIE_API_KEY", "").strip()
    if not k:
        raise SystemExit("KIE_API_KEY is not set. Export it in your shell profile. Never paste it in the chat.")
    return k


def kie_upload(path):
    """public URL for a local file. Uploads expire, so upload right before the task that uses them."""
    r = subprocess.run(["curl", "-sS", "-X", "POST", UPLOAD, "-H", f"Authorization: Bearer {key()}", "-F", f"file=@{path}",
                        "-F", "uploadPath=actor-swap"], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout).get("data") or {}
    url = d.get("downloadUrl") or d.get("fileUrl")
    if not url:
        raise RuntimeError(f"upload of {path} failed: {r.stdout[:300]}")
    return url


def kie_run(model, inp, timeout=1800):
    def call(path, body=None):
        req = urllib.request.Request(KIE + path, method="POST" if body else "GET",
                                     data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=60))
    r = call("/jobs/createTask", {"model": model, "input": inp})
    tid = (r.get("data") or {}).get("taskId")
    if not tid:
        raise RuntimeError(f"{model} refused: {r.get('msg') or r}")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(10)
        d = call(f"/jobs/recordInfo?taskId={tid}").get("data") or {}
        if d.get("state") == "fail":
            raise RuntimeError(f"{model} failed: {d.get('failMsg')}")
        if d.get("state") == "success":
            return json.loads(d["resultJson"]).get("resultUrls") or []
    raise RuntimeError(f"{model} task {tid} still running after {timeout}s: check the provider dashboard")


def fetch(url, dst):
    tmp = Path(str(dst) + ".part")
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dst)


# ------------------------------------------------------------------ map: winner audio -> raw ranges

def wav8k(src, name):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64)


def spec(x, nf=256, hop=80):
    """log-magnitude spectrogram, 10 ms frames at 8 kHz"""
    import numpy as np
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(x, (nf // 2, nf // 2)), nf)[::hop] * np.hanning(nf)
    return np.log(np.abs(np.fft.rfft(fr, axis=1))[:, 4:100] + 1e2)


def viterbi(C, Pn):
    import numpy as np
    T, K = C.shape
    dp, back = C[0].copy(), np.zeros((T, K), np.int32)
    for t in range(1, T):
        j = int(np.argmin(dp))
        back[t] = np.where(dp <= dp[j] + Pn, np.arange(K), j)
        dp = np.minimum(dp, dp[j] + Pn) + C[t]
    path = np.empty(T, int)
    path[-1] = int(np.argmin(dp))
    for t in range(T - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def scene_cuts(path, thr=0.25):
    out = subprocess.run(["ffmpeg", "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return [round(float(x.split(":")[1]), 2) for x in out.split() if x.startswith("pts_time:")]


def map_(penalty="10"):
    """1. 0.5 s windows of winner audio cross-correlated against the whole raw -> candidate offsets.
    2. Viterbi over candidates (spectral distance + switch penalty) -> piecewise-constant offsets. This finds the
       0.3-0.6 s pauses the editor trimmed inside one take; missing them clips word endings.
    3. Segment edges within 60 ms of a visual cut in the winner snap to it."""
    import numpy as np
    W_.mkdir(parents=True, exist_ok=True)
    Pn = float(penalty)
    RS = spec(wav8k(pth(cfg("raw")), "raw"))
    RS -= RS.mean(1, keepdims=True)
    N = 1 << int(np.ceil(np.log2(len(RS) + 100)))
    F = np.fft.rfft(RS, N, axis=0)
    cs = np.concatenate([[0], np.cumsum((RS ** 2).sum(1))])
    rows = []
    for ad in ADS:
        Hs = spec(wav8k(pth(cfg("winners")[ad]), ad))
        Hs -= Hs.mean(1, keepdims=True)
        T, L = len(Hs), 50
        offs = []
        for t0 in range(0, T - L, 10):
            q = Hs[t0:t0 + L]
            c = np.fft.irfft((F * np.conj(np.fft.rfft(q, N, axis=0))).sum(1), N)[:len(RS) - L]
            c /= np.sqrt(np.maximum(cs[L:L + len(c)] - cs[:len(c)], 1e-9)) * np.linalg.norm(q)
            i = int(np.argmax(c))
            if c[i] > 0.7:
                offs.append(i - t0)
        groups = []
        for o in sorted(offs):
            if groups and o - groups[-1][-1] <= 2:
                groups[-1].append(o)
            else:
                groups.append([o])
        cand = [int(np.median(g)) for g in groups if len(g) >= 2]
        if not cand:
            raise SystemExit(f"{ad}: no part of the winner audio was found in the raw. Is it the right raw?")
        eq = 0
        for _ in range(2):
            C = np.full((T, len(cand)), 1e3)
            for k, o in enumerate(cand):
                lo, hi = max(0, -o), min(T, len(RS) - o)
                C[lo:hi, k] = ((Hs[lo:hi] - RS[lo + o:hi + o] - eq) ** 2).mean(1)
            path = viterbi(C, Pn)
            eq = (Hs - RS[np.clip(np.array(cand)[path] + np.arange(T), 0, len(RS) - 1)]).mean(0)
        vc = scene_cuts(pth(cfg("winners")[ad]))
        edges = [0] + [t for t in range(1, T) if path[t] != path[t - 1]] + [T]
        snap = lambda t: min([c for c in vc if abs(c - t / 100) <= 0.06] or [t / 100], key=lambda c: abs(c - t / 100))
        mine = []
        for a, b in zip(edges, edges[1:]):
            o = cand[path[a]] / 100
            ws, we = (0.0 if a == 0 else snap(a)), (T / 100 if b == T else snap(b))
            mine.append(dict(ad=ad, win_in=round(ws, 2), win_out=round(we, 2), raw_in=round(ws + o, 2),
                             raw_out=round(we + o, 2), dist=round(float(C[a:b, path[a]].mean()), 3)))
        for r in list(mine[1:]):   # short, badly matching = an effect only the winner has: keep the previous take
            if r["dist"] > 0.7 and r["win_out"] - r["win_in"] < 0.6:
                prev = mine[mine.index(r) - 1]
                prev["win_out"], prev["raw_out"] = r["win_out"], round(prev["raw_out"] + r["win_out"] - r["win_in"], 2)
                mine.remove(r)
        rows += mine
        print(f"{ad}: {len(mine)} segments, {len(cand)} candidate offsets")
        for r in mine:
            print(f"   winner {r['win_in']:6.2f}-{r['win_out']:6.2f}  raw {r['raw_in']:7.2f}-{r['raw_out']:7.2f}  dist {r['dist']}")
    with open(W_ / "mapping.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=rows[0].keys())
        wr.writeheader()
        wr.writerows(rows)
    print(f"-> {W_ / 'mapping.csv'}")


def cut(force=False):
    """union of raw ranges over all ads -> takes -> clips of min..max s. Used by one ad only = that hook, else BODY.
    Run only after the final map: re-mapping after the swap moves edges outside the swapped clips."""
    paid = list(GEN.glob("*/*.mp4"))
    if paid and not force:
        raise SystemExit(f"{len(paid)} paid swaps exist in renders/gen/swap: re-cutting would move clips under them. "
                         "Move the folder aside first, or pass --force if the ranges did not change.")
    MAX, MIN = cfg("swap.max_clip", 10.0), cfg("swap.min_clip", 4.0)
    PAD, GAP = cfg("swap.pad", 0.15), cfg("swap.gap", 1.5)
    rows = list(csv.DictReader(open(W_ / "mapping.csv")))
    for r in rows:
        r["raw_in"], r["raw_out"] = float(r["raw_in"]), float(r["raw_out"])
    merged = []
    for a, b in sorted({(r["raw_in"], r["raw_out"]) for r in rows}):
        if merged and a <= merged[-1][1] + 0.05:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    users = lambda a, b: sorted({r["ad"] for r in rows if r["raw_in"] < b and r["raw_out"] > a})
    takes = []
    for a, b in merged:
        tag = users(a, b)[0] if len(users(a, b)) == 1 and len(ADS) > 1 else "BODY"
        if takes and a - takes[-1][1][-1][1] < GAP and takes[-1][0] == tag:
            takes[-1][1].append([a, b])
        else:
            takes.append([tag, [[a, b]]])
    clips = []
    for tag, ivs in takes:
        cur = [ivs[0]]
        for x in ivs[1:]:
            if x[1] - cur[0][0] + 2 * PAD > MAX:
                clips.append((tag, cur))
                cur = [x]
            else:
                cur.append(x)
        clips.append((tag, cur))
    out = W_ / "clips"
    out.mkdir(parents=True, exist_ok=True)
    raw_len = dur(pth(cfg("raw")))
    n, idx = {}, []
    for tag, ivs in clips:
        n[tag] = n.get(tag, 0) + 1
        name = f"{tag}_{n[tag]:02d}"
        s, e = ivs[0][0] - PAD, ivs[-1][1] + PAD
        if e - s < MIN:
            s, e = s - (MIN - (e - s)) / 2, e + (MIN - (e - s)) / 2
        s, e = max(0.0, s), min(raw_len, e)
        ff("-ss", f"{s:.3f}", "-i", pth(cfg("raw")), "-t", f"{e - s:.3f}", "-c:v", "libx264", "-crf", 16, "-preset", "slow",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out / f"{name}.mp4")
        idx.append(dict(clip=name, raw_in=round(s, 2), raw_out=round(e, 2), dur=round(e - s, 2), used_in=" ".join(users(s, e))))
        flag = "  (over max_clip: one unbroken piece, kept whole)" if e - s > MAX + 0.01 else ""
        print(f"{name}: {e - s:.2f}s, used in {idx[-1]['used_in']}{flag}")
    with open(out / "index.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=idx[0].keys())
        wr.writeheader()
        wr.writerows(idx)


# ------------------------------------------------------------------ ref and swap (paid)

def ref(src, avatar, out, prompt=None, t="0", approved=False):
    src, out = pth(src), pth(out)
    if out.exists():
        raise SystemExit(f"{out} exists: choose another --out (paid outputs are never overwritten)")
    g = load_gate()
    g.gate([(MODELS["ref"], 1, "image")], approved, step="swap")
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = out.with_name(out.stem + "_frame.png")
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        ff("-i", src, frame)
    else:
        ff("-ss", t, "-i", src, "-frames:v", 1, frame)
    wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                         str(frame)], capture_output=True, text=True).stdout.strip().split(",")[:2]
    imgs = [frame] + ([pth(avatar)] if avatar != "-" else [])
    urls = kie_run(MODELS["ref"], dict(prompt=prompt or cfg("ref_prompt", REF_PROMPT), image_input=[kie_upload(i) for i in imgs],
                                       aspect_ratio="auto", resolution="2K", output_format="png"))
    gen = out.with_name(out.stem + "_gen.png")
    fetch(urls[0], gen)
    ff("-i", gen, "-vf", f"scale={wh[0]}:{wh[1]}:flags=lanczos", out)
    print(f"-> {out} {wh[0]}x{wh[1]}. Look at it before any swap: eyes open, face visible, props and product intact.")


def pick(table, name, default):
    table = table or {}
    if name in table:
        return table[name]
    keys = [k for k in table if name.startswith(k)]
    return table[max(keys, key=len)] if keys else default


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(p).name)]


def units(src):
    d = pth(src) if src != "clips" else W_ / "clips"
    return sorted((p for p in d.glob("*.mp4") if not p.stem.startswith("alt_")), key=natural)


def todo_units(src, model):
    gdir = GEN / model
    return [p for p in units(src) if not (gdir / p.name).exists()]


def quote(src="clips", model=None):
    model = model or cfg("swap.model", "seedance")
    todo = todo_units(src, model)
    short = [p for p in todo if dur(p) < cfg("swap.min_clip", 4.0)] if model == "seedance" else []
    secs = round(sum(dur(p) for p in todo if p not in short), 2)
    print(f"{len(todo)} clip(s) not generated yet, {secs}s of source on {MODELS[model]}"
          + (f" | under {cfg('swap.min_clip', 4.0)}s, skipped: {' '.join(p.stem for p in short)}" if short else ""))
    return todo, short, secs


def motion_offset(src, gen, K=5):
    """frames by which gen starts late vs src (best correlation of per-frame motion energy)"""
    import numpy as np

    def sig(p):
        b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", f"fps={FPS},scale=90:160,format=gray", "-f",
                            "rawvideo", "-"], capture_output=True).stdout
        d = np.abs(np.diff(np.frombuffer(b, np.uint8).reshape(-1, 160, 90).astype(float)[:, 70:140, 5:85], axis=0)).mean((1, 2))
        return (d - d.mean()) / (d.std() + 1e-9)
    s, g = sig(src), sig(gen)

    def c(k):
        a = s[k:]
        n = min(len(a), len(g))
        return np.corrcoef(a[:n], g[:n])[0, 1]
    return max(range(K + 1), key=c)


def remux(src, gen, dst, kind="seedance"):
    """model output + source audio at source length. Video edit models can return the whole clip uniformly retimed
    (stretch back by src/gen); motion-control models can start a few frames late (measured offset, edge frames held)."""
    s, g = dur(src), dur(gen)
    if kind == "kling":
        k = motion_offset(src, gen)
        vf = f"fps={FPS},tpad=start={k}:stop={FPS}:start_mode=clone:stop_mode=clone"
        print(f"  {Path(src).stem}: starts {k} frame(s) late, fixed")
    else:
        vf = f"setpts=PTS*{s / g:.5f},fps={FPS}"
    ff("-i", gen, "-i", src, "-map", "0:v", "-map", "1:a", "-vf", vf, "-t", f"{s:.3f}", "-c:v", "libx264", "-crf", 16,
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", dst)


def swap(names, src="clips", model=None, approved=False):
    from concurrent.futures import ThreadPoolExecutor
    model = model or cfg("swap.model", "seedance")
    if model not in ("seedance", "kling"):
        raise SystemExit("--model seedance or kling")
    todo, short, _ = quote(src, model)
    if not names:
        raise SystemExit("name the clips (or all) after the quote: swap BODY_01 H1_01 ...  or  swap all")
    todo = [p for p in todo if p not in short and ("all" in names or p.stem in names)]
    if not todo:
        print("nothing to generate (already generated, skipped, or not found)")
        return
    g = load_gate()
    g.gate([(MODELS[model], round(sum(dur(p) for p in todo), 2), "second")], approved, step="swap")
    gdir = GEN / model
    out = W_ / "swapped"
    for d in (gdir, out, W_ / "_in"):
        d.mkdir(parents=True, exist_ok=True)
    up = {}

    def refurl(f):
        if f not in up:
            up[f] = kie_upload(pth(f))
        return up[f]

    def one(p):
        refs = [refurl(f) for f in pick(cfg("swap.refs_by"), p.stem, cfg("swap.refs", []))]
        if not refs:
            raise RuntimeError("no reference image: set swap.refs in project.json (make it with  ref)")
        if model == "kling":
            inp = dict(input_urls=refs[:1], video_urls=[kie_upload(p)], mode=cfg("swap.kling_mode", "720p"),
                       character_orientation="image")
            kp = pick(cfg("swap.kling_prompts"), p.stem, cfg("swap.kling_prompt"))
            if kp:
                inp["prompt"] = kp
        else:
            small = W_ / "_in" / p.name
            ff("-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=decrease:force_divisible_by=2", "-c:v", "libx264",
               "-crf", 16, "-an", small)
            inp = dict(prompt=pick(cfg("swap.prompts"), p.stem, cfg("swap.prompt")), reference_video_urls=[kie_upload(small)],
                       reference_image_urls=refs, resolution=cfg("swap.resolution", "720p"), duration=-1,
                       generate_audio=False)
        urls = kie_run(MODELS[model], inp)
        gen = gdir / p.name
        fetch(urls[0], gen)
        remux(p, gen, out / p.name, kind=model)
        return f"{p.stem}: source {dur(p):.2f}s, model returned {dur(gen):.2f}s, remuxed to {dur(out / p.name):.2f}s"

    with ThreadPoolExecutor(int(cfg("swap.parallel", 3))) as ex:
        for p, fut in [(p, ex.submit(one, p)) for p in todo]:
            try:
                print(fut.result(), flush=True)
            except Exception as e:
                print("FAILED", p.stem, repr(e)[:300], flush=True)
    print("Next: compare every clip with its source and send the review video before the rest of the batch.")


# ------------------------------------------------------------------ edit, review, qa

def edit():
    """winner timeline rebuilt from swapped clips: audio straight from the raw, video frame-exact from the clip that
    holds each segment. A segment that runs past a clip edge holds the edge frame and is reported."""
    clips = [dict(r, raw_in=float(r["raw_in"]), raw_out=float(r["raw_out"])) for r in csv.DictReader(open(W_ / "clips/index.csv"))]
    out = W_ / "edits"
    out.mkdir(parents=True, exist_ok=True)
    raw = pth(cfg("raw"))
    for ad in ADS:
        segs = [r for r in csv.DictReader(open(W_ / "mapping.csv")) if r["ad"] == ad]
        inputs, fc = [str(raw)], []
        for n, s in enumerate(segs):
            ws, we, a, b = (float(s[k]) for k in ("win_in", "win_out", "raw_in", "raw_out"))
            c = max(clips, key=lambda c: min(b, c["raw_out"]) - max(a, c["raw_in"]))
            f = str(W_ / "swapped" / f"{c['clip']}.mp4")
            if not Path(f).exists():
                raise SystemExit(f"{f} missing: swap {c['clip']} first")
            if f not in inputs:
                inputs.append(f)
            nf = round(we * FPS) - round(ws * FPS)
            sf = round((a - c["raw_in"]) * FPS)
            pre, sf = max(0, -sf), max(0, sf)
            take = min(nf - pre, round(dur(f) * FPS) - sf)
            post = nf - pre - take
            if pre or post:
                print(f"  {ad} at {ws}s: {c['clip']} short by {pre + post} frame(s), edge frame held")
            fc.append(f"[{inputs.index(f)}:v]trim=start_frame={sf}:end_frame={sf + take},setpts=PTS-STARTPTS,scale={W}:{H},"
                      f"setsar=1,tpad=start={pre}:stop={post}:start_mode=clone:stop_mode=clone[v{n}];"
                      f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{n}];")
        k = len(segs)
        fc.append("".join(f"[v{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0[v];" +
                  "".join(f"[a{i}]" for i in range(k)) + f"concat=n={k}:v=0:a=1[a]")
        o = out / f"{ad}.mp4"
        ff(*[x for f in inputs for x in ("-i", f)], "-filter_complex", "".join(fc), "-map", "[v]", "-map", "[a]",
           "-r", FPS, "-c:v", "libx264", "-crf", 16, "-c:a", "aac", "-b:a", "192k", o)
        print(f"{ad}: {k} segments, {dur(o):.2f}s vs winner {dur(pth(cfg('winners')[ad])):.2f}s -> {o}")


def compare(a, b, out, start="0", length=None):
    t = ["-t", str(length)] if length else []
    Path(pth(out)).parent.mkdir(parents=True, exist_ok=True)
    ff("-ss", start, *t, "-i", pth(a), "-ss", start, *t, "-i", pth(b), "-filter_complex",
       f"[0:v]scale=540:960,fps={FPS},setsar=1[x];[1:v]scale=540:960,fps={FPS},setsar=1[y];[x][y]hstack[v]",
       "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-crf", 20, "-c:a", "aac", pth(out))
    print(f"-> {out} (left {Path(a).name}, right {Path(b).name})")


def qa(*files):
    import numpy as np
    for f in files:
        b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vf", "scale=90:160,format=gray", "-f", "rawvideo", "-"],
                           capture_output=True).stdout
        F = np.frombuffer(b, np.uint8).reshape(-1, 160, 90).astype(float)
        d = np.abs(np.diff(F, axis=0)).mean((1, 2))
        idx = np.where(d > 12)[0]
        double = [f"{(a + 1) / FPS:.2f}s+{b - a}f" for a, b in zip(idx, idx[1:]) if 1 <= b - a <= 3]
        frozen = [i for i in range(2, len(d) - 2) if d[i] < 0.3 and d[i - 1] > 1.5 and d[i + 1] > 1.5]
        st = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", str(f)],
                            capture_output=True, text=True).stdout.split()
        lens = {s.split(",")[0]: float(s.split(",")[1]) for s in st if "," in s and s.split(",")[1] not in ("N/A", "")}
        print(f"{Path(f).name}: {len(F)} frames, {len(idx)} cuts | double cuts: {double or 'none'} | single frozen frames: "
              f"{len(frozen)} | audio minus video {lens.get('audio', 0) - lens.get('video', 0):+.3f}s")


def speechcheck(ad, f):
    import numpy as np
    Wn, En = spec(wav8k(pth(cfg("winners")[ad]), ad)), spec(wav8k(pth(f), "x"))
    n = min(len(Wn), len(En))
    d = ((Wn[:n] - En[:n] - (Wn[:n] - En[:n]).mean(0)) ** 2).mean(1)
    bad = (d > 1.0) & (Wn[:n].mean(1) > np.percentile(Wn[:n].mean(1), 40))
    regs, k = [], 0
    while k < n:
        if bad[k]:
            j = k
            while j < n and bad[j:j + 3].any():
                j += 1
            if j - k >= 6:
                regs.append(f"{k / 100:.2f}-{j / 100:.2f}s")
            k = j
        else:
            k += 1
    print(f"{ad}: median spectral distance {float(np.median(d)):.2f} | differing spoken regions: {regs or 'none'}")


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
    ok = opt(a, "--approved", False, True)
    if cmd != "help" and not CFG and cmd not in ("compare", "qa"):
        raise SystemExit("no project.json in this folder: write it first (see the skill)")
    if cmd == "map":
        map_(opt(a, "--penalty", "10"))
    elif cmd == "cut":
        cut(opt(a, "--force", False, True))
    elif cmd == "ref":
        out, pr, t = opt(a, "--out", "renders/gen/ref/actor_in_scene.png"), opt(a, "--prompt"), opt(a, "--t", "0")
        ref(a[0], a[1] if len(a) > 1 else "-", out, pr, t, ok)
    elif cmd == "quote":
        quote(opt(a, "--src", "clips"), opt(a, "--model"))
    elif cmd == "swap":
        src, model = opt(a, "--src", "clips"), opt(a, "--model")
        swap(a, src, model, ok)
    elif cmd == "edit":
        edit()
    elif cmd == "compare":
        st, ln = opt(a, "--start", "0"), opt(a, "--length")
        compare(a[0], a[1], a[2], st, ln)
    elif cmd == "qa":
        qa(*a)
    elif cmd == "speechcheck":
        speechcheck(a[0], a[1])
    else:
        raise SystemExit(__doc__)
