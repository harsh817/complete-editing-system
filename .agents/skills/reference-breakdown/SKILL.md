---
name: reference-breakdown
description: "Measure cuts and transcribe a reference ad, then describe its timed shots for an edit plan."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Reference Breakdown

Copy the measured rhythm and structure of the reference. Never copy a frame or a line 1:1.

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run everything from the ad folder `ads/<AD>/`. If the venv `~/.venvs/editing` exists, use `C:/Users/pc/.venvs/editing/Scripts/python.exe` instead of `python3`.
All output goes to `renders/_work/ref1/`. `refs/` holds inputs only.

## Steps

1. **Get the file.**
   - Local file: copy it to `refs/ref1.mp4` (ref2, ref3 for more).
   - URL: `yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" --merge-output-format mp4 -o "refs/ref1.%(ext)s" "<URL>"`
     If the download fails (login wall, ad library page), ask the user to screen-record or download it, and stop.

2. **Cuts, frames, contact sheet.**
   `python3 <skill-dir>/scripts/shots.py refs/ref1.mp4`
   Writes `renders/_work/ref1/shots.json`, `renders/_work/ref1/frames/shot_NN.jpg` and `renders/_work/ref1/contact.jpg`.
   Report duration, size, fps, shot count, average shot length, longest shot.

3. **Check the cuts.** Open `renders/_work/ref1/contact.jpg` and look at it.
   - Two neighbouring thumbnails that look like the same shot: a false cut. Merge them in your table.
   - A shot over 3 s that obviously changes framing (punch-in, new angle): a missed cut. Rerun with `--threshold 0.10` and compare.
   - State which threshold you kept.

4. **Transcribe.**
   `python3 <skill-dir>/scripts/transcribe.py refs/ref1.mp4 --out-dir renders/_work/ref1`
   Writes `renders/_work/ref1/ref1.words.json`. If the ad has no speech, Whisper may return a few junk words: check them against the frames and say "no speech" when that is the case.

5. **Read every frame.** Open each `renders/_work/ref1/frames/shot_NN.jpg`. For each shot write: what is seen, shot size (close-up, medium, wide), type (talking head, punch-in, B-roll, product, screen recording, text card, split screen), and the on-screen text word for word.

6. **Time the on-screen text.** For every text box that appears or changes, find its first and last frame:
   `python3 <skill-dir>/scripts/shots.py frames refs/ref1.mp4 --start <s> --end <s> --step 0.1`
   Open the dense sheet and read where the text appears and leaves. Never guess a text duration.

7. **Map words to shots.** Put each Whisper word into the shot whose start/end contains the word's start time.

8. **Label the purpose** of every shot: HOOK, PROBLEM, AGITATE, PRODUCT INTRO, DEMO, PROOF, OFFER, CTA, or TRANSITION.

9. Write `renders/_work/ref1/breakdown.md` in the output format. If `brief/edit-plan.md` exists, add the shot table to it under a heading `Reference`. Report in the reporting guidance from AGENTS.md.

## Output format (renders/_work/ref1/breakdown.md)

```
# Reference breakdown: ref1
Source: <file or URL> · <W>x<H> · <fps> fps · <duration> s · cut threshold <t>

| # | In | Out | Dur | Shot (what is seen, size, type) | On-screen text (verbatim, in-out s) | Audio (verbatim speech / music / SFX) | Purpose |
|---|---|---|---|---|---|---|---|

## Structure
Hook: <in-out s> · Body: <in-out s> · CTA: <in-out s>

## Rhythm
Shots: <n> · average <s> · longest #<n> <s> · shortest #<n> <s>
Cuts per 5 s in the hook vs the body: <from the table>

## Style
Captions: <box or stroke, colour, position, words per caption, animation or none>
Headline: <position, size relative to frame, how long it stays>
Music: <present or not, where it changes or drops>
Transitions: <hard cuts, whip, zoom, none>

## Use in our edit
Copy: <3 things: rhythm, transitions, structure>
Change: <1 thing our brief should do differently>
```

## Rules

- Every time in the table comes from `shots.json`, the Whisper words or a dense frame sheet. If you could not measure it, write `[NEEDS: check by eye]`.
- Speech is verbatim from Whisper, corrected only where the frame text proves the right spelling.
- Label anything you infer (for example the purpose of a shot) as your reading, never as fact.
- The breakdown feeds rhythm and structure. Never translate the reference 1:1 into our script.
