---
name: broll-from-brief
description: "Plan missing ad B-roll and generate approved starting frames and clips through the paid-run wrapper."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# B-roll from the Brief

Image first, then video. Never generate video from text alone: approve a starting frame, then animate it.
B-roll only: no talking, no dialogue. For a person speaking, use the talking-avatar skill.

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run from the ad folder `ads/<AD>/`. Job files and the prompt sheet go in `renders/_work/broll/`. Paid output goes in `renders/gen/broll/` and is never overwritten.

## Steps

1. **Shot list.** Read the B-roll list in `brief/edit-plan.md`. Take the shots marked "generate", each with the script line it covers.
   Mid-edit idea: one shot, from the user's words or a reference image.

2. **Prompt sheet.** Write `renders/_work/broll/prompts.md`:
   | ID | Script line | Shot | Image prompt | Motion prompt | Seconds | Product in frame |
   - Image prompt, English, in this order: subject and action, setting with 3 concrete details, camera (phone camera, handheld, eye level, shot size), light (window light, overhead kitchen light), what text must read exactly.
   - Look: real phone footage. Real rooms, natural light, slight grain, no studio gloss, no text unless the brief asks.
   - The person (hands, age, skin tone, nails, clothes) matches the creator in the a-roll. Say it in the prompt.
   - Motion prompt: one physical action (pours, opens, slides, presses), plus "handheld phone footage, subtle natural camera shake, realistic motion, labels and text stay unchanged". No metaphors.
   - Product in frame: attach `refs/packshot.png` as the LAST reference and add: "The final supplied image is the real product photograph and the only authority for the product: reproduce its packaging, label layout, lettering and colors exactly."
   Show the sheet. Wait for the user's OK on the prompts.

3. **Stills jobs.** Write `renders/_work/broll/stills_jobs.json` (template below), one job per shot, the brief's ratio, resolution 1K.
   `python3 <skill-dir>/scripts/kie.py quote renders/_work/broll/stills_jobs.json`
   Show the quote table, the total, the running total for this ad from `ledger.csv` against the cap, and the cost tag line.
   **Stop. Wait for the user to type OK.**
   MISSING PRICES: ask the user to fill `prices.json` from the provider's pricing page. Never fill a price yourself.

4. **Test 1 or 2 stills first** (after OK). The command carries the tag from the quote, with `ok=yes`:
   ```bash
   # cost: ad=<AD> step=broll model=nano-banana-pro units=2 unit=image usd=<from quote> ok=yes
   python3 <skill-dir>/scripts/kie.py run renders/_work/broll/stills_jobs.json --only S01,S02 --approved
   ```
   Show them. Wait for the OK. Then quote and run the rest the same way.
   "Still running" means run the same command again. Nothing is submitted twice.
   Open every still and rate it: usable, fix (one line what is wrong), or drop.

5. **Repairs.** Never re-roll on your own. Show the defect, then add a job with a new id (`S03-r1`, out `renders/gen/broll/stills/S03-r1.png`), the prompt unchanged plus one line:
   `Revision request: <what is wrong, e.g. the label text is blurred, make it sharp and readable>`.
   Quote it, wait for OK, run with `--only S03-r1`. To make the same job again, use `--redo S03` (the old file becomes `alt_S03_v1.png`).

6. **Clips jobs.** Only for stills the user approved. Write `renders/_work/broll/clips_jobs.json`: image-to-video, starting frame = the approved still, 5 s unless the shot needs more, sound off.
   Quote, **stop, wait for OK**, test one clip, OK, then the rest. Each run carries its tag with `step=clips`.

7. **Hand over** in the reporting guidance from AGENTS.md: shot ID, script line, still path, clip path, and COST (spent this step, running total, cap).

## Job templates

Stills (Nano Banana Pro, up to 8 references in `image_input`):
```json
{"skill": "broll-from-brief", "step": "broll",
 "jobs": [
  {"id": "S01", "model": "nano-banana-pro", "out": "renders/gen/broll/stills/S01.png",
   "input": {"prompt": "<image prompt>", "aspect_ratio": "9:16", "resolution": "1K", "output_format": "png"},
   "files": {"image_input": ["refs/packshot.png"]}}
 ]}
```
Stills where text on the product must be exact (GPT Image 2): `"model": "gpt-image-2-image-to-image"`, references go in `"files": {"input_urls": [...]}`. With no reference use `gpt-image-2-text-to-image` and no `files`.

Clips (Kling 3.0 image-to-video):
```json
{"skill": "broll-from-brief", "step": "clips",
 "jobs": [
  {"id": "V01", "model": "kling-3.0/video", "out": "renders/gen/broll/clips/V01.mp4",
   "input": {"prompt": "<image prompt> <motion prompt>", "duration": "5", "sound": false, "mode": "pro", "multi_shots": false},
   "files": {"image_urls": ["renders/gen/broll/stills/S01.png"]}}
 ]}
```
`duration` is a string. Kling on kie needs `multi_shots: false`. Model ids and fields change: if a job is rejected, check the model's page in the kie.ai docs and fix the field name.

## Rules

- No paid call without a quote and the user's "OK" for that run. `ok=yes` and `--approved` mean exactly that.
- One model per run, so one cost tag per run. The quote says when a batch mixes models.
- One quote per batch. A repair round is a new batch with a new quote.
- Never ask for the API key in the chat. If `KIE_API_KEY` is missing, say which key and point to the set-key tool.
- Never generate a fake product. The real product photo is the only authority.
- Failed jobs are not billed by kie. Rephrase and retry once (`--retry <id>`), then show the error.
