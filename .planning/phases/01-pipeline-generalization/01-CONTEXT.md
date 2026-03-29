# Phase 1: Pipeline Generalization - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove hardcoded Peace River column assumptions from the Streamlit dashboard so any researcher can upload their own CSVs and run the pipeline. The pipeline core (`src/pipeline.py`) is already generic — the work is entirely in the UI and bridge layers. Three coupled locations must change together: `pipeline_bridge.py:build_model_df()`, `app.py` Step 0 column validation, and the variable selectbox. Single-variable per run only (multi-variable deferred).

</domain>

<decisions>
## Implementation Decisions

### Model CSV Column Selection

- **D-01:** Step 0 shows two dropdowns for the model CSV — one for the date column, one for the value column. Both are populated from the uploaded CSV's headers.
- **D-02:** Single-variable per run only. User selects one date column + one value column. Multi-variable (running reanalysis on multiple columns at once) is out of scope for Phase 1.
- **D-03:** The observation CSV column mapping (date + value column selection) already exists in the current Step 1 flow and does not need to be redesigned — only the model CSV side is new.

### Variable Label

- **D-04:** The selected value column name is used as the variable label throughout: output filenames, log messages, and UI labels. No separate "display name" field. Example: user selects column `streamflow_cms` → outputs are `reanalysis_streamflow_cms_mean.csv`.

### CSV Preview

- **D-05:** Preview appears inline on Step 0, directly below each upload widget, as soon as a file is uploaded (before the user configures columns or clicks Next).
- **D-06:** Preview shows 5 rows. Both model CSV and observation CSV get their own preview.
- **D-07:** Preview is display-only. No editing.

### What Does NOT Change

- **D-08:** `src/pipeline.py` and all modules under `src/` are not touched in Phase 1. The generalization is entirely in `Reanalysis_Dashboard/pipeline_bridge.py` and `Reanalysis_Dashboard/app.py`.
- **D-09:** `data_loader.py` in `src/` is used only by Jupyter notebooks, not by the dashboard — no changes needed there.
- **D-10:** The existing `build_obs_df_dedicated()` function in `pipeline_bridge.py` already accepts arbitrary `date_col` / `value_col` parameters — reuse as-is.

### Claude's Discretion

- How to handle the UploadedFile buffer for preview (need `seek(0)` after reading) — standard pattern already established in `get_csv_columns()`.
- Whether to use `st.dataframe()` or `st.table()` for the preview display.
- Exact wording of column dropdown labels.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Dashboard Code
- `Reanalysis_Dashboard/pipeline_bridge.py` — Bridge layer; `build_model_df()` is the primary target for generalization; `get_csv_columns()` and `build_obs_df_dedicated()` are reusable as-is
- `Reanalysis_Dashboard/app.py` — UI; Step 0 (`render_step_upload()`) contains the hardcoded validation and variable selectbox to replace
- `Reanalysis_Dashboard/job_runner.py` — Background thread runner; no changes needed in Phase 1

### Pipeline Core (read-only — not modified in Phase 1)
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` — `run_single_reanalysis()` accepts `(model_df, obs_df, variable, station_name, hyperparams, output_dir)` — already generic
- `Sprint_2/Reanalysis_Pipeline/src/visualization.py` — Uses `UNITS` and `LABELS` dicts keyed by variable name; will need fallback for unknown variable names

### Research Findings
- `.planning/research/ARCHITECTURE.md` — Precise analysis of the three coupling locations with line numbers
- `.planning/research/PITFALLS.md` — Column hardcoding pitfall (Pitfall 3) with specific fix locations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline_bridge.get_csv_columns(uploaded_file)` — Already reads headers without consuming buffer (seek(0) pattern established). Reuse for populating dropdowns.
- `pipeline_bridge.get_csv_unique_values(uploaded_file, column)` — Already generic. May be useful for obs filtering if needed.
- `app.py:_best_guess_index(cols, candidates)` — Helper for pre-selecting likely date/value columns. Reuse to auto-highlight the most plausible column in each dropdown.
- `pipeline_bridge.build_obs_df_dedicated(uploaded_file, date_col, value_col)` — Already generic, already used by existing Step 1. No changes needed.

### Established Patterns
- `io.BytesIO(uploaded_file.read())` + `uploaded_file.seek(0)` — Buffer exhaustion prevention pattern. Used consistently throughout `pipeline_bridge.py`. Must be applied to any new CSV reads.
- `encoding="utf-8-sig"` — Used on all CSV reads to handle UTF-8 BOM. Keep this.
- `st.session_state` for all inter-step state — don't change this pattern.

### Integration Points
- `build_model_df()` return value feeds into `job_runner.py` → `run_single_reanalysis()`. The new generic version must return a DataFrame with DatetimeIndex and `'value'` column — same contract as today.
- `app.py:render_step_upload()` calls `build_model_df()` after the user clicks Next. The new version will pass `date_col` and `value_col` from session state.
- `visualization.py` uses `UNITS[variable]` and `LABELS[variable]` — both are dicts with hardcoded keys (`discharge`, `TN`, `TP`). The bridge or pipeline call will need to handle unknown variable names gracefully (e.g., empty string fallback for units, column name as label fallback).

</code_context>

<specifics>
## Specific Ideas

- The `_best_guess_index()` helper in `app.py` should be applied to the new date dropdown to auto-suggest common date column names (`date`, `time`, `datetime`, `simdate`, `timestamp`).
- The new `build_model_df_generic(uploaded_file, date_col, value_col, variable_name)` function should replace `build_model_df()` — takes explicit column parameters instead of assuming column names.
- The variable selectbox `["discharge", "TN", "TP"]` on Step 0 should be removed entirely; the variable name is now derived from the selected value column name.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-variable runs** — User wanted to select multiple value columns and run reanalysis on all of them in one job, each with its own observation CSV. Deferred: the observation CSV mapping complexity (one obs file per variable) makes this a separate milestone. Start with single-variable, validate the flow, then extend.
- **Auto-detect date column** — App automatically identifies the datetime column so user only has to pick the value column. Deferred to keep Phase 1 changes minimal; the `_best_guess_index()` pre-selection provides most of the benefit already.

</deferred>

---
*Context gathered: 2026-03-29*
*Next step: `/gsd:plan-phase 1`*
