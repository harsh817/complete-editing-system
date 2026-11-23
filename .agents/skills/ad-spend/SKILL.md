---
name: ad-spend
description: "Show reserved estimated provider spending per ad or prepare a quote for its next paid step."
---

Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.

# Spending

Read the ad ledger, plan and cap from AGENTS.md or brief/budget.txt. Use the gated-generation
helper `gate.py spend --ad <AD>` to summarize estimates by step/status. Report total reserved,
remaining cap and rework; confirmed provider billing is unknown unless separately supplied.
Never edit or delete past rows. Failed/interrupted attempts keep their conservative reservation.
For a new quote, use the gated-generation skill and tools/paid_run.py; show its quote ID and wait.
Next: the approved production step or ad-deliver after successful QA.
