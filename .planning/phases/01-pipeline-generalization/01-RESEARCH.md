# Phase 01: Pipeline Generalization - Research

**Researched:** 2026-03-29
**Updated:** 2026-03-29 (re-verified against live codebase; all findings remain accurate)
**Domain:** Streamlit UI refactoring — dynamic column selection, CSV preview, bridge-layer generalization
**Confidence:** HIGH (all findings derived from direct code inspection of the live codebase; no external library speculation needed)

---

## Summary

This phase removes three tightly coupled hardcoded assumptions from the Streamlit dashboard's Step 0 and bridge layer, replacing them with a dynamic column-selection flow. The pipeline core (`src/pipeline.py`) is already generic and is not touched. The work is entirely in two files: `Reanalysis_Dashboard/pipeline_bridge.py` (add one new function, one new helper) and `Reanalysis_Dashboard/app.py` (rework `render_step_upload()` and update `_start_job()`).

The three coupling points are: (1) `pipeline_bridge.build_model_df()` hardcodes `SimDate/Flow/TN/TP` column names; (2) `app.py` Step 0 validates uploaded model CSVs against that same fixed set; (3) the variable selectbox is a static `["discharge", "TN", "TP"]` list. All three must change together or the app silently picks the wrong column or crashes mid-run with a `KeyError`.

The approved UI-SPEC and CONTEXT.md leave very little discretion — column selection pattern, preview widget choice (`st.dataframe`), session state keys (`model_date_col`, `model_value_col`), and `_best_guess_index` auto-hint candidates are all specified. The planner's job is to sequence the four discrete file-edit tasks in the correct dependency order.

**Current state (re-verified 2026-03-29):** Both source files remain in their pre-Phase-1 state. `pipeline_bridge.py` does NOT yet have `get_csv_numeric_columns`, `get_csv_preview`, or `build_model_df_generic`. `app.py` still has the `SimDate/Flow/TN/TP` validation, the `["discharge", "TN", "TP"]` selectbox, and the old `build_model_df()` call in `_start_job()`. Plans 01-01 and 01-02 are written and ready to execute.

**Primary recommendation:** Implement changes in dependency order — bridge new functions first (Plan 01), app.py UI and wire-up second (Plan 02). Each plan is independently testable before the next.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Step 0 shows two dropdowns for the model CSV — one for the date column, one for the value column. Both are populated from the uploaded CSV's headers.
- **D-02:** Single-variable per run only. User selects one date column + one value column. Multi-variable is out of scope for Phase 1.
- **D-03:** The observation CSV column mapping already exists in the current Step 1 flow and does not need to be redesigned — only the model CSV side is new.
- **D-04:** The selected value column name is used as the variable label throughout: output filenames, log messages, and UI labels. No separate "display name" field.
- **D-05:** Preview appears inline on Step 0, directly below each upload widget, as soon as a file is uploaded (before the user configures columns or clicks Next).
- **D-06:** Preview shows 5 rows. Both model CSV and observation CSV get their own preview.
- **D-07:** Preview is display-only. No editing.
- **D-08:** `src/pipeline.py` and all modules under `src/` are not touched in Phase 1. The generalization is entirely in `Reanalysis_Dashboard/pipeline_bridge.py` and `Reanalysis_Dashboard/app.py`.
- **D-09:** `data_loader.py` in `src/` is used only by Jupyter notebooks — no changes needed.
- **D-10:** `pipeline_bridge.build_obs_df_dedicated()` already accepts arbitrary `date_col` / `value_col` — reuse as-is.

### Claude's Discretion
- How to handle the UploadedFile buffer for preview (need `seek(0)` after reading) — standard pattern already established in `get_csv_columns()`.
- Whether to use `st.dataframe()` or `st.table()` for the preview display. (UI-SPEC resolves this: use `st.dataframe` — faster render, horizontally scrollable.)
- Exact wording of column dropdown labels. (UI-SPEC resolves this: "Date column" and "Value column (variable to reanalyse)".)

