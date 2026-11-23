#!/usr/bin/env python3
"""Shared quote helpers for Codex ad generation.
Free: gate.py quote --step S --model M --units N --unit image|second|clip|char [--ad AD]
Free: gate.py spend [--ad AD] or gate.py doctor [--ad AD]
Paid execution uses tools/paid_run.py; these functions validate its reserved context.
Comment tags retained in quote output are informational and do not register lifecycle hooks.
"""
import csv, json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools"))
import cost_control as _control

LEDGER_HEADER = ["date", "time", "ad", "step", "provider", "model", "units", "unit", "usd_est", "status", "note"]
UNITS = {"image", "second", "clip", "char"}
STALE_DAYS = 30


def workspace():
    env = os.environ.get("EDITING_WORKSPACE")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for p in [here, *here.parents]:
        if (p / "AGENTS.md").exists() and (p / "ads").is_dir():
            return p
    return here.parent.parent if here.parent.name == "ads" else here


def ad_name(ad=None):
    if ad:
        return ad
    here = Path.cwd().resolve()
    if here.parent.name == "ads":
        return here.name
    raise SystemExit("run from ads/<AD>/ or pass --ad <AD>")


def ad_dir(ad):
    return workspace() / "ads" / ad


def read_var(name):
    try:
        m = re.search(rf"{name}\s*[:=]\s*([0-9.]+)", (workspace() / "AGENTS.md").read_text(encoding="utf-8"))
        return float(m.group(1)) if m else None
    except OSError:
        return None


