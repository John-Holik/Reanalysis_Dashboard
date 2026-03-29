# Architecture Patterns

**Domain:** Scientific data assimilation pipeline with web UI — LSTM + EnKF reanalysis
**Researched:** 2026-03-29
**Confidence:** HIGH (based on direct codebase analysis of all layers)

---

## Current State (Baseline)

Before proposing refactored architecture, the precise coupling problems must be named, because each one has a distinct resolution strategy.

### Coupling Inventory

| Location | Hardcoded Assumption | How It Manifests |
|----------|----------------------|------------------|
| `data_loader.py:load_model_data()` | `col_map = {"discharge": "Flow", "TN": "TN", "TP": "TP"}` | Caller must pass one of three magic strings; function rejects any other value |
| `data_loader.py:check_data_availability()` | Iterates `["discharge", "TN", "TP"]` | Availability scan is hardwired to Peace River variable names |
| `pipeline_bridge.py:build_model_df()` | Reads `SimDate`, `Flow`, `TN`, `TP` by name | Breaks on any model CSV with different column names |
| `app.py:render_step_upload()` | Validates `required = {"SimDate", "Flow", "TN", "TP"}` | Rejects valid model CSVs that use different column names |
| `app.py:render_step_upload()` | `["discharge", "TN", "TP"]` variable selectbox | Variable list is static, not derived from uploaded file |
| `visualization.py:UNITS / LABELS` | Dicts keyed on `"discharge"`, `"TN"`, `"TP"` | Plot axis labels fall back to empty string for unknown variables |
| `pipeline.py:run_single_reanalysis()` | `variable` param typed as string; no domain logic | Already generic — receives pre-built DataFrames, not raw CSV paths |

**Critical observation:** `pipeline.py` itself is already generic. It accepts two DataFrames with a `value` column and a `variable` string label. The coupling is entirely in the two layers above it — data loading and the UI upload step. The algorithm core does not need to change.

---

## Recommended Architecture

### Separation of Concerns (Three Zones)

```
Zone 1: UI Layer          Zone 2: Bridge Layer       Zone 3: Pipeline Core
─────────────────────     ──────────────────────     ─────────────────────
app.py                    pipeline_bridge.py         src/pipeline.py
  - File upload           build_model_df_generic()   run_single_reanalysis()
  - Column mapping UI     build_obs_df_generic()       ← already generic
  - Job launch            run_single_reanalysis()    src/preprocessing.py
  - Progress display          (re-export)            src/lstm_model.py
  - Results display       job_runner.py              src/enkf.py
                          launch_job()               src/openloop.py
                                                     src/postprocessing.py
                                                     src/visualization.py
```

**Zone boundary rule:** Zone 1 (UI) never touches file paths or DataFrames directly. Zone 2 (Bridge) owns the translation from "user's CSV + column selections" to "normalized DataFrames with DatetimeIndex and 'value' column." Zone 3 (Pipeline Core) only sees normalized DataFrames and a `variable` label string.

This boundary is already 90% correct in the existing code. The refactor is about enforcing it consistently rather than redesigning from scratch.

---

## Component Boundaries

### Component 1: UI (app.py)

**Responsibility:** Collect user inputs. Display outputs. Drive step navigation.

**Owns:**
- Streamlit session state
- Step routing (wizard steps 0–4)
- Validation feedback to the user
- Polling loop and progress log display

**Does NOT own:**
- CSV parsing logic
- DataFrame construction
- Threading/queue setup
- Pipeline invocation

**Communicates with:** Bridge Layer only, via function calls. Never imports from `src/` directly.

**Key refactor target:** The variable selectbox must be populated dynamically from the model CSV's numeric columns, not from a hardcoded list. The model CSV column validation must drop the hardcoded `required = {"SimDate", "Flow", "TN", "TP"}` check; instead it should verify only that a datetime-parseable column exists.

---

### Component 2: Bridge Layer (pipeline_bridge.py)

**Responsibility:** Translate user-provided files + column selections into normalized DataFrames. Re-export `run_single_reanalysis` so the UI never imports from `src/` directly.

