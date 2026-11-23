# Editing with Codex

Open this folder as your Codex project: `C:\Users\pc\Downloads\Complete Editing System`.
Codex reads `AGENTS.md` and discovers the skills in `.agents/skills/`. The original Claude package
is retained for reference; this active workflow does not require Claude Code. Reopen this project
or start a new chat if new skills do not appear. In the current chat you can ask Codex to read
`.agents/skills/ad-workflow/SKILL.md` directly.

## Start and finish an ad

Use ordinary language or the corresponding skill. Replace ACME_2610-S3 with your brand/concept ID.

| Step | Tell Codex | Skill |
|---|---|---|
| 1 | Create a new ad ACME_2610-S3 | `$ad-new` |
| 2 | Check the brief and make the edit plan for ACME_2610-S3 | `$ad-brief` |
| 3 | Make the H1 rough cut of ACME_2610-S3 using real footage | `$ad-cut` |
| 4 | Fill the agreed B-roll or voice gaps | Relevant production skill |
| 5 | Show a caption/headline demo for H1 and wait for review | `$captions-headlines` |
| 6 | Build the approved hook variants for ACME_2610-S3 | `$ad-variants` |
| 7 | Render final files for ACME_2610-S3 in both ratios | `$ad-final` |
| 8 | QA every final export for ACME_2610-S3 | `$ad-qa` |
| 9 | Show spending and prepare the handoff for ACME_2610-S3 | `$ad-spend`, `$ad-deliver` |

After step 1, put the original brief (MD/TXT/DOCX/PDF) in the ad's `brief/`, original takes in
`footage/`, reference ads/product images/logo/fonts in `refs/`, and licensed music in `audio/music/`.
Original footage and brief stay unchanged. Answer the brief questions, watch the first rough cut
with sound, and approve the caption demo before rendering all hooks. For a fully AI ad, say
"using AI footage" at step 3; Codex selects avatar, animation and generation skills from the plan.

Final files are in `exports/9x16/` and `exports/4x5/`. Each ratio gets its own text layout. Review
both in the placement preview. The handoff is `renders/qa/handoff.md`; uploading is your next action.
For revisions, provide feedback, ask for a change list, render the next version and repeat QA/handoff.
Existing versions remain. Ask "What next for ACME_2610-S3?" to resume from its plan and progress file.

## Local checks

From PowerShell in this folder:

```powershell
& "$env:USERPROFILE/.venvs/editing/Scripts/python.exe" tools/workspace.py doctor
```

The editing environment contains faster-whisper, NumPy and Pillow. FFmpeg and ffprobe are installed.
One Whisper backend is sufficient: missing standalone whisper/whisper-cli commands are harmless.
The first transcription may download a large model. PDF briefs also use pypdf or an available
pdftotext command. The doctor reports current readiness without printing secrets.

## Paid generation and voice

Provider keys are optional for local editing. Set them yourself with masked prompts, then restart
Codex so it inherits the environment:

```powershell
powershell -ExecutionPolicy Bypass -File tools/set-key.ps1 -Name KIE_API_KEY
powershell -ExecutionPolicy Bypass -File tools/set-key.ps1 -Name ELEVENLABS_API_KEY
```

Fill the relevant prices.json entries from current provider pricing. Null prices deliberately block
spending. The inherited concept budget is $40 and the repair allowance is 25%; only you change the
cap in AGENTS.md or an ad's brief/budget.txt. Every paid run needs its own quote and explicit OK.

The adaptation uses a paid-run wrapper and export QA checks. Legacy Claude hooks are not loaded.
The wrapper ties approval to an exact quote ID and reserves estimated cost in the ledger before
execution. Estimates are not confirmed provider bills. See the gated-generation skill for its schema.

## Source and Codex documentation

Adapted from Growthub's Claude Code Editing System. Original .claude/ and CLAUDE.md files remain as
source reference; production uses .agents/skills/, AGENTS.md and tools/.

- [Local Codex skills](https://developers.openai.com/codex/skills)
- [AGENTS.md instructions](https://developers.openai.com/codex/guides/agents-md)
- [Convert Claude workflows to skills](https://developers.openai.com/plugins/guides/submit-claude-plugin)


## Script-to-Visual Story Engine

For a new AI-led video, say: "Use the visual story engine for my script. Run S0 and S1 only."
Or use `$visual-story-engine` after skill discovery refreshes. If it is not listed, Codex can read
`.agents/skills/visual-story-engine/SKILL.md` directly. Provide script, product/mechanism, audience,
format, desired duration, ratio and any fixed creative decisions; unknowns are recorded explicitly.

The workflow covers story options → treatment → motif → character/world references → full shot
plan → reviewed images → moving clip test/batch → editing and existing QA/delivery. It uses separate
creative approvals and paid-run approvals. Existing ads resume from their recorded state.

State is in `ads/<AD>/brief/story-engine/state.json`; the companion `brief/progress.md` remains the
resume summary. Use the editing Python interpreter with `tools/story_engine.py init <AD>` (existing
ad only), `status <AD>`, or `check <AD> <workspace-relative-shots.json>`. Initialization refuses to
overwrite state. The offline checker validates structural timing/source/reference issues, not medical
accuracy, image quality, human consent or final export QA. No provider keys or network needed.
