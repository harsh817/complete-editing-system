#!/usr/bin/env python3
"""timing.py: Suno song ads. New songs and hook versions through kie.ai, Suno's own word timestamps, and one timing
grid per hook built from the script. Run from the ad folder. Paid commands need KIE_API_KEY and Skill 12 (gate.py):
without --approved they print the quote and stop.

  timing.py song --lyrics renders/_work/lyrics_h1.txt --style "<style>" [--hook H1] [--vocal f|m] [--instrumental] [--approved]
        Suno makes 2 takes -> audio/music/h1_v1.mp3, h1_v2.mp3 + word timings (audio/music/h1_v1.words.json ...)
  timing.py stt audio/music/h1.mp3 [--hook H1] [--lyrics renders/_work/lyrics_h1.txt] [--approved]
        word timestamps for a song made in the Suno app: kie re-reads it through "upload and extend" from its last 1.5 s,
        then asks Suno for the aligned words; only words before the extension point are kept
  timing.py hook --song audio/music/h1.mp3 --grid renders/_work/grid_h1.md --hook H2 [--style "<style>"] [--approved]
        same song, new hook: Suno rewrites the opening (up to the first module boundary at or after 10 s) with Hook 2's
        lines and blends it into the untouched rest -> audio/music/h2_v1.mp3, h2_v2.mp3 + timings
  timing.py grid --song audio/music/h1.mp3 --hook H1 [--words audio/music/h1.words.json] [--script renders/_work/script.json] [--out renders/_work/grid_h1.md]
        module start = first sung word of each module (Hook n of this hook, Scene n, CTA); Outro = instrumental tail. Free.
  timing.py bodyonly --song audio/music/h2.mp3 --grid renders/_work/grid_h2.md --hook H3 [--from "Scene 1"]
        a hook that starts on the body: cuts the song at that module -> audio/music/h3.mp3 + renders/_work/grid_h3.md. Free.

renders/_work/script.json = [["Hook 1", "text"], ["Hook 2", "text"], ["Scene 1", "text"], ..., ["CTA", "text"]] in brief order.
Inside a text, " | " separates captions and " / " forces a line break. Never time sung vocals with Whisper: it drops
whole sung sections. The Suno model names below are the ones kie exposed when this was written: check kie's docs."""

# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")

import difflib, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

KIE = "https://api.kie.ai/api/v1"
UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
SUNO_MODEL = os.environ.get("SUNO_MODEL", "V6")   # the Suno version kie offers; check kie's docs
STYLE = "catchy upbeat pop, clear lead vocal, vocals start immediately, no instrumental intro"
M_GEN, M_EXT, M_REP, M_TS = ("ai-music-api/generate", "ai-music-api/upload-and-extend-audio",
                             "ai-music-api/replace-section", "ai-music-api/timeStamped-lyrics")


def load_gate():
    """import gate.py from Skill 12 (gated-generation)"""
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


def key():
    k = os.environ.get("KIE_API_KEY", "").strip()
    if not k:
        raise SystemExit("KIE_API_KEY is not set. Export it in your shell profile. Never paste it in the chat.")
    return k


