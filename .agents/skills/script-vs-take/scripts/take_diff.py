#!/usr/bin/env python3
"""Match every script line to every take that says it, diff the words, pick the best take per line.

  python3 take_diff.py brief/script.txt "renders/_work/transcripts/*.words.json"
  python3 take_diff.py brief/script.txt "renders/_work/transcripts/*.words.json" --min-score 0.55

brief/script.txt, one line per script line, with a label:
  H1: Stop scrolling if your skin feels tight after washing.
  H2: Your moisturizer is not the problem.
  B1: I tried every serum for my dry skin.
  B2: Nothing worked until I found this one.
  CTA: Tap the link and try it for 30 days.
Lines without a label get B1, B2... in order. Lines that start with # are ignored.

Writes <out>.json (read by the rough-cut skill) and <out>.md (the take map for the editor).
Free, local, standard library only. Input = transcripts from transcribe.py.
"""
import argparse
import difflib
import glob
import json
import os
import re

FILLERS = {"um", "uh", "er", "erm", "ah", "hmm", "mm", "uhm"}
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
       "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num_words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + num_words(n % 100))
    if n < 10000:
        return num_words(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + num_words(n % 1000))
    return str(n)


def norm_tokens(text):
    """'10%' -> ['ten', 'percent'], "don't" -> ['dont'], punctuation removed. Returns one list per input word."""
    out = []
    t = text.lower().replace("%", " percent").replace("&", " and ").replace("$", " dollars ")
    for raw in t.split():
        w = re.sub(r"[^\w']", "", raw).replace("'", "")
        if not w:
            continue
        if w.isdigit():
            out.extend(num_words(int(w)).split())
        else:
            out.append(w)
    return out


def load_script(path):
    lines, auto = [], 0
    for raw in open(path, encoding="utf-8"):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z]+\d*)\s*[:.)-]\s+(.*)$", raw)
        if m:
            label, text = m.group(1).upper(), m.group(2)
        else:
            auto += 1
            label, text = f"B{auto}", raw
        lines.append({"id": label, "text": text, "tokens": norm_tokens(text)})
    return lines


def load_take(path):
    d = json.load(open(path, encoding="utf-8"))
    toks = []   # one entry per normalized token, pointing back to its word
    for i, w in enumerate(d["words"]):
        for t in norm_tokens(w["text"]):
            toks.append({"tok": t, "word": i})
    return {"file": d["source"], "words": d["words"], "toks": toks, "duration": d.get("duration")}


def candidates(line, take, min_score):
    L = line["tokens"]
    n = len(L)
    T = [t["tok"] for t in take["toks"]]
    out = []
    sm = difflib.SequenceMatcher(autojunk=False)
    sm.set_seq2(L)
    for i in range(len(T)):
        best = None
        for ln in range(max(1, n - 3), n + 4):
            win = T[i:i + ln]
            if len(win) < ln:
                break
            sm.set_seq1(win)
            r = sm.ratio()
            if best is None or r > best[0]:
                best = (r, ln)
        if best and best[0] >= min_score:
            out.append((best[0], i, i + best[1]))
    return out


