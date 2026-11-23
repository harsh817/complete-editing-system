---
name: actor-swap
description: "Plan and quote an authorized actor replacement while checking original gestures, hands, props and timing."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Actor Swap

Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Run every command from the ad folder: `cd ads/<AD>`. The CLI reads `project.json` in that folder.
Use gated-generation and tools/paid_run.py for quoted, approved execution.

## Two modes

| Mode | Input | Output |
|---|---|---|
| A: recreate a winner | the winner ad(s) in `refs/`, the raw footage they were cut from in `footage/`, one image of the new actor | the same ads with the new actor: identical cuts and timing, raw audio |
| B: restyle clips | a folder of clips, one image of the new actor (or a change to make: age, outfit) | the same clips with the new or changed actor, source length and audio |

Ask which mode if the files do not make it obvious. Mode A: read the brief too, it fixes brand names and numbers.

## Rules that save money and revisions

1. **No paid call without an OK for that run.** Paid = `ref`, `swap`. Bare `swap` and `quote` print the quote only.
   This includes a cheap regeneration of a defect you found yourself: show the defect side by side, quote, wait.
2. **Test before batch.** Swap 1 or 2 clips, send the `compare` video, wait for the OK, then the rest.
3. **Seedance by default, Kling as the cheaper option.** Seedance 2.5 edit holds hands, products in hand, gestures and
   the editor's zooms best. Kling 3.0 Motion Control is cheaper per second (compare both lines in `prices.json`) and is
   fine on plain talking heads with nothing in hand: offer it once, side by side in the quote, and test it on one clip.
   If the Kling test fails, go back to Seedance for the run. Never try other models or re-roll on your own.
4. **Measure, never trust.** Whisper word times are about 50 ms off, model timestamps drift, video models retime clips.
   Every step below has a measured check: run it, report the number.
5. **Never overwrite paid output.** `renders/gen/` is append only. The CLI skips anything already generated and anything
   named `alt_*`. To redo a clip: rename the old output `alt_<name>_v1`, quote, OK, run.
6. **Map once, then cut, then swap.** Re-mapping after a swap moves segment edges outside the swapped clips: frozen
   frames, then a paid re-swap. `cut` refuses to run over paid swaps unless `--force`.
7. Keys only as environment variables. Check with `[ -n "$KIE_API_KEY" ] && echo set || echo missing`.

## project.json

```json
{
 "name": "ACME_2610-S3",
 "fps": 30,
 "size": [720, 1280],
 "raw": "footage/raw_take.mp4",
 "winners": {"H1": "refs/winner_H1.mp4", "H2": "refs/winner_H2.mp4"},
 "clips_dir": null,
 "swap": {
  "model": "seedance",
  "refs": ["renders/gen/ref/actor_in_scene.png"],
  "refs_by": {},
  "prompt": "Replace the woman in the video with the woman in the reference image (curly shoulder-length grey hair, around 60, laugh lines). Keep exactly the same camera framing, background, lighting, sweater, hand gestures, head movements, lip movements and timing. Keep every object exactly as in the video: do not add or remove anything. Photorealistic.",
  "prompts": {},
  "kling_prompt": null,
  "resolution": "720p",
  "parallel": 3,
  "min_clip": 4.0,
  "max_clip": 10.0
 }
}
```

`fps` = the winner's frame rate. `size` = the swap output size (720p edits come back at 720x1280; Skill 15 scales to
1080x1920 at export). `refs_by` and `prompts` override per clip or per clip prefix (`"BODY": [...]`).

## Mode A steps

