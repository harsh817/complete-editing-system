#!/usr/bin/env python3
"""voice.py: one character, one voice, every clip. ElevenLabs speech-to-speech with one locked settings file.
Run from the ad folder. Needs ffmpeg, numpy, curl, ELEVENLABS_API_KEY, and Skill 12 (gate.py) for the quotes.

  voice.py init [--character NAME]                   write audio/vo/voice.json (the locked settings for this character)
  voice.py voices                                    list the voices on the account (id + name), free
  voice.py clone --name NAME FILE ... [--approved]   instant voice clone from clean samples -> voice_id in voice.json
  voice.py convert FILE ... [--approved]             ONE conversion over all files back to back, split back per file
                                                     -> renders/gen/voice/<stem>_<character>.mp4 (or .wav) + sidecar settings
  voice.py check FILE_ORIG FILE_NEW                  sync lag (envelope cross-correlation) + word diff if Whisper is installed
  voice.py audit                                     every output made with settings different from voice.json

Why one pass: the model re-hears the words. More context in one request = fewer mangled words than clip by clip.
Without --approved, clone and convert print the quote and stop."""

# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")

import hashlib, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

CFG = Path("audio/vo/voice.json")      # the locked settings for this character
OUT = Path("renders/gen/voice")        # paid output, never overwritten
SR = 44100
API = "https://api.elevenlabs.io/v1"
EXAMPLE = {
    "character": "NAME",
    "voice_id": None,
    "model_id": "eleven_multilingual_sts_v2",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
    "remove_background_noise": True,
    "seed": 1234,
    "output_format": "mp3_44100_192",
    "pre_loudnorm": "I=-16:TP=-1.5",
    "max_minutes_per_request": 4.5,
    "mask": {}
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


def key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not k:
        raise SystemExit("ELEVENLABS_API_KEY is not set. Export it in your shell profile. Never paste it in the chat.")
    return k


def cfg():
    if not CFG.exists():
        raise SystemExit("no audio/vo/voice.json: run  voice.py init  first")
    return {**EXAMPLE, **json.loads(CFG.read_text(encoding="utf-8"))}


def settings_hash(c):
    keep = {k: c[k] for k in ("voice_id", "model_id", "voice_settings", "remove_background_noise", "seed", "pre_loudnorm")}
    return hashlib.sha1(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:10]


def pcm(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def write_wav(y, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(path)],
                   input=y.astype("float32").tobytes(), check=True)


def has_video(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True)
    return "video" in r.stdout


def sts(wav, c, out_mp3):
    vs = json.dumps(c["voice_settings"])
    cmd = ["curl", "-sS", "--fail-with-body", "-o", str(out_mp3) + ".part", "-X", "POST",
           f"{API}/speech-to-speech/{c['voice_id']}?output_format={c['output_format']}",
           "-H", f"xi-api-key: {key()}", "-F", f"model_id={c['model_id']}", "-F", f"voice_settings={vs}",
           "-F", f"remove_background_noise={'true' if c['remove_background_noise'] else 'false'}",
           "-F", f"audio=@{wav}"]
    if c.get("seed") is not None:
        cmd += ["-F", f"seed={c['seed']}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        Path(str(out_mp3) + ".part").unlink(missing_ok=True)
        raise SystemExit(f"ElevenLabs refused: {r.stdout[:300]} {r.stderr[:200]}")
    os.replace(str(out_mp3) + ".part", out_mp3)


def convert(files, approved):
    import numpy as np
    c = cfg()
    if not c.get("voice_id"):
        raise SystemExit("voice_id is empty in audio/vo/voice.json: pick one with  voice.py voices  or make one with  voice.py clone")
    parts = []
    for f in files:
        a = pcm(f)
        keep = np.ones(len(a), np.float32)
        for s, e in c["mask"].get(Path(f).stem, []):
            keep[int(s * SR):int(e * SR)] = 0
        keep = np.convolve(keep, np.ones(441) / 441, "same").astype(np.float32)   # 10 ms fades at mask edges
        parts.append((Path(f), a, keep))
    groups, cur, cur_len = [], [], 0
    for p in parts:
        if cur and cur_len + len(p[1]) / SR / 60 > c["max_minutes_per_request"]:
            groups.append(cur)
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p[1]) / SR / 60
    groups.append(cur)
    tag = settings_hash(c)

    def pass_file(grp):
        """one cached conversion per settings + exact input audio, so a re-run never pays twice and never reuses
        a pass made from other files"""
        h = hashlib.sha1(tag.encode())
        for _, a, k in grp:
            h.update((a * k).astype(np.float32).tobytes())
        return OUT / f"_pass_{tag}_{h.hexdigest()[:10]}.mp3"
    new = [grp for grp in groups if not pass_file(grp).exists()]
    if new:
        g = load_gate()
        secs = round(sum(len(a) for grp in new for _, a, _ in grp) / SR, 1)
        g.gate([(c["model_id"], secs, "second")], approved, step="vo", provider="elevenlabs")
    else:
        print("every pass is already on disk with these settings and files: nothing to pay")
    OUT.mkdir(parents=True, exist_ok=True)
    for gi, grp in enumerate(groups):
        x = np.concatenate([a * k for _, a, k in grp])
        tmp = Path(tempfile.mkdtemp())
        write_wav(x, tmp / "in.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp / "in.wav", "-af", f"loudnorm={c['pre_loudnorm']}", "-ar", str(SR),
                        tmp / "norm.wav"], check=True)
        raw = pass_file(grp)
        if raw.exists():
            print(f"reusing {raw} (same settings, same files: not paid again)")
        else:
            sts(tmp / "norm.wav", c, raw)
        b = pcm(raw)
        b = np.pad(b, (0, max(0, len(x) - len(b))))[:len(x)]
        i = 0
        for f, a, k in grp:
            seg = b[i:i + len(a)]
            i += len(a)
            gain = np.sqrt((k * a ** 2).sum() / ((k * seg ** 2).sum() + 1e-9))
            mixed = k * seg * gain + (1 - k) * a
            wav = OUT / f"_{f.stem}.wav"
            write_wav(mixed, wav)
            name = f.stem + "_" + re.sub(r"\W", "", c["character"])
            dst = OUT / f"{name}.mp4" if has_video(f) else OUT / f"{name}.wav"
            if dst.exists():
                n = 1
                while (OUT / f"alt_{dst.stem}_v{n}{dst.suffix}").exists():
                    n += 1
                alt = OUT / f"alt_{dst.stem}_v{n}{dst.suffix}"
                os.replace(dst, alt)
                print(f"   kept the old version as {alt.name}")
            if has_video(f):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                                "-c:a", "aac", "-b:a", "192k", "-shortest", dst], check=True)
                wav.unlink()
            else:
                os.replace(wav, dst)
            (dst.parent / (dst.name + ".voice.json")).write_text(json.dumps({"source": str(f), "settings_hash": tag, **c}, indent=1))
            print(f"-> {dst}  lag {lag_ms(a, mixed):+.0f} ms")
    print(f"settings {tag}. Next: voice.py check <original> <converted> on every file, then listen to the flagged ones.")


