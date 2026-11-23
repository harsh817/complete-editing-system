---
name: ad-final
description: "Render versioned final ad exports in both ratios with measured encoding and audio."
---

Read AGENTS.md and EDITING_RULES.md; use the editing Python environment.

# Final exports

Read the approved plan, hooks and review decisions. Use reframe-exports and captions-headlines.
Render 9x16 1080x1920 and 4x5 1080x1350 from the same approved inputs in separate passes with
ratio-specific text layout. Do not crop a finished text-bearing 9x16 file to create 4x5.
Use H.264 High, yuv420p, source constant fps, AAC 48 kHz stereo and faststart; normalize in two
passes and measure the result against AGENTS.md. First write in renders/, then copy final-named
files into the ratio export folders. Preserve every existing version. Measure name, resolution,
fps, duration, LUFS, true peak and size. Any change invalidates the previous QA pass.
Update progress. Next: ad-qa; do not call the files ready for handoff yet.
