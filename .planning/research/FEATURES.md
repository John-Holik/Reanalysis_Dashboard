# Feature Landscape

**Domain:** Scientific ML pipeline web app — CSV upload, data assimilation, results delivery
**Researched:** 2026-03-29
**Overall confidence:** HIGH (based on direct codebase analysis + domain knowledge of Streamlit/scientific tool UX)

---

## What Already Exists (Baseline)

The existing `Reanalysis_Dashboard/app.py` is a 547-line, 5-step Streamlit wizard. Before cataloguing
features as table stakes or differentiators, it helps to be precise about the current state:

| Feature Area | Already Built? | Quality |
|---|---|---|
| File upload (model + obs CSVs) | Yes | Functional; hardcoded column validation (`SimDate`, `Flow`, `TN`, `TP`) |
| Column mapping (obs CSV) | Yes | Functional; dropdowns + auto-detect for dedicated vs multi-station format |
| Variable selection | Partial | Hardcoded to `["discharge", "TN", "TP"]` — not generic |
| Hyperparameter configuration | Yes | Full expander UI with sliders |
| Progress display (live log) | Yes | Queue-based 2-second poll; shows last 30 log lines |
| Summary metrics | Yes | 6 metrics shown post-run (T, obs_count, best_val_loss, stopped_epoch, CI width) |
| Inline plot display | Yes | Loads PNG files from temp dir; 3 plots |
| CSV download | Yes | 4 download buttons (obs, open-loop, mean, ensemble) |
| Error display | Partial | Shows traceback; single "Start Over" button |
| Run again flow | Yes | "Run Another Analysis" button resets job state |

The gap is not presence of features — it is robustness, generalizability, and the specific UX moments
that determine whether a researcher trusts and finishes the workflow rather than abandoning it.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy.

### 1. Flexible Model CSV Ingestion (No Hardcoded Column Names)

| Attribute | Detail |
|---|---|
| Why expected | Researchers have arbitrary CSV schemas. "Upload a CSV" that silently rejects anything not named `SimDate`/`Flow`/`TN`/`TP` defeats the purpose of a general tool. |
| Current state | `app.py` step 0 validates `{"SimDate", "Flow", "TN", "TP"}` exactly and rejects other schemas with an error. `pipeline_bridge.build_model_df` hardcodes these names. |
| Complexity | Medium — requires generalizing `data_loader.py` and `pipeline_bridge.py` to use user-selected column names |
| Notes | The variable selection dropdown (step 0) is already present but limited to `["discharge", "TN", "TP"]`. Making it driven by actual model CSV headers is the fix. |

### 2. User-Driven Date Column Selection (Model CSV)

| Attribute | Detail |
|---|---|
| Why expected | Model CSVs from different simulation software (SWAT, HBV, VIC) use different date column names. Rejecting any non-`SimDate` header is a hard blocker. |
| Current state | Hardcoded to `SimDate` in `pipeline_bridge.py:61`. |
| Complexity | Low — add a selectbox for date column, pre-guess via `_best_guess_index` pattern already present |
| Notes | Same auto-detect heuristic used in obs config step can be reused. |

### 3. Validation Feedback Before Proceeding (Not Silent Failures)

| Attribute | Detail |
|---|---|
| Why expected | Scientific users need to know *why* something failed, not just that it did. A cryptic traceback mid-run (after 5+ minutes of LSTM training) is a severe usability failure. |
| Current state | `CONCERNS.md` documents multiple silent failure paths: empty obs match, R=NaN from single observation, empty val set after train split. The UI shows a traceback on error but no pre-flight checks. |
| Complexity | Medium — requires adding pre-run validation guards in `pipeline.py` and surfacing them as structured errors in the UI |
| Notes | The obs preview button (step 1) is the right pattern — extend to model CSV preview and a "validate before run" check that surfaces: row count, date range, data gaps, obs match count. |

### 4. Meaningful Error Messages on Pipeline Failure

| Attribute | Detail |
|---|---|
| Why expected | "The pipeline encountered an error" + Python traceback is developer output, not user output. Researchers need actionable guidance: "Your observation CSV returned 0 rows — check station ID filter" or "Train set too short after split." |
| Current state | `render_step_running()` shows `result.error_message` (raw traceback) with a single "Start Over" button. No guidance on what went wrong or how to fix it. |
| Complexity | Low — requires categorizing known exception types and showing targeted messages |
| Notes | The known failure modes are already catalogued in `CONCERNS.md`. Map each to a user-readable message. |

### 5. Persistent Progress Indicator with Phase Labels

| Attribute | Detail |
|---|---|
| Why expected | A 2–10 minute job with no visual progress indicator causes users to wonder if the app has crashed. Researchers expect to know what phase is running (data loading, training epoch N/200, EnKF step). |
| Current state | Log stream shows last 30 print lines; `time.sleep(2)` polling. There is no epoch counter, no overall progress bar, no phase label. |
| Complexity | Low-Medium — requires pipeline to emit structured progress tokens that the UI can parse into a progress bar |
| Notes | Streamlit `st.progress()` and `st.status()` (available since Streamlit 1.28) are the right primitives. The existing `_QueueWriter` mechanism can emit structured messages. |

