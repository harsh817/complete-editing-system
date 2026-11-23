#!/usr/bin/env python3
"""Voiceover files from brief/vo.json with the ElevenLabs text-to-speech API, then loudness normalized.

Run from the ad folder (ads/<AD>/).
  python3 vo.py quote brief/vo.json [--parts]             # free: characters per file and the total
  python3 vo.py make  brief/vo.json [--parts] --approved  # paid: only after the user typed OK
  python3 vo.py norm  audio/some_file.wav [more files]    # free: two-pass loudnorm on any audio file

Default build: one full read per hook (hook + body in ONE request, so the join sounds like one take).
--parts also builds each hook alone and the body alone (the talking-avatar skill needs those).

brief/vo.json:
  {"name": "BRAND_CONCEPT",
   "voice_id": "",                       # or set ELEVENLABS_VOICE_ID
   "model_id": "eleven_v3",              # check the current model ids in the ElevenLabs docs
   "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": true},
   "language_code": null,
   "pronunciations": {"Brandname": "Brand-name as it should sound"},
   "hooks": {"H1": "hook one text", "H2": "hook two text"},
   "body": "body text, CTA included",
   "usd_per_1k_chars": null}            # your plan's dollar cost per 1,000 characters; "make" needs it

Outputs: audio/vo/<name>_H1_VO_v1.wav (48 kHz, 24-bit, -14 LUFS integrated, -1 dBTP true peak) plus the raw
mp3 in audio/vo/_raw/ (a rerun with the same text and voice reuses it and pays nothing).
"quote" prints the cost tag line. After the user's OK, run:
  # cost: ad=<AD> step=vo model=<model_id> units=<chars> unit=char usd=<est> ok=yes
  python3 vo.py make brief/vo.json --approved
This script never writes the ledger itself.
The key comes from ELEVENLABS_API_KEY. Never paste the key into the chat.
"""

# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.0, 11.0   # LOUDNESS_TARGET_LUFS and TRUE_PEAK_DBTP in AGENTS.md


def loudnorm(src, dst):
    """Two-pass EBU R128 loudnorm: measure, then apply the measured values (linear mode)."""
    f1 = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", f1, "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)[-1])
    f2 = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", f2, "-ar", "48000", "-c:a", "pcm_s24le", dst], check=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", dst, "-af", f1, "-f", "null", "-"], capture_output=True, text=True)
    after = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)[-1])
    print(f"  {os.path.basename(dst)}: {m['input_i']} -> {after['input_i']} LUFS, true peak {after['input_tp']} dBTP")


def speakable(text, pron):
    for k, v in (pron or {}).items():
        text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    return re.sub(r"\s+", " ", text).strip()


def builds(cfg, parts):
    out, body = [], cfg["body"]
    for h, hook in cfg["hooks"].items():
        out.append((f"{h}_VO", f"{hook.strip()} {body.strip()}"))
    if parts:
        for h, hook in cfg["hooks"].items():
            out.append((f"{h}_HOOKONLY_VO", hook))
        out.append(("BODY_VO", body))
    return [(n, speakable(t, cfg.get("pronunciations"))) for n, t in out]


def next_version(stem):
    v = 1
    while os.path.exists(f"{stem}_v{v}.wav"):
        v += 1
    return f"{stem}_v{v}.wav"


def tts(cfg, voice, text, raw):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set. Set it in your shell profile. Never paste the key into the chat.")
    body = {"text": text, "model_id": cfg.get("model_id", "eleven_v3"), "voice_settings": cfg.get("voice_settings", {})}
    if cfg.get("language_code"):
        body["language_code"] = cfg["language_code"]
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(raw, "wb") as f:
            f.write(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs error {e.code}: {e.read().decode(errors='replace')[:400]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["quote", "make", "norm"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--parts", action="store_true")
    ap.add_argument("--approved", action="store_true")
    a = ap.parse_args()
    from cost_control import setting as _house_setting
    global TARGET_I, TARGET_TP
    TARGET_I = float(_house_setting("LOUDNESS_TARGET_LUFS"))
    TARGET_TP = float(_house_setting("TRUE_PEAK_DBTP"))

    if a.cmd == "norm":
        for p in a.paths:
            loudnorm(p, os.path.splitext(p)[0] + "_norm.wav")
        return

    cfg = json.load(open(a.paths[0], encoding="utf-8"))
    voice = cfg.get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not voice:
        sys.exit("No voice id. Put it in vo.json (voice_id) or set ELEVENLABS_VOICE_ID.")
    rate = cfg.get("usd_per_1k_chars")
    os.makedirs("audio/vo/_raw", exist_ok=True)
    plan = []
    for name, text in builds(cfg, a.parts):
        h = hashlib.sha1(f"{voice}|{cfg.get('model_id')}|{json.dumps(cfg.get('voice_settings'), sort_keys=True)}|{text}"
                         .encode()).hexdigest()[:10]
        raw = f"audio/vo/_raw/{cfg['name']}_{name}_{h}.mp3"
        plan.append((name, text, raw, os.path.exists(raw)))

    total = 0
    print(f"{'file':<28} {'chars':>6}  status")
    for name, text, raw, cached in plan:
        print(f"{name:<28} {len(text):>6}  {'cached, free' if cached else 'paid'}")
        total += 0 if cached else len(text)
    money = f"${total / 1000 * rate:.2f}" if rate is not None else "no rate: check your ElevenLabs plan's cost per character"
    print(f"\nTOTAL: {total} characters to generate ({money}). Model {cfg.get('model_id')}, voice {voice}.")
    if rate is not None:
        print(f"Cost tag (write ok=yes only after the user's OK):\n  # cost: ad={os.path.basename(os.getcwd())} step=vo "
              f"model={cfg.get('model_id')} units={total} unit=char usd={total / 1000 * rate:.2f} ok=no")
    if a.cmd == "quote":
        print("Quote only. Nothing was spent. " + ("Reply OK to make the files." if rate is not None else
              "Put your plan's cost per 1,000 characters in usd_per_1k_chars, then quote again."))
        return
    if not a.approved:
        sys.exit("Blocked: 'make' needs --approved, and --approved needs the user's OK to the quote above.")
    if rate is None and total:
        sys.exit("Blocked: usd_per_1k_chars is empty in vo.json, so there is no dollar quote for the cost tag.")

    if total:
        codex_validate_paid([(cfg.get("model_id", "eleven_v3"), total, "char", total / 1000 * rate)])
    for name, text, raw, cached in plan:
        if not cached:
            tts(cfg, voice, text, raw)
        loudnorm(raw, next_version(f"audio/vo/{cfg['name']}_{name}"))
    print("Done. Listen to every full read end to end before it goes under the edit.")


if __name__ == "__main__":
    main()