def api(path, body=None):
    req = urllib.request.Request(KIE + path, method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def upload(path):
    r = subprocess.run(["curl", "-sS", "-X", "POST", UPLOAD, "-H", f"Authorization: Bearer {key()}",
                        "-F", f"file=@{path}", "-F", "uploadPath=song-timing"], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout).get("data") or {}
    url = d.get("downloadUrl") or d.get("fileUrl")
    if not url:
        raise SystemExit(f"upload failed: {r.stdout[:300]}")
    return url


def task(model, inp, timeout=900):
    """submit one kie task, poll, return (task_id, result records). Failed tasks raise."""
    r = api("/jobs/createTask", {"model": model, "input": inp})
    tid = (r.get("data") or {}).get("taskId")
    if not tid:
        raise SystemExit(f"{model} refused: {r.get('msg') or r}")
    Path("renders/_work/song_jobs").mkdir(parents=True, exist_ok=True)
    Path(f"renders/_work/song_jobs/{tid}.payload.json").write_text(json.dumps({"model": model, "input": inp}, indent=1))
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(10)
        d = api(f"/jobs/recordInfo?taskId={tid}").get("data") or {}
        if d.get("state") == "fail":
            raise SystemExit(f"{model} failed: {d.get('failMsg')}")
        if d.get("state") == "success":
            res = json.loads(d["resultJson"])
            Path(f"renders/_work/song_jobs/{tid}.result.json").write_text(json.dumps(res, indent=1))
            return tid, res
    raise SystemExit(f"task {tid} still running after {timeout}s: check it in the kie dashboard, then rerun")


def timestamps(task_id, audio_id):
    d = api("/jobs/createTask", {"model": M_TS, "input": {"task_id": task_id, "audio_id": audio_id}})
    words = ((d.get("data") or {}).get("data") or {}).get("alignedWords")
    if not words:
        raise SystemExit(f"no timestamps for {audio_id}: {str(d)[:300]}")
    return words


def norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True).stdout)


def save_words(words, path, until=None, **meta):
    """Suno alignedWords -> {"words": [{"text", "start", "end"}]}, section tags stripped"""
    out = [{"text": re.sub(r"\[[^\]]*\]", "", w["word"]).strip(), "start": w["startS"], "end": w["endS"]}
           for w in words if (until is None or w["startS"] < until) and w["endS"] - w["startS"] < 4]
    out = [w for w in out if norm(w["text"])]
    Path(path).write_text(json.dumps({"source": "suno", **meta, "words": out}, ensure_ascii=False, indent=1))
    print(f"-> {path} ({len(out)} words)")


def lines(text):
    return [l.strip() for l in text.replace(" / ", " ").split("|") if l.strip()]


def script(path="renders/_work/script.json"):
    if not Path(path).exists():
        raise SystemExit(f"{path} not found: write it from the brief (see the skill)")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def body_lines(sc):
    return [l for k, v in sc if not k.startswith("Hook") and k != "Outro" for l in lines(v)]


def hook_lines(sc, hook):
    k = "Hook " + re.sub(r"\D", "", hook)
    v = dict(sc).get(k)
    if v is None:
        raise SystemExit(f"{k} not in script.json")
    return lines(v)


def takes(res, tid, n, timed=True):
    Path("audio/music").mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(res["data"], 1):
        mp3 = f"audio/music/h{n}_v{i}.mp3"
        if Path(mp3).exists():
            os.replace(mp3, f"audio/music/alt_h{n}_v{i}_{time.strftime('%H%M%S')}.mp3")
        subprocess.run(["curl", "-sS", "-o", mp3, t["audio_url"]], check=True)
        print(f"-> {mp3} ({t.get('duration', 0):.1f} s)")
        if timed:
            w = timestamps(tid, t["id"])
            save_words(w, f"audio/music/h{n}_v{i}.words.json", task_id=tid, audio_id=t["id"])
            if w and w[0]["startS"] > 1.5:
                print(f"  WARNING v{i} opens on {w[0]['startS']:.1f} s of intro before the first word: discard it")
    print(f"Listen to both takes. Keep one:  mv audio/music/h{n}_v1.mp3 audio/music/h{n}.mp3"
          + (f" && mv audio/music/h{n}_v1.words.json audio/music/h{n}.words.json" if timed else ""))


def song(lyrics, style, hook, vocal, instrumental, approved):
    g = load_gate()
    g.gate([(M_GEN, 1, "clip")], approved, step="song")
    n = re.sub(r"\D", "", hook) or "1"
    inp = {"custom_mode": True, "instrumental": instrumental, "model": SUNO_MODEL, "title": f"h{n}", "style": style}
    if not instrumental:
        inp["lyrics"] = Path(lyrics).read_text(encoding="utf-8")
    if vocal:
        inp["vocal_gender"] = vocal
    tid, res = task(M_GEN, inp)
    takes(res, tid, n, timed=not instrumental)


