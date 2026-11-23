#!/usr/bin/env python3
"""Small kie.ai client with a quote gate. Python 3.9+, standard library only.

Run it from the ad folder (ads/<AD>/).

  python3 kie.py quote  <jobs.json> [--only ID,ID]              # free: prints the cost, spends nothing
  python3 kie.py run    <jobs.json> [--only ID,ID] --approved   # paid: only after the user typed OK
  python3 kie.py status <jobs.json>                             # free: state of every job
  python3 kie.py quote  <jobs.json> --redo ID                   # make a finished job again: quote, then run
                                                                #   with --redo ID --approved (old file -> alt_<name>_v#)
  python3 kie.py upload <file>                                  # free: prints a public URL (kie deletes it after 24 h)

jobs.json:
  {"skill": "broll-from-brief", "step": "broll",
   "jobs": [{"id": "S01", "model": "nano-banana-pro", "out": "renders/gen/broll/S01.png",
             "input": {"prompt": "...", "aspect_ratio": "9:16", "resolution": "1K", "output_format": "png"},
             "files": {"image_input": ["refs/product.png"]}}]}

"files" maps an input field to local files. Each file is uploaded right before the job and its URL goes into
that field (a list stays a list, a single path becomes a single URL). "units" is optional: by default 1 per
image, input.duration seconds for video, or the length of the audio file for audio-driven models.

prices.json, in the ad folder or the workspace root (fill it from the provider's pricing page and keep it in
step with the price list in AGENTS.md; the script never guesses a price):
  {"nano-banana-pro": {"unit": "image", "usd": 0.00, "checked": "YYYY-MM-DD"},
   "kling-3.0/video": {"unit": "second", "usd": 0.00, "checked": "YYYY-MM-DD"},
   "kling-3.0/video:sound": {"unit": "second", "usd": 0.00, "checked": "YYYY-MM-DD"}}
A key with ":sound" is used when input.sound is true. A price of null blocks "run".

"quote" prints the cost tag line for the run command. After the user's OK, run:
  # cost: ad=<AD> step=<step> model=<model> units=<n> unit=<unit> usd=<est> ok=yes
  python3 kie.py run <jobs.json> --approved
Paid output is never overwritten: --redo renames the old file alt_<name>_v1 first.
The key comes from the KIE_API_KEY environment variable. Never paste the key into the chat.
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
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

API = "https://api.kie.ai/api/v1"
UPLOAD = "https://kieai.redpandaai.co/api/file-stream-upload"
POLL_EVERY = 10


def key():
    k = os.environ.get("KIE_API_KEY", "").strip().lstrip("﻿")
    if not k:
        sys.exit("KIE_API_KEY is not set. Set it in your shell profile. Never paste the key into the chat.")
    return k


def http(method, url, body=None, headers=None):
    h = {"Authorization": f"Bearer {key()}", "User-Agent": "cc-editing/1.0"}
    h.update(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} failed: HTTP {e.code} {e.read().decode(errors='replace')[:500]}")


def upload(path):
    if not os.path.isfile(path):
        sys.exit(f"No such file: {path}")
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        data = f.read()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"uploadPath\"\r\n\r\ncc-editing\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n"
         f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    r = http("POST", UPLOAD, b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    url = (r.get("data") or {}).get("downloadUrl") or (r.get("data") or {}).get("fileUrl")
    if not url:
        sys.exit(f"Upload failed for {path}: {r}")
    return url


def media_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def price_key(job):
    m = job["model"]
    return f"{m}:sound" if job.get("input", {}).get("sound") is True else m


def units(job, unit):
    if "units" in job:
        return float(job["units"])
    if unit == "image":
        return 1.0
    if unit == "second":
        d = job.get("input", {}).get("duration")
        if d not in (None, "", -1, "-1"):
            return float(d)
        for v in (job.get("files") or {}).values():
            for p in (v if isinstance(v, list) else [v]):
                if os.path.splitext(p)[1].lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".mp4", ".mov"):
                    return round(media_seconds(p), 2)
    sys.exit(f"Job {job['id']}: cannot work out units for unit '{unit}'. Add \"units\" to the job.")


def load(jobs_path, only):
    with open(jobs_path, encoding="utf-8") as f:
        spec = json.load(f)
    jobs = spec["jobs"]
    if only:
        want = set(only.split(","))
        jobs = [j for j in jobs if j["id"] in want]
        missing = want - {j["id"] for j in jobs}
        if missing:
            sys.exit(f"Unknown job ids: {', '.join(sorted(missing))}")
    return spec.get("step", "?"), jobs


def prices():
    """prices.json in the ad folder wins, else the nearest one above it (the workspace root)."""
    d = os.path.abspath(os.getcwd())
    while True:
        p = os.path.join(d, "prices.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        if os.path.dirname(d) == d:
            return {}
        d = os.path.dirname(d)


def quote(jobs, state, redo=(), step="?"):
    table = prices()
    rows, total, gaps, tags = [], 0.0, [], {}
    for j in jobs:
        if j["id"] not in redo and (os.path.exists(j["out"]) or state.get(j["id"], {}).get("status") == "done"):
            rows.append((j["id"], j["model"], "-", "-", "already done, not charged"))
            continue
        p = table.get(price_key(j)) or table.get(j["model"])
        if not p or p.get("usd") is None:
            gaps.append(price_key(j))
            rows.append((j["id"], j["model"], "?", "?", "no price: check the provider's current price"))
            continue
        u = units(j, p["unit"])
        cost = u * float(p["usd"])
        total += cost
        t = tags.setdefault(j["model"], [0.0, 0.0, p["unit"]])
        t[0] += u
        t[1] += cost
        rows.append((j["id"], j["model"], f"{u:g} {p['unit']}", f"${cost:.2f}", f"price checked {p.get('checked', '?')}"))
    print(f"{'job':<10} {'model':<34} {'units':<14} {'usd':<9} note")
    for r in rows:
        print(f"{r[0]:<10} {r[1]:<34} {r[2]:<14} {r[3]:<9} {r[4]}")
    print(f"\nTOTAL: ${total:.2f} for {sum(1 for r in rows if r[3] not in ('-', '?'))} paid job(s)")
    ad = os.path.basename(os.getcwd())
    for model, (u, usd, unit) in tags.items():
        print(f"Cost tag (write ok=yes only after the user's OK):\n"
              f"  # cost: ad={ad} step={step} model={model} units={u:g} unit={unit} usd={usd:.2f} ok=no")
    if len(tags) > 1:
        print("More than one model in this batch: run one model at a time with --only, one tag per run.")
    if gaps:
        print("MISSING PRICES: " + ", ".join(sorted(set(gaps))) +
              ". Add them to prices.json from the provider's pricing page. 'run' is blocked until then.")
    return total, gaps


def submit(job):
    inp = dict(job.get("input", {}))
    for field, paths in (job.get("files") or {}).items():
        inp[field] = [upload(p) for p in paths] if isinstance(paths, list) else upload(paths)
    r = http("POST", f"{API}/jobs/createTask", {"model": job["model"], "input": inp})
    tid = (r.get("data") or {}).get("taskId")
    if not tid:
        sys.exit(f"Submit failed for {job['id']}: {r}")
    return tid


def record(tid):
    return (http("GET", f"{API}/jobs/recordInfo?taskId={tid}").get("data")) or {}


def download(url, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "cc-editing/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        f.write(r.read())


def result_urls(rec):
    rj = rec.get("resultJson") or "{}"
    rj = json.loads(rj) if isinstance(rj, str) else rj
    return rj.get("resultUrls") or []


def run(jobs, state, state_path, max_wait):
    for j in jobs:
        if os.path.exists(j["out"]) or j["id"] in state:
            continue
        state[j["id"]] = {"task": submit(j), "status": "submitted", "model": j["model"]}
        save(state, state_path)
        print(f"submitted {j['id']} ({state[j['id']]['task']})")
    start = time.time()
    while True:
        pending = [j for j in jobs if state.get(j["id"], {}).get("status") == "submitted"]
        if not pending:
            break
        for j in pending:
            rec = record(state[j["id"]]["task"])
            st = rec.get("state")
            if st == "success":
                urls = result_urls(rec)
                outs = [j["out"]] if len(urls) == 1 else \
                    [f"{os.path.splitext(j['out'])[0]}_{i + 1}{os.path.splitext(j['out'])[1]}" for i in range(len(urls))]
                for u, o in zip(urls, outs):
                    download(u, o)
                state[j["id"]].update(status="done", outputs=outs)
                print(f"done {j['id']} -> {', '.join(outs)}")
            elif st == "fail":
                state[j["id"]].update(status="failed", error=rec.get("failMsg") or rec.get("failCode"))
                print(f"FAILED {j['id']}: {state[j['id']]['error']}  (kie does not bill failed tasks; rephrase and rerun)")
        save(state, state_path)
        if any(state.get(j["id"], {}).get("status") == "submitted" for j in jobs):
            if time.time() - start > max_wait:
                print(f"Still running after {max_wait}s. Run the same command again to keep waiting. Nothing is resubmitted.")
                return
            time.sleep(POLL_EVERY)


def save(state, path):
    with open(path, "w") as f:
        json.dump(state, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["quote", "run", "status", "upload"])
    ap.add_argument("path")
    ap.add_argument("--only", default=None, help="comma separated job ids")
    ap.add_argument("--approved", action="store_true", help="the user typed OK to the quote")
    ap.add_argument("--max-wait", type=int, default=90, help="seconds to wait before handing back (keep it under the shell tool timeout)")
    ap.add_argument("--retry", default=None, help="comma separated failed job ids to submit again")
    ap.add_argument("--redo", default=None, help="comma separated done job ids to make again (old file kept as alt_<name>_v#)")
    a = ap.parse_args()

    if a.cmd == "upload":
        print(upload(a.path))
        return
    step, jobs = load(a.path, a.only)
    state_path = os.path.splitext(a.path)[0] + ".state.json"
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    if a.retry:
        for i in a.retry.split(","):
            if state.get(i, {}).get("status") == "failed":
                state.pop(i)
    redo = set(a.redo.split(",")) if a.redo else set()
    if a.cmd == "status":
        for j in jobs:
            s = state.get(j["id"], {})
            print(f"{j['id']:<10} {s.get('status', 'not submitted'):<14} {s.get('error', '') or ', '.join(s.get('outputs', []))}")
        return
    total, gaps = quote(jobs, state, redo, step)
    if a.cmd == "quote":
        print("\nQuote only. Nothing was spent. " + ("Fill the missing prices, then quote again." if gaps
                                                     else "Reply OK to run it."))
        return
    if not a.approved:
        sys.exit("\nBlocked: 'run' needs --approved, and --approved needs the user's OK to the quote above.")
    if gaps:
        sys.exit("\nBlocked: some jobs have no price. Fill prices.json first.")
    actual = []
    table = prices()
    for job in jobs:
        if job["id"] not in redo and (os.path.exists(job["out"]) or state.get(job["id"], {}).get("status") == "done"):
            continue
        record = table.get(price_key(job)) or table.get(job["model"])
        count = units(job, record["unit"])
        actual.append((price_key(job), count, record["unit"], count * float(record["usd"])))
    codex_validate_paid(actual)
    for j in jobs:   # --redo: keep the old file next to the new one, forget the old task
        if j["id"] in redo:
            if os.path.exists(j["out"]):
                d, base = os.path.split(j["out"])
                stem, ext = os.path.splitext(base)
                k = 1
                while os.path.exists(os.path.join(d, f"alt_{stem}_v{k}{ext}")):
                    k += 1
                os.replace(j["out"], os.path.join(d, f"alt_{stem}_v{k}{ext}"))
            state.pop(j["id"], None)
    save(state, state_path)
    run(jobs, state, state_path, a.max_wait)


if __name__ == "__main__":
    main()
