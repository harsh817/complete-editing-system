#!/usr/bin/env python3
"""captions.py: word timestamps -> styled captions, hook headline and end card in one house style, burned in.
Run from the ad folder. Needs ffmpeg, Pillow. Word timestamps need mlx-whisper (Apple Silicon) or faster-whisper.

  captions.py words VIDEO [--lang en]               Whisper word timestamps -> renders/_work/captions/<NAME>.words.json
  captions.py init                                  write an example renders/_work/captions.json (style, headlines, fixes)
  captions.py build VIDEO [--words W.json]          chunks + headline + end card -> renders/_work/captions/<NAME>.ass
                                                    and <NAME>.layout.json (every text box, read by edit-qa)
  captions.py burn VIDEO [--out renders/NAME.mp4] [--engine auto|ass|pillow]
                                                    burn the .ass with libass, or the same layout with Pillow
                                                    overlays when this ffmpeg has no ass filter
  captions.py preview VIDEO [--t 1.5]               one frame with the text, the house zone (green) and Meta's
                                                    Reels bottom zone (red) -> renders/_work/captions/<NAME>_preview.png

VIDEO is a clean render (renders/ACME_2610-S3_H1_9x16_v1_clean.mp4). <NAME> is its name without _clean, which is
also the final file name: renders/ACME_2610-S3_H1_9x16_v1.mp4.

The ratio comes from the frame size (1080x1920 = 9x16, 1080x1350 = 4x5), so each ratio gets its own positions.
The hook id (H1, H2...) comes from the file name BRAND_CONCEPT_H1_9x16_v1.mp4 and picks the headline."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

CFG_FILE = Path("renders/_work/captions.json")
CAP = Path("renders/_work/captions")
META_BOTTOM = 0.65   # Meta Reels guidance: keep key text out of the bottom 35 % (check the current Ads Guide)
EXAMPLE = {
    "lang": "en",
    "font": None,
    "font_index": 0,
    "caption_style": "stroke",
    "caption_size": 68,
    "caption_min_size": 60,
    "caption_y": {"9x16": 0.74, "4x5": 0.78},
    "headline_size": 58,
    "headline_y": {"9x16": 0.20, "4x5": 0.17},
    "endcard_y": {"9x16": 0.24, "4x5": 0.19},
    "accent": "#E2121A",
    "max_words": 6,
    "max_chars": 30,
    "line_chars": 18,
    "gap_s": 0.6,
    "starters": ["and", "but", "so", "because", "when", "if", "or", "then", "which", "that"],
    "function_words": ["a", "an", "the", "of", "to", "in", "on", "for", "with", "and", "or", "my", "your", "is"],
    "fix": {"brandname": "BrandName"},
    "solo": [],
    "uppercase": False,
    "headlines": {"H1": "Headline line one|line *two*", "H2": "Second hook headline"},
    "headline_until": {"H1": None, "H2": None},
    "banners": {"H3": "WOW: buy 2, get the *third free*"},
    "banner_gap": 0.10,
    "endcard": "Tap below / Shop *now*",
    "endcard_s": 3.0,
    "safe_zone": {"9x16": [0.0602, 0.1484, 0.9398, 0.8516], "4x5": [0.06, 0.05, 0.94, 0.95]}
}
FONT_CANDIDATES = ["/System/Library/Fonts/SFNS.ttf", "C:/Windows/Fonts/seguisb.ttf", "/System/Library/Fonts/Helvetica.ttc",
                   "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def cfg():
    c = dict(EXAMPLE)
    if CFG_FILE.exists():
        c.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
    return c


def run(cmd, **kw):
    return subprocess.run([str(x) for x in cmd], capture_output=True, text=True, **kw)


def probe(f):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
             "-of", "json", f])
    j = json.loads(r.stdout)
    return int(j["streams"][0]["width"]), int(j["streams"][0]["height"]), float(j["format"]["duration"])


def ratio_of(w, h):
    r = w / h
    return "9x16" if abs(r - 9 / 16) < 0.02 else "4x5" if abs(r - 4 / 5) < 0.02 else "1x1" if abs(r - 1) < 0.02 else f"{w}x{h}"


def final_stem(path):
    return re.sub(r"_clean$", "", Path(path).stem)


def hook_of(path):
    m = re.search(r"_(H\d+)_", Path(path).name)
    return m.group(1) if m else None


def font_path(c):
    if c.get("font"):
        return c["font"]
    f = next((x for x in FONT_CANDIDATES if Path(x).exists()), None)
    if not f:
        raise SystemExit("no font found: set \"font\" in captions.json to a .ttf/.otf/.ttc path")
    return f


def font(c, size):
    from PIL import ImageFont
    f = font_path(c)
    ft = ImageFont.truetype(f, size, index=int(c.get("font_index", 0)) if f.lower().endswith(".ttc") else 0)
    try:
        ft.set_variation_by_name(c.get("font_weight", "Medium"))   # SF Pro is a variable font: pick Medium
    except Exception:
        pass
    return ft


# ------------------------------------------------------------------ words

def words(video, lang):
    out = CAP / f"{final_stem(video)}.words.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = Path(tempfile.mkdtemp()) / "a.wav"
    r = run(["ffmpeg", "-v", "error", "-y", "-i", video, "-ac", 1, "-ar", 16000, wav])
    if r.returncode:
        raise SystemExit(r.stderr)
    try:
        import mlx_whisper
        res = mlx_whisper.transcribe(str(wav), language=lang, word_timestamps=True,
                                     path_or_hf_repo="mlx-community/whisper-large-v3-turbo")
        ws = [(w["word"], w["start"], w["end"]) for s in res["segments"] for w in s.get("words", [])]
    except ImportError:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise SystemExit("install a Whisper: pip install mlx-whisper (Apple Silicon) or pip install faster-whisper")
        segs, _ = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8").transcribe(str(wav), language=lang,
                                                                                              word_timestamps=True)
        ws = [(w.word, w.start, w.end) for s in segs for w in (s.words or [])]
    data = {"words": [{"text": t.strip(), "start": round(s, 3), "end": round(e, 3)} for t, s, e in ws if t.strip()]}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"-> {out} ({len(data['words'])} words). Read it against the script: brand names, numbers.")


# ------------------------------------------------------------------ chunking

def clean(w):
    return re.sub(r"[^\w']", "", w.lower())


def chunk(ws, c):
    """phrase chunks: new chunk on max words / chars, a pause, a sentence end, or before a starter word;
    a chunk never ends on a function word; solo words get their own chunk"""
    starters, func, solo = set(c["starters"]), set(c["function_words"]), {s.lower() for s in c["solo"]}
    chunks, cur = [], []
    for i, w in enumerate(ws):
        t = w["text"]
        if cur:
            text_len = len(" ".join(x["text"] for x in cur)) + 1 + len(t)
            prev = cur[-1]
            brk = (len(cur) >= c["max_words"] or text_len > c["max_chars"] or w["start"] - prev["end"] > c["gap_s"]
                   or re.search(r"[.!?]$", prev["text"]) or (clean(t) in starters and len(cur) >= 2)
                   or clean(t) in solo or clean(prev["text"]) in solo)
            if brk:
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    for i in range(len(chunks) - 1):
        while len(chunks[i]) > 1 and clean(chunks[i][-1]["text"]) in func:
            chunks[i + 1].insert(0, chunks[i].pop())
    return [ch for ch in chunks if ch]


def fix_text(t, c):
    for wrong, right in c["fix"].items():
        t = re.sub(r"(?i)\b" + re.escape(wrong) + r"\b", right, t)
    return t.upper() if c["uppercase"] else t


def two_lines(t, limit):
    """split on meaning: after punctuation first, else the space nearest the middle; ' / ' forces the break"""
    if " / " in t:
        return [x.strip() for x in t.split(" / ", 1)]
    if len(t) <= limit:
        return [t]
    sp = [m.start() for m in re.finditer(" ", t)]
    if not sp:
        return [t]
    punct = [i for i in sp if t[i - 1] in ",.;:!?"]
    pool = punct or sp
    best = min(pool, key=lambda i: abs(i - len(t) / 2))
    return [t[:best].strip(), t[best:].strip()]


def events(video, words_file, c):
    W, H, D = probe(video)
    ratio = ratio_of(W, H)
    ws = json.loads(Path(words_file).read_text(encoding="utf-8"))["words"]
    ev = []
    hook = hook_of(video)
    hl = c["headlines"].get(hook) if hook else None
    hl_until = (c.get("headline_until") or {}).get(hook) if hook else None
    chunks = chunk(ws, c)
    if hl and not hl_until:
        first_scene = chunks[1][0]["start"] if len(chunks) > 1 else D
        hl_until = min(D, max(first_scene, 2.0))
    last_word = ws[-1]["end"] if ws else 0.0
    ec_from = min(max(D - float(c["endcard_s"]), last_word + 0.1), D - 1.0) if c.get("endcard") else D
    for k, ch in enumerate(chunks):
        s = ch[0]["start"]
        nxt = chunks[k + 1][0]["start"] if k + 1 < len(chunks) else None
        e = nxt if nxt is not None and nxt - ch[-1]["end"] < 0.3 else ch[-1]["end"] + 0.1
        e = max(e, s + 0.4)
        if s >= ec_from:
            continue
        text = fix_text(" ".join(w["text"] for w in ch), c)
        if hl and s < hl_until and clean(text) and clean(text) in clean(hl.replace("|", " ").replace("*", "")):
            continue
        ev.append(dict(kind="caption", start=round(s, 3), end=round(min(e, ec_from), 3),
                       lines=two_lines(text, c["line_chars"])))
    if hl:
        ev.append(dict(kind="headline", start=0.0, end=round(hl_until, 3), lines=[x.strip() for x in hl.split("|")]))
    banner = (c.get("banners") or {}).get(hook) if hook else None
    if banner:   # offer banner: only on the hook that carries the offer, whole ad, end card included
        ev.append(dict(kind="banner", start=0.0, end=round(D, 3), lines=[x.strip() for x in banner.split("|")]))
    if c.get("endcard"):
        ev.append(dict(kind="endcard", start=round(ec_from, 3), end=round(D, 3),
                       lines=[x.strip() for x in c["endcard"].split(" / ")]))
    return W, H, ratio, ev


# ------------------------------------------------------------------ layout (shared by both engines and by edit-qa)

def spans(line):
    """'Shop *now*' -> [('Shop ', False), ('now', True)]"""
    out = []
    for i, part in enumerate(line.split("*")):
        if part:
            out.append((part, i % 2 == 1))
    return out


def plain(line):
    return line.replace("*", "")


def layout(W, H, ratio, ev, c):
    """pixel box of every event; captions shrink from caption_size to caption_min_size before they overflow"""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    margin = int(W * 0.07)
    for e in ev:
        if e["kind"] == "caption":
            size, y = c["caption_size"], c["caption_y"].get(ratio, 0.74)
        elif e["kind"] in ("headline", "banner"):
            size, y = c["headline_size"], c["headline_y"].get(ratio, 0.20)
            if e["kind"] == "headline" and any(x["kind"] == "banner" for x in ev):
                y += c.get("banner_gap", 0.10)   # a hook with both: the headline sits under the banner
        else:
            size, y = c["headline_size"], c["endcard_y"].get(ratio, 0.24)
            if any(x["kind"] == "banner" for x in ev):
                y += c.get("banner_gap", 0.10)   # the end card moves below the banner
        while True:
            f = font(c, size)
            widths = [d.textlength(plain(l), font=f) for l in e["lines"]]
            if max(widths) <= W - 2 * margin or size <= c["caption_min_size"]:
                break
            size -= 2
        asc, desc = f.getmetrics()
        lh = int((asc + desc) * 1.12)
        pad = int(size * 0.28) if e["kind"] != "caption" or c["caption_style"] == "box" else int(size * 0.08)
        bw, bh = int(max(widths)) + 2 * pad, lh * len(e["lines"]) + 2 * pad
        cy = int(H * y)
        e.update(size=size, line_h=lh, pad=pad, box=[int((W - bw) / 2), int(cy - bh / 2), bw, bh])
    return ev


# ------------------------------------------------------------------ ASS

def ass_color(hexrgb, alpha=0):
    h = hexrgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t):
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, W, H, ev, c):
    fname = font(c, 20).getname()[0]   # the family name libass looks up, not the file name
    acc = ass_color(c["accent"])
    white, black = "&H00FFFFFF", "&H00000000"
    cap_style = (f"Style: Caption,{fname},{c['caption_size']},{white},{white},{black},{black},1,0,0,0,100,100,0,0,1,"
                 f"{max(3, c['caption_size'] // 14)},0,5,0,0,0,1")
    if c["caption_style"] == "box":
        cap_style = (f"Style: Caption,{fname},{c['caption_size']},{black},{black},{white},{white},1,0,0,0,100,100,0,0,3,"
                     f"{max(6, c['caption_size'] // 5)},0,5,0,0,0,1")
    box = (f"Style: Box,{fname},{c['headline_size']},{black},{black},{white},{white},1,0,0,0,100,100,0,0,3,"
           f"{max(8, c['headline_size'] // 4)},0,5,0,0,0,1")
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding", cap_style, box, "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    rows = []
    for e in ev:
        x, y, bw, bh = e["box"]
        style = "Caption" if e["kind"] == "caption" else "Box"
        base = white if style == "Caption" and c["caption_style"] != "box" else black
        txt = "\\N".join("".join(("{\\c" + acc + "}" + p + "{\\c" + base + "}") if a else p for p, a in spans(l))
                         for l in e["lines"])
        rows.append(f"Dialogue: {1 if style == 'Box' else 0},{ass_time(e['start'])},{ass_time(e['end'])},{style},,0,0,0,,"
                    f"{{\\fs{e['size']}\\pos({x + bw // 2},{y + bh // 2})}}{txt}")
    Path(path).write_text("\n".join(head + rows) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ Pillow engine

def render_png(e, c, out):
    from PIL import Image, ImageDraw
    x, y, bw, bh = e["box"]
    f = font(c, e["size"])
    stroke = c["caption_style"] == "stroke" and e["kind"] == "caption"
    sw = max(3, e["size"] // 14) if stroke else 0
    img = Image.new("RGBA", (bw + 2 * sw, bh + 2 * sw), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not stroke:
        d.rounded_rectangle([sw, sw, sw + bw, sw + bh], radius=int(e["size"] * 0.25), fill=(255, 255, 255, 255))
    base = (255, 255, 255, 255) if stroke else (0, 0, 0, 255)
    acc = tuple(int(c["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    for i, line in enumerate(e["lines"]):
        lw = d.textlength(plain(line), font=f)
        cx = sw + (bw - lw) / 2
        cy = sw + e["pad"] + i * e["line_h"]
        for part, accent in spans(line):
            d.text((cx, cy), part, font=f, fill=acc if accent else base,
                   stroke_width=sw, stroke_fill=(0, 0, 0, 255) if stroke else None)
            cx += d.textlength(part, font=f)
    img.save(out)
    return x - sw, y - sw


def has_ass_filter():
    r = run(["ffmpeg", "-hide_banner", "-filters"])
    return bool(re.search(r"^\s*\S+\s+ass\s", r.stdout, re.M))


def burn(video, out, engine="auto"):
    stem = final_stem(video)
    ass, lay = CAP / f"{stem}.ass", CAP / f"{stem}.layout.json"
    if not ass.exists() or not lay.exists():
        raise SystemExit(f"run  captions.py build {video}  first")
    out = Path(out or Path("renders") / f"{stem}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} exists: never overwritten. Render the next version (reframe.py render --bump)")
    if engine == "auto":
        engine = "ass" if has_ass_filter() else "pillow"
    c = cfg()
    if engine == "ass":
        fontsdir = Path(font_path(c)).parent
        vf = f"ass={ass.as_posix()}:fontsdir={fontsdir.as_posix()}"
        r = run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", vf, "-c:v", "libx264", "-crf", 18, "-preset", "medium",
                 "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out])
    else:
        ev = json.loads(lay.read_text(encoding="utf-8"))["events"]
        tmp = Path(tempfile.mkdtemp())
        args, graph, last = ["ffmpeg", "-v", "error", "-y", "-i", video], [], "0:v"
        for i, e in enumerate(ev):
            png = tmp / f"e{i:03d}.png"
            px, py = render_png(e, c, png)
            args += ["-loop", "1", "-i", png]
            graph.append(f"[{last}][{i + 1}:v]overlay={px}:{py}:shortest=1:enable='between(t,{e['start']:.3f},{e['end'] - 0.001:.3f})'[o{i}]")
            last = f"o{i}"
        if not ev:
            raise SystemExit("no events to burn")
        r = run(args + ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-map", "0:a?", "-c:v", "libx264", "-crf", 18,
                        "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out])
    if r.returncode:
        raise SystemExit(f"burn failed ({engine}): {r.stderr[-500:]}")
    print(f"-> {out} (engine: {engine})")


def preview(video, t):
    from PIL import Image, ImageDraw
    stem = final_stem(video)
    lay = json.loads((CAP / f"{stem}.layout.json").read_text(encoding="utf-8"))
    c = cfg()
    png = CAP / f"{stem}_preview.png"
    run(["ffmpeg", "-v", "error", "-y", "-ss", t, "-i", video, "-frames:v", 1, png])
    img = Image.open(png).convert("RGBA")
    W, H = img.size
    for e in lay["events"]:
        if e["start"] <= float(t) < e["end"]:
            tile = Path(tempfile.mkdtemp()) / "t.png"
            px, py = render_png(e, c, tile)
            img.alpha_composite(Image.open(tile), (max(px, 0), max(py, 0)))
    z = lay["safe_zone"]
    d = ImageDraw.Draw(img)
    d.rectangle([z[0] * W, z[1] * H, z[2] * W, z[3] * H], outline=(0, 255, 0, 255), width=4)
    if lay["ratio"] == "9x16":
        d.line([0, META_BOTTOM * H, W, META_BOTTOM * H], fill=(255, 0, 0, 255), width=4)
    img.convert("RGB").save(png)
    print(f"-> {png} (green = house text zone, red = top of Meta's Reels bottom zone)")


def build(video, words_file=None):
    c = cfg()
    stem = final_stem(video)
    words_file = words_file or CAP / f"{stem}.words.json"
    if not Path(words_file).exists():
        raise SystemExit(f"no words file {words_file}: run  captions.py words {video}")
    W, H, ratio, ev = events(video, words_file, c)
    ev = layout(W, H, ratio, ev, c)
    CAP.mkdir(parents=True, exist_ok=True)
    write_ass(CAP / f"{stem}.ass", W, H, ev, c)
    zone = c["safe_zone"].get(ratio, [0.05, 0.05, 0.95, 0.95])
    (CAP / f"{stem}.layout.json").write_text(json.dumps(
        {"video": str(video), "size": [W, H], "ratio": ratio, "safe_zone": zone, "events": ev}, ensure_ascii=False, indent=1))
    out_zone = [e for e in ev if not (e["box"][0] >= zone[0] * W and e["box"][1] >= zone[1] * H and
                                      e["box"][0] + e["box"][2] <= zone[2] * W and e["box"][1] + e["box"][3] <= zone[3] * H)]
    n = {k: sum(1 for e in ev if e["kind"] == k) for k in ("caption", "headline", "banner", "endcard")}
    print(f"-> {CAP}/{stem}.ass + .layout.json | {ratio} | {n['caption']} captions, {n['headline']} headline, {n['banner']} banner, "
          f"{n['endcard']} end card | outside the house zone: {len(out_zone)}")
    for e in out_zone:
        print(f"   OUTSIDE: {e['kind']} {e['start']}s '{' / '.join(e['lines'])}' box {e['box']}")
    low = [e for e in ev if ratio == "9x16" and e["box"][1] + e["box"][3] > META_BOTTOM * H]
    if low:
        print(f"   NOTE: {len(low)} text block(s) reach into Meta's Reels bottom 35 % (below y = {int(META_BOTTOM * H)}). "
              "The house caption line sits there on purpose: check the hook in the Ads Manager placement preview, "
              "and set caption_y to 0.60 for this ad if the Reels interface covers the captions.")


def opt(a, name, default=None):
    if name not in a:
        return default
    i = a.index(name)
    v = a[i + 1]
    del a[i:i + 2]
    return v


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a.pop(0) if a else "help"
    if cmd == "words":
        lang = opt(a, "--lang", cfg()["lang"])
        words(a[0], lang)
    elif cmd == "init":
        if CFG_FILE.exists():
            raise SystemExit("captions.json exists: edit it")
        CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps(EXAMPLE, indent=1, ensure_ascii=False))
        print(f"wrote {CFG_FILE}: set the headlines, end card, fixes and font")
    elif cmd == "build":
        w = opt(a, "--words")
        build(a[0], w)
    elif cmd == "burn":
        out, eng = opt(a, "--out"), opt(a, "--engine", "auto")
        burn(a[0], out, eng)
    elif cmd == "preview":
        t = opt(a, "--t", "1.0")
        preview(a[0], t)
    else:
        raise SystemExit(__doc__)