**Owns:**
- `build_model_df_generic(uploaded_file, date_col, value_col)` — reads any CSV, uses user-selected column names
- `build_obs_df_dedicated(...)` — already generic, keep as-is
- `build_obs_df_multi_station(...)` — already generic, keep as-is
- `get_csv_columns(...)` — already exists, keep as-is
- `get_csv_numeric_columns(uploaded_file)` — new helper: returns only numeric columns for the variable dropdown
- `get_csv_unique_values(...)` — already exists, keep as-is

**Does NOT own:**
- Session state
- Algorithm logic
- Threading

**Key refactor:** Replace `build_model_df()` (which hardcodes `SimDate/Flow/TN/TP`) with `build_model_df_generic(uploaded_file, date_col, value_col)`. The UI passes the user's column selections; the bridge constructs one normalized DataFrame.

**Normalized contract (output of all build_ functions):**
```
pd.DataFrame(
    index=DatetimeIndex(freq=None),   # irregular is fine; pipeline resamples
    columns=["value"],                # exactly one column, float64
)
```

---

### Component 3: Job Runner (job_runner.py)

**Responsibility:** Manage the background thread and communication channel between the thread and Streamlit's main thread.

**Owns:**
- `JobStatus` enum and `JobResult` dataclass
- `_QueueWriter` (stdout redirect)
- `launch_job()` — spawns daemon thread, returns `(JobResult, queue.Queue, Thread)`
- Thread lifecycle (start only; Streamlit polling handles join)

**Does NOT own:**
- DataFrame construction (happens before `launch_job` is called)
- Pipeline logic
- UI rendering

**Current design is correct.** The threading pattern — daemon thread, Queue for log lines, sentinel values `__DONE__` / `__ERROR__`, stdout redirect via `_QueueWriter` — is the appropriate design for this problem. The 2-second polling loop in `render_step_running()` is acceptable for a local tool with 2–10 minute jobs. No changes needed structurally.

**Why this threading pattern is correct:**
- Streamlit reruns on every interaction; state must outlive a rerun — hence storing `(result, queue, thread)` in `session_state`
- `Queue.get_nowait()` in a polling loop avoids blocking Streamlit's render cycle
- Daemon thread ensures the process exits cleanly if the user closes the browser tab mid-run
- Stdout redirect to `_QueueWriter` requires no changes to pipeline.py's `print()` calls — zero modifications to pipeline core

**One known fragility:** `sys.stdout = _QueueWriter(q)` is a process-global redirect. If TensorFlow writes to stdout from a C extension thread during LSTM training, those messages bypass the redirect. This is a monitoring fidelity issue, not a correctness issue; the pipeline still runs correctly.

---

### Component 4: Pipeline Core (src/)

**Responsibility:** Execute the LSTM + EnKF algorithm. Accept normalized DataFrames. Produce output files.

**Already generic.** `run_single_reanalysis(model_df, obs_df, variable, station_name, output_dir, hyperparams, seed)` has no hardcoded column names. It operates entirely on `df["value"]` after receiving pre-built DataFrames.

**Refactor target — visualization.py only:**
- `UNITS` and `LABELS` dicts must handle arbitrary `variable` strings. The fallback should use `variable` itself as the label and an empty units string rather than silently producing broken axis labels.
- This is a three-line change, not an architectural issue.

**No other changes needed in Zone 3.**

---

## Data Flow

### Upload → Run (Happy Path)

```
User uploads model CSV
        |
        v
get_csv_columns() → [col names] shown in UI
get_csv_numeric_columns() → [numeric cols] → variable dropdown populated
        |
User selects: date_col, value_col (model), obs CSV columns, hyperparams
        |
        v
_start_job() in app.py:
  build_model_df_generic(file, date_col, value_col) → model_df (DatetimeIndex, 'value')
  build_obs_df_*(file, ...) → obs_df (DatetimeIndex, 'value')
        |
        v
launch_job(model_df, obs_df, variable, station_name, hyperparams, seed)
  → spawns daemon Thread
  → returns (JobResult, Queue, Thread) stored in session_state
        |
        v
[Background Thread]
  sys.stdout → _QueueWriter → Queue
  run_single_reanalysis(model_df, obs_df, ...)
    resample_model_to_daily()
    align_sparse() or align_dense()
    standardize()
    build_sequences() + train_val_split()
    build_forecast_lstm() + train_forecast_lstm()
    estimate_process_noise() → Q
    compute_obs_error() → R
    run_enkf() → ensemble arrays
    run_openloop() → baseline array
    inverse_transform() × N
    compute_ci_bounds() + compute_ci_integral()
    export_results() → CSVs in tempdir
    plot_*() → PNGs in tempdir
    returns metrics dict
  Queue.put("__DONE__")
        |
        v
[Main Thread, polled every 2s]
  Queue.get_nowait() drains log lines → session_state.progress_log
  on "__DONE__" sentinel → step = 4 → st.rerun()
        |
        v
render_step_results():
  reads result.output_dir → loads PNGs, serves CSV download buttons
```

