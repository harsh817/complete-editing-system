---
name: ad-deliver
description: "Validate the QA manifest and prepare the ad file list and handoff report."
---

Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.

# Handoff

Run `tools/workspace.py delivery-check <AD>` from the workspace root with the editing interpreter.
A missing/stale manifest or changed export blocks handoff and requires ad-qa again.
Compare every approved hook with both ratio folders, confirm naming and ensure no rough, clean or
review files are in exports/. Preserve previous versions; identify current approved deliverables.
Write renders/qa/handoff.md: current file list with hook, ratio, duration and size; accepted script
changes and who approved them; music licence/source; estimated spending by step and rework; and
any open items. Update progress and show the final local files with clickable paths.
The user uploads the files and checks playback in both ratios. Do not upload as part of handoff.
