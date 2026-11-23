---
name: edit-qa
description: "Measure final ad files and inspect visual and script compliance, writing timestamped QA findings."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Edit QA

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`. Free and local. `$ad-qa` runs this review in the current chat.

## What this skill never does

- It never writes or touches `renders/qa/LAST_PASS`. Only the `$ad-qa` command does, after every blocking check passed.
- It never fixes a file. For each FAIL it names the fix and the command that makes it. A fixed file is a new version.

## Steps

1. **Rules.** `python3 <skill-dir>/scripts/qa.py init` once per ad writes `renders/qa/qa.json`. Set `wrong_names` (old
   brand names, competitor names, the previous product name), the duration range of this ad, and extra
   `banned_patterns` from the brief (a claim compliance flagged). Loudness target and true peak come from
   LOUDNESS_TARGET_LUFS and TRUE_PEAK_DBTP in AGENTS.md.
2. **Automatic checks.** `qa.py run` checks every file in `exports/9x16/` and `exports/4x5/` and writes
   `renders/qa/qa-<YYYYMMDD-HHMM>.md` plus one contact sheet per file (`renders/qa/<name>_sheet.png`, one frame per
   second, timestamp on each tile, the house text zone drawn in green).

   The name pattern: `^[A-Z]{3,4}_\d{4}-S\d+(-[A-Za-z0-9]+)?_(H\d+|BODY)_(9x16|4x5)_v\d+\.mp4$`

   | Check | Pass |
   |---|---|
   | name | matches the name pattern and sits in the exports folder of its own ratio |
   | specs | 1080x1920 for 9x16, 1080x1350 for 4x5; fps in the list; H.264, yuv420p; AAC audio present |
   | duration | inside the ad's range; audio and video lengths within 0.1 s |
   | loudness | integrated within 1 LU of the target; true peak at or under the maximum |
   | black | no black segment of 0.1 s or more |
   | frozen | no frozen segment of 0.5 s or more before the end card |
   | safe_zone | every caption, headline, banner and end card box inside the house zone (from the captions layout file) |
   | caption_text | no URL, domain, phone number, handle or wrong brand name in the caption text |

   WARN lines (silences of 1.5 s or more, text in Meta's Reels bottom 35 %) do not block. Report them.
3. **Visual check: read every contact sheet yourself.** Open each `renders/qa/<name>_sheet.png` and look, tile by tile, for:
   - a watermark or a logo from a stock site, an AI tool or another app;
   - a phone number, URL, @handle or email in the picture (on a screen, a sign, a pack);
   - a wrong brand or product name, an old pack, a competitor product;
   - text outside the green box, cut-off text, a caption over the speaking face or the product;
   - a black, blank or broken frame the detector missed, a clip from another hook.
   Write the result in the `visual` column: PASS, or FAIL with the second (from the tile timestamp) and what you saw.
   Text burned into the footage is not in the layout file: only this visual check finds it.
4. **Report.** One line per FAIL: file, check, measured number, the second to look at, the fix and its command
   (for example: `loudness -16.8 LUFS: reframe.py render --bump --only H2, then captions, then export`). Then the WARN
   lines, then the count of files that pass. The `$ad-qa` command decides on LAST_PASS from this report.

## Phrase cut (compliance)

When the brief or the strategist asks to remove a phrase (a time-bound claim, a word that cannot be said):
1. On the clean render, before captions: `phrase.py find renders/<name>_clean.mp4 "in one week"`. It needs the words file
   from Skill 14 (`captions.py words`).
2. With Whisper installed, every candidate join (frame-aligned, around the word boundaries) is re-transcribed and kept
   only if it reads "<word before> <word after>". A join with only 1 or 2 good candidates is FRAGILE: listen to it.
   Without Whisper the join is picked by energy and marked UNVERIFIED: a person listens to every one.
3. `phrase.py apply renders/<name>_clean.mp4` writes the next version (`..._v2_clean.mp4`). Audio and video drop the same
   frames, with 8 ms fades. The picture jumps at the cut: offer a punch-in to hide it (the editor's choice).
4. Run the words, captions and export again on the new version. Every caption after the cut moved.

## Output format

```
QA: <AD>, <n> files, report renders/qa/qa-<YYYYMMDD-HHMM>.md
| file | name | specs | duration | loudness | black | frozen | safe_zone | caption_text | visual | result |
FAIL <file> <check>: <measured> at <second>. Fix: <command>
WARN <file>: <note>
<p>/<n> files pass every blocking check.
NEXT: <the fixes | $ad-deliver <AD> once $ad-qa wrote LAST_PASS>
```