### Deferred Ideas (OUT OF SCOPE)
- **Multi-variable runs** — Deferred: one obs file per variable mapping complexity.
- **Auto-detect date column** — Deferred to keep Phase 1 changes minimal; `_best_guess_index()` pre-selection provides most of the benefit.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UPLOAD-01 | User can upload a model CSV and an observation CSV from their local machine | Already implemented; this requirement is about preserving the upload widget while removing the hardcoded column validation that currently blocks arbitrary CSVs. |
| UPLOAD-02 | User can select the date column and target variable column from dropdowns auto-populated from uploaded CSV headers (model CSV) and from uploaded observation CSV headers | Requires adding `get_csv_numeric_columns()` helper to bridge and two new `st.selectbox` widgets in Step 0. The `get_csv_columns()` + `_best_guess_index()` pattern for auto-hint is already established. |
| UPLOAD-03 | User can preview the first rows of each uploaded CSV before proceeding to run | Requires reading 5 rows from the uploaded file buffer and rendering with `st.dataframe()`. The `io.BytesIO + seek(0)` buffer pattern is already established in `pipeline_bridge.py`. |
| REL-02 | Pipeline accepts arbitrary CSV column names for both model and observation inputs — not hardcoded to SimDate/Flow/TN/TP | Requires replacing `build_model_df()` with `build_model_df_generic(uploaded_file, date_col, value_col)`, removing the `required = {"SimDate", "Flow", "TN", "TP"}` validation in app.py, and updating `_start_job()` to pass `model_date_col` and `model_value_col` from session state. |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 1 |
|-----------|-------------------|
| Python + Streamlit — no framework changes | All UI work uses Streamlit native widgets only; no React, no HTML injection |
| All public functions use `snake_case` | New bridge functions: `get_csv_numeric_columns`, `get_csv_preview`, `build_model_df_generic` |
| NumPy-style docstrings on all public functions | New functions require Parameters/Returns docstring blocks |
| `encoding="utf-8-sig"` on all CSV reads | All new `pd.read_csv()` calls in `pipeline_bridge.py` must include `encoding="utf-8-sig"` |
| `io.BytesIO(uploaded_file.read())` + `uploaded_file.seek(0)` pattern | Every new CSV read in bridge must follow this pattern; no exceptions |
| No `try/except` blocks in pipeline src modules | Does not apply to `pipeline_bridge.py` or `app.py` — those already use try/except |
| No build system — execution via Jupyter notebooks | Not applicable to dashboard changes |
| GSD workflow enforcement | Changes must go through execute-phase workflow |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Streamlit | 1.55.0 (installed, confirmed) | UI framework — all widgets, session state, file upload | Locked by project constraint; no framework changes |
| pandas | 2.3.2 (installed, confirmed) | CSV reading, DataFrame construction, DatetimeIndex | All data handling in bridge uses pandas |
| Python | 3.13.7 | Runtime | Locked by project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| io (stdlib) | — | `io.BytesIO` for buffer wrapping | Every CSV read in bridge to avoid exhausting UploadedFile |
| pathlib (stdlib) | — | Path resolution | Already used in `pipeline_bridge.py` import setup |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `st.dataframe()` for preview | `st.table()` | `st.table` is static HTML with no scroll; `st.dataframe` is horizontally scrollable — required for wide CSVs. UI-SPEC mandates `st.dataframe`. |
| `st.selectbox` for column dropdowns | `st.radio` | Selectbox is appropriate for 2+ items from a list; radio is for small fixed option sets. Dropdowns can grow to 20+ columns. |

**No installation needed.** All required packages are already installed and listed in `Reanalysis_Dashboard/requirements.txt`.

---

## Architecture Patterns

### Recommended File-Edit Sequence

```
Wave 1: Foundation (no risk to existing working path)
  pipeline_bridge.py  ← add build_model_df_generic(), get_csv_numeric_columns(), get_csv_preview()
  tests/              ← create synthetic_model.csv and synthetic_obs.csv

Wave 2: UI + Wire-up (depends on Wave 1 bridge functions)
  app.py              ← rework render_step_upload() Step 0
  app.py              ← update _start_job() to use build_model_df_generic()
  app.py              ← update _init_state() for new session state keys

Wave 3: Validation
  Smoke-test with synthetic non-Peace-River CSV end-to-end
```

### Pattern 1: Buffer-Safe CSV Read (already established — follow exactly)

**What:** Read a Streamlit `UploadedFile` without consuming the buffer permanently.
**When to use:** Every CSV read operation in `pipeline_bridge.py`.

