"""Offline behavioral checks for the migrated cost and delivery controls. No provider calls."""
import contextlib
import csv
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import cost_control as control
import paid_run
import workspace

REAL_ROOT = control.ROOT


class WorkflowControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='editing-check-', dir=REAL_ROOT / 'tools')
        self.root = Path(self.temp.name).resolve()
        if not self.root.is_relative_to(REAL_ROOT / 'tools'):
            raise RuntimeError('Test folder escaped its intended workspace')
        self.stack = contextlib.ExitStack()
        for module in (control, paid_run, workspace):
            self.stack.enter_context(patch.object(module, 'ROOT', self.root))
        (self.root / 'AGENTS.md').write_text(
            'MAX_BUDGET_PER_CONCEPT_USD = 40\nREPAIR_BUDGET_PCT = 25\n', encoding='utf-8')
        self.ad = 'TEST_2610-S1'
        with contextlib.redirect_stdout(io.StringIO()):
            workspace.create_ad(self.ad)
        self.folder = control.ad_folder(self.ad)
        self.price = {'test-image': {'unit': 'image', 'usd': 0.09,
                                     'checked': control.local_now().date().isoformat()}}
        (self.root / 'prices.json').write_text(json.dumps(self.price))
        self.helper = '.agents/skills/broll-from-brief/scripts/kie.py'
        helper = self.root / self.helper
        helper.parent.mkdir(parents=True)
        helper.write_text('print("offline fixture")\n')
        self.request = {'ad': self.ad, 'step': 'broll', 'provider': 'kie', 'model': 'test-image',
                        'units': 1, 'unit': 'image', 'script': self.helper,
                        'args': ['run', 'renders/_work/jobs.json']}
        self.path = self.folder / 'renders/_work/request.json'
        self.write_request()

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def write_request(self):
        self.path.write_text(json.dumps(self.request))
        return self.path.relative_to(self.root).as_posix()

    def run_wrapper(self, *flags):
        with patch.object(sys, 'argv', ['paid_run.py', 'run', self.write_request(), *flags]):
            with contextlib.redirect_stdout(io.StringIO()):
                return paid_run.main()

    def test_new_ad_rejects_replacement_and_path_escape(self):
        with self.assertRaises(FileExistsError):
            workspace.create_ad(self.ad)
        with self.assertRaises(ValueError):
            workspace.create_ad('../OUTSIDE')
        self.assertTrue((self.folder / 'ledger.csv').exists())

    def test_quotes_change_with_inputs_and_reject_invalid_units_or_prices(self):
        first = control.request_quote(self.write_request())['quote_id']
        (self.folder / 'brief/source.txt').write_text('new creative input')
        second = control.request_quote(self.write_request())['quote_id']
        self.assertNotEqual(first, second)
        self.assertEqual(control.spent(self.ad), Decimal(0))
        for invalid in (-1, float('nan'), float('inf')):
            self.request['units'] = invalid
            with self.assertRaises(ValueError):
                control.request_quote(self.write_request())
        self.request['units'] = 1
        for invalid in (None, -0.1, float('nan')):
            self.price['test-image']['usd'] = invalid
            (self.root / 'prices.json').write_text(json.dumps(self.price))
            with self.assertRaises(ValueError):
                control.request_quote(self.write_request())

    def test_missing_approval_and_changed_quote_do_not_execute_or_reserve(self):
        quote_id = control.request_quote(self.write_request())['quote_id']
        with patch.object(paid_run.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                self.run_wrapper('--quote-id', quote_id)
            self.request['units'] = 2
            with self.assertRaises(ValueError):
                self.run_wrapper('--approved', '--quote-id', quote_id)
            run.assert_not_called()
        self.assertEqual(control.spent(self.ad), Decimal(0))

    def test_budget_includes_repair_allowance(self):
        (self.folder / 'brief/budget.txt').write_text('0.10')
        with self.assertRaises(ValueError):
            control.request_quote(self.write_request())

    def test_run_reserves_before_launch_and_uses_direct_argument_array(self):
        quote_id = control.request_quote(self.write_request())['quote_id']
        def launch(command, cwd, env):
            self.assertIsInstance(command, list)
            self.assertEqual(control.spent(self.ad), Decimal('0.0900'))
            self.assertEqual(Path(cwd), self.folder)
            self.assertEqual(command[-1], '--approved')
            self.assertIn(control.CONTEXT, env)
            return subprocess.CompletedProcess(command, 1)
        with patch.object(paid_run.subprocess, 'run', side_effect=launch):
            self.assertEqual(self.run_wrapper('--approved', '--quote-id', quote_id), 1)
        self.assertEqual(control.spent(self.ad), Decimal('0.0900'))
        self.assertFalse((self.folder / 'renders/_work/paid-run.lock').exists())

    def test_actual_run_cannot_exceed_context(self):
        context = {'run_id': 'offline-test', 'ad': self.ad, 'model': 'test-image',
                   'units': '1', 'unit': 'image', 'amount': '0.09'}
        with patch.dict(os.environ, {control.CONTEXT: json.dumps(context)}), patch.object(Path, 'cwd', return_value=self.folder):
            control.validate_context([('test-image', 1, 'image', 0.09)])
            with self.assertRaises(SystemExit):
                control.validate_context([('test-image', 2, 'image', 0.18)])
            with self.assertRaises(SystemExit):
                control.validate_context([('other-model', 1, 'image', 0.09)])

    def test_shared_gate_reads_codex_settings_without_double_reserving(self):
        (self.folder / 'brief/budget.txt').write_text('0.15')
        with (self.folder / 'ledger.csv').open('a', newline='') as stream:
            csv.DictWriter(stream, fieldnames=control.HEADER).writerow({'ad': self.ad, 'usd_est': '0.09'})
        path = REAL_ROOT / '.agents/skills/gated-generation/scripts/gate.py'
        spec = importlib.util.spec_from_file_location('editing_gate_fixture', path)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        context = {'run_id': 'offline-test', 'ad': self.ad, 'model': 'test-image',
                   'units': '1', 'unit': 'image', 'amount': '0.09'}
        environment = {control.CONTEXT: json.dumps(context), 'EDITING_WORKSPACE': str(self.root)}
        with patch.dict(os.environ, environment), patch.object(Path, 'cwd', return_value=self.folder):
            with contextlib.redirect_stdout(io.StringIO()):
                result = gate.gate([('test-image', 1, 'image')], True, ad=self.ad)
        self.assertAlmostEqual(result, 0.09)

    def test_changed_export_invalidates_pass(self):
        export = self.folder / f'exports/9x16/{self.ad}_H1_9x16_v1.mp4'
        export.write_bytes(b'offline manifest fixture, not a real media QA result')
        report = self.folder / 'renders/qa/offline-fixture.md'
        report.write_text('RESULT: PASS\nOffline manifest fixture only.\n')
        with contextlib.redirect_stdout(io.StringIO()):
            workspace.qa_pass(self.ad, report.relative_to(self.root))
            workspace.delivery_check(self.ad)
        export.write_bytes(b'changed contents')
        with self.assertRaises(ValueError):
            workspace.delivery_check(self.ad)

    def test_direct_paid_helpers_block_before_network(self):
        for relative in sorted(control.PAID_SCRIPTS):
            helper = REAL_ROOT / '.agents/skills' / relative
            env = dict(os.environ)
            env.pop(control.CONTEXT, None)
            result = subprocess.run([sys.executable, str(helper), '--approved'],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, relative)
            self.assertIn('tools/paid_run.py', result.stderr, relative)


if __name__ == '__main__':
    unittest.main(verbosity=2)
