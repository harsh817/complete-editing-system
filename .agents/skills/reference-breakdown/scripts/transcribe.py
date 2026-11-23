#!/usr/bin/env python3
"""Word-level transcription with local Whisper. Free, nothing leaves the machine.

  python3 transcribe.py <audio-or-video> [more files...] [--out-dir DIR] [--lang en] [--model large-v3-turbo]

Run from the ad folder. Writes <out-dir>/<file-stem>.words.json for each input (default out-dir:
renders/_work/transcripts, so nothing is ever written next to the raw takes in footage/):
  {"source": "<file>", "backend": "...", "language": "en", "duration": 12.3,
   "text": "full transcript", "words": [{"text": "Hello", "start": 0.12, "end": 0.48}, ...]}

Backends, first one found wins:
  mlx-whisper     (Apple Silicon)   pip install mlx-whisper
  faster-whisper  (any CPU or GPU)  pip install faster-whisper
  openai-whisper  (any)             pip install openai-whisper
Speech only. Whisper drops words on sung vocals.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def to_wav(src):
    wav = os.path.join(tempfile.mkdtemp(), "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    return wav


def duration(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                         capture_output=True, text=True).stdout.strip()
    try:
        return round(float(out), 3)
    except ValueError:
        return None


def run_mlx(wav, lang, model):
    import mlx_whisper
    repo = model if "/" in model else f"mlx-community/whisper-{model}"
    r = mlx_whisper.transcribe(wav, language=lang, word_timestamps=True, path_or_hf_repo=repo)
    words = [(w["word"], w["start"], w["end"]) for s in r["segments"] for w in s.get("words", [])]
    return words, r.get("language", lang)


def run_faster(wav, lang, model):
    from faster_whisper import WhisperModel
    import numpy as np
    import wave
    with wave.open(wav) as w:   # decode ourselves: avoids PyAV version problems
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    m = WhisperModel(model, device="auto", compute_type="int8")
    segs, info = m.transcribe(audio, language=lang, word_timestamps=True, vad_filter=False)
    words = [(w.word, w.start, w.end) for s in segs for w in (s.words or [])]
    return words, info.language


def run_openai(wav, lang, model):
    import whisper
    m = whisper.load_model("turbo" if model == "large-v3-turbo" else model)
    r = m.transcribe(wav, language=lang, word_timestamps=True)
    words = [(w["word"], w["start"], w["end"]) for s in r["segments"] for w in s.get("words", [])]
    return words, r.get("language", lang)


def transcribe(wav, lang, model):
    for name, fn in (("mlx-whisper", run_mlx), ("faster-whisper", run_faster), ("openai-whisper", run_openai)):
        try:
            words, language = fn(wav, lang, model)
            return name, words, language
        except ImportError:
            continue
    sys.exit("No Whisper backend found. Install one: pip install faster-whisper (or mlx-whisper on Apple Silicon).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out-dir", default="renders/_work/transcripts")
    ap.add_argument("--lang", default=None, help="language code, e.g. en. Default: auto-detect")
    ap.add_argument("--model", default="large-v3-turbo", help="use 'tiny' or 'base' for a fast test")
    a = ap.parse_args()
    for src in a.files:
        out_dir = a.out_dir
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".words.json")
        if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src):
            print(f"skip {src} (transcript is newer than the file)")
            continue
        backend, words, language = transcribe(to_wav(src), a.lang, a.model)
        clean = [{"text": t.strip(), "start": round(float(s), 3), "end": round(float(e), 3)}
                 for t, s, e in words if t.strip()]
        data = {"source": os.path.abspath(src), "backend": backend, "language": language,
                "duration": duration(src), "text": " ".join(w["text"] for w in clean), "words": clean}
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"{src} -> {out} ({len(clean)} words, {backend})")


if __name__ == "__main__":
    main()
