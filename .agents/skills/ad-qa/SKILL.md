---
name: ad-qa
description: "Perform measured and visual QA, report timestamped failures and stamp unchanged passing exports."
---

Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.

# Export QA

Read the brief, edit plan, AGENTS.md and EDITING_RULES.md. Use the edit-qa skill and the complete
`references/edit-qa.md` checklist here. Perform the review in this chat; another agent is optional
only when independently authorized. Automatic output is not proof of the pending visual checks.
Write renders/qa/qa-<date-time>.md with exactly `RESULT: PASS` or `RESULT: FAIL` on its own line.
Record per-file values, all blocking checks, visual inspection, timestamps and warnings. A missing,
unrun or pending blocking check means FAIL. Verify approved hooks exist in both ratios.
If every blocking check passed and visual review is complete, run from the workspace root:
`tools/workspace.py qa-pass <AD> --report ads/<AD>/renders/qa/qa-<date-time>.md`
using the editing interpreter. Do not use touch or write LAST_PASS manually.
On failure, report fixes and wait for creative/cost decisions as needed; changed exports get a new
version and another QA pass. Update progress. Next after PASS: ad-spend, then ad-deliver.
