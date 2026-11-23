---
name: captions-headlines
description: "Create word-timed captions, verbatim headlines and end cards with a separate layout per aspect ratio."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Captions and Headlines

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`. Free and local.

## Where it sits

Skill 15 renders a clean file per hook and ratio (`renders/<AD>_H1_9x16_v1_clean.mp4`, `..._4x5_v1_clean.mp4`). This
skill burns the text into each one with the layout of its own ratio and writes the final name
(`renders/<AD>_H1_9x16_v1.mp4`). Skill 15 then copies the finals into `exports/`. Skill 16 checks them. Never caption the
9x16 file and crop it to 4x5: the headline ends up at the top edge.

## House style (from AGENTS.md, set in renders/_work/captions.json)

- Captions: style 1 white text with a black stroke (default), style 2 black text on white rounded boxes
  (`caption_style: "box"`). CAPTION_FONT at 68 px on a 1080 wide frame, shrinking to 60 px before a caption is split.
  Max 2 lines, broken by meaning. Never end a caption on a function word. No pop-in animation unless the brief or the
  reference ad has one.
- Hook headline: black text on a white box, max 2 lines, for the length of the hook. Key words in ACCENT_COLOR, written
  `*like this*`. The caption is dropped while the headline repeats it.
- Offer banner: only on the hook that carries the offer in the brief (`banners` in the config). White box at the
  headline position for the whole ad, end card included, the offer word in accent. The headline and the end card move
  below it. It never goes on the other hooks.
- End card: "action / product + arrow" (`Tap below / Shop the *Night Cream* ↓`), last `endcard_s` seconds. The brand font,
  if any, goes only on the end card and the offer banner.
- Positions (centre of each block, share of the height): headline 20 % (9x16) and 17 % (4x5), end card 24 % and 19 %,
  captions 74 % and 78 %.
- House text zone: the centred 4x5 band of the 9x16 frame (x 65 to 1015, y 285 to 1635). Every box must be inside it.

**Meta's Reels zone.** Meta's Reels guidance keeps the bottom 35 % of a 9:16 frame (below y = 1248 on 1920) clear of key
text. The house caption line at 74 % sits inside that zone on purpose. `build` prints a NOTE when any box reaches into
it. Before export, check the hook in the Ads Manager placement preview. If the Reels interface covers the captions in
your placements, set `caption_y` to 0.60 for this ad, build again, and say so in the report. Meta changes these
templates: check the current Ads Guide for your placement.

## Steps

1. **Config.** `python3 <skill-dir>/scripts/captions.py init` writes `renders/_work/captions.json`. Fill:
   - `headlines`: per hook, verbatim from the brief's hooks table, `|` for the line break, `*key words*` in accent.
   - `banners`: only the hook that carries the offer. Delete the example entry when no hook has one.
   - `endcard` and `endcard_s`; `fix`: wrong spelling -> product page spelling (brand names, product names);
     `solo`: words that get a caption of their own (the brand reveal); `lang`; `font` if CAPTION_FONT is not found.
2. **Words.** For each clean render: `captions.py words renders/<AD>_H1_9x16_v1_clean.mp4`. Read the transcript against
   the script. List every place the speaker said something else, as a slip or as a better line. Never change the copy
   on your own. Every word that Whisper got wrong goes into `fix`.
   One transcript per hook is enough: copy `<name>_9x16_v1.words.json` to `<name>_4x5_v1.words.json`, the audio is the same.
3. **Build.** `captions.py build <clean file>` writes `renders/_work/captions/<name>.ass` and `<name>.layout.json`, and
   prints the counts, any box outside the house zone, and the Meta zone note.
4. **Demo first.** Burn the first hook in 9x16 only. `captions.py preview <clean file> --t <second>` draws the zones on a
   frame. Show the preview and the file. Wait for the OK on the style before the other hooks and ratios.
5. **Burn.** `captions.py burn <clean file>` -> `renders/<name>.mp4`. `--engine auto` uses libass when this ffmpeg has the
   `ass` filter, else Pillow overlays with the same layout. Both read the same layout, so the result matches.
6. **Never cover the hero.** Check the preview frames where a face speaks close to the caption line or the product is low
   in frame. Move that ad's `caption_y` up and build again.
7. Hand the finals to Skill 15 (`reframe.py export`).

## Output format

```
CAPTIONS: <AD>
| file | ratio | captions | headline | banner | end card | outside house zone | in Meta bottom zone | engine |
Transcript vs script: <differences, each marked slip or better line>
Fixed spellings: <wrong -> right>
Preview: renders/_work/captions/<name>_preview.png
NEXT: <OK on the demo | reframe.py export | /final>
```
