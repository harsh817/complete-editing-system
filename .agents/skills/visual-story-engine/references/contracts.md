# State and artifacts
Store state in brief/story-engine/state.json and versioned stage .md/.json files alongside it.
Use existing renders/gen and renders/_work for media. Keep original brief/footage unchanged.
Stage statuses: not_started | in_progress | needs_review | approved | superseded.
State fields: schema_version, project_id, current_stage, stages, script, intake, human_truth,
selected_story_id, stories, exaggeration, characters, environments, shots_path, frames, clips,
approvals, rejected_directions, outstanding_questions, change_log.
Approved artifact: id, version, approved_by, approved_at, approval_evidence, depends_on (IDs/versions).
Never manufacture consent, evidence or dates. State is a planning record, not an execution permission.

shots JSON: {"sequences":[{"id":"H1","duration_sec":7,"shots":[...]}]}.
Each sequence starts at zero; separate H1/H2/H3/BODY sequences. Each shot requires:
id, start_sec, duration_sec, marketing_beat, story_function, visible_action, character_ids,
environment_id, emotion_and_microexpression, exaggeration_and_meaning, camera_and_composition,
wardrobe_and_prop_state, reference_asset_ids, opening_state, ending_state, voiceover_segment_ids,
setup_or_payoff_ref, continuity_notes, review_status, source_duration_sec, source_in_sec,
source_out_sec, reference_paths, source_clip_id, reuse_reason.
Unknown values may be null while drafting; resolve relevant unknowns before approval/generation.
reference_paths are ad-relative local paths. Plan JSON is not a provider request; translate approved
shots into the provider's verified schema and paid wrapper request.

Commands from workspace root (use editing Python):
- tools/story_engine.py init AD: create fresh state only for an existing ad; refuse overwrite.
- tools/story_engine.py status AD: report next unapproved stage without mutation.
- tools/story_engine.py check AD WORKSPACE_RELATIVE_SHOTS_JSON: timeline, trims, field and reference checks.
Checker does not inspect imagery, confirm consent, verify medicine or replace measured export QA.

Stage artifacts: S0 intake, S1 options, S2 treatment/script-fit, S3 motif arc, S4 asset bible,
S5 edit-plan/shots, S6 frame prompts/QA, S7 motion prompts/QA, S8 production edit and delivery manifests.
