---
name: voiceover
description: "Quote and produce approved ad voiceover reads, with local normalization and transcript checks."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Voiceover

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md. Run from the ad folder.

## Steps

1. **Parse.** Read `brief/script.txt` (or the brief). Hooks = H lines. Body = every other line in order, CTA included.
   Copy every word verbatim. Show the parts as a numbered list. Wait for the OK.

2. **Prepare for speech** (in `brief/vo.json`, never in the brief):
   - Numbers, prices, units and dates the way they are said: "$29" becomes "twenty-nine dollars", "2x" becomes "twice" or "two times" (ask which).
   - Pronunciations: every brand, product or foreign word goes in `pronunciations` as written to spelled-as-said. The script swaps them before it sends the text.
   - Delivery: ask for the ad format if the brief does not say. Write the delivery in one line (pace, energy) so the user can change it.
   - Delivery tags in square brackets (for example `[laughs]`, `[whispers]`) only where the brief asks, and only with a model that supports them (check the model's docs). Never tag every line.

3. **Write `brief/vo.json`:**
   ```json
   {"name": "<AD>",
    "voice_id": "",
    "model_id": "eleven_v3",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": true},
    "language_code": null,
    "pronunciations": {},
    "hooks": {"H1": "...", "H2": "..."},
    "body": "...",
    "usd_per_1k_chars": null}
   ```
   `model_id`: check the current model ids in the ElevenLabs docs. Use one model and one voice for every file of one ad.

4. **Quote:** `python3 <skill-dir>/scripts/vo.py quote brief/vo.json` (add `--parts` when the talking-avatar skill or the editor needs the hooks and body alone).
   Show the table, the running total for this ad against the cap, and the cost tag. **Stop. Wait for "OK".**

5. **Make** (after OK), with the tag from the quote set to `ok=yes` and the same `--parts` flag as the quote:
   ```bash
   # cost: ad=<AD> step=vo model=eleven_v3 units=<chars> unit=char usd=<from quote> ok=yes
   python3 <skill-dir>/scripts/vo.py make brief/vo.json --approved
   ```

6. **Check every file.** Transcribe the full reads with the transcribe script from the script-vs-take skill (`--out-dir renders/_work/vo`) and compare against the text. List any word that came out wrong.

7. **Hand over** in the reporting guidance from AGENTS.md. For each file: name, text, pronunciations applied, tags used, the measured loudness and true peak after normalization (the script prints them; report the measured values, never the target).

## Naming

```
audio/vo/ACME_2610-S3_H1_VO_v1.wav            full read: hook 1 + body
audio/vo/ACME_2610-S3_H2_VO_v1.wav            full read: hook 2 + body
audio/vo/ACME_2610-S3_H1_HOOKONLY_VO_v1.wav   --parts only
audio/vo/ACME_2610-S3_BODY_VO_v1.wav          --parts only
audio/vo/_raw/                                the paid mp3s, reused on reruns
```
48 kHz, 24-bit WAV, -14 LUFS integrated, -1 dBTP true peak (LOUDNESS_TARGET_LUFS and TRUE_PEAK_DBTP in AGENTS.md; change `TARGET_I` and `TARGET_TP` at the top of `vo.py` if yours differ). A new run never overwrites: it writes `_v2`.

## Loudness by hand

Any file: `python3 <skill-dir>/scripts/vo.py norm audio/vo/file.wav` writes `audio/vo/file_norm.wav`.
The same two passes in plain ffmpeg:
```
ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null -
ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1:LRA=11:measured_I=<input_i>:measured_TP=<input_tp>:measured_LRA=<input_lra>:measured_thresh=<input_thresh>:offset=<target_offset>:linear=true -ar 48000 -c:a pcm_s24le out.wav
```
Normalize the voice alone. Mix music under it in the editor, then check the final mix again.

## Rules

- Never change the brief's words. A line that reads badly aloud is flagged for the strategist.
- No paid call without the quote and the user's "OK".
- Same voice, model and settings for every file of one ad.
- If a full read sounds like two takes at the hook/body join, make it again in one request. Never stitch a hook file onto a body file for a final.