```python
# Source: existing pipeline_bridge.py lines 32-37 — replicate this pattern
def get_csv_columns(uploaded_file) -> list:
    buf = io.BytesIO(uploaded_file.read())
    cols = pd.read_csv(buf, nrows=0, encoding="utf-8-sig").columns.tolist()
    uploaded_file.seek(0)
    return cols
```

Apply the same `io.BytesIO(uploaded_file.read())` + `uploaded_file.seek(0)` pattern to both the new preview helper and `build_model_df_generic()`.

### Pattern 2: Best-Guess Pre-selection (already established — reuse)

**What:** Auto-highlight the most plausible dropdown option by matching column names to a candidate list.
**When to use:** Both new model CSV dropdowns (date column, value column).

```python
# Source: existing app.py lines 69-75 — reuse as-is
def _best_guess_index(cols: list, candidates: list) -> int:
    lower_cols = [c.lower() for c in cols]
    for candidate in candidates:
        if candidate in lower_cols:
            return lower_cols.index(candidate)
    return 0
```

Date column candidates: `["date", "time", "datetime", "simdate", "timestamp"]`
Value column candidates: `["value", "flow", "discharge", "streamflow"]`

### Pattern 3: Numeric Column Filter (new helper needed)

**What:** Return only columns that contain numeric (float/int) data, for populating the value column dropdown.
**When to use:** Populating the "Value column" selectbox so users don't accidentally select a date string or ID column as their target variable.

```python
# New function to add to pipeline_bridge.py
def get_csv_numeric_columns(uploaded_file) -> list:
    """Return column names that contain numeric data."""
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, nrows=100, encoding="utf-8-sig")
    uploaded_file.seek(0)
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return numeric if numeric else df.columns.tolist()
```

Note: If a CSV has only 1 numeric column, the dropdown will still show — user sees the correct pre-selection and cannot accidentally pick a non-numeric column.

Edge case: if `get_csv_numeric_columns()` returns an empty list (CSV has no numeric columns — i.e., a malformed file), fall back to showing all columns. The pipeline will fail gracefully at the `pd.to_numeric(..., errors="coerce")` step in `build_model_df_generic`.

### Pattern 4: Generic Model DataFrame Builder (new function)

**What:** Replace `build_model_df()` with a function that takes explicit column selections.
**When to use:** Called from `_start_job()` after the user has selected columns.
**Contract:** Must return `pd.DataFrame` with `DatetimeIndex` and single `"value"` column (float64). Same output contract as today's `build_model_df()[variable]`.

```python
# New function to add to pipeline_bridge.py
def build_model_df_generic(uploaded_file, date_col: str, value_col: str) -> pd.DataFrame:
    """
    Parse a model CSV with arbitrary column names.

    Parameters
    ----------
    uploaded_file : UploadedFile
    date_col : str  — column name for the datetime values
    value_col : str — column name for the numeric target variable

    Returns
    -------
    pd.DataFrame with DatetimeIndex and 'value' column (float64).
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, encoding="utf-8-sig")
    uploaded_file.seek(0)
    df["time"] = pd.to_datetime(df[date_col], format="mixed", dayfirst=False)
    df["value"] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.set_index("time")[["value"]].sort_index()
    return df
```

### Pattern 5: CSV Preview Helper

**What:** Read the first N rows for display without consuming the buffer.
**When to use:** In `render_step_upload()` immediately after a file is uploaded.

```python
# New function to add to pipeline_bridge.py
def get_csv_preview(uploaded_file, nrows: int = 5) -> pd.DataFrame:
    """Return first nrows of an uploaded CSV as a DataFrame for display."""
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, nrows=nrows, encoding="utf-8-sig")
    uploaded_file.seek(0)
    return df
```

### Pattern 6: visualization.py Fallback (already in place — no changes needed)

**What:** Allow `visualization.py` to handle any `variable` string, not just `"discharge"`, `"TN"`, `"TP"`.
**Verification:** Direct inspection of `Sprint_2/Reanalysis_Pipeline/src/visualization.py` lines 22-23 confirms:

```python
# Source: visualization.py lines 22-23 — already uses .get() on both dicts
unit = UNITS.get(variable, "")       # empty string for unknown units
label = LABELS.get(variable, variable)   # column name itself as fallback label
```

