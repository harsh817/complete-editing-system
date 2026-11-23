---
name: talking-avatar
description: "Plan and produce approved talking-avatar clips and hook reads from a supplied script and reference."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Talking Avatar

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md. Run from the ad folder.
Run from the ad folder `ads/<AD>/`. `<AD>` is also the name in every file. Work files go to `renders/_work/avatar/`, paid output to `renders/gen/avatar/` (never overwritten).

## Steps

1. **Split the script.** Read `brief/script.txt` (H lines = hooks, every other line = body, CTA included).
   Show the split as a numbered list: H1, H2, ..., then the body. Words verbatim.
   Estimate seconds per part at about 2.5 words per second and mark it as an estimate. Wait for the OK.

2. **Avatar still** (`renders/gen/avatar/still.png`).
   - The user has a photo they have the rights to use: copy it there. Skip to step 3.
   - Else write one prompt from the brief's speaker description (or propose one, marked [proposed]): 9:16, head and shoulders, face to camera, eyes open, mouth closed and relaxed, a real room that fits the speaker, phone-camera look, soft light on the face, plain clothes with no logos or text.
   - Job file `renders/_work/avatar/still_jobs.json`:
     ```json
     {"skill": "talking-avatar", "step": "avatar",
      "jobs": [{"id": "AV1", "model": "nano-banana-pro", "out": "renders/gen/avatar/still.png",
                "input": {"prompt": "<prompt>", "aspect_ratio": "9:16", "resolution": "2K", "output_format": "png"}}]}
     ```
   - `python3 <skill-dir>/scripts/kie.py quote renders/_work/avatar/still_jobs.json`. **Stop. Wait for "OK".** Then run it with the tag:
     ```bash
     # cost: ad=<AD> step=avatar model=nano-banana-pro units=1 unit=image usd=<from quote> ok=yes
     python3 <skill-dir>/scripts/kie.py run renders/_work/avatar/still_jobs.json --approved
     ```
   - Show the still. It is the first frame of every clip: get it right before any audio is paid for.

3. **Voiceover.** Write `brief/vo.json` for the voiceover skill (hooks and body from step 1) and run it with `--parts`, so it makes each hook alone and the body alone: `audio/vo/<AD>_H1_HOOKONLY_VO_v1.wav`, `audio/vo/<AD>_BODY_VO_v1.wav`. The voiceover skill has its own quote and OK.

4. **Split the body** at pauses so each chunk stays under the model's limit:
   `python3 <skill-dir>/scripts/avatar.py split audio/vo/<AD>_BODY_VO_v1.wav --max 15`
   `--max` is the longest chunk in seconds. Check the avatar model's page for its maximum audio length and lower it if needed. Each audio file must stay under 10 MB.

5. **Lip-sync jobs.**
   `python3 <skill-dir>/scripts/avatar.py jobs --still renders/gen/avatar/still.png --name <AD>`
   writes `renders/_work/avatar/avatar_jobs.json` (one job per hook and per body chunk).
   `python3 <skill-dir>/scripts/kie.py quote renders/_work/avatar/avatar_jobs.json`
   Show the table. **Stop. Wait for "OK".** Missing price: ask the user to fill `prices.json`. Never fill it yourself.

6. **Run** (after OK), with the tag from the quote set to `ok=yes`:
   ```bash
   # cost: ad=<AD> step=avatar model=infinitalk/from-audio units=<seconds> unit=second usd=<from quote> ok=yes
   python3 <skill-dir>/scripts/kie.py run renders/_work/avatar/avatar_jobs.json --only H1 --approved
   ```
   "Still running" means run it again; nothing is submitted twice.
   Test on one hook first (above), show it, wait for the OK, then quote and run the rest.

7. **Assemble.** `python3 <skill-dir>/scripts/avatar.py finish --name <AD> --ratio 9:16` (repeat with `4:5` if needed).
   Each output is one hook plus the full body, with the clean voiceover chunks as the only audio:
   `renders/<AD>_H1_9x16_v1_avatar.mp4`. Never to `exports/`.

8. **Hand over** in the reporting guidance from AGENTS.md: every render with its length, the checks below, and COST (this step, running total, cap).

## The avatar model

Default: `infinitalk/from-audio` on kie.ai. Input: `image_url` (the still), `audio_url` (the voice chunk), `prompt`, `resolution` (`480p` or `720p`). The field list comes from kie's model docs as published in early 2026: if a job is rejected, open the model's page in the kie.ai docs and fix the field in `avatar.py` (one line in `jobs`). To try another audio-driven avatar model, pass `--model <id>` to `avatar.py jobs` and add its price to `prices.json`.

Prompt (default in `avatar.py`, change with `--prompt`): natural talking to camera, small head movements and blinks, subtle hand gestures, mouth matches the speech, static phone framing, background unchanged. Add the delivery from the brief in a few words (calm, excited, matter-of-fact).

## Rules

- No paid call without a quote and the user's "OK" for that step.
- One still for every clip. A new still means new clips, and a new quote.
- Only a face you have the rights to use. Never a real public person.
- The voiceover is the master audio. The finish step throws away the audio the avatar model returns and puts the clean voiceover back.
