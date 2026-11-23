"""Rebuild the Codex adaptation from the preserved original package (maintenance helper)."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / '.agents/skills'
COMMANDS = {name: 'ad-' + ('new' if name == 'new-ad' else name)
            for name in ('new-ad', 'brief', 'cut', 'variants', 'final', 'qa', 'deliver', 'spend')}
DESCRIPTIONS = {
    'brief-check': 'Check an ad brief and source footage for gaps; write the verbatim script, edit plan and blocking questions.',
    'reference-breakdown': 'Measure cuts and transcribe a reference ad, then describe its timed shots for an edit plan.',
    'script-vs-take': 'Transcribe creator takes, compare spoken words with the script, and propose timed take selections.',
    'rough-cut': 'Build an H1 rough cut from approved takes and timing, with local video renders and edit decision files.',
    'broll-from-brief': 'Plan missing ad B-roll and generate approved starting frames and clips through the paid-run wrapper.',
    'scene-edit': 'Plan and quote a focused image edit while preserving the referenced product, person and scene.',
    'talking-avatar': 'Plan and produce approved talking-avatar clips and hook reads from a supplied script and reference.',
    'voiceover': 'Quote and produce approved ad voiceover reads, with local normalization and transcript checks.',
    'one-voice': 'Quote and apply a consistent approved voice across character clips or create an authorized voice clone.',
    'actor-swap': 'Plan and quote an authorized actor replacement while checking original gestures, hands, props and timing.',
    'animated-ad': 'Plan an animated ad scene table, references and prompts, then generate approved still and clip batches.',
    'gated-generation': 'Quote and control provider spending for paid ad generation, rerolls and voice workflows; inspect the ledger.',
    'song-timing': 'Plan song-led ads, measure beats and lyric timing, and quote approved song generation or edits.',
    'captions-headlines': 'Create word-timed captions, verbatim headlines and end cards with a separate layout per aspect ratio.',
    'reframe-exports': 'Render approved hooks in 9:16 and 4:5, normalize audio, version exports and measure deliverables.',
    'edit-qa': 'Measure final ad files and inspect visual and script compliance, writing timestamped QA findings.',
}


def convert(text):
    text = (text.replace('CLAUDE_PROJECT_DIR', 'EDITING_WORKSPACE').replace('CLAUDE.md', 'AGENTS.md')
            .replace('.claude/skills', '.agents/skills').replace('Claude Code', 'Codex').replace('Claude', 'Codex'))
    text = text.replace('~/.venvs/editing/bin/python', 'C:/Users/pc/.venvs/editing/Scripts/python.exe')
    text = text.replace('the slash commands read them', 'the workflow skills read them')
    text = text.replace('runs this skill through the edit-qa subagent', 'runs this review in the current chat')
    text = text.replace('under the Bash tool timeout', 'under the shell tool timeout')
    text = text.replace('For a Google Doc, ask the user to download it as .docx first.',
                        'For a Google Doc, use an available connected document reader; otherwise request a .docx export.')
    for old, new in sorted(COMMANDS.items(), key=lambda item: -len(item[0])):
        text = re.sub(r'(?<![\w/])/' + re.escape(old) + r'(?=[\s`.,<]|$)', '$' + new, text)
    return text


BOOTSTRAP = '''
# Codex: resolve shared controls relative to this installed helper, not the shell's current folder.
import sys as _codex_sys
import os as _codex_os
from pathlib import Path as _CodexPath
_codex_sys.path.insert(0, str(_CodexPath(__file__).resolve().parents[4] / "tools"))
from cost_control import validate_context as codex_validate_paid
if "--approved" in _codex_sys.argv and not _codex_os.environ.get("EDITING_PAID_CONTEXT"):
    raise SystemExit("BLOCKED: use tools/paid_run.py with an approved quote ID for paid execution")
'''


def add_bootstrap(text):
    tree = ast.parse(text)
    first = tree.body[0]
    position = first.end_lineno if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) else 1
    lines = text.splitlines(keepends=True)
    lines.insert(position, BOOTSTRAP + '\n')
    return ''.join(lines)


def patch_script(text, relative):
    text = convert(text).replace('.read_text()', '.read_text(encoding="utf-8")')
    paid = relative.as_posix() in {
        'actor-swap/scripts/actorswap.py', 'animated-ad/scripts/gen.py',
        'broll-from-brief/scripts/kie.py', 'scene-edit/scripts/kie.py',
        'talking-avatar/scripts/kie.py', 'voiceover/scripts/vo.py',
        'one-voice/scripts/voice.py', 'song-timing/scripts/timing.py'}
    if paid:
        text = add_bootstrap(text)
    if relative.name == 'kie.py':
        marker = '    for j in jobs:   # --redo:'
        validation = '''    actual = []
    table = prices()
    for job in jobs:
        if job["id"] not in redo and (os.path.exists(job["out"]) or state.get(job["id"], {}).get("status") == "done"):
            continue
        record = table.get(price_key(job)) or table.get(job["model"])
        count = units(job, record["unit"])
        actual.append((price_key(job), count, record["unit"], count * float(record["usd"])))
    codex_validate_paid(actual)
'''
        if marker not in text:
            raise ValueError(f'Cannot locate KIE execution gate in {relative}')
        text = text.replace(marker, validation + marker)
    if relative.name == 'vo.py':
        marker = '    for name, text, raw, cached in plan:\n        if not cached:'
        validation = '''    if total:
        codex_validate_paid([(cfg.get("model_id", "eleven_v3"), total, "char", total / 1000 * rate)])
'''
        if marker not in text:
            raise ValueError('Cannot locate voiceover execution gate')
        text = text.replace(marker, validation + marker)
        # Read the configured loudness settings, including for the free norm subcommand.
        text = text.replace('    a = ap.parse_args()\n', '''    a = ap.parse_args()
    from cost_control import setting as _house_setting
    global TARGET_I, TARGET_TP
    TARGET_I = float(_house_setting("LOUDNESS_TARGET_LUFS"))
    TARGET_TP = float(_house_setting("TRUE_PEAK_DBTP"))
''')
    if relative.as_posix() == 'gated-generation/scripts/gate.py':
        start = text.index('"""')
        end = text.index('"""', start + 3) + 3
        text = text[:start] + '''"""Shared quote helpers for Codex ad generation.
Free: gate.py quote --step S --model M --units N --unit image|second|clip|char [--ad AD]
Free: gate.py spend [--ad AD] or gate.py doctor [--ad AD]
Paid execution uses tools/paid_run.py; these functions validate its reserved context.
Comment tags retained in quote output are informational and do not register lifecycle hooks.
"""''' + text[end:]
        text = text.replace('LEDGER_HEADER =', '''sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools"))
import cost_control as _control

LEDGER_HEADER =''', 1)
        text = text.replace('    total, lines, missing = 0.0, [], []', '    actual = []\n    total, lines, missing = 0.0, [], []')
        text = text.replace('        p = price(ad, model)', '''        try:
            _control.number(units, "units")
            _control.unit_price(ad, model, unit)
        except ValueError as error:
            raise SystemExit(str(error)) from None
        p = price(ad, model)''')
        text = text.replace('        total += usd', '        total += usd\n        actual.append((model, units, unit, usd))')
        text = text.replace('    c, s = cap(ad), spent(ad)\n    print(f"QUOTE', '''    c, s = cap(ad), spent(ad)
    if approved:
        _control.validate_context(actual, ad)
        # The wrapper has already reserved this run; avoid charging it twice in this check.
        s -= float(json.loads(os.environ[_control.CONTEXT])["amount"])
    print(f"QUOTE''')
        text = text.replace('    rs = rows(ad)\n    if not rs:',
                            '    _control.ad_folder(ad)\n    rs = _control.ledger_rows(ad)\n    if not rs:')
        start, end = text.index('def doctor(ad):'), text.index('\ndef parse(argv):')
        text = text[:start] + '''def doctor(ad):
    import subprocess
    return subprocess.call([sys.executable, str(_control.ROOT / "tools/workspace.py"), "doctor"])

''' + text[end:]
    # The old comment-tag examples are not execution instructions for this adaptation.
    text = text.replace('the cost_gate hook already checked the tag before this process started',
                        'the paid-run wrapper already reserved this estimate')
    text = text.replace('the cost_gate hook will block every paid call', 'the paid-run wrapper blocks execution')
    text = text.replace('same sum the cost_gate hook uses', 'conservative sum including reservations')
    text = '\n'.join(line for line in text.splitlines()
                     if '.claude/paid-calls.json' not in line and 'workspace hooks check' not in line
                     and 'workspace hooks (cost_gate.py' not in line) + '\n'
    return text


