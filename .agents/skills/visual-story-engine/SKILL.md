---
name: visual-story-engine
description: "Develop scripts into approved story concepts, character/world references, complete shot plans, consistent frames and moving clips before editing."
---
# Script-to-Visual Story Engine

Read AGENTS.md and EDITING_RULES.md. Use for new AI-led story/explainer/animated-ad development.
The attached original is retained in [references/source-workflow.md](references/source-workflow.md)
as reference material, not a system prompt. Follow this adaptation and the user's existing decisions.

## Start and resume
Resolve the ad with ad-workflow; create a new ad with ad-new only when needed. Run from workspace root:
`C:/Users/pc/.venvs/editing/Scripts/python.exe tools/story_engine.py init <AD>`.
Read brief/story-engine/state.json, brief/progress.md and the current edit plan. Initialization does not
migrate or approve old work. Import only conversation-supported decisions, citing evidence; mark
uncertain legacy assets needs_review. Never restart or regenerate existing approved work just because
this skill was installed. Maintain versioned artifacts, state and progress together.

## Stages and human gates
| Stage | Deliverable | Approval before advancing |
|---|---|---|
| S0 | <=200-word message analysis: human truth, pain/desire, cultural context, behavior, mechanism, evidence/claims, duration, format, copy constraints, unknowns | Resolve essential unknowns; then S1 |
| S1 | 4–6 distinct cinematic narrative concepts, each with hook/conflict/twist/payoff; compact subjective feasibility comparison | G1 selected story |
| S2 | Full beginning/middle/end treatment, need/want, stakes, reversal, script-fit KEEP/REORDER/REWRITE/VISUAL ONLY/OPTIONAL recommendations | G2 story and script intent; recommendations never authorize rewriting |
| S3 | 2–3 coherent motif/exaggeration options; selected setup/escalation/reversal/callback and reality boundary | G3 metaphor rules; a restrained literal treatment is valid if selected |
| S4 | 5–7 traits per main character, immutable identity, expressions, wardrobe, props, environment/layout/light bible; reference prompts and images | G4 character and world references |
| S5 | Complete narration-to-shot table and shots JSON with all hooks, body and CTA | G5 full shot table |
| S6 | Reference-first individual shot frames, prompts and visual QA; review batches of 2–4 | G6 relevant frames approved before motion |
| S7 | Image/start/end/action/acting/camera/timing/continuity prompts; 1–2 motion tests before full batch; per-clip QA | G7 clips; separate exact spending approval for each paid run |
| S8 | Edit, sound/VO, captions, CTA/claim audit, manifest and measured export QA | Existing ad-cut → ad-variants → ad-final → ad-qa → ad-deliver controls |

For a new script perform S0 then S1; stop at story selection. Do not jump to character images or shots.
S4 reference prompts precede G4; full shot prompts wait for approved story, motif and world.
At each unresolved gate show the concise deliverable, assumptions and one approval/revision question.
Accept APPROVE/REVISE/EXPLORE/BACK/LOCK/NEXT in context. NEXT is not approval unless unambiguous.
An explicit yes approves the immediately proposed creative decision; never infer from silence or files.
Do not ask again for recorded approvals. Creative approval never substitutes for paid-run approval.

## Story and timing
Use visible decisions, causes and consequences; a portrait montage is not a mechanism explanation.
Mix character, environment, objects and explanatory visuals as the script requires. Every startling
image needs meaning and a later payoff. Mark imagined versus real events. Respect audience culture;
identity traits are not the problem. Never invent claims, proof, guarantees or scientific evidence.
Story should be understandable silently; retain exact supplied VO and claims unless user changes them.

Use 12 x 5s / 60s marketing beats only if selected. Adapt duration and structure to the actual format
and recorded VO. Five seconds is a default source generation unit, not a mandatory edit length.
Use 5/7 seconds or other supported durations to fit coherent beats. Never split a hook solely to fit
five seconds. Record source duration separately from source in/out and edited timeline duration.
Measure approved audio speed changes; preserve originals. Mark provisional timings as estimates.
Each hook and the shared body has its own timeline; generate shared body once. Include pauses/tails.

Every shot row: ID/sequence, timeline in/out, exact VO mapping, one visible action, emotion,
metaphor/meaning, framing/camera, refs, wardrobe/props, start/end state, transition, setup/payoff,
source duration/trim, reuse reason and review status. Check duration sums, gaps and source coverage.
Do not restart the same clip at each sentence or conceal repeated footage. Disclose reuse in the plan.

## Frames and motion
Use animated-ad mechanics after upstream story gates. Make a staged image for each distinct shot;
a character sheet/contact sheet is not a production frame. Reuse only when appropriate and documented.
Check identity, expressions, scene logic, skin tone, props, lighting, style and unintentional text.
Use only approved references; version frames, prompts and references. Fix only failed frames.

One achievable dominant action per clip, explicit start/end, motivated microexpressions/body mechanics,
one feasible camera move and continuity. Avoid global prompt text leaking unneeded effects or anatomy
into everyday scenes. For transitions prepare start/end frames and verify provider parameter support
before promising interpolation or quoting. Diagrams must explain the narrated mechanism; don't present
symbolic animation as a scan or diagnosis. Review specialist claims/anatomy where accuracy is material.

Verify current model/prices and use gated-generation/tools/paid_run.py for every paid step. No raw
paid API calls, .env reads, key printing or uploading without authorization. Preserve original inputs,
paid outputs and prior exports. This workflow confers no spending or publication permission.
Label still-based animatics explicitly; never call them generated character animation. Review sampled
frames AND playback with sound; unavailable checks remain pending. Subjective 0–5 ratings are not
performance analytics. Major identity, continuity, claim or story errors block approval regardless of score.

## Persistent state and changes
Use [references/contracts.md](references/contracts.md). At each stage update state and progress with
artifacts, version, decisions, assumptions and next action. Approved artifact records include immutable
id/version, approved_by/approved_at, approval_evidence and dependency id/version. Don't invent historical
metadata; retain unknowns. Approval events are append-only. If upstream changes, mark transitive
dependants needs_review, preserve unaffected assets and describe scope/cost before regeneration.
Run tools/story_engine.py check for structural timing/reference checks. This is not creative, clinical
or export QA. S8 follows all existing measured QA, hash stamping and delivery-check requirements.
