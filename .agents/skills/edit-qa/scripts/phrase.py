#!/usr/bin/env python3
"""phrase.py: cut a spoken phrase (a time-bound claim, a word compliance flagged) from a clean render, on frame-aligned
joins that still read as speech. Run from the ad folder. Needs ffmpeg, numpy; Whisper (mlx-whisper or faster-whisper)
to verify the joins.

  phrase.py find FILE "in one week" [--words W.json]   candidate joins around every hit -> renders/_work/cuts/<name>.cuts.json
  phrase.py apply FILE                                 drop those ranges from audio and video -> the next version of FILE

Speech has no pause between words ("weight in one week" runs together), so energy alone lies. With Whisper, each
candidate join is re-transcribed and kept only if it reads "<word before> <word after>". Without Whisper the joins
are ranked by energy and marked UNVERIFIED: listen to every one."""
import json, re, subprocess, sys, tempfile, wave
from pathlib import Path

SR = 16000


def fps_of(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate",
                        "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip()
    n, d = r.split("/")
    return round(float(n) / float(d))


def pcm(f):
    import numpy as np
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(b, np.int16).astype(float)


def norm(s):
    return re.sub(r"[^\w' ]", "", s.lower()).split()


def transcribe(wav):
    try:
        import mlx_whisper
        return mlx_whisper.transcribe(str(wav), path_or_hf_repo="mlx-community/whisper-large-v3-turbo")["text"]
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
        segs, _ = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8").transcribe(str(wav))
        return " ".join(s.text for s in segs)
    except ImportError:
        return None


def name_of(f):
    return re.sub(r"_clean$", "", Path(f).stem)


def find(f, phrase, words_file=None):
    import numpy as np
    words_file = Path(words_file or Path("renders/_work/captions") / f"{name_of(f)}.words.json")
    if not words_file.exists():
        raise SystemExit(f"no {words_file}: run  captions.py words {f}  first (Skill 14)")
    W = json.loads(words_file.read_text(encoding="utf-8"))["words"]
    fps = fps_of(f)
    x = pcm(f)
    target = norm(phrase)
    toks = [" ".join(norm(w["text"])) for w in W]
    hits = [i for i in range(1, len(W) - len(target)) if toks[i:i + len(target)] == target]
    if not hits:
        raise SystemExit(f"'{phrase}' not found in {words_file}. Check the spelling against the transcript.")
    rms = lambda t: float(np.sqrt((x[max(0, int((t - 0.01) * SR)):int((t + 0.01) * SR)] ** 2).mean() + 1e-9))
    near = lambda t: min([k / fps for k in range(round((t - 0.08) * fps), round((t + 0.08) * fps) + 1)], key=rms)
    tmp = Path(tempfile.mkdtemp())
    out = []
    for i in hits:
        prev, nxt = W[i - 1], W[i + len(target)]
        lo = (prev["end"] + W[i]["start"]) / 2
        hi = (W[i + len(target) - 1]["end"] + nxt["start"]) / 2
        a0, c0 = near(lo), near(hi)
        want = f"{' '.join(norm(prev['text']))} {' '.join(norm(nxt['text']))}"
        cands = [(round(a, 3), round(c, 3)) for a in (a0 - 1 / fps, a0, a0 + 1 / fps)
                 for c in (c0 - 1 / fps, c0, c0 + 1 / fps, c0 + 2 / fps, c0 + 3 / fps)]
        ok, verified = [], True
        for a, c in cands:
            A, C = int(a * SR), int(c * SR)
            l, r = x[max(0, A - 2 * SR):A].copy(), x[C:C + 2 * SR].copy()
            l[-128:] *= np.linspace(1, 0, 128)
            r[:128] *= np.linspace(0, 1, 128)
            wv = wave.open(str(tmp / "j.wav"), "wb")
            wv.setnchannels(1), wv.setsampwidth(2), wv.setframerate(SR)
            wv.writeframes(np.concatenate([l, r]).astype(np.int16).tobytes())
            wv.close()
            txt = transcribe(tmp / "j.wav")
            if txt is None:
                verified = False
                break
            if want in " ".join(norm(txt)):
                ok.append((a, c))
        if not verified:
            best = min(cands, key=lambda p: rms(p[0]) + rms(p[1]))
            print(f"@{W[i]['start']:.2f}s: cut {best[0]:.2f}-{best[1]:.2f} by energy only. UNVERIFIED: install Whisper or "
                  f"listen to the join '{want}'")
            out.append({"start": best[0], "end": best[1], "verified": False, "join": want})
            continue
        if not ok:
            print(f"@{W[i]['start']:.2f}s: NO clean join reads '{want}'. Pick it by ear, or hide the cut with a punch-in")
            continue
        best = min(ok, key=lambda p: abs(p[0] - a0) + abs(p[1] - c0 - 1 / fps))
        print(f"@{W[i]['start']:.2f}s: cut {best[0]:.2f}-{best[1]:.2f} ({len(ok)}/{len(cands)} joins read '{want}')"
              + ("  FRAGILE: listen to it" if len(ok) <= 2 else ""))
        out.append({"start": best[0], "end": best[1], "verified": True, "join": want, "good_joins": len(ok)})
    p = Path("renders/_work/cuts") / f"{Path(f).stem}.cuts.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"file": str(f), "phrase": phrase, "cuts": out}, indent=1))
    print(f"-> {p}")


def bump(f):
    m = re.search(r"_v(\d+)", Path(f).name)
    if not m:
        return Path(f).with_name(Path(f).stem + "_cut.mp4")
    v = int(m.group(1)) + 1
    while True:
        cand = Path(f).with_name(Path(f).name.replace(m.group(0), f"_v{v}", 1))
        if not cand.exists() and not any(Path("exports").glob(f"*/{re.sub(r'_clean', '', cand.name)}")):
            return cand
        v += 1


def apply(f):
    p = Path("renders/_work/cuts") / f"{Path(f).stem}.cuts.json"
    cuts = sorted((c["start"], c["end"]) for c in json.loads(p.read_text(encoding="utf-8"))["cuts"])
    if not cuts:
        raise SystemExit("no cuts to apply")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                               capture_output=True, text=True).stdout)
    keep, t = [], 0.0
    for a, c in cuts:
        keep.append((t, a))
        t = c
    keep.append((t, dur))
    fc = []
    for i, (a, b) in enumerate(keep):
        fc.append(f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS[v{i}];"
                  f"[0:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,"
                  f"areverse,afade=t=in:d=0.008,areverse[a{i}];")
    n = len(keep)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    out = bump(f)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-filter_complex", "".join(fc), "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-400:])
    removed = sum(c - a for a, c in cuts)
    print(f"-> {out} ({removed:.2f}s removed in {len(cuts)} cut(s)). The image jumps at each cut: offer a punch-in to hide it. "
          "Then run the words and captions again on this file: every caption after the cut moved.")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a.pop(0) if a else "help"
    if cmd == "find":
        w = None
        if "--words" in a:
            i = a.index("--words")
            w = a[i + 1]
            del a[i:i + 2]
        find(a[0], a[1], w)
    elif cmd == "apply":
        apply(a[0])
    else:
        raise SystemExit(__doc__)
