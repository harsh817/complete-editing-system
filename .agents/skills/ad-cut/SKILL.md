---
name: ad-cut
description: "Build the first H1 rough cut using the planned real footage or approved AI footage."
---

Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.

# H1 rough cut

Read the ad plan and progress. Stop for unresolved decisions that change the cut.
For real footage, inventory with ffprobe, flag mixed/VFR inputs, and use script-vs-take to select
timed takes and list deviations for user review. Write proxies into renders/_work/ when needed.
For new AI footage whose creative story and shot plan are unresolved, use visual-story-engine
first. Do not jump straight to generating scenes. For already approved AI footage, select talking-avatar, animated-ad and/or song-timing according to the plan.
Route every paid operation through gated-generation and the paid-run wrapper.
Use rough-cut for H1 only. Keep script order and the approved copy. List missing B-roll and propose
the appropriate production skill; no generation without its own quote and OK.
Render a versioned H1 rough file to renders/, never exports/. Report measured duration, cuts,
take choices, script changes and gaps. Show the video and wait for creative review.
After review fill agreed gaps, handle voice/music, then prepare a captions-headlines demo.
Update progress. Next: ad-variants after the rough cut and text style are approved.
