"""Quote or execute a bundled paid helper. No shell evaluation; secrets remain in the environment."""
import argparse
import csv
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from cost_control import CONTEXT, HEADER, ROOT, local_now, request_quote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['quote', 'run'])
    parser.add_argument('request', help='workspace-relative JSON inside the ad renders/_work folder')
    parser.add_argument('--approved', action='store_true')
    parser.add_argument('--quote-id')
    args = parser.parse_args()
    info = request_quote(args.request)
    request = info['request']
    print(f"QUOTE {info['quote_id']}  ad={request['ad']}  step={request['step']}", flush=True)
    print(f"Run ${info['amount']:.4f}; repair allowance ${info['repair']:.4f}; "
          f"reserved so far ${info['spent']:.4f}; cap ${info['cap']:.2f}", flush=True)
    if args.action == 'quote':
        print('No provider request sent. Show this quote to the user and wait for OK.')
        return 0
    if not args.approved or args.quote_id != info['quote_id']:
        raise ValueError('Execution requires explicit user OK and the unchanged quote ID')
    lock = info['folder'] / 'renders/_work/paid-run.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    # One run per ad at a time, including quote revalidation and ledger reservation.
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    try:
        latest = request_quote(args.request)
        if latest['quote_id'] != args.quote_id:
            raise ValueError('Inputs, prices, budget or ledger changed; quote and approve again')
        run_id = uuid.uuid4().hex
        context = {'run_id': run_id, 'ad': request['ad'], 'model': request['model'],
                   'units': str(request['units']), 'unit': request['unit'],
                   'amount': str(info['amount'])}
        now = local_now()
        row = dict(zip(HEADER, [now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
                   request['ad'], request['step'], request['provider'], request['model'],
                   request['units'], request['unit'], str(info['amount']), 'reserved',
                   f"run={run_id};quote={args.quote_id};actual_billing_unknown"]))
        with (info['folder'] / 'ledger.csv').open('a', newline='', encoding='utf-8') as stream:
            csv.DictWriter(stream, fieldnames=HEADER).writerow(row)
            stream.flush()
            os.fsync(stream.fileno())
        environment = os.environ.copy()
        environment[CONTEXT] = json.dumps(context)
        environment['EDITING_WORKSPACE'] = str(ROOT)
        command = [sys.executable, str(info['script']), *request['args'], '--approved']
        result = subprocess.run(command, cwd=info['folder'], env=environment)
        print(f"Run {run_id}: process exit {result.returncode}. Estimated reservation retained; "
              'check provider job status for actual billing.')
        return result.returncode
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f'BLOCKED: {error}', file=sys.stderr)
        raise SystemExit(2)