def skill(name, description, body):
    folder = DEST / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'SKILL.md').write_text('---\nname: ' + name + '\ndescription: ' + json.dumps(description)
                                    + '\n---\n\n' + body.strip() + '\n', encoding='utf-8')


WORKFLOWS = {
    'ad-new': ('Create the standard folder tree and ledger for a new named ad concept.', '''# New ad

Resolve the requested BRAND_YYMM-S# name (3–4 capital brand letters, optional -Product suffix).
From the workspace root run the editing Python interpreter with `tools/workspace.py new <AD>`.
The helper rejects invalid names and existing folders; it never creates a budget override.
Tell the user where to put the original brief, raw footage and references. Keep originals unchanged.
Next: ad-brief after the materials arrive. Do not start a fictitious sample ad without a request.
'''),
    'ad-brief': ('Review the supplied ad brief and write an edit plan before cutting footage.', '''# Check the brief

Read AGENTS.md and EDITING_RULES.md, then the original brief and the file lists in refs/ and footage/.
No brief: ask for it. Use the brief-check skill and `references/brief-checker.md` in this skill.
Perform the review here; another agent is not required. Write brief/script.txt, edit-plan.md and
questions.md without modifying the brief. Preserve exact hooks, headlines, brand names and claims.
If a reference ad exists, use reference-breakdown; quote any paid analysis before proceeding.
Record format/length, hooks, body, B-roll, audio, text, footage path, missing facts, expected paid
steps and deliverables. Answer blocking questions before cutting. Update brief/progress.md.
Next: ad-cut once the footage exists and decisions that affect the cut or cost are resolved.
'''),
    'ad-cut': ('Build the first H1 rough cut using the planned real footage or approved AI footage.', '''# H1 rough cut

Read the ad plan and progress. Stop for unresolved decisions that change the cut.
For real footage, inventory with ffprobe, flag mixed/VFR inputs, and use script-vs-take to select
timed takes and list deviations for user review. Write proxies into renders/_work/ when needed.
For AI footage, select talking-avatar, animated-ad and/or song-timing according to the plan.
Route every paid operation through gated-generation and the paid-run wrapper.
Use rough-cut for H1 only. Keep script order and the approved copy. List missing B-roll and propose
the appropriate production skill; no generation without its own quote and OK.
Render a versioned H1 rough file to renders/, never exports/. Report measured duration, cuts,
take choices, script changes and gaps. Show the video and wait for creative review.
After review fill agreed gaps, handle voice/music, then prepare a captions-headlines demo.
Update progress. Next: ad-variants after the rough cut and text style are approved.
'''),
    'ad-variants': ('Build approved ad hook variants on a shared body with reviewed headlines and captions.', '''# Hook variants

Read the plan and determine the approved rough cut and text demo; ask if approval is ambiguous.
Use captions-headlines. If a headline is absent or alternatives are requested, use
`references/hook-writer.md` here as a checklist, label proposals and wait for the user's selection.
Preserve each verbatim approved hook/headline and the frame-identical body. Offer banners appear
only on the appropriate hooks. Render H1 first if the style has not been reviewed, then wait.
Render other approved hooks into renders/. Measure duration/body equality within one frame and
inspect first-three-second contact sheets for covered faces/products. Update progress.
Next: ad-final after the variants are approved.
'''),
    'ad-final': ('Render versioned final ad exports in both ratios with measured encoding and audio.', '''# Final exports

Read the approved plan, hooks and review decisions. Use reframe-exports and captions-headlines.
Render 9x16 1080x1920 and 4x5 1080x1350 from the same approved inputs in separate passes with
ratio-specific text layout. Do not crop a finished text-bearing 9x16 file to create 4x5.
Use H.264 High, yuv420p, source constant fps, AAC 48 kHz stereo and faststart; normalize in two
passes and measure the result against AGENTS.md. First write in renders/, then copy final-named
files into the ratio export folders. Preserve every existing version. Measure name, resolution,
fps, duration, LUFS, true peak and size. Any change invalidates the previous QA pass.
Update progress. Next: ad-qa; do not call the files ready for handoff yet.
'''),
    'ad-qa': ('Perform measured and visual QA, report timestamped failures and stamp unchanged passing exports.', '''# Export QA

Read the brief, edit plan, AGENTS.md and EDITING_RULES.md. Use the edit-qa skill and the complete
`references/edit-qa.md` checklist here. Perform the review in this chat; another agent is optional
only when independently authorized. Automatic output is not proof of the pending visual checks.
Write renders/qa/qa-<date-time>.md with exactly `RESULT: PASS` or `RESULT: FAIL` on its own line.
Record per-file values, all blocking checks, visual inspection, timestamps and warnings. A missing,
unrun or pending blocking check means FAIL. Verify approved hooks exist in both ratios.
If every blocking check passed and visual review is complete, run from the workspace root:
`tools/workspace.py qa-pass <AD> --report ads/<AD>/renders/qa/qa-<date-time>.md`
using the editing interpreter. Do not use touch or write LAST_PASS manually.
On failure, report fixes and wait for creative/cost decisions as needed; changed exports get a new
version and another QA pass. Update progress. Next after PASS: ad-spend, then ad-deliver.
'''),
    'ad-spend': ('Show reserved estimated provider spending per ad or prepare a quote for its next paid step.', '''# Spending

Read the ad ledger, plan and cap from AGENTS.md or brief/budget.txt. Use the gated-generation
helper `gate.py spend --ad <AD>` to summarize estimates by step/status. Report total reserved,
remaining cap and rework; confirmed provider billing is unknown unless separately supplied.
Never edit or delete past rows. Failed/interrupted attempts keep their conservative reservation.
For a new quote, use the gated-generation skill and tools/paid_run.py; show its quote ID and wait.
Next: the approved production step or ad-deliver after successful QA.
'''),
    'ad-deliver': ('Validate the QA manifest and prepare the ad file list and handoff report.', '''# Handoff

Run `tools/workspace.py delivery-check <AD>` from the workspace root with the editing interpreter.
A missing/stale manifest or changed export blocks handoff and requires ad-qa again.
Compare every approved hook with both ratio folders, confirm naming and ensure no rough, clean or
review files are in exports/. Preserve previous versions; identify current approved deliverables.
Write renders/qa/handoff.md: current file list with hook, ratio, duration and size; accepted script
changes and who approved them; music licence/source; estimated spending by step and rework; and
any open items. Update progress and show the final local files with clickable paths.
The user uploads the files and checks playback in both ratios. Do not upload as part of handoff.
'''),
}


