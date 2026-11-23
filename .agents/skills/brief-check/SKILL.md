---
name: brief-check
description: "Check an ad brief and source footage for gaps; write the verbatim script, edit plan and blocking questions."
---

Read AGENTS.md and EDITING_RULES.md. Use the editing Python interpreter in AGENTS.md
where examples say python3. Script paths come from this skill's installed directory.
Run helpers from the named ad folder unless the helper specifies the workspace root.
For every paid operation, use gated-generation and tools/paid_run.py. Direct --approved examples
below are helper argument templates only; the wrapper supplies the flag after the exact quote is
approved. Cost comment tags are not Codex authorization or automatic ledger hooks.
Read the original brief as source material; update brief/progress.md when finishing a step.

# Brief Check

Find every problem in the brief before the first cut, then write the edit plan.
The editor fixes problems with the strategist now, not with the client after delivery.

## Folder

Run inside the ad folder `ads/<AD>/`:
```
brief/     the brief (never changed), edit-plan.md, questions.md, script.txt, budget.txt
footage/   raw takes, read only
refs/      reference ads, packshot, fonts, logo
audio/     vo/, music/, sfx/
renders/   _work/ (transcripts, JSON, contact sheets), gen/ (paid output), qa/
exports/   9x16/ and 4x5/ final files only
ledger.csv estimated reservations written by the paid-run wrapper
```
Scripts live in `<skill-dir>/scripts/`. `<skill-dir>` is the folder that holds this SKILL.md.
Use the workspace venv if it exists: `C:/Users/pc/.venvs/editing/Scripts/python.exe` instead of `python3`.

## Steps

1. **Extract the brief.**
   `python3 <skill-dir>/scripts/extract_brief.py brief/<file>` writes `renders/_work/brief.txt`.
   Read the whole text. For a Google Doc, use an available connected document reader; otherwise request a .docx export.

2. **Inventory the footage** (skip if `footage/` is empty, and say so).
   `python3 <skill-dir>/scripts/footage_inventory.py footage/ --csv renders/_work/inventory.csv`
   Read the flags: ROTATED, VFR, LOW_RES, NO_AUDIO, SHORT.

3. **Read-through.** Use the checklist at ../ad-brief/references/brief-checker.md in this chat.

4. **Run every check below.** Each check is PASS, FLAG or BLOCKER.
   BLOCKER means the edit cannot start without an answer.
   Quote the brief line (with its line number in `renders/_work/brief.txt`) for every FLAG and BLOCKER.

5. **Write `brief/script.txt`.** One script line per row, labelled, words copied verbatim:
   ```
   H1: <hook 1 exactly as written>
   H2: <hook 2>
   B1: <first body line>
   B2: ...
   CTA: <call to action>
   ```
   Split the body at sentence ends. Never fix the brief's wording here. The script-vs-take and voiceover skills read this file.

6. **Write `brief/edit-plan.md`** and **`brief/questions.md`** in the formats below.

7. **Report** in the reporting guidance from AGENTS.md (STATUS, FILES, CHECKS, COST, NEXT, QUESTIONS). NEXT is `$ad-cut <AD>` once the footage is in and the blocking questions are answered.

## Checks

| # | Check | BLOCKER when | FLAG when |
|---|---|---|---|
| 1 | Hooks | no hook at all | only one hook, or two hooks that open with the same first three words |
| 2 | Ratios and lengths | no ratio stated | ratio stated but no target length, or a length the script cannot fit (count about 2.5 spoken words per second, mark it ESTIMATE) |
| 3 | CTA | no CTA in script or on screen | CTA only in the voiceover, with no on-screen text |
| 4 | Shot list | a script line names a visual that no shot or B-roll covers | a shot has no script line, or B-roll is "TBD" |
| 5 | Claims | a health, financial, before/after or guarantee claim with no proof source | any number, "best", "#1", "clinically", "proven" with no source named |
| 6 | Footage vs script | a script line has no matching footage (once footage exists) | footage is ROTATED, VFR, LOW_RES or NO_AUDIO |
| 7 | On-screen text | text overlays are required but not written | overlay text longer than its time on screen allows (about 3 words per second of reading, ESTIMATE) |
| 8 | Music and VO | the brief needs a voiceover but names no voice | no music direction, or music with no licence source |
| 9 | Deliverables | no delivery list | number of exports unclear (hooks x ratios) |
| 10 | References | a reference ad is named but not attached | reference attached with no note on what to copy |

## edit-plan.md

Sections in this order (the workflow skills read them):
```
# Edit plan: <AD>

## Verdict
READY / READY WITH FLAGS / BLOCKED (n blockers) · checks: <n PASS, n FLAG, n BLOCKER>

## Overrides for this ad
<rules for this ad only, or "none">

## Format and length
<target seconds per hook, ratios 9x16 / 4x5, from the brief or [NEEDS: length]>

## Hooks table
| Hook | Spoken line (verbatim) | Headline (verbatim, key words *like this*) | Visual opener | Offer banner |

## Body
| Line | Text (verbatim) | Est. seconds | Visual that shows what is said | Footage file or [NEEDS: footage] |

## B-roll list
| Shot | Script line | Source: footage / stock / generate / ask |

## Audio
Voice: <creator / voiceover skill / [NEEDS: voice]> · Music: <source and licence> · SFX: <list>

## Text
Captions: <style> · End card CTA: <verbatim> · Offer banner: <verbatim or none>

## Footage path
<real footage, AI footage, or both, and the skills each path needs>

## Paid steps expected
| Step | Units | ESTIMATE |

## Flags
1. <problem>. Brief line <n>: "<quote>".

## Deliverables
| File name | Hook | Ratio | Target length |
| <AD>_H1_9x16_v1 | H1 | 9x16 | <seconds or [NEEDS: length]> |

## Footage notes
<inventory flags and the fix: conform VFR to constant frame rate in renders/_work/, ask for a reshoot>
```

## questions.md

Only questions whose answer changes the cut or the cost. Max 7. Blockers first. Multiple choice when possible:
```
1. [BLOCKER] Brief line <n>: "<quote>". <question>?  a) ...  b) ...  c) other
```

## Rules

- Never change the brief. Never invent a missing value: write `[NEEDS: x]`.
- Never rewrite the brief's copy. Report a line that reads badly aloud as a FLAG for the strategist.
- A claim is judged only on whether a proof source is named. You do not decide if a claim is true.
- File names follow `<AD>_<HOOK>_<RATIO>_v#`, ratio written `9x16` or `4x5`.
- Write only in `brief/` (new files next to the brief) and `renders/_work/`. Never in `footage/`.