def stt(song_file, hook, lyrics, approved):
    g = load_gate()
    g.gate([(M_EXT, 1, "clip")], approved, step="song")
    stem = Path(song_file).stem
    sc = script()
    hook = hook or "H" + (re.sub(r"\D", "", stem) or "1")
    text = Path(lyrics).read_text(encoding="utf-8") if lyrics else "[Verse]\n" + "\n".join(hook_lines(sc, hook) + body_lines(sc))
    at = round(dur(song_file) - 1.5, 2)
    tid, res = task(M_EXT, {"upload_url": upload(song_file), "model": SUNO_MODEL, "continue_at": at, "lyrics": text,
                            "style": STYLE, "title": stem})
    track = res["data"][0]
    save_words(timestamps(tid, track["id"]), str(Path(song_file).with_suffix(".words.json")), until=at, task_id=tid, audio_id=track["id"])


def grid_rows(grid):
    rx = re.compile(r"^\| ([^|]+?) \| ([\d.]+) \| ([\d.]+) \| [\d.]+ \| (.*) \|$")
    return [(m[1], float(m[2]), float(m[3]), m[4]) for m in (rx.match(l.rstrip()) for l in open(grid)) if m]


def hook(song_file, grid, new_hook, style, approved):
    sc, rows = script(), grid_rows(grid)
    n = re.sub(r"\D", "", new_hook)
    end = next((s for k, s, e, t in rows if not k.startswith("Hook") and s >= 10.0), None)
    if end is None:
        raise SystemExit("no module boundary at or after 10 s in the grid (Suno replaces at least 10 s)")
    if end > dur(song_file) / 2:
        raise SystemExit(f"the hook window ({end:.1f} s) is over half the song: Suno refuses it")
    g = load_gate()
    g.gate([(M_REP, 1, "clip")], approved, step="song")
    sung = [k for k, s, e, t in rows if not k.startswith("Hook") and s < end]
    seg = hook_lines(sc, new_hook) + [l for k, v in sc if k in sung for l in lines(v)]
    full = seg + [l for k, v in sc if not k.startswith("Hook") and k != "Outro" and k not in sung for l in lines(v)]
    tid, res = task(M_REP, {"upload_url": upload(song_file), "model": SUNO_MODEL, "prompt": "\n".join(seg),
                            "lyrics": "[Verse]\n" + "\n".join(seg), "full_lyrics": "[Verse]\n" + "\n".join(full),
                            "tags": style, "title": f"h{n}", "infill_start_s": 0.0, "infill_end_s": round(end, 2)})
    takes(res, tid, n)
    print(f"(the seam is near {end:.1f} s: listen there first)")


def load_words(path):
    J = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(norm(w["text"]), w["start"], min(w.get("end", w["start"]), w["start"] + 1.0))
            for w in J.get("words", []) if norm(w["text"])]


