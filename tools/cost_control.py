"""Budget, exact-quote and execution-context checks for the Codex editing helpers."""
import csv
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ['date', 'time', 'ad', 'step', 'provider', 'model', 'units', 'unit', 'usd_est', 'status', 'note']
AD_PATTERN = re.compile(r'^[A-Z]{3,4}_\d{4}-S\d+(?:-[A-Za-z0-9]+)?$')
PAID_SCRIPTS = {
    'actor-swap/scripts/actorswap.py', 'animated-ad/scripts/gen.py',
    'broll-from-brief/scripts/kie.py', 'scene-edit/scripts/kie.py',
    'talking-avatar/scripts/kie.py', 'voiceover/scripts/vo.py',
    'one-voice/scripts/voice.py', 'song-timing/scripts/timing.py',
}
CONTEXT = 'EDITING_PAID_CONTEXT'


def local_now():
    # This workstation's user-facing timezone is Asia/Calcutta (UTC+05:30, without DST).
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def number(value, label, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label} must be a finite number') from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(f'{label} must be finite and ' + ('positive' if positive else 'nonnegative'))
    return result


def within(path, parent):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(Path(parent).resolve()):
        raise ValueError(f'Path must be inside {parent}')
    return resolved


def ad_folder(ad, must_exist=True):
    if not AD_PATTERN.fullmatch(ad):
        raise ValueError('Use BRAND_YYMM-S# with a 3–4 capital letter brand, e.g. ACME_2610-S3')
    folder = within(ROOT / 'ads' / ad, ROOT / 'ads')
    if must_exist and not folder.is_dir():
        raise ValueError(f'No ad folder: {ad}')
    return folder


def setting(name):
    match = re.search(rf'^{re.escape(name)}\s*=\s*(-?[0-9.]+)\s*$',
                      (ROOT / 'AGENTS.md').read_text(encoding='utf-8'), re.M)
    if not match:
        raise ValueError(f'Missing {name} in AGENTS.md')
    return Decimal(match[1])


def cap(ad):
    override = ad_folder(ad) / 'brief/budget.txt'
    return number(override.read_text().strip() if override.exists()
                  else setting('MAX_BUDGET_PER_CONCEPT_USD'), 'budget cap')


def ledger_rows(ad):
    path = ad_folder(ad) / 'ledger.csv'
    if not path.exists():
        raise ValueError('ledger.csv is missing; restore it before paid work')
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADER:
            raise ValueError('ledger.csv header is invalid; do not overwrite the ledger')
        return list(reader)


def spent(ad):
    return sum((number(row.get('usd_est'), 'ledger estimate') for row in ledger_rows(ad)), Decimal(0))


def price_table(ad):
    table = {}
    for path in (ROOT / 'prices.json', ad_folder(ad) / 'prices.json'):
        if path.exists():
            table.update(json.loads(path.read_text(encoding='utf-8')))
    return table


def unit_price(ad, model, unit):
    record = price_table(ad).get(model)
    if not record or record.get('usd') is None:
        raise ValueError(f'No verified price for {model}; update prices.json from provider pricing')
    if unit not in {'image', 'second', 'clip', 'char'} or record.get('unit') != unit:
        raise ValueError(f'Price unit does not match {unit}')
    try:
        checked = date.fromisoformat(record['checked'])
    except (ValueError, KeyError, TypeError):
        raise ValueError(f'{model} needs a valid checked date') from None
    age = (local_now().date() - checked).days
    if not 0 <= age <= 30:
        raise ValueError(f'{model} price is stale or dated in the future; verify it again')
    return number(record['usd'], 'unit price'), record


def request_quote(request_path):
    path = within(ROOT / request_path, ROOT / 'ads')
    request = json.loads(path.read_text(encoding='utf-8'))
    folder = ad_folder(request['ad'])
    within(path, folder / 'renders/_work')
    script = within(ROOT / request['script'], ROOT / '.agents/skills')
    relative = script.relative_to(ROOT / '.agents/skills').as_posix()
    if relative not in PAID_SCRIPTS or not script.is_file():
        raise ValueError('Request must use one of the bundled paid production helpers')
    args = request.get('args')
    if not isinstance(args, list) or not args or any(not isinstance(a, str) for a in args):
        raise ValueError('args must be a nonempty JSON array of strings')
    if any(a == '--approved' or a.startswith('--approved=') for a in args):
        raise ValueError('The wrapper supplies --approved after approval')
    if not request.get('step') or request.get('provider') not in {'kie', 'elevenlabs'}:
        raise ValueError('Request needs a step and provider (kie or elevenlabs)')
    units = number(request['units'], 'units', positive=True)
    price, record = unit_price(request['ad'], request['model'], request['unit'])
    amount = (price * units).quantize(Decimal('0.0001'), rounding=ROUND_CEILING)
    reserve = amount * number(setting('REPAIR_BUDGET_PCT'), 'repair budget') / 100
    current, limit = spent(request['ad']), cap(request['ad'])
    if current + amount + reserve > limit:
        raise ValueError('Run plus repair allowance exceeds the remaining concept budget')
    # Pin the helper and every ad input. Outputs/transcripts outside renders/_work are not inputs.
    hashes = {}
    for base in ('brief', 'refs', 'footage', 'audio', 'renders/_work', 'renders/gen'):
        for item in sorted((folder / base).rglob('*')):
            if (not item.is_file() or item == path or '__pycache__' in item.parts
                    or item.name == 'paid-run.lock' or item == folder / 'brief/progress.md'):
                continue
            resolved = within(item, folder)
            digest = hashlib.sha256()
            with resolved.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            hashes[item.relative_to(folder).as_posix()] = digest.hexdigest()
    payload = {'request': request, 'price': record, 'spent': str(current), 'cap': str(limit),
               'repair': str(reserve), 'inputs': hashes,
               'helper': hashlib.sha256(script.read_bytes()).hexdigest()}
    quote_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
    return {'request': request, 'script': script, 'folder': folder, 'amount': amount,
            'repair': reserve, 'spent': current, 'cap': limit, 'quote_id': quote_id}


def validate_context(items, ad=None):
    """Paid helpers require a matching wrapper reservation, not just an --approved flag."""
    raw = os.environ.get(CONTEXT)
    if not raw:
        raise SystemExit('BLOCKED: paid execution requires tools/paid_run.py and its approved quote ID')
    try:
        context = json.loads(raw)
        folder = ad_folder(context['ad'])
        if Path.cwd().resolve() != folder or (ad and ad != context['ad']):
            raise ValueError('Approval is for a different ad/working directory')
        total, count = Decimal(0), Decimal(0)
        for model, units, unit, amount in items:
            if model.split(':')[0] != context['model'].split(':')[0] or unit != context['unit']:
                raise ValueError('Actual run model/unit differs from the approved quote')
            total += number(amount, 'actual estimate')
            count += number(units, 'actual units')
        if total > number(context['amount'], 'approved amount') + Decimal('0.000001'):
            raise ValueError('Actual estimated cost exceeds the approved run')
        if count > number(context['units'], 'approved units') + Decimal('0.000001'):
            raise ValueError('Actual units exceed the approved run')
        if not context.get('run_id'):
            raise ValueError('Missing paid-run reservation ID')
    except (ValueError, KeyError, TypeError):
        raise SystemExit('BLOCKED: paid-run context does not match this operation') from None
