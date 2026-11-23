---
name: rough-cut
description: "Build an H1 rough cut from approved takes and timing, with local video renders and edit decision files."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Rough Cut

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run from the ad folder `ads/<AD>/`.

## Steps

1. **Check the input.** `renders/_work/takes.json` must exist. If not, run the script-vs-take skill first and stop.
   Read `renders/_work/takes.md`. List the lines with status MISSING: they are left out of the cut. Say so.

2. **Pick the hooks and ratio.** Hooks are the H lines in the take map. Ratio from `brief/edit-plan.md`, else ask (9:16 or 4:5).
   The name is the ad folder name `<AD>` (for example `ACME_2610-S3`).

3. **Plan first, render second.**
   `python3 <skill-dir>/scripts/rough_cut.py renders/_work/takes.json --hook H1 --ratio 9:16 --name <AD> --plan-only`
   Show the cut list. Look for: a line split into many tiny pieces (the silence threshold is too high for this room, rerun with `--noise -30`), or a line with no cut where you expected a pause.

4. **Render H1 first** as the demo the house rules ask for. Wait for the OK, then the other hooks.
   ```
   python3 <skill-dir>/scripts/rough_cut.py renders/_work/takes.json --hook H1 --ratio 9:16 --name <AD>
   python3 <skill-dir>/scripts/rough_cut.py renders/_work/takes.json --hook H2 --ratio 9:16 --name <AD>
   ```
   Add `--cut-fillers` only if the user asked to remove "um" and "uh".
   Without `--name` the file is `renders/rough_v1.mp4`.

5. **Report** in the reporting guidance from AGENTS.md. For each render: path, total seconds against the target length in the edit plan, number of cuts, lines left out. Then the import steps below. Never render to `exports/`.

## Settings

| Flag | Default | Change it when |
|---|---|---|
| `--max-pause` | 0.35 | pauses feel rushed (raise to 0.5) or the read drags (lower to 0.25) |
| `--keep` | 0.06 | cuts sound clipped at the breath (raise to 0.1) |
| `--noise` | -35 | noisy room or music bed: raise to -30; quiet booth: -40 |
| `--fps` | 30 | the delivery spec asks for 25 or 24 |

## Import into the editor

- **Premiere Pro:** File > Import > the `.edl`. The clips come in offline: relink each one to the file named in `* FROM CLIP NAME`.
- **DaVinci Resolve:** import the source clips into the media pool first, then File > Import > Timeline > the `.edl`.
- **Avid:** import the EDL through the EDL tool and relink by clip name.
- The `.csv` has the same cuts in seconds, for any tool or for a quick check.

Source timecode comes from the file's own timecode track when it has one, else it starts at 00:00:00:00 (normal for phone footage). Record timecode starts at 01:00:00:00.

## Rules

- The render is a rough cut: no captions, no music, no B-roll, no color. Those come later.
- Never cut inside a word. If a cut clips a word, raise `--keep` or fix the in/out of that line in `renders/_work/takes.json` (`best.in`, `best.out`) and render again.
- Never overwrite a render. The script writes `_v2`, `_v3` and so on.