def lag_ms(a, b):
    """envelope cross-correlation lag of b vs a, in ms (positive = b late)"""
    import numpy as np
    hop = SR // 200
    ea = np.abs(a[:len(a) // hop * hop]).reshape(-1, hop).mean(1)
    eb = np.abs(b[:len(b) // hop * hop]).reshape(-1, hop).mean(1)
    n = min(len(ea), len(eb))
    ea, eb = ea[:n] - ea[:n].mean(), eb[:n] - eb[:n].mean()
    best, lag = -1e18, 0
    for k in range(-20, 21):
        s = float((ea[max(0, -k):n - max(0, k)] * eb[max(0, k):n - max(0, -k)]).sum())
        if s > best:
            best, lag = s, k
    return lag * 1000 * hop / SR


def whisper_words(path, lang=None):
    tmp = Path(tempfile.mkdtemp()) / "a.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", tmp], check=True)
    try:
        import mlx_whisper
        r = mlx_whisper.transcribe(str(tmp), language=lang, path_or_hf_repo="mlx-community/whisper-large-v3-turbo")
        return r["text"]
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
        segs, _ = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8").transcribe(str(tmp), language=lang)
        return " ".join(s.text for s in segs)
    except ImportError:
        return None


def check(orig, new):
    import difflib
    a, b = pcm(orig), pcm(new)
    print(f"sync lag {lag_ms(a, b):+.0f} ms (pass: under one frame, 33 ms at 30 fps)")
    ta, tb = whisper_words(orig), whisper_words(new)
    if ta is None:
        print("word diff skipped: install mlx-whisper (Apple Silicon) or faster-whisper")
        return
    wa = re.findall(r"[\w']+", ta.lower())
    wb = re.findall(r"[\w']+", tb.lower())
    bad = [(" ".join(wa[i1:i2]), " ".join(wb[j1:j2])) for op, i1, i2, j1, j2 in
           difflib.SequenceMatcher(None, wa, wb).get_opcodes() if op != "equal"]
    print(f"words: {len(wa)} original, {len(wb)} converted, {len(bad)} differences")
    for x, y in bad:
        print(f"  '{x}' -> '{y}'")


def voices():
    r = subprocess.run(["curl", "-sS", "--fail-with-body", f"{API}/voices", "-H", f"xi-api-key: {key()}"],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout[:300])
    for v in json.loads(r.stdout).get("voices", []):
        print(f"{v['voice_id']}  {v['name']}  ({v.get('category', '')})")


def clone(name, files, approved):
    g = load_gate()
    g.gate([("voice-clone", 1, "clip")], approved, step="vo", provider="elevenlabs")
    cmd = ["curl", "-sS", "--fail-with-body", "-X", "POST", f"{API}/voices/add", "-H", f"xi-api-key: {key()}",
           "-F", f"name={name}", "-F", "remove_background_noise=true"]
    for f in files:
        cmd += ["-F", f"files=@{f}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"clone refused: {r.stdout[:300]}")
    vid = json.loads(r.stdout)["voice_id"]
    c = cfg()
    c["voice_id"] = vid
    CFG.write_text(json.dumps(c, indent=1))
    print(f"voice_id {vid} written to {CFG}")


def audit():
    c = cfg()
    tag = settings_hash(c)
    side = sorted(OUT.glob("*.voice.json"))
    off = [s for s in side if json.loads(s.read_text(encoding="utf-8")).get("settings_hash") != tag]
    print(f"{len(side)} outputs, {len(off)} made with other settings than voice.json ({tag})")
    for s in off:
        print(f"  {s.name[:-11]}: {json.loads(s.read_text(encoding="utf-8")).get('settings_hash')}")


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
    if cmd == "init":
        if CFG.exists():
            raise SystemExit(f"{CFG} exists: it is the locked file for this character, edit it on purpose only")
        CFG.parent.mkdir(parents=True, exist_ok=True)
        CFG.write_text(json.dumps({**EXAMPLE, "character": opt(a, "--character", "NAME")}, indent=1))
        print(f"wrote {CFG}")
    elif cmd == "voices":
        voices()
    elif cmd == "clone":
        n = opt(a, "--name")
        clone(n, a, ok)
    elif cmd == "convert":
        convert(a, ok)
    elif cmd == "check":
        check(a[0], a[1])
    elif cmd == "audit":
        audit()
    else:
        raise SystemExit(__doc__)
