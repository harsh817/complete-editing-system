"""Offline story-state initialization and shot-plan checks. Never calls providers."""
import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = [f'S{i}' for i in range(9)]
FIELDS = ('id start_sec duration_sec marketing_beat story_function visible_action character_ids '
          'environment_id emotion_and_microexpression exaggeration_and_meaning camera_and_composition '
          'wardrobe_and_prop_state reference_asset_ids opening_state ending_state voiceover_segment_ids '
          'setup_or_payoff_ref continuity_notes review_status source_duration_sec source_in_sec '
          'source_out_sec reference_paths source_clip_id reuse_reason').split()


def ad_path(ad):
    if not re.fullmatch(r'[A-Z]{3,4}_\d{4}-S\d+(?:-[A-Za-z0-9-]+)?', ad):
        raise ValueError('Invalid ad ID')
    base = (ROOT / 'ads').resolve()
    p = (base / ad).resolve()
    if not p.is_relative_to(base) or not p.is_dir():
        raise ValueError('Ad must already exist inside workspace ads/')
    return p


def init(ad):
    folder = ad_path(ad) / 'brief/story-engine'
    folder.mkdir(parents=True, exist_ok=True)
    state = dict(schema_version=1, project_id=ad, current_stage='S0',
                 stages={s: {'status': 'not_started', 'artifacts': []} for s in STAGES},
                 script={'path': None, 'version': None}, intake={}, human_truth={},
                 selected_story_id=None, stories=[], exaggeration={}, characters=[],
                 environments=[], shots_path=None, frames=[], clips=[], approvals=[],
                 rejected_directions=[], outstanding_questions=[], change_log=[])
    with (folder / 'state.json').open('x', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    return folder / 'state.json'


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate(data, folder):
    errors, warnings, ids = [], [], set()
    sequences = data.get('sequences') if isinstance(data, dict) else None
    if not isinstance(sequences, list) or not sequences:
        return ['Nonempty sequences list required'], []
    seq_ids = set()
    for seq in sequences:
        if not isinstance(seq, dict):
            errors.append('Sequence must be an object'); continue
        sid = seq.get('id')
        if not isinstance(sid, str) or not sid or sid in seq_ids:
            errors.append('Sequence IDs must be unique nonempty strings')
        else:
            seq_ids.add(sid)
        shots = seq.get('shots')
        if not isinstance(shots, list) or not shots:
            errors.append(f'{sid}: nonempty shots list required'); continue
        cursor, used = 0., set()
        for shot in shots:
            if not isinstance(shot, dict):
                errors.append(f'{sid}: shot must be an object'); continue
            label = str(shot.get('id', '?'))
            for key in FIELDS:
                if key not in shot:
                    errors.append(f'{label}: missing {key}')
            if not isinstance(shot.get('id'), str) or not shot['id'] or shot['id'] in ids:
                errors.append(f'{label}: invalid or duplicate shot ID')
            else:
                ids.add(shot['id'])
            a, d = shot.get('start_sec'), shot.get('duration_sec')
            if not number(a) or not number(d) or a < 0 or d <= 0:
                errors.append(f'{label}: invalid timeline numbers'); continue
            if abs(a-cursor) > .05:
                errors.append(f'{label}: gap/overlap at {cursor:.3f}s')
            cursor = a+d
            source, lo, hi = (shot.get(k) for k in ('source_duration_sec', 'source_in_sec', 'source_out_sec'))
            if not all(number(v) for v in (source, lo, hi)) or not (0 <= lo < hi <= source):
                errors.append(f'{label}: invalid source trim/coverage')
            elif abs(hi-lo-d) > .05:
                errors.append(f'{label}: source trim differs from edited duration; specify retiming in a revised plan')
            refs = shot.get('reference_paths')
            if not isinstance(refs, list) or not refs:
                errors.append(f'{label}: reference_paths must be nonempty list')
            else:
                for ref in refs:
                    if not isinstance(ref, str):
                        errors.append(f'{label}: invalid reference path'); continue
                    p = (folder / ref).resolve()
                    if not p.is_relative_to(folder.resolve()) or not p.is_file():
                        errors.append(f'{label}: missing/outside-ad reference {ref}')
            clip = shot.get('source_clip_id')
            if not isinstance(clip, str) or not clip:
                errors.append(f'{label}: source_clip_id required')
            elif clip in used and not shot.get('reuse_reason'):
                errors.append(f'{label}: repeated source requires reuse_reason')
            else:
                used.add(clip)
            if shot.get('review_status') != 'approved':
                warnings.append(f'{label}: creative review pending')
        expected = seq.get('duration_sec')
        if not number(expected) or expected <= 0 or abs(cursor-expected) > .05:
            errors.append(f'{sid}: duration sum does not match sequence duration')
    return errors, warnings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['init', 'status', 'check'])
    p.add_argument('ad')
    p.add_argument('shots', nargs='?')
    a = p.parse_args()
    folder = ad_path(a.ad)
    if a.command == 'init':
        print(init(a.ad)); return 0
    if a.command == 'status':
        state = json.loads((folder / 'brief/story-engine/state.json').read_text(encoding='utf-8-sig'))
        print('Next creative stage:', next((s for s in STAGES if state['stages'][s]['status'] != 'approved'), 'S8 complete'))
        return 0
    if not a.shots:
        p.error('check requires workspace-relative shots JSON path')
    path = (ROOT / a.shots).resolve()
    if not path.is_relative_to(folder):
        raise ValueError('Shot file must be inside this ad')
    errors, warnings = validate(json.loads(path.read_text(encoding='utf-8-sig')), folder)
    for x in errors: print('ERROR:', x)
    for x in warnings: print('REVIEW:', x)
    print(f'Structural check: {len(errors)} errors, {len(warnings)} pending reviews. Not export QA.')
    return int(bool(errors))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as e:
        raise SystemExit(str(e))
