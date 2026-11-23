---
name: gated-generation
description: "Quote and control provider spending for paid ad generation, rerolls and voice workflows; inspect the ledger."
---

# Paid generation in Codex

Read AGENTS.md. Every paid run needs a current quote, explicit user OK for that run, and the
paid-run wrapper. A cost comment or --approved flag is insufficient. Use the editing Python
interpreter; run wrapper commands from the workspace root. Local planning and quotes are free.

1. Build the prompt/job/config files locally. Count images, seconds, clips or characters from
   the actual plan/media. Run the production helper without --approved for its free estimate.
2. Verify the chosen model and current price at the provider. Store the per-unit price and checked
   YYYY-MM-DD in root prices.json or the ad override. Null/stale/invalid prices block execution.
   For voiceover, prices.json is dollars per character; the voice config uses dollars per 1,000
   characters, so convert explicitly and ensure the two agree. Never invent a missing price.
3. Save a JSON request inside ads/<AD>/renders/_work/. Example schema (replace with real values):

```json
{
  "ad": "ACME_2610-S3",
  "step": "broll",
  "provider": "kie",
  "model": "nano-banana-pro",
  "units": 1,
  "unit": "image",
  "script": ".agents/skills/broll-from-brief/scripts/kie.py",
  "args": ["run", "renders/_work/broll_jobs.json", "--only", "S01"]
}
```

The script path is workspace-relative. Its args and input paths are relative to the ad folder.
Use one model and unit per request; use a pricing variant such as model:sound when appropriate.
Do not include --approved, a key value or a shell expression in args. The wrapper launches the
installed Python helper directly with no shell evaluation. Other supported helpers: scene-edit
and talking-avatar kie.py, voiceover vo.py, one-voice voice.py, actor-swap actorswap.py,
animated-ad gen.py and song-timing timing.py.

4. Run `tools/paid_run.py quote ads/<AD>/renders/_work/<request>.json` with the editing interpreter.
   Show run cost, repair allowance, reserved total, cap and quote ID. The quote fingerprints the
   request, prices, budget, ledger, helper and ad inputs. Wait for the user's OK for this exact run.
5. After OK run `tools/paid_run.py run <request> --approved --quote-id <quoted ID>`.
   Changed inputs or budget/spend invalidate the quote: re-quote and ask again. Do not alter inputs
   after quote approval. Do not manually set EDITING_PAID_CONTEXT or bypass a rejection.
6. Start with 1–2 items. Download results immediately to renders/gen/, inspect them and obtain
   another quote/OK for the larger batch. Re-rolls and repairs need their own quote and OK.
7. Show spending after every run using `scripts/gate.py spend --ad <AD>`.

The ledger records an estimate before executing the helper, with status reserved and a run ID.
This protects the cap if the job fails or is interrupted. Never delete or edit those rows, and
never treat estimates as confirmed provider charges. If a run failed before sending anything,
report that fact separately; reconciliation of actual billing is a user decision.

If a paid-run.lock remains after a crash, inspect whether its process is still running before
removing a stale lock. Never remove a live run's lock. Do not rerun an interrupted job blindly;
check provider/job state first. The wrapper governs these bundled helpers, not arbitrary Codex
tools or other connectors. Apply the same quote/OK policy to paid actions outside this bundle;
do not pretend another connector is recorded by this ledger.

Keys are optional until needed. Check only set/missing; use the masked tools/set-key.ps1 helper
for user entry. User authorization must also cover any private media uploaded to the provider.