### 6. Graceful Job Cancellation

| Attribute | Detail |
|---|---|
| Why expected | A researcher who set wrong parameters and started a 10-minute run needs a way to stop it without killing the browser tab. |
| Current state | No cancel button exists. The background thread is a daemon thread — it runs until completion or process death. |
| Complexity | Medium — requires threading.Event-based cancellation signal and early-exit checks in the pipeline loop |
| Notes | Without this, users will reload the page and lose their session state, which is frustrating. |

### 7. Data Preview Before Committing to Run

| Attribute | Detail |
|---|---|
| Why expected | Before a 10-minute job, users want to confirm: "Is this the right data? Did the date parsing work? How many obs matched?" Obs preview exists (button), model data has no equivalent. |
| Current state | Obs step has a "Preview parsed observations" button. Model CSV shows column count but no data preview. |
| Complexity | Low — `st.dataframe(df.head(10))` with row count, date range, and value range statistics |
| Notes | Summary stats (min, max, mean, nulls) for the selected variable column are more useful than a raw row preview. |

### 8. Output File Presence Check with Fallback Message

| Attribute | Detail |
|---|---|
| Why expected | If a plot or CSV is missing (pipeline error, incomplete run), the results page should explain why, not just show "Not found: filename." |
| Current state | `render_step_results()` uses `col.warning(f"Not found: {filename}")` — no explanation of cause. |
| Complexity | Low — check `result.status` and cross-reference with which stage likely produced the missing file |
| Notes | Already partially handled; just needs better copy. |

---

## Differentiators

Features that set this product apart. Not universally expected, but meaningfully increase trust and usability.

### 1. Structured Progress with Training Epoch Counter

| Attribute | Detail |
|---|---|
| Value proposition | Makes LSTM training feel predictable. "Epoch 47/200, val_loss: 0.00234 (best: 0.00198)" turns waiting into watching. Researchers trained on Jupyter know what epochs mean. |
| Complexity | Low — Keras `on_epoch_end` callback emits to the queue; UI parses and updates `st.progress()` |
| Notes | The `_QueueWriter` mechanism is already in place; just needs a structured callback. |

### 2. Pre-Run Data Quality Report

| Attribute | Detail |
|---|---|
| Value proposition | Flags problems before the run that would cause silent failure or poor results: gaps > N days, obs sparsity level, obs/model temporal overlap percentage, suspicious value ranges. |
| Complexity | Medium — structured validation pass over the constructed DataFrames before `launch_job()` |
| Notes | Catches the known silent failures from `CONCERNS.md` (empty obs match, R=NaN risk, short train set) before spending 10 minutes finding out. |

### 3. Interactive Results Chart (Plotly vs Static PNG)

| Attribute | Detail |
|---|---|
| Value proposition | Researchers want to zoom in on specific time periods, hover to read exact values, toggle series on/off. Static Matplotlib PNGs have none of this. |
| Complexity | Medium — requires replacing `visualization.py` Matplotlib output with Plotly in the UI layer, or adding a separate interactive chart layer while keeping PNG for download |
| Notes | Plotly is already commonly used with Streamlit. The existing PNG download is still valuable; interactive display is the differentiator. Recommend: use Plotly for display, keep Matplotlib for saved files. |

### 4. Session State Persistence Across Browser Reload

| Attribute | Detail |
|---|---|
| Value proposition | If the user reloads the browser mid-run (or after results), they should be able to resume viewing results rather than losing everything. |
| Complexity | High — requires persisting output_dir and result data to disk, then checking on load. Streamlit session state is in-memory only. |
| Notes | For demo scope: out of reach reliably. For genuine usability: important. Defer unless timeline allows. |

### 5. Configurable Output Column Names in Downloaded CSVs

| Attribute | Detail |
|---|---|
| Value proposition | Researchers want to know what the columns in `reanalysis_discharge_mean.csv` mean. Headers like `time`, `mean`, `ci_lower`, `ci_upper` with clear units are expected for data that feeds into papers. |
| Complexity | Low — postprocessing.py determines column names; ensure they are descriptive and consistent |
| Notes | Currently the output format is well-defined in `CLAUDE.md` but not verified as user-friendly. |

### 6. Run Summary Export (PDF or Text Report)

| Attribute | Detail |
|---|---|
| Value proposition | For demo day and for inclusion in a thesis/report, a one-page summary with hyperparameters used, data summary, and key metrics (val loss, CI width, obs count) is highly valued. |
| Complexity | Medium — generate a text/markdown summary file in the output directory; offer download button |
| Notes | Even a plain-text `.txt` summary is useful. PDF requires additional dependencies. Recommend plain text. |

