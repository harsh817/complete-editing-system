---
name: scene-edit
description: "Plan and quote a focused image edit while preserving the referenced product, person and scene."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Scene Edit

Change ONE thing. Every prompt says what changes and lists what stays the same.

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md. Run from the ad folder `ads/<AD>/`.
The original can sit anywhere (`renders/gen/`, `refs/`, a frame grab in `renders/_work/`). Edits go to `renders/gen/edits/`, named `<original>_edit-<mode>_v#.png`. The original is never touched; `footage/` is read only.

## Steps

1. **Look first.** Open the image. Describe it back in one line: subject, setting, light, framing, product.
   Ask the user to correct it before you write anything. Wrong description = wrong edit.

2. **Pick the mode** (below) and fill its template. Then add the KEEP block, and the fix lines that apply.

3. **Pick the model.**
   - `nano-banana-pro` for most edits (references in `image_input`).
   - `gpt-image-2-image-to-image` when label text or the product must be exact (references in `input_urls`).
   - Image order: the scene first, extra references after, the product photo LAST.

4. **Write the job** to `renders/_work/edits/edit_jobs.json`:
   ```json
   {"skill": "scene-edit", "step": "broll",
    "jobs": [
     {"id": "S03-light", "model": "nano-banana-pro", "out": "renders/gen/edits/S03_edit-light_v1.png",
      "input": {"prompt": "<filled template>", "aspect_ratio": "9:16", "resolution": "1K", "output_format": "png"},
      "files": {"image_input": ["renders/gen/broll/stills/S03.png"]}}
    ]}
   ```
   Keep `aspect_ratio` the same as the original.

5. **Quote:** `python3 <skill-dir>/scripts/kie.py quote renders/_work/edits/edit_jobs.json`
   Show the table, the running total for this ad against the cap, and the cost tag. **Stop. Wait for "OK".** Missing price: ask the user to fill `prices.json`. Never fill it yourself.

6. **Run** (after OK), with the tag from the quote set to `ok=yes`:
   ```bash
   # cost: ad=<AD> step=broll model=nano-banana-pro units=1 unit=image usd=<from quote> ok=yes
   python3 <skill-dir>/scripts/kie.py run renders/_work/edits/edit_jobs.json --approved
   ```

7. **Compare:** `bash <skill-dir>/scripts/side_by_side.sh renders/gen/broll/stills/S03.png renders/gen/edits/S03_edit-light_v1.png renders/_work/edits/S03_compare.jpg`
   Open the compare image. Run the 4-point check (output format). Anything that changed besides the one thing is a failure: show it, add it to KEEP and quote a new version (`_v2`). Never re-roll on your own.

## Mode templates

1. **Product swap** (image 1 = scene, image 2 = new product):
   `Replace the product in the first image with the product from the second image. The new product sits in the same place, at the same size relative to the hand, at the same angle. Match the scene's light and shadows on the new product. Completely replace the original product, no remnants.`
2. **Location:**
   `Move the subject to <new place> with <detail 1>, <detail 2>, <detail 3>. The subject, pose, clothes, product and camera framing are identical to the image.`
3. **Camera angle:**
   `Show the same scene from <eye level | low angle | high angle | over the shoulder | close-up | wide>. Same subject, same clothes, same product, same room, same light.`
4. **Position or pose:**
   `The subject now <moves to the left third of the frame | sits | holds the product at chest height | looks at the product>. The background, light and camera stay identical.`
5. **Light:**
   `Change the light to <soft window light from the left | warm golden hour from behind | overhead kitchen light | hard direct flash>. Subject, pose, product and background stay identical.`
6. **Before and after:**
   Edit the "before" into the "after", or generate both with the same person, angle, light and framing.
   `Same person, same framing, same light. Change only: <the visible result>. Keep the change realistic and modest.`
   Exaggerated results look fake and can break the platform's ad rules. The strategist approves every before/after.

## KEEP block (append to every prompt)

`Keep everything else exactly as in the original image: the person's face, hair, skin, clothes and hands, the background, every object, the camera framing and the colours. Photorealistic phone photo.`

## Fix lines (add only the ones that apply)

- Label blurry or wrong: `Sharp, readable label with exact text: "<TEXT>".`
- Product size wrong: `The product is <size>, about <comparison, e.g. fits in the palm>.`
- Hand grip wrong: `Hand naturally gripping the <shape>, fingers around the <part>.`
- Material wrong: `Glossy glass with visible reflections.` or `Matte plastic, soft texture.`
- Colour drift: `The product colour is exactly <colour>.`
- Product reference attached: `The final supplied image is the real product photograph and the only authority for the product: reproduce its packaging, label layout, lettering and colors exactly.`

## Output format

```
Original: <one-line description>
Mode: <mode> · Model: <model> · Job: <id>
Prompt: <full prompt>
Quote: <from kie.py>
--- after the run ---
Compare: <path to compare image>
1. Changed thing correct: yes/no
2. Everything else unchanged: yes/no (list what moved)
3. Label readable and correct: yes/no/n.a.
4. Light consistent on subject and product: yes/no
```

## Rules

- No paid call without a quote and the user's "OK". The run command carries the cost tag.
- Never overwrite the original or a paid edit. New version = new file name, `_v2`, `_v3`.
- Never edit a real person's face into someone else. Only edit footage you have the rights to.
