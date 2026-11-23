---
name: song-timing
description: "Plan song-led ads, measure beats and lyric timing, and quote approved song generation or edits."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Song Timing

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`.
`timing.py` paid commands need `KIE_API_KEY`, gated-generation and the Codex paid-run wrapper. `beats.py` is free.

## Part A: lyrics and style (free, before any song exists)

1. **Lyrics verbatim from the brief**, mapped to Suno section tags: the brief's own labels first, unlabeled lines to the
   nearest section (say where you put them). Spoken lines keep a tag: `[Spoken] "..."`.
2. **Never put the hook in `[Intro]`.** Suno sings intros softly. The hook opens `[Verse 1]`. An `[Outro]` that carries
   the CTA has the same risk: if it comes out soft, relabel it `[Final Chorus]`.
3. **One base song, the other hooks by replacement.** Make the song with Hook 1. Make every other hook with
   `timing.py hook`, which rewrites only the opening and keeps the body. Hooks with the same lyrics share one song. A hook
   that starts on the body needs no song: `timing.py bodyonly`.
4. **Respell for the singer, never for the viewer.** Brand and foreign words are written the way a singer of the song's
   language would read them, in the lyrics sent to Suno only. Captions and on-screen copy keep the real spelling.
   Numbers as words ("number one", not "#1"). If a brand word still comes out wrong, try the next respelling before you
   touch the edit.
5. **Style prompt:** genre, mood, lead vocal, BPM, arrangement, and `vocals start immediately, no instrumental intro`.
   No artist names. Add exclusions (`slow intro, ballad, spoken intro`). Example shape:
   `upbeat pop, catchy, bright female lead vocal, clear diction, 110 BPM, punchy drums, warm bass, big singalong chorus,
   vocals start immediately, no instrumental intro`.
6. **Write `renders/_work/script.json`** from the brief: `[["Hook 1", "..."], ["Hook 2", "..."], ["Scene 1", "..."],
   ..., ["CTA", "..."]]`, copy verbatim, ` | ` between captions, ` / ` for a forced line break. Write the lyrics as sung
   (with tags and respellings) to `renders/_work/lyrics_h1.txt`.

## Part B: make or time the song (paid steps)

Each paid command without `--approved` prints the quote and the cost tag with `ok=no`. **Stop. Wait for OK.** Then the
same command with the tag at `ok=yes` and `--approved`:

```bash
# cost: ad=<AD> step=song provider=kie model=ai-music-api/generate units=1 unit=clip usd=<est> ok=yes
cd ads/<AD> && python3 <skill-dir>/scripts/timing.py song --lyrics renders/_work/lyrics_h1.txt --style "<style>" --approved
```

- **New song:** `timing.py song` makes 2 takes with their word timings: `audio/music/h1_v1.mp3`, `h1_v2.mp3` and
  `.words.json` next to each. The user listens and keeps one (`mv` lines printed by the script).
- **Song made in the Suno app:** put it at `audio/music/h1.mp3`, then `timing.py stt audio/music/h1.mp3 --lyrics
  renders/_work/lyrics_h1.txt`. Always pass the lyrics exactly as sung: Suno aligns the words it is given, so a chorus
  sung 4 times but written twice shifts the next scene.
- **Other hooks:** `timing.py hook --song audio/music/h1.mp3 --grid renders/_work/grid_h1.md --hook H2`. 2 takes, each
  timed. Listen at the seam (the script prints its second). Time every hook version: the body shifts when the hook
  length changes.
- **Music bed for a spoken ad:** `timing.py song --instrumental --style "<style>"`. Sections follow the ad: hook, build,
  a break on the payoff beat, resolve under the CTA. Length = the longest hook version plus about 5 s. Mixed at
  MUSIC_LEVEL_DB under the voice.
- Never time sung vocals with Whisper: it drops whole sung sections. Whisper is for speech only.

## Part C: the grid (free)

1. `timing.py grid --song audio/music/h1.mp3 --hook H1` -> `renders/_work/grid_h1.md`. Each module (Hook n, Scene n,
   CTA) starts on the first sung word of its line, the first module at 0.00, and the instrumental tail is the Outro (end
   card slot).
2. `beats.py detect audio/music/h1.mp3` -> tempo, beats and bars (`audio/music/h1.beats.json`). If the user knows the
   BPM from the Suno style, pass `--bpm`: it skips the tempo guess.
3. `beats.py snap --grid renders/_work/grid_h1.md --beats audio/music/h1.beats.json --fps <ad fps>` -> every cut moved to
   the nearest beat at or before the sung word, within 0.25 s, with in and out frame numbers. `--to bar` for slower,
   bigger cuts. A cut with no beat in reach stays on the word and says so.
4. Fast montage inside one long line: `beats.py cuts --beats ... --every 2 --start <s> --end <s>` gives a cut every 2
   beats in that window.
5. A hook that starts on the body: `timing.py bodyonly --song audio/music/h2.mp3 --grid renders/_work/grid_h2.md --hook H3`.
6. Check every line: a sung line over about 10 words on a 3 s shot is too much text for the captions. Say so: the shot or
   the line has to change, and the brief decides which.

Then the grid goes to the scene plan (Skill 11 for animated scenes, Skill 4 for the rough cut) and the word timings go to
the captions (Skill 14), which keep the brief's spelling.

## Output format

```
SONG TIMING: <AD>, hook <H#>, song <file> (<seconds> s), <bpm> BPM, <beats> beats, <bars> bars
| module | start | end | dur s | in frame | out frame | snap | lyric |
Takes to listen to: <files> (seam at <second> s)
Flags: <lines too long for their shot | modules found late | takes that open on an intro>
Spend: <usd_est this run> | spent on this ad <total> of <cap>
NEXT: <listen and pick a take | scene plan | captions>
```