All three plot functions (`plot_comparison`, `plot_ci_area`, `plot_model_vs_observed`) use `.get()` with fallbacks. An unknown variable name like `"streamflow_cms"` produces plots with empty unit strings in axis labels (`"streamflow_cms ()"`) — not crashes. **No changes needed to `visualization.py`.**

### Pattern 7: Session State for New Keys

**What:** Add `model_date_col` and `model_value_col` to the default session state in `_init_state()`.
**When to use:** `_init_state()` in `app.py` — called once on first render.

```python
# Add to the defaults dict in _init_state() — use None (not "") as initial value
"model_date_col": None,
"model_value_col": None,
```

The existing `"variable": "discharge"` key should be changed to `"variable": None`. The `variable` key is set dynamically in `_start_job()` before calling `launch_job()`.

### Session State Key Rename Impact

The existing `st.session_state.variable` key is referenced in:
- `_init_state()` (line 52) — set to `"discharge"` default
- `render_step_upload()` (lines 128-134) — selectbox reads/writes it
- `_start_job()` (line 375, 400) — passed to `launch_job()` as `variable=`
- `render_step_results()` (line 470, 488-511) — used for plot filenames and CSV download names

After Phase 1: In `_start_job()`, assign `st.session_state.variable = st.session_state.model_value_col` before calling `launch_job()`. This single line keeps all downstream consumers correct without touching `render_step_results()`.

### Anti-Patterns to Avoid

- **Do not validate specific column names:** The new Step 0 must NOT check for `SimDate`, `Flow`, `TN`, or `TP`. Only verify the file is parseable as CSV (catches truly broken uploads).
- **Do not store DataFrames in session_state:** Store only the `UploadedFile` reference and column name strings. Parse to DataFrame only in `_start_job()`.
- **Do not call `build_model_df()` (old function) from `_start_job()`:** It will be left in place for safety but `_start_job()` must use the new `build_model_df_generic()`.
- **Do not remove `build_model_df()` in this phase:** Removing it creates unnecessary risk. Leave it in place, add the generic version alongside with a legacy comment.
- **Do not initialize `model_date_col` / `model_value_col` as `""`:** Use `None`. The `can_proceed` gate checks `is not None`; if these are `""`, the gate stays closed even after selectboxes render with valid values.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Column type detection | Custom dtype-sniffing loop | `pd.api.types.is_numeric_dtype(series)` | Handles int, float, nullable types correctly; one call |
| Date column parsing | Custom regex date detector | `pd.to_datetime(series, format="mixed", dayfirst=False)` | Already used in bridge; handles ISO 8601, M/D/Y, mixed formats |
| Fuzzy column name matching | Levenshtein distance or regex | `_best_guess_index()` with exact lowercase match | Already written; sufficient for common date/value column names |
| File buffer management | Custom buffer tracking class | `io.BytesIO(uploaded_file.read())` + `uploaded_file.seek(0)` | Already established pattern throughout bridge |
| Preview widget | Custom HTML table | `st.dataframe(df, hide_index=False)` | Built-in, horizontally scrollable, no extra code |

**Key insight:** Every low-level utility this phase needs is already written in `pipeline_bridge.py` or pandas. This phase adds functions that compose existing utilities, not new utilities.

---

## Runtime State Inventory

Step 2.5 SKIPPED — this phase is a UI refactor/generalization, not a rename or migration. No stored data, live service config, OS-registered state, secrets, or build artifacts reference Peace River column names at runtime. The Peace River column names (`SimDate`, `Flow`, `TN`, `TP`) exist only as Python string literals in source code, not in any database, cache, or OS registration.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.13.7 | — |
| Streamlit | UI framework | Yes | 1.55.0 | — |
| pandas | CSV parsing, DataFrame | Yes | 2.3.2 | — |
| numpy | Numeric operations | Yes | 2.3.2 | — |
| TensorFlow | LSTM pipeline (not Phase 1 scope) | Yes | 2.20.0 | — |

**No missing dependencies.** All required packages are installed and importable. Phase 1 changes do not introduce any new dependencies.

---

## Common Pitfalls

### Pitfall 1: Three Coupling Points Must Change Together

**What goes wrong:** If `app.py` column validation is loosened without updating `build_model_df` in `_start_job()`, the app accepts arbitrary CSVs but then crashes mid-run with `KeyError: 'Flow'` because `_start_job()` still calls the old `build_model_df()`.