def describe(line, take, a, b):
    """Score, in/out and word changes for take tokens a..b."""
    toks = take["toks"][a:b]
    words = take["words"]
    w0, w1 = toks[0]["word"], toks[-1]["word"]
    said = [t["tok"] for t in toks]
    sm = difflib.SequenceMatcher(None, line["tokens"], said, autojunk=False)
    changes = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        at = words[toks[j1]["word"]]["start"] if j1 < len(toks) else words[w1]["end"]
        changes.append({"type": {"replace": "changed", "delete": "missing", "insert": "extra"}[op],
                        "script": " ".join(line["tokens"][i1:i2]), "said": " ".join(said[j1:j2]), "at": round(at, 2)})
    fillers = sum(1 for t in said if t in FILLERS)
    repeats = sum(1 for x, y in zip(said, said[1:]) if x == y and x not in FILLERS)
    score = sm.ratio() - 0.05 * fillers - 0.05 * repeats
    prev_end = words[w0 - 1]["end"] if w0 > 0 else 0.0
    next_start = words[w1 + 1]["start"] if w1 + 1 < len(words) else (take["duration"] or words[w1]["end"] + 1.0)
    t_in = max(prev_end, words[w0]["start"] - 0.08, 0.0)
    t_out = min(next_start, words[w1]["end"] + 0.15)
    risks = []
    if words[w0]["start"] - prev_end < 0.3 and w0 > 0:
        risks.append("tight in")
    if next_start - words[w1]["end"] < 0.3 and w1 + 1 < len(words):
        risks.append("tight out")
    return {"file": take["file"], "in": round(t_in, 3), "out": round(t_out, 3),
            "first_word": round(words[w0]["start"], 3), "last_word": round(words[w1]["end"], 3),
            "said": " ".join(words[k]["text"] for k in range(w0, w1 + 1)), "score": round(score, 3),
            "fillers": fillers, "repeats": repeats, "changes": changes, "risks": risks,
            "words": words[w0:w1 + 1]}


def tc(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("transcripts", nargs="+")
    ap.add_argument("--min-score", type=float, default=0.6)
    ap.add_argument("--out", default="renders/_work/takes")
    a = ap.parse_args()
    files = sorted(set(f for p in a.transcripts for f in glob.glob(p)))
    script = load_script(a.script)
    takes = [load_take(f) for f in files]
    result = []
    for line in script:
        found = []
        for order, take in enumerate(takes):
            used = []
            for r, i, j in sorted(candidates(line, take, a.min_score), key=lambda c: -c[0]):
                if any(i < uj and j > ui for ui, uj in used):
                    continue
                used.append((i, j))
                d = describe(line, take, i, j)
                d["order"] = (order, i)
                found.append(d)
        # best = highest score; within 0.02 of the best, prefer the later attempt (usually the clean one)
        best = None
        if found:
            top = max(f["score"] for f in found)
            best = max((f for f in found if f["score"] >= top - 0.02), key=lambda f: f["order"])
        for f in found:
            f.pop("order")
        found.sort(key=lambda f: -f["score"])
        result.append({"id": line["id"], "text": line["text"], "best": best, "takes": found,
                       "status": "ok" if best and not best["changes"] else ("changed" if best else "MISSING")})

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump({"script": a.script, "lines": result}, f, ensure_ascii=False, indent=1)

    md = ["# Take map", "", "| Line | Status | File | In | Out | Score | Takes found | Risks |", "|---|---|---|---|---|---|---|---|"]
    for r in result:
        b = r["best"]
        if b:
            md.append(f"| {r['id']} | {r['status']} | {os.path.basename(b['file'])} | {tc(b['in'])} | {tc(b['out'])} | "
                      f"{b['score']:.2f} | {len(r['takes'])} | {', '.join(b['risks']) or '-'} |")
        else:
            md.append(f"| {r['id']} | MISSING | - | - | - | - | 0 | - |")
    md += ["", "# Word changes in the chosen takes", "", "| Line | At | Type | Script says | Take says |", "|---|---|---|---|---|"]
    for r in result:
        for c in (r["best"] or {}).get("changes", []):
            md.append(f"| {r['id']} | {tc(c['at'])} | {c['type']} | {c['script'] or '-'} | {c['said'] or '-'} |")
    md += ["", "# Missing lines", ""] + [f"- {r['id']}: {r['text']}" for r in result if r["status"] == "MISSING"]
    with open(a.out + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    ok = sum(r["status"] == "ok" for r in result)
    ch = sum(r["status"] == "changed" for r in result)
    miss = sum(r["status"] == "MISSING" for r in result)
    print(f"{len(result)} lines: {ok} word-perfect, {ch} with changes, {miss} missing -> {a.out}.md, {a.out}.json")


if __name__ == "__main__":
    main()