| # | Step | Command | Check before moving on |
|---|---|---|---|
| 1 | Inventory | ffprobe the raw and every winner; write `project.json` | fps, size, durations; how many winners share a body |
| 2 | Map winner to raw | `actorswap.py map` | every winner segment found; `dist` low on talking segments |
| 3 | Cut | `actorswap.py cut` | clips 4 to 10 s; the body shared across hooks is cut once |
| 4 | Actor in scene | `actorswap.py ref renders/_work/swap/clips/<first>.mp4 refs/new_actor.png` (paid, 1 image) | same room, light, outfit, product in hand; eyes open, face visible |
| 5 | Quote | `actorswap.py quote` | seconds per model; clips under 4 s listed (Seedance minimum) |
| 6 | Test swap | `actorswap.py swap <1-2 clips> --approved` with the cost tag | `compare` each clip with its source: identity, hands, nothing added |
| 7 | Batch swap | new quote, OK, `swap all --approved` with the cost tag | the remux line per clip: model length vs source length |
| 8 | Rebuild | `actorswap.py edit` | each edit equals its winner length within 1 to 2 frames; "edge frame held" lines at 2 to 3 frames or fewer |
| 9 | QA | `actorswap.py qa renders/_work/swap/edits/*.mp4` and `speechcheck H1 renders/_work/swap/edits/H1.mp4` | 0 double cuts; no differing spoken regions |
| 10 | Hand over | the edits go to captions (Skill 14) and exports (Skill 15) | |

The paid commands carry the cost tag from the quote. Write `ok=yes` only after the user typed OK for this run:

```bash
# cost: ad=<AD> step=swap provider=kie model=bytedance/seedance-2-5 units=<seconds> unit=second usd=<est> ok=yes
cd ads/<AD> && python3 <skill-dir>/scripts/actorswap.py swap BODY_01 --approved
```

Start with one ad, or the first 20 s of it, as the demo. Style problems show fastest on a short demo.

## Mode B steps

1. ffprobe the clips. Set `clips_dir` in `project.json`.
2. One reference per scene: `ref <scene clip> refs/new_actor.png --out renders/gen/ref/actor_<scene>.png`.
   Age or outfit change on the same person: `ref <clip> - --out ... --prompt "Same person, 20 years older: ..."`.
   Map scenes to references with `swap.refs_by`.
3. `quote --src <clips_dir>`, OK, `swap <one clip> --src <clips_dir> --approved`, `compare`, OK, then the rest.
   Seedance needs clips of 4 s or more: join short clips of the same scene first, or use Kling for them.
4. `compare` every clip against its source. Redo only the clips the user rejects, each with its own quote.

## Prompts: what works and what breaks

- Works: name 2 to 4 identity traits of the new actor, then "keep exactly the same camera framing, background, lighting,
  [the objects really on screen], hand gestures, head movements, lip movements and timing. Do not add or remove anything."
- Breaks: listing an object that is not always on screen makes the model add it to every shot. Say "There is no table
  and no product in this scene" when that is true.
- Breaks: describing the clothes changes them. Describe clothes only to fix a problem the user named.
- Identity drifts younger or softer on big close-ups with head motion. Fix in this order: add the new actor's close-up as
  a second reference, then a third from a scene that held well. Re-rolling the same inputs is a lottery: ask what is
  wrong first.
- A gesture that carries meaning (counting on fingers) can get lost: name it in the prompt for that clip.
- The best Kling reference is the new actor already placed in that clip's own first frame (`ref`).

## What the remux fixes

- Seedance returns the whole clip, uniformly retimed to its own length and frame rate. `remux` stretches it back by
  source length / model length and resamples to `fps`. Checking only the first and last frame hides this: the drift is
  in the middle.
- Kling starts a few frames late. `remux` measures the offset on motion energy and holds the edge frames.
- 24 fps model output at a 25 or 30 fps project repeats a frame every few frames. `qa` counts them as single frozen
  frames. Users usually accept it; frame interpolation is the fix if they do not.

## Output format

```
ACTOR SWAP: <AD>, mode <A|B>, model <seedance|kling>
| clip | source s | model s | remuxed s | used in |
| ad | segments | edit s | winner s | edge frames held | double cuts | speech differences |
Review videos: renders/_work/swap/review/<clip>_compare.mp4 (look at <second>)
Spend: <usd_est this run> | spent on this ad <total> of <cap>
NEXT: <user review of the test clips | captions (Skill 14) | exports (Skill 15)>
```
