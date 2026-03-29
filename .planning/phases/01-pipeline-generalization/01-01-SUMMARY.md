---
phase: 01-pipeline-generalization
plan: "01"
subsystem: api
tags: [pandas, streamlit, pipeline_bridge, csv, dataframe]

# Dependency graph
requires: []
provides:
  - "get_csv_numeric_columns: returns numeric column names from any uploaded CSV"
  - "get_csv_preview: returns first N rows of uploaded CSV as DataFrame"
  - "build_model_df_generic: parses arbitrary date_col/value_col into DatetimeIndex + 'value' DataFrame"
  - "tests/synthetic_model.csv: non-Peace-River sub-daily model CSV for smoke testing"
  - "tests/synthetic_obs.csv: sparse monthly observation CSV for smoke testing"
affects:
  - 01-02-pipeline-generalization

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "buffer-safe CSV read: io.BytesIO(uploaded_file.read()) + uploaded_file.seek(0) + encoding=utf-8-sig"
    - "generic DataFrame contract: DatetimeIndex named 'time' + single 'value' column (float64)"

key-files:
  created:
    - tests/synthetic_model.csv
    - tests/synthetic_obs.csv
  modified:
    - Reanalysis_Dashboard/pipeline_bridge.py

key-decisions:
  - "Reanalysis_Dashboard submodule gitlink absorbed into main repo as individually tracked files (no .gitmodules or separate .git present)"
  - "build_model_df_generic placed after build_model_df (not replacing it) — backward compatibility preserved"
  - "get_csv_numeric_columns uses nrows=100 for dtype detection — sufficient and fast"

patterns-established:
  - "Buffer-safe pattern: io.BytesIO(uploaded_file.read()) then uploaded_file.seek(0) — all CSV helpers follow this"
  - "Generic DataFrame contract: DatetimeIndex named 'time' + 'value' column — matches launch_job() model_df expectation"

requirements-completed: [UPLOAD-02, UPLOAD-03, REL-02]

# Metrics
duration: 4min
completed: 2026-03-29
---

# Phase 01 Plan 01: Pipeline Bridge Generic Helpers Summary

**Three buffer-safe pipeline_bridge.py helpers added (get_csv_numeric_columns, get_csv_preview, build_model_df_generic) plus synthetic test CSVs with non-Peace-River column names, decoupling the bridge layer from hardcoded SimDate/Flow/TN/TP assumptions**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-29T22:50:55Z
- **Completed:** 2026-03-29T22:55:08Z
- **Tasks:** 3 (Task 0, Task 1, Task 2)
- **Files modified:** 3

## Accomplishments
- Created synthetic test CSVs with arbitrary column names (timestamp, streamflow_cms, nitrate_mgl, obs_date, nitrate_value)
- Added get_csv_numeric_columns and get_csv_preview following exact buffer-safe pattern of existing helpers
- Added build_model_df_generic with identical output contract to build_model_df()[variable] for compatibility with launch_job()
- Absorbed Reanalysis_Dashboard gitlink submodule into properly tracked files in main repo

## Task Commits

Each task was committed atomically:

1. **Task 0: Create synthetic test CSV files** - `729f753` (chore)
2. **Task 1: Add get_csv_numeric_columns and get_csv_preview helpers** - `f0416eb` (feat)
3. **Task 2: Add build_model_df_generic function** - `b7545e9` (feat)

## Files Created/Modified
- `Reanalysis_Dashboard/pipeline_bridge.py` - Three new generic helper functions added; build_model_df annotated as legacy
- `tests/synthetic_model.csv` - 12 rows of sub-daily 6-hour data: timestamp, streamflow_cms, nitrate_mgl
- `tests/synthetic_obs.csv` - 3 sparse monthly observations: obs_date, nitrate_value

## Decisions Made
- `Reanalysis_Dashboard` was stored as a gitlink (mode 160000) submodule pointer in the main repo without `.gitmodules` or a separate `.git` directory. Removed the gitlink and re-added files as individual tracked entries so pipeline_bridge.py changes can be committed normally.
- `build_model_df_generic` placed directly after existing `build_model_df` with a legacy comment on the old function — no existing logic modified.
- `get_csv_numeric_columns` reads only 100 rows for dtype detection (fast) and falls back to all columns if no numeric types detected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resolved Reanalysis_Dashboard gitlink preventing file commits**
- **Found during:** Task 1 (adding pipeline_bridge.py helpers)
- **Issue:** `Reanalysis_Dashboard` tracked as git submodule gitlink (mode 160000) — `git add Reanalysis_Dashboard/pipeline_bridge.py` raised fatal error "Pathspec is in submodule"
- **Fix:** Ran `git rm --cached Reanalysis_Dashboard` to remove the gitlink, then `git add Reanalysis_Dashboard/` to stage all files as regular tracked files. No `.gitmodules` or separate `.git` dir existed, so this was safe.
- **Files modified:** Reanalysis_Dashboard/.gitignore, app.py, job_runner.py, pipeline_bridge.py, requirements.txt (all newly tracked)
- **Verification:** `git status` shows files as individually staged/committed
- **Committed in:** f0416eb (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking issue)
**Impact on plan:** Necessary infrastructure fix — no scope creep, no logic changes to existing files.

## Issues Encountered
- Reanalysis_Dashboard gitlink: the directory existed on disk with full source files but git treated it as a submodule pointer. Since there was no `.gitmodules` file and no separate `.git`, the files were absorbed into the main repo index. This is a one-time fix; all future commits to these files work normally.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three generic helpers are importable from pipeline_bridge: `get_csv_numeric_columns`, `get_csv_preview`, `build_model_df_generic`
- Legacy `build_model_df`, `get_csv_columns`, `get_csv_unique_values` remain unchanged
- Synthetic test CSVs ready for Plan 02 smoke testing
- No blockers for Plan 02 (Streamlit UI column dropdowns and preview wiring)

---
*Phase: 01-pipeline-generalization*
*Completed: 2026-03-29*

## Self-Check: PASSED

- FOUND: tests/synthetic_model.csv
- FOUND: tests/synthetic_obs.csv
- FOUND: Reanalysis_Dashboard/pipeline_bridge.py
- FOUND: .planning/phases/01-pipeline-generalization/01-01-SUMMARY.md
- FOUND: commit 729f753 (Task 0 — synthetic CSVs)
- FOUND: commit f0416eb (Task 1 — get_csv_numeric_columns + get_csv_preview)
- FOUND: commit b7545e9 (Task 2 — build_model_df_generic)