**Why it happens:** The three coupling locations (bridge function, app validation, variable selectbox) are easy to update one at a time when testing locally — but the failure only surfaces at job launch time, not at upload time.

**How to avoid:** Update all three in the same Wave 2 edit session and smoke-test immediately with a synthetic CSV before committing.

**Warning signs:** `KeyError: 'Flow'` or `KeyError: 'SimDate'` in job ERROR traceback when a non-Peace-River CSV is used.

---

### Pitfall 2: UploadedFile Buffer Exhaustion

**What goes wrong:** If `get_csv_preview()` reads the buffer and the code path does not call `uploaded_file.seek(0)` after, subsequent calls to `get_csv_columns()` or `get_csv_numeric_columns()` in the same render cycle return empty data.

**Why it happens:** The `UploadedFile` is a `BytesIO`-backed buffer. `read()` advances the cursor to EOF. `io.BytesIO(uploaded_file.read())` pattern copies the bytes into a new buffer, leaving the original cursor at EOF.

**How to avoid:** Every function in `pipeline_bridge.py` that reads an `UploadedFile` must call `uploaded_file.seek(0)` as the last line before returning. The preview helper must follow this same contract.

**Warning signs:** `EmptyDataError: No columns to parse from file` in the progress log or preview area.

---

### Pitfall 3: Selectbox `key=` Conflicts with Session State Initial Value

**What goes wrong:** If `_init_state()` sets `"model_date_col"` and `"model_value_col"` to `""` (empty string), Streamlit's selectbox `key=` sync will not override the empty string with a valid column name on first render. The `can_proceed` gate stays `False` indefinitely.

**Why it happens:** Streamlit selectbox with `index` parameter controls the default selection — but if the `key` is already in session_state with a value that is not in the options list, Streamlit uses the `index` parameter. However, the `can_proceed` check `!= ""` fails because `""` is not `None`.

**How to avoid:** Initialize `model_date_col` and `model_value_col` to `None` in `_init_state()`. Use `st.session_state.get("model_date_col") is not None` in the `can_proceed` check. Streamlit auto-populates the key to the column name at `index` when the widget renders, replacing `None`.

**Warning signs:** "Next" button stays disabled even after file upload and dropdowns appear.

---

### Pitfall 4: `variable` Session State Key Used Downstream in Results

**What goes wrong:** `render_step_results()` uses `st.session_state.variable` to construct plot filenames (e.g., `f"{variable}_Comparison.png"`) and CSV download names. If `_start_job()` does not set `variable = model_value_col`, the results page looks for `discharge_Comparison.png` even though the pipeline wrote `streamflow_cms_Comparison.png`.

**Why it happens:** `variable` is used in two places with different concerns — as the key passed to `run_single_reanalysis()` (which determines output filenames) and as the key read by `render_step_results()` (which determines which files to display).

**How to avoid:** In `_start_job()`, immediately after building `model_df`, assign `st.session_state.variable = st.session_state.model_value_col`. This single line keeps all downstream consumers correct without changes to `render_step_results()`.

**Warning signs:** Results page shows "Plot not generated" for all three plots. Download buttons show "Not found" for all CSVs.

---

### Pitfall 5: visualization.py Fallback Already in Place (no action needed)

**What looks like a problem but isn't:** `visualization.py` uses `UNITS` and `LABELS` dicts keyed on `"discharge"`, `"TN"`, `"TP"`. This sounds like it needs changing.

**Reality (verified by direct inspection, lines 22-23 of visualization.py):** All three plot functions already use `.get(variable, "")` for units and `.get(variable, variable)` for labels. An unknown variable name like `"streamflow_cms"` produces plots with empty unit strings in axis labels — not crashes. **No changes to `visualization.py` are needed or should be made in Phase 1.**

---

## Code Examples

Verified patterns from existing codebase (all HIGH confidence — direct code inspection):

### Existing Buffer-Safe Read Pattern (replicate for new helpers)

```python
# Source: pipeline_bridge.py lines 32-37 (confirmed)
def get_csv_columns(uploaded_file) -> list:
    buf = io.BytesIO(uploaded_file.read())
    cols = pd.read_csv(buf, nrows=0, encoding="utf-8-sig").columns.tolist()
    uploaded_file.seek(0)
    return cols
```

