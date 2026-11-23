---
name: reframe-exports
description: "Render approved hooks in 9:16 and 4:5, normalize audio, version exports and measure deliverables."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Reframe and Exports

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`. Free and local. `$ad-final` runs this skill.

## Order of work

1. `reframe.py render` -> one clean file per hook and ratio: `renders/<AD>_H1_9x16_v1_clean.mp4`, `..._4x5_v1_clean.mp4`.
   Stitched (hook + body + end card), reframed, constant frame rate, loudness-normalized.
2. Skill 14 burns the text into each clean file with its own ratio layout -> `renders/<AD>_H1_9x16_v1.mp4`.
   An ad with no burned text: `render --final` writes the final names directly.
3. `reframe.py export` -> copies the finals into `exports/9x16/` and `exports/4x5/` and prints the measurement table.
4. `$ad-qa` (Skill 16). Nothing in `exports/` is delivered before `$ad-qa` passes.

## Names

`BRAND_CONCEPT_HOOK_RATIO_v#.mp4`, for example `ACME_2610-S3_H1_9x16_v1.mp4`. The ad folder name is `BRAND_CONCEPT`.
Ratio tokens are `9x16` and `4x5` only. v1 is the first export; any change after review is the next number, never a
reused one. Work files keep a suffix after the version (`_clean`, `_rough`, `_review`) and never go to `exports/`.
`export` checks every name with this regex and refuses the ones that fail:
`^[A-Z]{3,4}_\d{4}-S\d+(-[A-Za-z0-9]+)?_(H\d+|BODY)_(9x16|4x5)_v\d+\.mp4$`

## Steps

1. **Plan.** `python3 <skill-dir>/scripts/reframe.py plan` writes `renders/_work/plan.json`. Fill:
   - `hooks`: `{"H1": "renders/_work/hook1.mp4", ...}` in the order of the brief's hooks table; `body`; `endcard` or null.
   - `ratios`: `["9x16", "4x5"]` unless the brief says otherwise.
   - `mode`: `crop` (fill the frame, default for vertical or near-vertical footage), `pad` (fit with black bars),
     `blur` (fit over a blurred copy, for landscape footage that must stay whole).
   - `x`: crop centre from 0 (left) to 1 (right). `face: true` finds the face centre per input with OpenCV
     (`pip install opencv-python`), and falls back to `x` when no face is found.
   - `fps`: the source frame rate (24, 25 or 30). Never mix rates inside one ad: every input is resampled to this one.
   - `lufs` and `tp` default to LOUDNESS_TARGET_LUFS and TRUE_PEAK_DBTP in AGENTS.md. -14 LUFS integrated is a common
     reference for social platforms, not a Meta requirement: set your team's target there.
2. **Probe first.** `reframe.py probe <every input>`: size, fps, duration, audio. An input with no audio gets silence of
   the same length, so the stitch never shifts.
3. **Face check** (crop mode with people in frame): `reframe.py faces <input>` prints the centre it will use. If the
   speaker sits off-centre in some shots and the faces differ per input, split the input or set `x` per render.
4. **Render.** `reframe.py render`. One run renders every hook x ratio. Existing files are skipped; `--bump` writes the
   next version instead; `--only H2` limits it to some hooks. Each line reports size, fps, duration, loudness before and
   after, and true peak.
5. **Text.** Skill 14 on every clean file (headline, captions, banner, end card), each ratio with its own layout.
6. **Export.** `reframe.py export` copies every final-named file from `renders/` into `exports/<ratio>/`. A file that
   already exists there is never overwritten: render the next version. The table shows name, size, fps, seconds, LUFS,
   true peak and MB.

## Encoding (what the script writes)

H.264 (libx264, CRF 18), yuv420p, square pixels, constant frame rate, AAC 48 kHz stereo at 192 kbps, `+faststart`.
Loudness: pass 1 measures with `loudnorm print_format=json`, pass 2 applies it with the measured values and
`linear=true`, then a third measure confirms the result. Report the measured numbers, never the target as if it were
the result.

## Rules

- The 4x5 file is its own render from the same inputs, never a crop of the finished 9x16 file.
- The body is frame-identical in every hook: one body file, stitched after each hook.
- Never overwrite a file in `exports/`. Never write into `footage/`: inputs are read from there or from `renders/_work/`.

## Output format

```
EXPORTS: <AD> v<#>
| file | ok | size | fps | s | LUFS | dBTP | MB |
Names failing the pattern: <none | list>
Body length equal across hooks: <yes | the difference in frames>
NEXT: $ad-qa <AD>
```
