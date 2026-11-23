#!/usr/bin/env python3
"""beats.py: beat and bar grid of a song, then every scene cut snapped onto it. Free, local. Needs ffmpeg + numpy.

  beats.py detect audio/h1.mp3 [--bpm 110] [--beats-per-bar 4]
        tempo, beat times and bar starts -> audio/h1.beats.json  (--bpm when you know it: skips the tempo guess)
  beats.py snap --grid audio/grid_h1.md --beats audio/h1.beats.json [--to beat|bar] [--max-shift 0.25] [--fps 30]
        every module start moved to the nearest beat (or bar) at or before the sung word, within max-shift
        -> audio/grid_h1_snapped.md with frame numbers for the editor
  beats.py cuts --beats audio/h1.beats.json --every 2 [--unit beat|bar] [--start 0] [--end 15] [--fps 30]
        fixed montage cuts every N beats or bars between start and end (for fast b-roll runs) -> printed table

Snapping before the word, not after it, makes the picture change land on the beat and the word land on the new shot."""
import json, math, re, subprocess, sys
from pathlib import Path

SR, HOP, NFFT = 22050, 512, 2048


def audio(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def onset_envelope(x):
    """spectral flux on a log spectrum, half-wave rectified, one value per hop"""
    import numpy as np
    x = np.concatenate([np.zeros(NFFT // 2, np.float32), x])   # centre the windows: frame t = time t * HOP / SR
    n = 1 + (len(x) - NFFT) // HOP
    if n < 10:
        raise SystemExit("audio too short")
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    S = np.log1p(100 * np.abs(np.fft.rfft(x[idx] * np.hanning(NFFT), axis=1)))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, "same")       # remove the slow trend
    flux = np.maximum(flux, 0)
    return flux / (flux.std() + 1e-9)


def tempo(env, lo=70, hi=180):
    """autocorrelation, weighted toward 120 BPM so half and double tempo lose ties"""
    import numpy as np
    fps = SR / HOP
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    best, bpm = -1, 120.0
    for b in np.arange(lo, hi, 0.5):
        lag = fps * 60 / b
        i = int(round(lag))
        if i >= len(ac):
            continue
        w = math.exp(-0.5 * (math.log2(b / 120) / 0.9) ** 2)
        s = w * (ac[i] + 0.5 * ac[min(len(ac) - 1, 2 * i)])
        if s > best:
            best, bpm = s, b
    return float(bpm)


def track(env, bpm, tight=100.0):
    """dynamic-programming beat tracker: strong onsets, spaced close to one beat period"""
    import numpy as np
    period = SR / HOP * 60 / bpm
    score = env.copy()
    back = -np.ones(len(env), int)
    lo, hi = int(round(period / 2)), int(round(period * 2))
    for t in range(hi, len(env)):
        prev = np.arange(t - hi, t - lo + 1)
        cost = -tight * np.log((t - prev) / period) ** 2
        j = int(np.argmax(score[prev] + cost))
        score[t] = env[t] + score[prev[j]] + cost[j]
        back[t] = prev[j]
    tail = np.arange(max(0, len(env) - hi), len(env))
    t = int(tail[np.argmax(score[tail])])
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return [round(b * HOP / SR, 3) for b in reversed(beats)]


def detect(path, bpm=None, per_bar=4):
    import numpy as np
    env = onset_envelope(audio(path))
    bpm = float(bpm) if bpm else tempo(env)
    beats = track(env, bpm)
    fps = SR / HOP
    strength = [env[min(len(env) - 1, int(round(b * fps)))] for b in beats]
    phase = max(range(per_bar), key=lambda p: sum(strength[p::per_bar]))
    bars = beats[phase::per_bar]
    out = Path(path).with_suffix(".beats.json")
    out.write_text(json.dumps({"song": str(path), "bpm": round(bpm, 1), "beats_per_bar": per_bar,
                               "beats": beats, "bars": bars}, indent=1))
    gaps = np.diff(beats) if len(beats) > 1 else [0]
    print(f"-> {out}: {bpm:.1f} BPM, {len(beats)} beats, {len(bars)} bars, beat gap median {np.median(gaps):.3f}s")


def grid_rows(grid):
    rx = re.compile(r"^\| ([^|]+?) \| ([\d.]+) \| ([\d.]+) \| [\d.]+ \| (.*) \|$")
    return [(m[1], float(m[2]), float(m[3]), m[4]) for m in (rx.match(l.rstrip()) for l in open(grid)) if m]


def snap(grid, beats_file, to="beat", max_shift=0.25, fps=30):
    B = json.loads(Path(beats_file).read_text(encoding="utf-8"))
    marks = B["bars"] if to == "bar" else B["beats"]
    rows = grid_rows(grid)
    starts, notes = [], []
    for k, s, e, t in rows:
        if s == 0:
            starts.append(0.0)
            notes.append("start")
            continue
        before = [m for m in marks if s - max_shift <= m <= s + 0.04]
        if before:
            m = max(before)
            starts.append(m)
            notes.append(f"{m - s:+.2f}s to {to}")
        else:
            starts.append(s)
            notes.append(f"no {to} within {max_shift}s: kept on the word")
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 1 / fps)
    ends = starts[1:] + [rows[-1][2]]
    out = Path(grid).with_name(Path(grid).stem + "_snapped.md")
    with open(out, "w") as f:
        f.write(f"# {Path(grid).stem} snapped to {to}s ({B['bpm']} BPM, {fps} fps)\n\n"
                "| module | start | end | dur s | in frame | out frame | snap | lyric |\n|---|---|---|---|---|---|---|---|\n")
        for (k, s, e, t), a, b, n in zip(rows, starts, ends, notes):
            f.write(f"| {k} | {a:.2f} | {b:.2f} | {b - a:.2f} | {round(a * fps)} | {round(b * fps)} | {n} | {t} |\n")
    moved = sum(1 for n in notes if n.endswith(f"to {to}"))
    print(f"-> {out}: {moved}/{len(rows) - 1} cuts on a {to}")


def cuts(beats_file, every=2, unit="beat", start=0.0, end=None, fps=30):
    B = json.loads(Path(beats_file).read_text(encoding="utf-8"))
    marks = [m for m in (B["bars"] if unit == "bar" else B["beats"]) if m >= start and (end is None or m <= end)]
    sel = marks[::int(every)]
    print(f"| shot | start | end | dur s | in frame | out frame |\n|---|---|---|---|---|---|")
    for i, (a, b) in enumerate(zip(sel, sel[1:]), 1):
        print(f"| {i} | {a:.2f} | {b:.2f} | {b - a:.2f} | {round(a * fps)} | {round(b * fps)} |")


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
    if cmd == "detect":
        bpm, pb = opt(a, "--bpm"), int(opt(a, "--beats-per-bar", "4"))
        detect(a[0], bpm, pb)
    elif cmd == "snap":
        snap(opt(a, "--grid"), opt(a, "--beats"), opt(a, "--to", "beat"), float(opt(a, "--max-shift", "0.25")),
             int(opt(a, "--fps", "30")))
    elif cmd == "cuts":
        e = opt(a, "--end")
        cuts(opt(a, "--beats"), int(opt(a, "--every", "2")), opt(a, "--unit", "beat"), float(opt(a, "--start", "0")),
             float(e) if e else None, int(opt(a, "--fps", "30")))
    else:
        raise SystemExit(__doc__)