### Existing Best-Guess Index Helper (reuse as-is)

```python
# Source: app.py lines 69-75 (confirmed)
def _best_guess_index(cols: list, candidates: list) -> int:
    lower_cols = [c.lower() for c in cols]
    for candidate in candidates:
        if candidate in lower_cols:
            return lower_cols.index(candidate)
    return 0
```

### Existing _start_job() Model Block (lines 372-375 — REPLACE this block in Plan 02)

```python
# Source: app.py lines 372-375 (confirmed — current pre-Phase-1 state)
# Build model DataFrame for the selected variable
st.session_state.model_file.seek(0)
model_dfs = pipeline_bridge.build_model_df(st.session_state.model_file)
model_df = model_dfs[st.session_state.variable]

# REPLACE WITH (Plan 02):
st.session_state.model_file.seek(0)
model_df = pipeline_bridge.build_model_df_generic(
    st.session_state.model_file,
    date_col=st.session_state.model_date_col,
    value_col=st.session_state.model_value_col,
)
st.session_state.variable = st.session_state.model_value_col  # keep downstream in sync
```

### st.dataframe API (Streamlit 1.55.0, confirmed by introspection)

```python
# Confirmed parameters in 1.55.0:
st.dataframe(
    data=preview_df,          # pd.DataFrame
    hide_index=False,         # bool | None
    use_container_width=None, # bool | None (defaults to stretch)
)
# width parameter defaults to 'stretch' — no explicit width needed
```

### st.selectbox with Key (Streamlit 1.55.0, confirmed)

```python
# Confirmed: key parameter syncs to st.session_state
st.selectbox(
    "Date column",
    options=cols,
    index=_best_guess_index(cols, ["date", "time", "datetime", "simdate", "timestamp"]),
    key="model_date_col",
)
# After this widget renders, st.session_state.model_date_col == selected column name
```

### Existing _init_state Defaults (lines 46-63 — requires partial update in Plan 02)

```python
# Source: app.py lines 46-63 (confirmed current state)
defaults = {
    "step": 0,
    "model_file": None,
    "obs_file": None,
    "obs_columns": [],
    "obs_config": {},
    "variable": "discharge",   # ← change to None
    "station_name": "MyStation",
    "hyperparams": DEFAULT_HYPERPARAMS.copy(),
    "seed": 42,
    "job_result": None,
    "progress_queue": None,
    "job_thread": None,
    "progress_log": [],
    # ADD:
    # "model_date_col": None,
    # "model_value_col": None,
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `st.dataframe(use_column_width=True)` | `st.dataframe(use_container_width=True)` or default `width='stretch'` | Streamlit ~1.20 | Old parameter deprecated; confirmed 1.55.0 uses `use_container_width` |
| `st.beta_columns()` | `st.columns()` | Streamlit 1.0 | Stable; already used correctly in existing code |

**Deprecated / not applicable:**
- `st.table()`: Use `st.dataframe()` for previews — horizontally scrollable, no deprecation risk, required by UI-SPEC.

---

## Open Questions

1. **What happens if the model CSV has no numeric columns at all?**
   - What we know: `get_csv_numeric_columns()` returns `[]`; the fallback returns all columns; the value dropdown shows all columns.
   - Resolution: Show `st.warning("No numeric columns detected — verify your value column selection carefully.")` when the fallback triggers. Implemented in Plan 02 Task 1.

2. **Should `build_model_df()` (old function) be left in place or deprecated with a comment?**
   - Resolution: Leave it in place with a `# Legacy: Peace River only. Use build_model_df_generic() for arbitrary CSVs.` comment. Do not delete.

3. **What does `can_proceed` look like when `key=` widgets auto-manage session state?**
   - Resolution: Initialize `model_date_col` and `model_value_col` to `None` in `_init_state()`. Use `st.session_state.get("model_date_col") is not None` in `can_proceed`. On first render, the widget at `index=0` initializes the key to the first column name, so `can_proceed` becomes `True` as soon as both files are uploaded and both dropdowns have rendered.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected — no pytest.ini, no test/ directory, no test files in repo |