### 7. Model CSV Column Mapping (Generalized Variable Selection)

| Attribute | Detail |
|---|---|
| Value proposition | Instead of requiring `Flow`/`TN`/`TP` names, let the user pick any numeric column as the model variable to reanalyze. Makes the tool usable with SWAT, VIC, RHESSys, or any other model output. |
| Complexity | Medium — requires pipeline generalization (removing hardcoded col names in `data_loader.py` and `pipeline_bridge.py`) plus UI changes to populate variable dropdown from CSV headers |
| Notes | Listed as "Active" requirement in `PROJECT.md`. This is the single most important generalization for post-demo usability. |

---

## Anti-Features

Features to explicitly NOT build in this milestone.

### 1. Multi-Station Batch UI

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Multi-station selection and batch processing in the UI | `pipeline.py` supports it internally; adding it to the UI multiplies the configuration surface area and adds significant complexity for demo scope. | Document that `multi_station_reanalysis.ipynb` handles batch runs for advanced users. |

### 2. Authentication / User Management

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Login, user accounts, saved run history per user | This is a local single-user research tool. Auth adds development complexity with zero user value. | Accept that Streamlit serves a single concurrent user when run locally. |

### 3. Cloud Deployment / Hosted Version

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Hosting on Streamlit Cloud, Heroku, etc. | TensorFlow requires ~500MB and significant CPU for training — cloud hosting costs are real and latency makes the tool worse. Privacy of research data is also a concern. | Ship as a local Docker container or Python installer. |

### 4. Real-Time Data Ingestion (API / Database)

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Connect to USGS NWIS, EPA WQP, or other live data sources | Adds substantial scope. The research need is to run reanalysis on prepared data, not automate data collection. | Keep CSV upload as the sole input interface; users prepare their data externally. |

### 5. Hyperparameter Search / AutoML

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Grid search or Bayesian optimization of LSTM hyperparameters | Multiplies run time by N×M. The current defaults are well-tuned for daily hydro data. | Let users adjust manually via existing sliders if they want to experiment. |

### 6. In-App Data Editing / Imputation

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Let user edit cells, interpolate gaps, remove outliers in the browser | Scope explosion; data preparation belongs in the user's existing workflow (Excel, Python). | Show a clear data quality report pre-run so users know to fix their data externally before re-uploading. |

### 7. Side-by-Side Run Comparison

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Run the pipeline with two configurations and overlay results | Nice to have but requires persisting multiple results and building a comparison UI. | Encourage users to download results and compare in their own plotting environment. |

---

## Feature Dependencies

```
Flexible model CSV headers
  └─→ User-driven date column selection (model CSV)
        └─→ Generalized variable dropdown (from headers)
              └─→ Pipeline generalization (remove hardcoded Flow/TN/TP)

Data preview (model)
  └─→ Pre-run data quality report
        └─→ Meaningful error messages on pipeline failure

Structured progress tokens from pipeline
  └─→ Epoch counter display
        └─→ Overall progress bar with phase labels

Pre-run data quality report
  └─→ Validation checks for known silent failures (empty obs, short train, R=NaN risk)
```

---

## MVP Recommendation

For the 4–6 week demo timeline, prioritize in this order:

**Must ship (table stakes that block basic usability):**
1. Flexible model CSV ingestion — remove hardcoded column validation (currently rejects any non-Peace-River CSV)
2. User-driven model column mapping — date column + variable column from CSV headers
3. Meaningful error messages on pipeline failure — map known exceptions to user guidance
4. Validation feedback before run — at minimum: obs match count, date overlap check, row count check

**Should ship (raise quality from demo to genuinely usable):**
5. Structured progress with epoch counter — transforms waiting from anxiety to monitoring
6. Pre-run data quality report — catches silent failure causes before the 10-minute run
7. Graceful job cancellation — prevents forced browser reload as the recovery path

**Nice to have (differentiators if time allows):**
8. Interactive results chart (Plotly) — table stakes for researchers who want to explore results
9. Run summary export (plain text) — useful for demo day and thesis appendix

**Defer:**
- Session state persistence — high complexity, low demo-day value
- Interactive chart if Matplotlib PNGs are acceptable for demo scope

---

## Sources

**Confidence:** HIGH — based on direct code analysis of the existing 780-line dashboard, `CONCERNS.md` silent failure audit, `PROJECT.md` requirements, and domain expertise in Streamlit scientific tooling. Web search was unavailable; findings are grounded in first-hand code evidence rather than secondary research.

- Existing codebase: `Reanalysis_Dashboard/app.py` (lines 81–546)
- Existing codebase: `Reanalysis_Dashboard/job_runner.py`
- Existing codebase: `Reanalysis_Dashboard/pipeline_bridge.py`
- Codebase audit: `.planning/codebase/CONCERNS.md` (silent failure modes)
- Project spec: `.planning/PROJECT.md` (Active requirements and constraints)
