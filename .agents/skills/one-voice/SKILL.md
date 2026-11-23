---
name: one-voice
description: "Quote and apply a consistent approved voice across character clips or create an authorized voice clone."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# One Voice

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`.
Use gated-generation and tools/paid_run.py for quoted, approved execution.

## Rules

1. One character = one settings file: `audio/vo/voice.json`. Every clip of that character goes through it. Never change a
   value in it to fix one clip: that is how the voice starts to drift. If a value must change, it changes for every clip
   and every clip is converted again (with a new quote).
2. One conversion over all clips back to back. More context in one request = fewer mangled words. Split back per clip
   by sample count, never by ear.
3. Other speakers (an off-camera interviewer, a second actor) are masked: muted in the input, restored from the original.
   Write their seconds in `mask` before the conversion, from the transcript.
4. The words must survive. Re-transcribe every converted file and diff it against the original. The user's ear decides on
   every flagged clip.
5. Paid outputs are never overwritten. The script keeps the old file as `alt_<name>_v1`, `alt_<name>_v2` and so on.
6. Keys only as environment variables. Check with `[ -n "$ELEVENLABS_API_KEY" ] && echo set || echo missing`.

## Steps

1. **Inventory.** List the clips of this character (`renders/gen/`, `footage/` copies in `renders/_work/`, or the voiceover
   files). ffprobe each one: duration, audio yes or no. Ask which clips are in scope if it is not obvious.
2. **Settings file.** `python3 <skill-dir>/scripts/voice.py init --character <NAME>` writes `audio/vo/voice.json`.
   - Voice: `python3 <skill-dir>/scripts/voice.py voices` lists the voices on the account. A cloned voice of the target
     held the words best in our runs. To clone: 1 to 3 clean samples of the target voice that the user has the rights
     to use, then `voice.py clone --name <NAME> <files>` (paid step, see step 4 for the gate). The voice id goes into
     `voice.json`.
   - Start values in `voice.json` are a starting point, not a recommendation. Lock them after the test in step 5.
3. **Masks.** If another person speaks in a clip, find their seconds from the transcript (and pitch, when two voices
   overlap) and write them in `mask`: `{"clip_stem": [[start, end], ...]}`.
4. **Quote.** `python3 <skill-dir>/scripts/voice.py convert <files>` with no `--approved` prints the seconds, the price
   from `prices.json`, the spend so far, the cap and the cost tag line with `ok=no`. Show it. **Stop. Wait for OK.**
   Missing price: ask the user to check the provider's current price and fill `prices.json`. Never fill it yourself.
5. **Test on the worst clip first** (fastest speech, most brand names). After OK, run it with the tag:
   ```bash
   # cost: ad=<AD> step=vo provider=elevenlabs model=eleven_multilingual_sts_v2 units=<seconds> unit=second usd=<est> ok=yes
   cd ads/<AD> && python3 <skill-dir>/scripts/voice.py convert <worst clip> --approved
   ```
   Then `voice.py check <original> renders/gen/voice/<stem>_<NAME>.mp4`. Show the lag and every word difference.
   The user listens. Change settings only now, before the batch, then lock them.
6. **Batch.** New quote for all clips, OK, same tagged command with every file. Same settings file, one pass.
7. **Check every file.** `voice.py check` on each pair. `voice.py audit` must say 0 outputs with other settings.
8. **Report** (shape below). Hand the files to the edit: they replace the original audio in the timeline.

## When the words still come out wrong

- Fast speech and brand names are where speech-to-speech re-hears words. Try, in this order, with a quote each time:
  a cloned voice of the target, noise removal on, one longer pass with more clips around the bad one.
- Last resort: text-to-speech with the same voice (Skill 8), each line fitted to the original line's length. The words are
  then exact and the lip sync is only phrase-level. Say so to the user.
- Denoised speech can sound dry next to roomy off-camera lines. A touch of reverb in the edit fixes it, if the user hears it.

## Output format

```
ONE VOICE: <character>, settings <hash> (audio/vo/voice.json)
| clip | seconds | lag ms | word differences | file |
|------|---------|--------|------------------|------|
Flagged words: <clip>: '<original>' -> '<converted>' ...
Spend: <usd_est this run> | spent on this ad <total> of <cap>
NEXT: <listen to the flagged clips | relink the files in the edit>
```