### Column Selection Flow (New vs Current)

**Current (broken for arbitrary CSVs):**
```
Upload → hardcoded validation {"SimDate","Flow","TN","TP"} → reject if missing
Variable dropdown: hardcoded ["discharge","TN","TP"]
```

**Target (generic):**
```
Upload → check only: at least one datetime-parseable column + at least one numeric column
Date column: selectbox from all columns (auto-hint: "date","time","datetime","simdate")
Value column: selectbox from numeric columns (auto-hint: "flow","value","discharge")
Variable label: text input OR use value_col name as default label
```

This is additive: the observation CSV path (steps 1–2 in the wizard) already works correctly for arbitrary CSVs. Only the model CSV path needs updating.

---

## Suggested Build Order

Dependencies flow upward — lower-numbered items must be completed before higher-numbered items can be validated end-to-end.

### 1. Generalize pipeline_bridge.py (foundation)

Add `build_model_df_generic(uploaded_file, date_col, value_col)`. Add `get_csv_numeric_columns(uploaded_file)`. Keep all existing functions; add new ones alongside. No deletions yet — old functions used by existing code paths.

**Why first:** Everything else depends on the bridge being able to handle arbitrary columns. This is a pure addition with no risk of breaking the existing working path.

### 2. Generalize visualization.py fallbacks (low-risk, independent)

Replace hardcoded `UNITS` / `LABELS` dict lookups with `.get(variable, variable)` fallbacks. Four-line change. Can be done in parallel with step 1.

**Why second:** Without this, a successful pipeline run on an arbitrary variable produces plots with missing axis labels. Short to fix; unblocks demo reliability.

### 3. Update app.py Step 0 (model CSV upload) to use generic bridge

Replace hardcoded column validation with dynamic date/value column selectors. Populate variable dropdown from numeric columns (or use a text label field). Update `_start_job()` to call `build_model_df_generic()` instead of `build_model_df()`.

**Why third:** Depends on bridge helpers from step 1. This is the highest-visibility change — it's the first thing a user sees. Test with the existing Peace River CSVs first, then a synthetic CSV with different column names.

### 4. Smoke-test end-to-end with a non-Peace-River CSV

Create a minimal synthetic CSV (date column, one numeric column) and run through the full wizard. This validates steps 1–3 together.

**Why fourth:** Integration point. Catches interactions between the generalized bridge, updated UI, and pipeline core that unit tests might miss.

### 5. Packaging (Docker or installer) — defer until core works

The packaging question (Docker vs PyInstaller/installer) is independent of the generalization work. Resolve it after the core pipeline runs reliably on arbitrary CSVs.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Adding a "column mapping" config object passed through all layers

**What it looks like:** A `ColumnConfig(date_col="SimDate", value_col="Flow")` dataclass threaded from UI through bridge through pipeline.

**Why bad:** The pipeline core already normalizes to `df["value"]` before column names are relevant. A config object that carries raw column names into algorithm code reintroduces coupling into exactly the layer that's currently clean.

**Instead:** Bridge does all column renaming. By the time `run_single_reanalysis()` is called, the DataFrames have only `"value"` columns. Column names are UI concerns.

---

### Anti-Pattern 2: Replacing the threading model with multiprocessing

**What it looks like:** Switching from `threading.Thread` to `multiprocessing.Process` for LSTM training because "TensorFlow works better in a separate process."

**Why bad:** Multiprocessing on Windows requires `if __name__ == '__main__'` guards and spawn context, which is incompatible with how Streamlit launches. The Queue-based stdout capture also doesn't work across process boundaries without additional IPC. The current threading model works and TensorFlow runs fine in a thread.