def cap(ad):
    try:
        return float((ad_dir(ad) / "brief" / "budget.txt").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return read_var("MAX_BUDGET_PER_CONCEPT_USD")


def rows(ad):
    f = ad_dir(ad) / "ledger.csv"
    if not f.exists():
        return []
    with open(f, newline="") as fh:
        return list(csv.DictReader(fh))


def spent(ad):
    """conservative sum including reservations: every row, failed ones included"""
    total = 0.0
    for r in rows(ad):
        try:
            total += float(r.get("usd_est") or 0)
        except ValueError:
            pass
    return total


def prices(ad):
    table = {}
    for f in (workspace() / "prices.json", ad_dir(ad) / "prices.json"):
        if f.exists():
            table.update(json.loads(f.read_text(encoding="utf-8")))
    return table


def price(ad, model):
    p = prices(ad).get(model)
    if not p or p.get("usd") is None:
        return None
    return float(p["usd"]), p.get("unit"), p.get("checked", "?")


def gate(items, approved=False, step="gen", ad=None, provider="kie", note=None):
    """items = [(price_key, units, unit)]. A price key is a model id, or model:variant when one model has several
    prices ("kling-3.0/video:sound", "google/gemini-omni-flash-1-1:6"). One model per paid command.
    Prints the quote and the cost tag line. Without approved: exit 0 after the quote. With approved: returns the
    total (the paid-run wrapper already reserved this estimate)."""
    ad = ad_name(ad)
    actual = []
    total, lines, missing = 0.0, [], []
    for model, units, unit in items:
        if unit not in UNITS:
            raise SystemExit(f"unit must be one of {', '.join(sorted(UNITS))}, not {unit}")
        try:
            _control.number(units, "units")
            _control.unit_price(ad, model, unit)
        except ValueError as error:
            raise SystemExit(str(error)) from None
        p = price(ad, model)
        if p is None:
            missing.append(model)
            continue
        if p[1] and p[1] != unit:
            raise SystemExit(f"prices.json prices {model} per {p[1]}, the quote counts per {unit}: fix one of them")
        usd = round(p[0] * float(units), 4)
        total += usd
        actual.append((model, units, unit, usd))
        lines.append(f"  {model}: {units} {unit} x ${p[0]} = ${usd:.2f}   (price checked {p[2]})")
    if missing:
        print("NO PRICE for: " + ", ".join(missing) + ". Check the provider's current price and add it to prices.json:")
        for m in missing:
            print(f'  "{m}": {{"unit": "<image|second|clip|char>", "usd": <price>, "checked": "{time.strftime("%Y-%m-%d")}"}}')
        raise SystemExit(3)
    pct = read_var("REPAIR_BUDGET_PCT")
    c, s = cap(ad), spent(ad)
    if approved:
        _control.validate_context(actual, ad)
        # The wrapper has already reserved this run; avoid charging it twice in this check.
        s -= float(json.loads(os.environ[_control.CONTEXT])["amount"])
    print(f"QUOTE  ad={ad}  step={step}")
    for line in lines:
        print(line)
    print(f"  this run ${total:.2f}" + (f" | repair budget {pct:g} % = ${total * pct / 100:.2f}" if pct else ""))
    print(f"  spent so far ${s:.2f} | cap " + (f"${c:.2f} | left after this run ${c - s - total:.2f}" if c is not None
                                               else "NOT SET (the paid-run wrapper blocks execution)"))
    if c is not None and s + total > c + 1e-9:
        print("OVER THE CAP: this run does not fit. Cut the batch or ask the user to raise the cap. Nothing was sent.")
        raise SystemExit(4)
    base = {i[0].split(":")[0] for i in items}
    if len(base) > 1 or len({i[2] for i in items}) > 1:
        raise SystemExit("one paid command per model and unit: quote and run each model as its own command")
    units_val = round(sum(float(u) for _, u, _ in items), 2)
    tag = (f"# cost: ad={ad} step={step} provider={provider} model={base.pop()} units={units_val:g} unit={items[0][2]} "
           f"usd={total:.2f}")
    if note:
        tag += " note=" + note.replace(" ", "_")
    if not approved:
        print("\nCost tag for the paid command (change ok=no to ok=yes only after the user types OK for this run):")
        print(tag + " ok=no")
        print("Nothing was sent.")
        raise SystemExit(0)
    return total


def spend(ad):
    ad = ad_name(ad)
    _control.ad_folder(ad)
    rs = _control.ledger_rows(ad)
    if not rs:
        print(f"ads/{ad}/ledger.csv is empty or missing: nothing spent.")
        return
    if list(rs[0].keys()) != LEDGER_HEADER:
        print("WARNING: ledger.csv header is not the house header: " + ",".join(LEDGER_HEADER))
    by = {}
    for r in rs:
        k = (r["step"], r["status"])
        n, u = by.get(k, (0, 0.0))
        by[k] = (n + 1, u + float(r.get("usd_est") or 0))
    print("| step | status | calls | usd_est |\n|---|---|---|---|")
    for (st, status), (n, u) in sorted(by.items()):
        print(f"| {st} | {status} | {n} | {u:.2f} |")
    failed = sum(u for (st, status), (n, u) in by.items() if status == "failed")
    c, s = cap(ad), spent(ad)
    print(f"\nspent ${s:.2f} (without failed rows ${s - failed:.2f})" + (f" | cap ${c:.2f} | left ${c - s:.2f}" if c else " | no cap"))


def doctor(ad):
    import subprocess
    return subprocess.call([sys.executable, str(_control.ROOT / "tools/workspace.py"), "doctor"])


def parse(argv):
    o, groups = {}, []
    i = 0
    while i < len(argv):
        k = argv[i]
        if not k.startswith("--") or i + 1 >= len(argv):
            raise SystemExit(f"bad argument {k}")
        v = argv[i + 1]
        if k == "--model":
            groups.append({"model": v})
        elif k in ("--units", "--unit"):
            if not groups:
                raise SystemExit("--model comes before --units and --unit")
            groups[-1][k[2:]] = v
        else:
            o[k[2:]] = v
        i += 2
    return o, groups


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    o, groups = parse(sys.argv[2:])
    if cmd == "quote":
        if not groups or any("units" not in g or "unit" not in g for g in groups):
            raise SystemExit("quote needs --model M --units N --unit U (repeat the three for each model)")
        gate([(g["model"], g["units"], g["unit"]) for g in groups], False, o.get("step", "gen"), o.get("ad"),
             o.get("provider", "kie"), o.get("item"))
    elif cmd == "spend":
        spend(o.get("ad"))
    elif cmd == "doctor":
        try:
            a = ad_name(o.get("ad"))
        except SystemExit:
            a = None
        doctor(a)
    else:
        raise SystemExit(__doc__)