def similar(a, b):
    return a == b or (len(a) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def build_grid(song_file, hook, words_path, script_path, out):
    hn = re.sub(r"\D", "", hook)
    mods = [(k, v) for k, v in script(script_path) if k != "Outro" and (not k.startswith("Hook") or k == f"Hook {hn}")]
    words, total = load_words(words_path), dur(song_file)
    toks, owner = [], []
    for mi, (_, text) in enumerate(mods):
        for w in text.replace(" | ", " ").replace(" / ", " ").split():
            if norm(w):
                toks.append(norm(w))
                owner.append(mi)
    match = {}
    for blk in difflib.SequenceMatcher(None, toks, [w[0] for w in words], autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            match[blk.a + k] = blk.b + k
    starts, ptr, last_end = [], 0, 0.0
    for mi in range(len(mods)):
        idx = [i for i, o in enumerate(owner) if o == mi]
        first = toks[idx[0]]
        hit = next((j for j in range(ptr, len(words)) if similar(words[j][0], first)), None)
        matched = [match[i] for i in idx if i in match and match[i] >= ptr]
        if hit is None or (matched and hit > matched[0] + 3):
            if matched:
                i0 = next(i for i in idx if i in match and match[i] >= ptr)
                hit = match[i0] - idx.index(i0)
            else:
                hit = ptr
        hit = max(hit, ptr)
        starts.append(0.0 if mi == 0 else words[min(hit, len(words) - 1)][1])
        tail = [match[i] for i in idx if i in match and match[i] >= hit]
        ptr = (max(tail) + 1) if tail else hit + len(idx)
        if tail:
            last_end = words[max(tail)][2]
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 0.5)
    end_sung = min(total, max(last_end, starts[-1] + 1.0) + 0.4)
    rows = [(k, s, e, t) for (k, t), s, e in zip(mods, starts, starts[1:] + [end_sung])]
    rows.append(("Outro", end_sung, total, "instrumental tail: end card"))
    write_grid(out, f"{hook} timing grid (song {song_file} = {total:.3f} s, words {words_path})", rows)
    for k, s, e, t in rows:
        print(f"  {k:9} {s:7.2f} {e:7.2f}  {t[:60]}")


def write_grid(out, title, rows):
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        f.write(f"# {title}\n\n| module | start | end | dur s | lyric |\n|---|---|---|---|---|\n")
        for k, s, e, t in rows:
            f.write(f"| {k} | {s:.2f} | {e:.2f} | {e - s:.2f} | {t} |\n")
    print(f"-> {out}")


def bodyonly(song_file, grid, hook, frm):
    rows = grid_rows(grid)
    t0 = next((s for k, s, e, t in rows if k == frm), None)
    if t0 is None:
        raise SystemExit(f"{frm} not in {grid}")
    n = re.sub(r"\D", "", hook)
    out_song, out_grid = f"audio/music/h{n}.mp3", f"renders/_work/grid_h{n}.md"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-i", song_file, "-af", "afade=t=in:d=0.03", out_song],
                   check=True)
    kept = [(k, s - t0, e - t0, t) for k, s, e, t in rows if s >= t0 - 0.01 and not k.startswith("Hook")]
    write_grid(out_grid, f"{hook} timing grid ({song_file} cut at {t0:.2f} s, body only)", kept)
    print(f"-> {out_song} ({dur(out_song):.2f} s). Word times of {song_file} shift by {-t0:.2f} s for this hook.")


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
    if cmd == "song":
        inst = opt(a, "--instrumental", False, True)
        st = opt(a, "--style")
        if not st:
            raise SystemExit('song needs --style "<Suno style prompt>"')
        song(opt(a, "--lyrics"), st, opt(a, "--hook", "H1"), opt(a, "--vocal"), inst, ok)
    elif cmd == "stt":
        h, ly = opt(a, "--hook"), opt(a, "--lyrics")
        stt(a[0], h, ly, ok)
    elif cmd == "hook":
        hook(opt(a, "--song"), opt(a, "--grid"), opt(a, "--hook"), opt(a, "--style", STYLE), ok)
    elif cmd == "grid":
        s = opt(a, "--song")
        h = opt(a, "--hook", "H1")
        stem = Path(s).stem
        build_grid(s, h, opt(a, "--words", str(Path(s).with_suffix(".words.json"))), opt(a, "--script", "renders/_work/script.json"),
                   opt(a, "--out", f"renders/_work/grid_{stem}.md"))
    elif cmd == "bodyonly":
        bodyonly(opt(a, "--song"), opt(a, "--grid"), opt(a, "--hook"), opt(a, "--from", "Scene 1"))
    else:
        raise SystemExit(__doc__)
