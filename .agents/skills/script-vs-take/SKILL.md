---
name: script-vs-take
description: "Transcribe creator takes, compare spoken words with the script, and propose timed take selections."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Script vs Take

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run from the ad folder `ads/<AD>/`. If the venv `~/.venvs/editing` exists, use `C:/Users/pc/.venvs/editing/Scripts/python.exe`.
`footage/` is read only: every output goes to `renders/_work/`.

## Steps

1. **Script.** Check `brief/script.txt` exists. Format, one line each:
   ```
   H1: hook one text
   H2: hook two text
   B1: first body line
   CTA: call to action
   ```
   If it is missing, build it from the brief (verbatim words, split at sentence ends) and show it for an OK.

2. **List the takes.** Every video or audio file under `footage/` that has speech (a-roll, hooks, body).
   Skip B-roll folders. Say which files you included.

3. **Transcribe.**
   `python3 <skill-dir>/scripts/transcribe.py footage/aroll/*.mp4 --lang <code> --model <WHISPER_MODEL from AGENTS.md>`
   Writes `renders/_work/transcripts/<take>.words.json`. Pass `--lang` when you know the language. Auto-detect fails on short clips.

4. **Match and diff.**
   `python3 <skill-dir>/scripts/take_diff.py brief/script.txt "renders/_work/transcripts/*.words.json"`
   Writes `renders/_work/takes.md` and `renders/_work/takes.json`.
   If many lines come back MISSING, rerun with `--min-score 0.5` and say so.

5. **Review the result before you show it.**
   - For every "changed" line, decide if the change is a slip (wrong word, dropped word) or a rewording that keeps the meaning. Mark it as your suggestion.
   - Numbers: Whisper writes "10" or "ten" at random. The script converts digits to words before the diff, so a number mismatch in the table is a real change.
   - Brand and product names: list how Whisper wrote each one and the correct spelling from the brief.
   - Lines with risk "tight in" or "tight out": less than 0.3 s of pause around the line. The cut will be hard. Say so.

6. **Show the output** (format below), reported in the reporting guidance from AGENTS.md. NEXT: the rough-cut skill reads `renders/_work/takes.json`.

## Output format

```
## Take map
| Line | Status | File | In | Out | Score | Takes found | Risks |

## Word changes (chosen takes)
| Line | At | Type | Script says | Take says | Slip or rewording (suggestion) |

## Missing lines
<line id and text, and the question for the creator: reshoot or cut>

## Brand names
| Written in brief | Whisper heard | Fix in captions |

## For the next shoot
<one line, only if the data shows it: e.g. leave one second of silence between lines>
```

## How the best take is picked

- Score = word match with the script (0 to 1), minus 0.05 for each filler (um, uh) and each repeated word.
- Within 0.02 of the top score, the later attempt wins. Creators usually get it right on the last try.
- In and out points keep 0.08 s before the first word and 0.15 s after the last word, and never cut into the neighbouring word.

## Rules

- Whisper word times are close but not exact. Never trim inside a word. A clipped word ending is a revision.
- Never judge delivery, energy or emotion. That stays with the editor.
- Never change the script to match the take. The strategist decides; captions follow what is said.
