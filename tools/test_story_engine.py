"""Offline tests for shot timing and state protection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import story_engine as engine


class StoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='story-check-', dir=engine.ROOT / 'tools')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ad = self.root / 'ads/TEST_2611-S1'
        self.ad.mkdir(parents=True)
        (self.ad / 'frame.png').write_bytes(b'fixture')
        shot = dict.fromkeys(engine.FIELDS, '')
        shot.update(id='H1-01', start_sec=0, duration_sec=5, source_duration_sec=7,
                    source_in_sec=1, source_out_sec=6, reference_paths=['frame.png'],
                    source_clip_id='CLIP-01', review_status='draft')
        self.data = {'sequences': [{'id': 'H1', 'duration_sec': 5, 'shots': [shot]}]}

    def test_valid_trim_and_pending_review(self):
        errors, warnings = engine.validate(self.data, self.ad)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_gap_and_insufficient_coverage(self):
        shot = self.data['sequences'][0]['shots'][0]
        shot.update(start_sec=1, source_out_sec=9)
        errors, _ = engine.validate(self.data, self.ad)
        self.assertTrue(any('gap/overlap' in e for e in errors))
        self.assertTrue(any('coverage' in e for e in errors))

    def test_reference_escape_and_missing(self):
        shot = self.data['sequences'][0]['shots'][0]
        shot['reference_paths'] = ['../outside.png', 'missing.png']
        errors, _ = engine.validate(self.data, self.ad)
        self.assertEqual(sum('reference' in e for e in errors), 2)

    def test_undocumented_reuse(self):
        seq = self.data['sequences'][0]
        other = copy.deepcopy(seq['shots'][0])
        other.update(id='H1-02', start_sec=5)
        seq['shots'].append(other); seq['duration_sec'] = 10
        self.assertTrue(any('reuse_reason' in e for e in engine.validate(self.data, self.ad)[0]))
        other['reuse_reason'] = 'Approved alternate portion of the same performance'
        self.assertFalse(engine.validate(self.data, self.ad)[0])

    def test_nonfinite_and_boolean_duration(self):
        for value in (float('nan'), float('inf'), True, -1):
            self.data['sequences'][0]['shots'][0]['duration_sec'] = value
            self.assertTrue(engine.validate(self.data, self.ad)[0])

    def test_init_refuses_overwrite_and_does_not_approve(self):
        with patch.object(engine, 'ROOT', self.root):
            path = engine.init('TEST_2611-S1')
            state = json.loads(path.read_text())
            self.assertFalse(state['approvals'])
            self.assertTrue(all(s['status'] == 'not_started' for s in state['stages'].values()))
            with self.assertRaises(FileExistsError):
                engine.init('TEST_2611-S1')
            with self.assertRaises(ValueError):
                engine.ad_path('../outside')

    def test_duplicate_and_duration_sum(self):
        seq = self.data['sequences'][0]
        seq['shots'].append(copy.deepcopy(seq['shots'][0]))
        errors, _ = engine.validate(self.data, self.ad)
        self.assertTrue(any('duplicate' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
