"""Codex editing workspace operations: new ad, dependency checks and export QA manifests."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cost_control import HEADER, ROOT, ad_folder, local_now, within


def create_ad(ad):
    folder = ad_folder(ad, must_exist=False)
    folder.mkdir(parents=True, exist_ok=False)
    for path in ('brief', 'footage', 'refs', 'audio/vo', 'audio/music', 'audio/sfx',
                 'renders/_work', 'renders/gen', 'renders/qa', 'exports/9x16', 'exports/4x5'):
        (folder / path).mkdir(parents=True, exist_ok=True)
    with (folder / 'ledger.csv').open('x', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerow(HEADER)
    (folder / 'brief/progress.md').write_text(
        f'# Progress: {ad}\n\nCompleted: ad folders created.\n\n'
        'Next: add the original brief, footage and references; then ask Codex to check the brief.\n\n'
        'Pending creative/spend approvals: none.\n', encoding='utf-8')
    print(f'Created {folder}. Budget uses AGENTS.md until the user supplies brief/budget.txt.')


def doctor():
    good = True
    print(f'Workspace: {ROOT}\nPython: {sys.executable}')
    for tool in ('ffmpeg', 'ffprobe'):
        found = shutil.which(tool)
        good &= bool(found)
        print(f'{tool}: ' + ('found' if found else 'MISSING'))
    for module in ('numpy', 'PIL', 'faster_whisper', 'pypdf'):
        # Check actual imports so missing DLLs are not mistaken for a working installation.
        result = subprocess.run([sys.executable, '-c', f'import {module}'], capture_output=True)
        exists = result.returncode == 0
        good &= exists
        print(f'{module}: ' + ('found' if exists else 'MISSING or import failed'))
    for tool in ('jq', 'yt-dlp'):
        found = shutil.which(tool)
        if tool == 'jq' and not found:
            candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/WinGet/Packages/jqlang.jq_Microsoft.Winget.Source_8wekyb3d8bbwe/jq.exe'
            found = candidate.is_file()
        print(f'{tool} (optional helper): ' + ('installed' if found else 'missing'))
    manifests = sorted((ROOT / '.agents/skills').glob('*/SKILL.md'))
    print(f'Project skills: {len(manifests)}')
    good &= len(manifests) == 25 and (ROOT / 'AGENTS.md').is_file()
    for key in ('KIE_API_KEY', 'ELEVENLABS_API_KEY'):
        print(f'{key}: ' + ('set' if key in os.environ and bool(os.environ[key]) else 'missing'))
    print('Paid prices: verify relevant prices.json entries before quoting; null entries block spending.')
    print('Whisper model cache: not checked; first transcription may download the model.')
    print('Local setup: ' + ('READY' if good else 'needs the missing items above'))
    return 0 if good else 1


def exports(ad):
    folder = ad_folder(ad)
    base = folder / 'exports'
    result = {}
    pattern = re.compile(re.escape(ad) + r'_(H\d+|BODY)_(9x16|4x5)_v[1-9]\d*\.mp4$')
    for path in sorted(base.rglob('*')):
        if not path.is_file():
            continue
        within(path, base)
        match = pattern.fullmatch(path.name)
        if not match or path.parent.name != match[2]:
            raise ValueError(f'Unexpected export name or ratio folder: {path.relative_to(base)}')
        if path.stat().st_size == 0:
            raise ValueError(f'Empty export: {path.name}')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        result[path.relative_to(base).as_posix()] = digest.hexdigest()
    if not result:
        raise ValueError('No exports to check')
    return result


def validate_report(ad, report):
    folder = ad_folder(ad)
    report = within(report, folder / 'renders/qa')
    text = report.read_text(encoding='utf-8')
    if not re.search(r'^RESULT:\s*PASS\s*$', text, re.M):
        raise ValueError('QA report must contain an explicit RESULT: PASS')
    if re.search(r'\b(PENDING|NOT RUN|UNCHECKED)\b', text, re.I):
        raise ValueError('QA report still has pending checks')
    if any(p.stat().st_mtime_ns > report.stat().st_mtime_ns
           for p in (folder / 'exports').rglob('*') if p.is_file()):
        raise ValueError('Exports changed after the QA report; rerun QA')
    return report


def qa_pass(ad, report):
    folder = ad_folder(ad)
    report = validate_report(ad, ROOT / report)
    manifest = {'ad': ad, 'time': local_now().isoformat(),
                'report': report.relative_to(ROOT).as_posix(),
                'report_hash': hashlib.sha256(report.read_bytes()).hexdigest(),
                'exports': exports(ad)}
    # This records the agent's completed measured/visual review; it does not perform that review.
    (folder / 'renders/qa/LAST_PASS').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'QA manifest saved for {len(manifest["exports"])} exports. Measured/visual checks remain in the report.')


def delivery_check(ad):
    folder = ad_folder(ad)
    manifest = json.loads((folder / 'renders/qa/LAST_PASS').read_text(encoding='utf-8'))
    report = validate_report(ad, ROOT / manifest['report'])
    if manifest.get('ad') != ad or manifest['exports'] != exports(ad):
        raise ValueError('Export set or contents changed; run QA again')
    if manifest.get('report_hash') != hashlib.sha256(report.read_bytes()).hexdigest():
        raise ValueError('QA report changed after the pass was recorded; run QA again')
    print(f'Delivery manifest: PASS for {len(manifest["exports"])} unchanged exports.')
    print('Also compare approved hooks with both ratio folders and complete the handoff checklist.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('doctor')
    for name in ('new', 'qa-pass', 'delivery-check'):
        item = commands.add_parser(name)
        item.add_argument('ad')
        if name == 'qa-pass':
            item.add_argument('--report', required=True)
    args = parser.parse_args()
    if args.action == 'new':
        create_ad(args.ad)
    elif args.action == 'doctor':
        return doctor()
    elif args.action == 'qa-pass':
        qa_pass(args.ad, args.report)
    else:
        delivery_check(args.ad)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f'BLOCKED: {error}', file=sys.stderr)
        raise SystemExit(2)