def main():
    for source in (ROOT / '.claude/skills').rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts:
            continue
        relative = source.relative_to(ROOT / '.claude/skills')
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == '.py':
            target.write_text(patch_script(source.read_text(encoding='utf-8'), relative), encoding='utf-8')
        elif source.suffix in {'.md', '.json', '.sh'}:
            text = convert(source.read_text(encoding='utf-8'))
            if source.name == 'SKILL.md':
                name = relative.parts[0]
                body = text.split('---', 2)[2].strip()
                body = body.replace('Needs Skill 12 (gated-generation) for the quotes and the Page 03 hooks for the cost tag.',
                                    'Use gated-generation and tools/paid_run.py for quoted, approved execution.')
                body = body.replace('one row per paid call, written by the cost hook', 'estimated reservations written by the paid-run wrapper')
                body = body.replace('Skill 12 (gated-generation) and the Page 03 hooks',
                                    'gated-generation and the Codex paid-run wrapper')
                body = re.sub(r'3\. \*\*Read-through\.\*\*.*?Else do the read yourself\.',
                              '3. **Read-through.** Use the checklist at ../ad-brief/references/brief-checker.md in this chat.',
                              body, flags=re.S)
                body = body.replace('house shape', 'reporting guidance')
                runtime = '''Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.
'''
                skill(name, DESCRIPTIONS[name], runtime + '\n' + body)
            else:
                target.write_text(text, encoding='utf-8')
        else:
            target.write_bytes(source.read_bytes())
    for name, (description, body) in WORKFLOWS.items():
        skill(name, description, 'Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.\n\n' + body)
    for reviewer, name in [('brief-checker', 'ad-brief'), ('hook-writer', 'ad-variants'), ('edit-qa', 'ad-qa')]:
        text = (ROOT / '.claude/agents' / (reviewer + '.md')).read_text(encoding='utf-8').split('---', 2)[2].strip()
        text = convert(text).replace('Return to the main session:', 'Report:')
        text = text.replace('Look at it with the Read tool.', 'Inspect it with the available image viewer.')
        text = text.replace('Never touch renders/qa/LAST_PASS. The main session sets it after it reads your report.',
                            'During review write the report only. After a complete PASS follow ad-qa to stamp the manifest.')
        folder = DEST / name / 'references'
        folder.mkdir(exist_ok=True)
        (folder / (reviewer + '.md')).write_text(text + '\n', encoding='utf-8')
    skill('gated-generation', DESCRIPTIONS['gated-generation'], '''# Paid generation in Codex

Read AGENTS.md. Every paid run needs a current quote, explicit user OK for that run, and the
paid-run wrapper. A cost comment or --approved flag is insufficient. Use the editing Python
interpreter; run wrapper commands from the workspace root. Local planning and quotes are free.

1. Build the prompt/job/config files locally. Count images, seconds, clips or characters from
   the actual plan/media. Run the production helper without --approved for its free estimate.
2. Verify the chosen model and current price at the provider. Store the per-unit price and checked
   YYYY-MM-DD in root prices.json or the ad override. Null/stale/invalid prices block execution.
   For voiceover, prices.json is dollars per character; the voice config uses dollars per 1,000
   characters, so convert explicitly and ensure the two agree. Never invent a missing price.
3. Save a JSON request inside ads/<AD>/renders/_work/. Example schema (replace with real values):

```json
{
  "ad": "ACME_2610-S3",
  "step": "broll",
  "provider": "kie",
  "model": "nano-banana-pro",
  "units": 1,
  "unit": "image",
  "script": ".agents/skills/broll-from-brief/scripts/kie.py",
  "args": ["run", "renders/_work/broll_jobs.json", "--only", "S01"]
}
```

The script path is workspace-relative. Its args and input paths are relative to the ad folder.
Use one model and unit per request; use a pricing variant such as model:sound when appropriate.
Do not include --approved, a key value or a shell expression in args. The wrapper launches the
installed Python helper directly with no shell evaluation. Other supported helpers: scene-edit
and talking-avatar kie.py, voiceover vo.py, one-voice voice.py, actor-swap actorswap.py,
animated-ad gen.py and song-timing timing.py.

4. Run `tools/paid_run.py quote ads/<AD>/renders/_work/<request>.json` with the editing interpreter.
   Show run cost, repair allowance, reserved total, cap and quote ID. The quote fingerprints the
   request, prices, budget, ledger, helper and ad inputs. Wait for the user's OK for this exact run.
5. After OK run `tools/paid_run.py run <request> --approved --quote-id <quoted ID>`.
   Changed inputs or budget/spend invalidate the quote: re-quote and ask again. Do not alter inputs
   after quote approval. Do not manually set EDITING_PAID_CONTEXT or bypass a rejection.
6. Start with 1–2 items. Download results immediately to renders/gen/, inspect them and obtain
   another quote/OK for the larger batch. Re-rolls and repairs need their own quote and OK.
7. Show spending after every run using `scripts/gate.py spend --ad <AD>`.

The ledger records an estimate before executing the helper, with status reserved and a run ID.
This protects the cap if the job fails or is interrupted. Never delete or edit those rows, and
never treat estimates as confirmed provider charges. If a run failed before sending anything,
report that fact separately; reconciliation of actual billing is a user decision.

If a paid-run.lock remains after a crash, inspect whether its process is still running before
removing a stale lock. Never remove a live run's lock. Do not rerun an interrupted job blindly;
check provider/job state first. The wrapper governs these bundled helpers, not arbitrary Codex
tools or other connectors. Apply the same quote/OK policy to paid actions outside this bundle;
do not pretend another connector is recorded by this ledger.

Keys are optional until needed. Check only set/missing; use the masked tools/set-key.ps1 helper
for user entry. User authorization must also cover any private media uploaded to the provider.
''')
    skill('ad-workflow', 'Run or resume the complete Codex video-ad workflow from brief through QA and handoff.', '''# Ad workflow

Read AGENTS.md and EDITING_RULES.md. Resolve the named ad from the request, existing folders and
brief/progress.md. If multiple ads fit, ask which. For a new concept use ad-new; obtain a valid
brand/concept name before creating folders. Maintain progress after each completed step.

Read only the appropriate entry point and the production skills it needs:

| Stage | Entry point | Review before advancing |
|---|---|---|
| Folder creation | ad-new | Original brief, footage and references supplied |
| Brief and reference review | ad-brief | Blocking questions answered; exact copy and claims verified |
| Take selection or AI plan; H1 rough cut | ad-cut | H1 watched and creative decisions accepted |
| B-roll, voice, music and text demo | Relevant production skill | Quote/OK for paid work; H1 style approved |
| Shared-body hook variants | ad-variants | Approved hooks and layout |
| Versioned final renders | ad-final | Both ratios measured |
| Measured and visual QA | ad-qa | Complete PASS report and hashed export manifest |
| Spend and handoff | ad-spend, ad-deliver | Current manifest and complete deliverable list |

For "what next", inspect the plan, progress and current files; give the single next action and
perform it if authorized. Files alone do not establish creative/spend approval. Resume useful
local work while waiting only when it does not depend on the missing decision.

For revisions, convert feedback into a list of affected hooks, timestamps, steps and costs.
Run only the required steps, assign new export versions, rerun QA and prepare a fresh handoff.
Never rewrite the brief, change claims or upload deliverables without the user's authorization.

Use ordinary language with the user; the named entry points are Codex skills rather than slash
commands. If discovery has not refreshed, read the sibling SKILL.md files directly.
''')
    print('Rebuilt Codex production skills, workflow entry points, reviewer checklists and paid helper controls.')


if __name__ == '__main__':
    main()