| Config file | None |
| Quick run command | Manual smoke-test: launch `streamlit run Reanalysis_Dashboard/app.py` and upload synthetic CSV |
| Full suite command | Manual end-to-end: upload synthetic CSV through all 5 wizard steps |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UPLOAD-01 | Model CSV uploads without format rejection | smoke | Manual — upload synthetic CSV with non-Peace-River column names; verify no "Missing required columns" error | No automated test |
| UPLOAD-02 | Date and value dropdowns populated from uploaded CSV headers | smoke | Manual — verify dropdowns show actual CSV columns, not `["discharge", "TN", "TP"]` | No automated test |
| UPLOAD-03 | 5-row preview appears below each upload widget | smoke | Manual — verify `st.dataframe` preview renders immediately after upload | No automated test |
| REL-02 | End-to-end run completes without KeyError on non-Peace-River CSV | integration | Manual — run full pipeline with synthetic CSV `(timestamp, streamflow_cms)` and verify output CSVs contain `streamflow_cms` in filenames | No automated test |

### Synthetic Test CSV (for smoke-testing — created in Plan 01 Task 0)

```
timestamp,streamflow_cms,nitrate_mgl
2010-01-01 00:00:00,12.5,0.45
2010-01-01 06:00:00,13.1,0.48
...
```

Required properties: date column named `timestamp` (not `SimDate`), numeric column named `streamflow_cms` (not `Flow`). A second synthetic observation CSV with two columns: `obs_date`, `nitrate_value`.

### Sampling Rate

- **Per task commit:** Manual — launch app, upload test CSV, verify Step 0 renders correctly
- **Per wave merge:** Full smoke-test — upload test CSVs and run full pipeline through all 5 steps
- **Phase gate:** Full end-to-end run with synthetic non-Peace-River CSV produces output files with correct variable name in filenames

### Wave 0 Gaps

- [ ] No automated test infrastructure exists — all validation is manual. Acceptable per project scope (Jupyter notebook / local research tool). Consider adding a `test_bridge.py` with pytest unit tests for `build_model_df_generic()` in a future phase.
- [ ] Synthetic test CSV files need to be created: `tests/synthetic_model.csv` and `tests/synthetic_obs.csv`. Created in Plan 01, Task 0.

---

## Sources

### Primary (HIGH confidence)

- Direct inspection of `Reanalysis_Dashboard/pipeline_bridge.py` — all function signatures, buffer patterns, encoding usage (re-verified 2026-03-29: file unchanged from original research)
- Direct inspection of `Reanalysis_Dashboard/app.py` — all coupling points, session state structure, `_best_guess_index`, `_start_job()` flow (re-verified 2026-03-29: file unchanged, still in pre-Phase-1 state)
- Direct inspection of `Reanalysis_Dashboard/job_runner.py` — `launch_job()` signature confirms `variable` parameter name
- Direct inspection of `Sprint_2/Reanalysis_Pipeline/src/visualization.py` lines 22-23 — confirmed `.get(variable, "")` and `.get(variable, variable)` fallback already in place on all UNITS/LABELS lookups
- `.planning/phases/01-pipeline-generalization/01-CONTEXT.md` — locked decisions D-01 through D-10
- `.planning/phases/01-pipeline-generalization/01-UI-SPEC.md` — widget contract, session state keys, copy, layout
- Python introspection of Streamlit 1.55.0: `inspect.signature(st.dataframe)`, `inspect.signature(st.selectbox)` — confirmed available parameters

### Secondary (MEDIUM confidence)

- `.planning/REQUIREMENTS.md` — requirement text for UPLOAD-01, UPLOAD-02, UPLOAD-03, REL-02
- `.planning/STATE.md` — project-level decisions and known blockers

### Tertiary (LOW confidence)

- None — all claims are grounded in direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed by `pip show streamlit`, direct import inspection, and package version outputs
- Architecture patterns: HIGH — derived from direct code inspection of all four modified files; zero speculation
- Pitfalls: HIGH — all pitfalls grounded in specific file/line citations from the existing codebase
- Validation: MEDIUM — no automated tests exist; validation is manual smoke-testing

**Research date:** 2026-03-29
**Re-verified:** 2026-03-29 — both source files confirmed unchanged from original research; all code patterns, line numbers, and architectural findings remain accurate
**Valid until:** 2026-04-28 (30 days; Streamlit and pandas APIs are stable at these versions)
