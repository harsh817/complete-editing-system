---
name: animated-ad
description: "Plan an animated ad scene table, references and prompts, then generate approved still and clip batches."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Animated Ad

## Story-engine integration

For new narrative/AI-led work, run visual-story-engine S0-S5 before full shot prompts. Its approved
story, motif, character/world bible and shot table feed this skill; do not repeat already-resolved
questions. The story-engine stage order supersedes the abbreviated creative discovery below when
that workflow applies. S4 character/world reference prompts may precede shot prompts. Its 2-4-frame
review batches replace the larger initial frame batch below; keep all paid quote and test gates.
Treat five seconds as a source default, not a compulsory shot length. Record source duration, trim,
edited duration and audio mapping separately. Current measured VO and user decisions override preset
60-second grids. Preserve existing approved project work and use this skill for S6/S7 mechanics.

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`.
Use gated-generation and tools/paid_run.py for quoted, approved execution.
Song ads: time the song first with Skill 13 (song-timing); its grid gives the scene count and the durations.

## Deliverables, always in this order

1. **The prompt sheet** (steps 1 to 5): `renders/_work/animated/<AD>_animated-ad-prompts.md` for people and
   `renders/_work/animated/scenes.json` for the script. Made every time.
2. **Stills, then clips** (step 6): only after the user has seen the sheet and writes "generate". Masters first, then a
   small batch 1, then the rest. Clips only after every still is approved and after their own quote.
3. **Hand-off** to the rough cut (Skill 4 or Skill 13's grid) and to captions (Skill 14).

## Step 1: read and classify

1. Read the whole brief. Note the script, visual notes, audience, tone, product, recurring characters and locations.
2. A reference video gives rhythm and structure only. Take its cut times from ffmpeg scene detection, never from a model's
   shot list. Never translate it 1:1.
3. Hooks table: per hook, its script, its headline, any offer banner, and its audio (own song, shared song, body only).
4. A real, named person in the brief is drawn only as an archetype, never as a likeness. A claim that the product page
   contradicts goes to the strategist as a question; the copy stays as in the brief.
5. Never change the brief's copy, dialogue or direction. Ask when anything is unclear.

## Step 2: questions (GATE)

Ask, two at a time, and wait:
1. Audio: voiceover, characters speaking on camera, or music only with text.
2. Style: Pixar 3D (default) or claymation. Strings below.
3. Pacing: short (30 to 60 s, durations from the content) or song-driven (durations from Skill 13's grid).
4. Recurring characters, and whether reference images exist.
5. Product shown or not; real packshot photo available.
6. Generate after the sheet, or the sheet only. Default: sheet only. A yes here is not the go.

If the brief is open on treatment, offer 2 or 3 treatments in two lines each: structure, scene count, still count, clip
count and seconds, and the cost from `prices.json` (`gate.py quote`). The user picks one.

## Style strings (fixed per project, never paraphrased)

| Slot | Pixar 3D | Claymation |
|---|---|---|
| style_block | `3D Pixar-style animated.` | `Modern 3D claymation style. Tactile handmade clay texture visible on every surface. Aardman-inspired character craftsmanship combined with Pixar-quality 3D lighting and depth. Subtle fingerprint imperfections on the clay. Cinematic studio lighting.` |
| style_closing | `9:16 vertical format.` | `Visible clay fingerprint texture. 9:16 vertical format.` |
| animation_closing | `3D Pixar-style animated. Smooth natural motion. No morphing. No style change.` | `Stop-motion claymation animation aesthetic in the style of Aardman Animations. Movement has the subtle frame-by-frame stutter characteristic of handcrafted stop-motion clay animation. Tactile clay surface vibration consistent throughout. No morphing between objects. No style change.` |

`gen.py` adds them to every prompt, so they stay byte-identical. Clay notes: avoid extreme lip close-ups (most clay ads
are voiceover), prefer medium shots for hands on objects, tell the editor to turn frame blending off.

## Step 3: scene breakdown (GATE)

Per scene: what is seen, what is heard (VO line, exact dialogue, or nothing; song ads: the sung line and its time),
duration, frame type (start only, or start + end), camera (angle, shot size, lens), cast on screen, location, product
visible yes or no. Lines you had to propose are marked `[proposed]`.

- Durations: dialogue about 2.5 to 3 words per second plus 0.5 s; B-roll and product 3 to 5 s. A line that fits in one
  clip is one clip. Song ads: the gap between two grid times.
- Start frame = the clean state before the action. End frame = the state after it. Never an action half done.
- Camera: change angle or shot size from one scene to the next. Low angles for talking products and hero shots.
- Cause and effect check on every silent scene: from the frame alone, can a viewer tell what happens and how the product
  is used? If not, restage it now.
- Song ads: shots over about 4 s, or three of the same kind in a row, get an insert planned now. The last 3 to 5 s is an
  end card scene (product, offer, CTA).

Then the **cast and anchors** list:
- one master per recurring character: name plus a one-line appearance (the cast clause) repeated verbatim in every
  prompt where they appear. A provided image is the master; nothing is generated for it.
- one voice clause per speaking character, repeated verbatim in every clip where they speak.
- one location anchor per location that appears in 2 or more scenes.
- the packshot, if the product is shown. It is the only authority for the product. Never generate a product master.

Show the table and the list. Wait for the OK.

## Step 4: image prompts

Order inside each prompt (gen.py adds the first and the last part): style_block, camera, subject with the cast clause
verbatim, static pose, environment, lighting, composition, reference sentences, style_closing. English, 80 to 150 words.
Attach the masters of the cast on screen only (an off-screen master walks into the frame), the location anchor, and the
packshot last. Never describe the pack from memory when a photo exists. Never add elements the brief does not have:
propose them.

## Step 5: animation prompts, then the sheet

Per clip: subject motion (subtle or moderate), the exact spoken line if any (`speaks to camera with natural lip sync,
saying: "<line from the script>"`, plus the voice clause), one camera move (static, slight push-in, slow pan, arc),
atmosphere in motion. 30 to 80 words, one main action, physical verbs ("bends, slides, rises"), static camera when in
doubt. Dialogue keeps the brief's language; everything else is English.

Write the sheet (markdown, for people) and `scenes.json` (for the script) from the same lists. Then
`python3 <skill-dir>/scripts/gen.py check`. Fix every ERROR before the sheet goes to the user.

## Step 6: generate (opt-in, GATE before every paid step)

Only after the user wrote "generate" having seen the sheet.
1. **Quote first.** `gen.py stills masters` prints the quote with the cost tag (`ok=no`). Add the repair budget
   (REPAIR_BUDGET_PCT in AGENTS.md) to the total you show. Wait for OK.
2. **Masters and anchors**, 2 variants each, then `gen.py contact`. The user picks (`gen.py pick M1 2`), asks for a
   small change (`gen.py repair M1 "<note>"`, quoted), or rejects. Approved masters are frozen: changing one later means
   regenerating every still that used it.
3. **Batch 1: 4 to 6 stills** with the most recurring cast and different framings. Contact sheet. The look, the camera and
   the style get approved here, before the rest. Ask "all of them, or only some?" before batch 2.
4. **Repairs**: `gen.py repair <id> "<note>" ...` keeps the original prompt and adds `Revision request: <note>`. If a
   character leaked in, remove its master from that still's refs first.
5. **The rest** in batches of up to 12, a quote and a contact sheet each.
6. **Clips**, only when every still is approved: re-read every animation prompt against the final stills (stills change
   between rounds), show the prompt table, wait for OK, then `gen.py clips all` for the quote, OK, run. `gen.py qa` makes
   a 4-frame grid per clip. A bad clip is redone alone, with its own quote, never re-rolled on your own.

Every paid run carries the cost tag from the quote, with `ok=yes` only after the user's OK:

```bash
# cost: ad=<AD> step=stills provider=kie model=nano-banana-pro units=<n> unit=image usd=<est> ok=yes
cd ads/<AD> && python3 <skill-dir>/scripts/gen.py stills M1 A1 --approved
```

A failed job is not billed by kie. Content-filter false positives happen: rephrase and resubmit as a repair once, then
show the user the error.

## Models

- Stills: `nano-banana-pro` (up to 8 references, 1K default; 2K only on request). For photoreal UGC b-roll, only when the
  brief or the user asks for it: `gpt-image-2` (set `image_model` in scenes.json).
- Clips: `kling-3.0/video` (3 to 15 s, start or start + end frame, `sound` on only for rows with a spoken line), or
  `google/gemini-omni-flash-1-1` when characters must speak a language Kling does not speak (3 to 10 s rows, rendered at
  4, 6, 8 or 10 s and cut to the row; it always renders audio, so every prompt ends with an `Audio:` line). Model ids are
  the ones kie.ai used when this was written: check the provider's model list.

## Output format

```
ANIMATED AD: <AD>, <style>, <treatment>
Sheet: renders/_work/animated/<AD>_animated-ad-prompts.md | scenes.json check: <errors> errors, <warnings> warnings
| still | refs | status | file |
| clip | dur | frames | status | file |
Contact sheet: renders/_work/animated/contact.png | clip QA: renders/_work/animated/qa_clips.png
Spend: <usd_est this run> | spent on this ad <total> of <cap>
NEXT: <the gate that is open>
```
