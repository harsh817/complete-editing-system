# Editing house rules

## Rule 1: the brief is sacred

- Never change copy, dialogue, hooks, claims or creative direction. If something is unclear, ask.
- The brief's hooks table is the source of truth for hook lines and headlines. Keep its capitals,
  punctuation and emphasis exactly.
- Never invent claims, numbers, results, reviews or testimonials for the ad. A missing fact is
  [NEEDS: source]. A timing or number you did not measure is [NEEDS: check].
- Product and brand names are spelled exactly as on the product page. Auto-captions do not know them.
- When the creator says something different from the script, list it. Say if it reads as a slip or as a
  better line. The editor or strategist decides.

## Naming

BRAND_CONCEPT_HOOK_RATIO_v#.mp4

- BRAND: the brand code, 3 to 4 capitals (ACME).
- CONCEPT: year + month + script number, YYMM-S# (2610-S3). Add -Product only when the brand sells more
  than one product (2610-S3-NightCream).
- HOOK: H1, H2, H3 ... in the order of the brief's hooks table. BODY for a hookless body render.
- RATIO: 9x16 or 4x5. Nothing else.
- v#: v1 for the first export. Any change after review is v2, v3. Never reuse a number.

Examples: ACME_2610-S3_H1_9x16_v1.mp4, ACME_2610-S3_H2_4x5_v2.mp4
Work files in renders/ add a suffix after the version: ACME_2610-S3_H1_9x16_v1_rough.mp4, _clean (no text),
_review (side by side). Suffixed files never go to exports/.
The ad folder name is BRAND_CONCEPT (ACME_2610-S3).

## Ratios and canvas

- 9x16: 1080x1920. 4x5: 1080x1350.
- Edit the whole ad with H1 first. Duplicate it and swap in H2, H3: the body is identical in every hook.
- Every hook ships in both ratios unless the brief says otherwise.
- The 4x5 file is rendered in its own pass from the same timeline, with its own text layout. Never crop
  the finished 9x16 file, because the headline ends up near the top edge. A plain crop (y = 285 on
  1080x1920) is fine only for a _clean render with no text.
- Keep the source frame rate (24, 25 or 30) at constant frame rate. Never mix rates inside one ad.

## Safe zones

House layout (centre of each text block, as a share of the canvas height):

| Element  | 9x16 (1080x1920) | 4x5 (1080x1350) |
|----------|------------------|-----------------|
| Headline | 20 %             | 17 %            |
| End card | 24 %             | 19 %            |
| Captions | 74 %             | 78 %            |

- All text sits inside the centred 4x5 band of the 9x16 canvas: y 285 to 1635, x 65 to 1015.
- Meta's Reels guidance keeps the top 14 % (about 270 px) and the bottom 35 % (about 670 px) clear of key
  text, and 6 % (about 65 px) on each side. Our caption line at 74 % sits inside Meta's bottom zone.
  Before export, check the hook in the Ads Manager placement preview. If the Reels interface covers the
  captions in your placements, move the captions above y = 1250 for that ad and say so in the report.
- Never cover the hero of the shot: the face that speaks, or the product. Move that section's captions up.
- No room for headline + face + captions: shrink the captions first, keep the headline at 2 lines, then
  resize the footage.

## Captions

- Organic Reels/TikTok style. Style 1 (default): white text, black stroke. Style 2 (second choice): black
  text on white rounded boxes.
- CAPTION_FONT, 68 px on 1080 wide, shrinking to 60 px before a caption is split. Never larger, never
  smaller.
- Max 2 lines. Break by meaning, not by width ("if you struggle / with back pain"). Never break inside
  quotes, or after a one or two letter word. Never end a caption on a function word or a number.
- A caption starts with the new scene when it can: snap caption starts to cuts within 0.35 s.
- The text is what is said, from the word-timed transcript, fixed against the brief for names and numbers.
- No pop-in or bounce animation unless the brief or the reference ad has one.
- Emphasis: restyle a caption (position, size) to stress pain points, benefits and outcomes. Use it rarely.
- Captions stay on over B-roll. They hide while a chat bubble or a full-screen text card is up.

## Headlines, offer banner, end card

- Hook headline: black text on a white box, max 2 lines, for the length of the hook. Colour only the key
  words (the promise or the pain) in ACCENT_COLOR, written as *words* in the edit plan. Drop the caption
  while the headline repeats it.
- Offer banner: only on the hook that carries the offer in the brief. White box, stays for the whole ad,
  end card included. The offer word in ACCENT_COLOR. It never goes on other hooks.
- End card CTA: action + product + an arrow down to the button ("Tap below / Shop the Night Cream ↓").
- Brand font: only on the end card and the offer banner. Captions and hook headlines stay in CAPTION_FONT.

## Audio

- Speech peaks at SPEECH_PEAK_DB. Music under the voice at MUSIC_LEVEL_DB. Some ads have no music.
- Copyright-free or licensed music only. Note the source of every track in edit-plan.md.
- Final mix: LOUDNESS_TARGET_LUFS integrated, TRUE_PEAK_DBTP true peak, measured with ffmpeg loudnorm
  in two passes. Report the measured values, never the target as if it were the result.
- Bad speech audio: export the voice alone first, clean it, then mix.
- Show what is said: the visual on screen proves the line being spoken.
- Speed up slow action instead of cutting it, up to 1.5x.

## Files: footage, renders, exports

- footage/ is read only. Copy or proxy what you need into renders/_work/.
- Every render goes to renders/ first. Only a finished file under its final name is copied to exports/.
  Nothing in exports/ is delivered before $ad-qa passes.
- Never overwrite a file you did not create in this session. Never overwrite paid output: rename the old
  file alt_<name>_v1 before you regenerate.
- Provider uploads and result URLs expire (kie deletes uploads after 24 h). Download every result to
  renders/gen/ at once, and keep local files as the reference, never a URL.

## Cost and approval

Follow AGENTS.md and the gated-generation skill. Quotes and paid executions use tools/paid_run.py.
Current prices.json entries are required. A comment tag or --approved flag alone does not authorize
spending. The wrapper checks the quote ID and budget and records the estimated charge.

## Keys

- Keys live in environment variables only: KIE_API_KEY, ELEVENLABS_API_KEY.
- Never ask for a key, never read, print, echo, log or measure one. Never read ~/.zshrc or any .env file.
- To check a key, print only set or missing: [ -n "$KIE_API_KEY" ] && echo set || echo missing
- If a key is missing, say which one and point to tools/set-key.ps1 for masked Windows entry.

## Measure, never guess

- Whisper word times are about 50 ms off. Model timestamps drift. Generated clips get retimed.
- Find cuts with ffmpeg scene detection on frames, never from a model's shot list.
- Every check in a report has a number: duration, frame count, LUFS, dBTP, fps, resolution, black or
  frozen frames found.
- Before you render every hook, render one hook or the first 20 s as a demo and wait for the OK.