**Instead:** Keep the daemon thread + Queue pattern. If TF GPU contention is observed, investigate `tf.config.threading` settings within the thread.

---

### Anti-Pattern 3: Storing DataFrames in Streamlit session_state

**What it looks like:** Parsing the uploaded CSV immediately on upload and storing the resulting DataFrame in `st.session_state.model_df`.

**Why bad:** Streamlit session state is serialized to disk for multi-page apps and can be pickled/unpickled on reconnect. Large DataFrames cause performance degradation and potential serialization failures. The current pattern — storing the uploaded file object and re-parsing at job launch — is correct.

**Instead:** Keep the current pattern of storing the raw `UploadedFile` and parsing it only in `_start_job()`. The `.seek(0)` pattern before each read is the right approach.

---

### Anti-Pattern 4: Modifying `run_single_reanalysis()` to accept raw file paths

**What it looks like:** Adding `model_csv_path`, `model_date_col`, `model_value_col` parameters to `pipeline.py` so it can load files itself.

**Why bad:** This moves file-format knowledge into algorithm code, recreating the original coupling problem in a new location. It also breaks the clean DataFrame contract that makes the pipeline independently testable.

**Instead:** The bridge is the format adapter. Pipeline core stays format-agnostic.

---

## Scalability Considerations

This is a local single-user tool. "Scalability" means reliability under different input shapes, not concurrent users.

| Concern | Current Handling | Risk | Mitigation |
|---------|-----------------|------|------------|
| Very short time series (< 30 days overlap) | `min_overlap_days` check in pipeline | LSTM may not converge | Already guarded; raise user-visible error before training |
| Very long time series (10+ years daily) | No guard | EnKF loop O(T×N) — ~3600 steps × 50 members is fine | No action needed |
| Sub-daily model data with irregular frequency | `resample("D").mean()` handles it | Edge case: all-NaN day after resample | `dropna()` in `resample_model_to_daily` handles it |
| Observation CSV with BOM (utf-8-sig) | `encoding="utf-8-sig"` in bridge | Only in bridge functions | All CSV reads in bridge already use utf-8-sig |
| Windows Matplotlib display error | `matplotlib.use("Agg")` at top of pipeline_bridge.py | Must run before any pyplot import | Already in place; must remain the first import |
| TensorFlow cold start latency | First TF import takes 5–15s | User sees blank progress screen | Acceptable; first print() appears quickly after |

---

## Component Dependency Graph

```
app.py
  ├── pipeline_bridge.py
  │     ├── src/pipeline.py
  │     │     ├── src/preprocessing.py
  │     │     ├── src/lstm_model.py
  │     │     ├── src/enkf.py
  │     │     ├── src/openloop.py
  │     │     ├── src/postprocessing.py
  │     │     └── src/visualization.py
  │     └── (sys.path manipulation → Sprint_2/Reanalysis_Pipeline/)
  └── job_runner.py
        └── pipeline_bridge.run_single_reanalysis  (imported inside thread)
```

**Critical path for import order:** `matplotlib.use("Agg")` in `pipeline_bridge.py` must execute before `src/visualization.py` is imported. The `import pipeline_bridge` line at the top of `app.py` guarantees this when Streamlit starts. The `from pipeline_bridge import run_single_reanalysis` inside `_run_pipeline_in_thread()` (inside `job_runner.py`) is safe because `pipeline_bridge` is already imported and cached by Python by the time the thread runs.

---

## Sources

- Direct analysis of `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` — confirms pipeline core is already generic
- Direct analysis of `Reanalysis_Dashboard/pipeline_bridge.py` — confirms bridge has both generic obs builders and legacy hardcoded model builder
- Direct analysis of `Reanalysis_Dashboard/app.py` — confirms hardcoded column validation and static variable dropdown at lines 100–106 and 129–133
- Direct analysis of `Reanalysis_Dashboard/job_runner.py` — confirms threading/queue pattern is structurally correct
- Direct analysis of `Sprint_2/Reanalysis_Pipeline/src/visualization.py` — confirms UNITS/LABELS coupling at lines 6–16
- Architecture codebase map: `.planning/codebase/ARCHITECTURE.md`

*Confidence: HIGH — all claims are derived from direct code inspection, not external sources.*
