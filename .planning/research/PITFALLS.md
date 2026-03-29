# Domain Pitfalls

**Domain:** Scientific ML pipeline generalized and packaged as a Streamlit application
**Project:** Reanalysis Dashboard (LSTM + EnKF hydrological data assimilation)
**Researched:** 2026-03-29
**Confidence:** HIGH — all pitfalls are grounded in direct code inspection of the existing
codebase, not speculation. Evidence citations reference specific files and line numbers.

---

## Critical Pitfalls

Mistakes that cause crashes, silent wrong results, or complete rewrites.

---

### Pitfall 1: `sys.stdout` Redirect Racing in Background Thread

**What goes wrong:**
`job_runner.py` replaces `sys.stdout` with a `_QueueWriter` inside the worker thread
(lines 75-76) and restores it in the `finally` block (line 95). `sys.stdout` is a
process-global; Streamlit's main thread and all other threads share it. If Streamlit
itself writes to stdout during the worker's execution (startup messages, deprecation
warnings, internal logging), those writes go to the queue instead of the terminal.
More critically, if a second job is ever launched before the first finishes (user
clicks "Run Reanalysis" on a second browser tab), the second thread overwrites
`sys.stdout` that the first thread just set, and the finally-block restore of the
first thread clobbers the second thread's writer — both jobs' output corrupts or
drops, and one thread's stdout is silently lost.

**Why it happens:**
The existing design assumes exactly one concurrent execution and zero Streamlit
internal stdout writes. Both assumptions are fragile. Python's GIL does not protect
object identity swaps of `sys.stdout`.

**Consequences:**
- Log output silently drops or interleaves under concurrent runs.
- Streamlit's own warning messages ("Warning: ScriptRunner...") end up in the queue
  and appear as log lines in the UI.
- In the single-tab case this usually works, but it is a race that will manifest
  during a live demo if the browser tab reloads mid-run.

**Prevention:**
Replace the global `sys.stdout` redirect with `contextlib.redirect_stdout` scoped
to the thread's call stack, or use a `logging.Handler` subclass that writes to
the queue. Either approach is thread-local and does not touch `sys.stdout` at all.
The pipeline already uses `print()` throughout; wrapping the entire
`run_single_reanalysis` call in `with contextlib.redirect_stdout(_QueueWriter(q))`
achieves the same result without global mutation.

**Detection:**
- Streamlit warning strings appearing as log lines in the progress display.
- Log output stopping mid-run without `__DONE__` or `__ERROR__` sentinel.
- Progress log showing lines from two different runs interleaved.

**Phase:** Generalization / pipeline bridge hardening phase (before any public demo run).

---

### Pitfall 2: TensorFlow Global Graph State Persists Across Runs

**What goes wrong:**
Each call to `run_single_reanalysis` calls `tf.random.set_seed(seed)`,
`build_forecast_lstm` (which creates a new Keras model), and `_make_fast_predict`
(which creates a `@tf.function` with `reduce_retracing=True` and a `tf.Variable`).
These objects are held in Python memory for the lifetime of the process. When the
user clicks "Run Another Analysis" (app.py line 529) and launches a new job,
TensorFlow's global default graph accumulates:

- A new Keras model (new layer variables registered in the default graph).
- A new `tf.Variable` (`batch_tf` in enkf.py line 75) allocated on the TF heap.
- A new `tf.function` trace.

After 3-5 runs in the same Streamlit process, GPU/CPU memory may be exhausted
and training time increases due to graph bloat. On Windows with CPU-only TF 2.20,
this manifests as gradually increasing per-epoch training time across runs.

**Why it happens:**
TensorFlow does not garbage-collect compiled graphs and variables until the Python
objects go out of scope AND the GC finalizer runs. Streamlit re-runs do not restart
the Python interpreter. The LSTM model object is stored in `session_state["job_result"]`
and only cleared to `None` (app.py line 530), which drops the Python reference but
does not guarantee immediate TF resource release.

**Consequences:**
- "Run Another Analysis" gets slower with each iteration.
- Memory exhaustion after many runs (OOM error on the 4th+ run during demo).
- `tf.function` retracing warnings appearing in the progress log.

**Prevention:**
Call `tf.keras.backend.clear_session()` at the start of each new job in
`job_runner.py` before importing or calling any TF code. This clears the Keras
model registry and frees compiled graph resources. It must be called from the worker
thread (not the main thread) since TF session state is per-process but the call is
safe from any thread. Also explicitly `del` the model and call `gc.collect()` after
the job completes.

**Detection:**
- Second run takes noticeably longer than the first.
- TF retracing warning: "5 out of the last 5 calls to `fast_predict` triggered
  tf.function retracing."
- Task Manager shows Python process memory growing monotonically across runs.

**Phase:** Generalization phase; add `clear_session()` call in `_run_pipeline_in_thread`
before launching pipeline code.

---

### Pitfall 3: Hardcoded Column Name Assumptions Hidden Throughout the Bridge

**What goes wrong:**
`pipeline_bridge.py` `build_model_df` (line 64) contains the mapping
`{"discharge": "Flow", "TN": "TN", "TP": "TP"}` — the three Peace River column
names. `app.py` Step 0 validates uploaded model CSVs against the hard-coded set
`{"SimDate", "Flow", "TN", "TP"}` (lines 100-103) and blocks progression if any
are missing. The variable selector is also hard-coded to `["discharge", "TN", "TP"]`
(line 131). These three places must all be updated together when generalizing to
arbitrary columns, or the app silently accepts a CSV with the right shape but maps
it to the wrong variable.

**Why it happens:**
The bridge was written as a thin shim over the existing Peace River pipeline
rather than as a general adapter. Column assumptions that were config-driven in
`data_loader.py` were re-hardcoded in the bridge for speed.

**Consequences:**
- Any CSV without exactly `SimDate` + `Flow`/`TN`/`TP` columns is rejected with
  a misleading error ("Missing required columns: Flow") even if the user's column
  is named `Q` or `streamflow`.
- If the column validation is loosened without updating `build_model_df`, the
  app silently picks the wrong column or raises a KeyError mid-run (no progress
  output, job shows ERROR status with a pandas KeyError traceback).

**Prevention:**
Replace the hard-coded required-column check in Step 0 with a flexible two-step
flow: (1) require only one parseable date column; (2) let the user pick the model
value column from a dropdown populated from CSV headers (same pattern already used
for the observation CSV in Step 1). The `build_model_df` `col_map` must be replaced
with the user-selected column name passed down through `launch_job`.

**Detection:**
- `KeyError: 'Flow'` in job ERROR traceback when a non-Peace-River CSV is uploaded.
- Step 0 shows "Missing required columns: Flow" for any valid model CSV that uses
  different column names.

**Phase:** This IS the core generalization work. Address in the first active milestone.

---

### Pitfall 4: Streamlit File Buffer Exhaustion After Multiple `seek(0)` Calls

**What goes wrong:**
`app.py` calls `.seek(0)` on `st.session_state.obs_file` and
`st.session_state.model_file` repeatedly across Step 1 (preview), Step 2
(unique values for dropdowns), and `_start_job()`. Streamlit's `UploadedFile`
object is a `BytesIO`-backed buffer that survives reruns within a session. However,
the buffer is owned by the session and can be reset to a closed state on certain
Streamlit internal operations (cache invalidation, widget key changes). If the
buffer is read after a rerun that replaces the upload widget's key, subsequent
`seek(0)` calls silently succeed but `read()` returns `b""`, causing `pd.read_csv`
to raise `EmptyDataError` with no informative message.

**Why it happens:**
Streamlit's `UploadedFile` wraps a server-side `BytesIO`; the reference in
`session_state` points to the original buffer, but if the widget is re-rendered
with a different key (e.g., due to `st.rerun()` flushing widget state), a new
upload object is created internally while the `session_state` reference still
points to the old (now effectively detached) buffer.

**Consequences:**
- `EmptyDataError: No columns to parse from file` during `_start_job()`, appearing
  as an ERROR state with a confusing traceback.
- This fails reliably if the user uploads a file, navigates Back, and re-uploads.

**Prevention:**
After successful upload, read the buffer contents to `bytes` and store the raw
bytes in `session_state`, not the `UploadedFile` object itself. Reconstruct a fresh
`io.BytesIO` for each read operation. This is exactly what `pipeline_bridge.py`
already does internally (`buf = io.BytesIO(uploaded_file.read())`) but the
`uploaded_file` itself must still be seekable at that point.

**Detection:**
- `pandas.errors.EmptyDataError` in job ERROR traceback.
- Reproduces reliably by uploading a file, pressing Back, and pressing Next again
  without re-uploading.

**Phase:** Generalization / UI hardening milestone. Low-effort fix; high impact on
demo reliability.

---

### Pitfall 5: Scaler Fitted on Observations Breaks When Observation Variance is Zero

**What goes wrong:**
`pipeline.py` lines 87-93 fit a `StandardScaler` on `valid_obs` (non-NaN observation
values) for the sparse path. `preprocessing.py` `standardize()` (line 77) does the
same for the dense path. If a user uploads an observation CSV where all values are
identical (e.g., a synthetic test file, a constant detection-limit fill, or a
single-observation dataset), `StandardScaler.fit` sets `scale_ = 0` and
`transform` produces `NaN` throughout the standardized arrays. The EnKF then
propagates `NaN` through the ensemble and all output CSVs contain only `NaN`.
No exception is raised; the job completes with status DONE.

**Why it happens:**
`StandardScaler` uses `std = 0` protection only in sklearn >= 1.1 via `copy=True`,
but the zero-variance check only warns; it does not raise. The downstream
`np.var(x_f, ddof=1)` in enkf.py line 104 returns 0 for an all-NaN ensemble,
making `K = 0 / (0 + R)` well-defined, but the analysis values are still NaN
propagated from the forecast step.

**Consequences:**
- Job shows status DONE with all metrics showing `0` or `NaN`.
- Output CSVs are all-NaN; plots are blank or raise matplotlib rendering errors.
- User cannot distinguish "pipeline ran and produced bad output" from "pipeline
  failed silently".

**Prevention:**
Add a pre-flight check in the bridge or pipeline entry point: if
`obs_df["value"].nunique() < 2`, raise a `ValueError` with a clear message before
fitting the scaler. Also check `obs_df["value"].std() == 0` explicitly. Surface
this to the user in Step 1 (preview) so they know before launching the 10-minute job.

**Detection:**
- All output CSV columns contain `NaN`.
- `ci_mean_width` metric shows `0.0000` in the results panel.
- Matplotlib may log "No artists with labels found to put in legend."

**Phase:** Input validation milestone. Add to the Step 1 preview check.

---

### Pitfall 6: matplotlib Thread Safety — `plt.show()` and Figure Registry Contamination

**What goes wrong:**
`pipeline_bridge.py` correctly sets `matplotlib.use("Agg")` before any other
matplotlib import. However, matplotlib's figure registry (`plt._pylab_helpers.Gcf`)
is a module-level global that accumulates open figures. `visualization.py` creates
figures with `plt.figure()` or `plt.subplots()` and saves them with `savefig()`.
If `plt.close("all")` is not called after each save, each run leaves figures open
in the registry. The registry is not thread-safe. With the background thread writing
to it concurrently with Streamlit's main thread (which may import matplotlib for
other purposes), this can cause `RuntimeError: dictionary changed size during iteration`
in the matplotlib GC path.

Additionally, the `Agg` backend import order constraint is fragile. If any transitive
import (e.g., a future addition to `pipeline_bridge.py`) imports matplotlib before
the `matplotlib.use("Agg")` call, the backend is already set and the call silently
does nothing, but on some Windows Python 3.13 environments the default backend
attempts to connect to a display and raises `_tkinter.TclError` which surfaces as
an unhelpful `ImportError`.

**Why it happens:**
matplotlib was designed for interactive single-threaded notebook use. Its global
state (figure registry, backend selection) predates thread-safety requirements.

**Consequences:**
- Intermittent `RuntimeError` in the plot generation step; job shows ERROR with
  a matplotlib internal traceback.
- On Windows without a display, `_tkinter.TclError: no display name and no $DISPLAY`
  if the Agg backend is not set before the import.
- Figure memory leak: each run adds 3 unclosed figures to the registry.

**Prevention:**
- In `visualization.py`, add `plt.close("all")` after every `savefig()` call,
  or use the object-oriented matplotlib API (`fig, ax = plt.subplots()` /
  `fig.savefig()` / `fig.clf()` / `plt.close(fig)`) to avoid touching global state.
- Move the `matplotlib.use("Agg")` call to the very first line of `pipeline_bridge.py`
  and add a guard: `if matplotlib.get_backend() != "Agg": matplotlib.use("Agg")`.
- Add a comment marking it as load-order-sensitive so future contributors don't
  accidentally reorder imports.

**Detection:**
- `RuntimeError: dictionary changed size during iteration` in ERROR traceback
  mentioning `matplotlib`.
- Python process memory grows by ~5-10MB per run (open figure leak).
- `UserWarning: Matplotlib is currently using TkAgg` appearing in the progress log.

**Phase:** Generalization phase; low effort, high demo reliability impact.

---

## Moderate Pitfalls

---

### Pitfall 7: `tempfile.mkdtemp` Output Directories Accumulate Indefinitely

**What goes wrong:**
`job_runner.py` creates a new `tempfile.mkdtemp(prefix="reanalysis_")` for every
job (line 69). These directories are never cleaned up. On Windows, the system temp
directory (`%TEMP%`) is not automatically purged between reboots. After 10-20 demo
runs (each producing ~6 CSV files + 3 PNG files averaging ~2MB total), the temp
directory accumulates 20-40MB of orphaned output. This is not a crash risk but is
unprofessional for a "one-step installer" product and can fill disk on low-storage
demo laptops.

**Prevention:**
Register a cleanup handler using `atexit.register(shutil.rmtree, output_dir,
ignore_errors=True)` in `_run_pipeline_in_thread`, or keep only the most recent
N output directories by scanning for `reanalysis_*` prefixed dirs in temp and
deleting the oldest. Alternatively, use a fixed output dir in the user's home
folder (`~/.reanalysis_dashboard/outputs/`) with a run-ID subdirectory and expose
a "Clear past results" button in the UI.

**Detection:**
- `C:\Users\<user>\AppData\Local\Temp\reanalysis_*` directories multiplying.
- Disk space warnings on laptops with small SSDs.

**Phase:** Packaging/installer milestone.

---

### Pitfall 8: `lookback` Hyperparameter Can Silently Produce Zero Training Sequences

**What goes wrong:**
`preprocessing.py` `build_sequences` produces `T - lookback` sequences. If a user
uploads a short observation CSV (e.g., 2 years of monthly TN data = ~24 observations)
and the model CSV covers the same short period, `T` may be small. If the user then
sets `lookback = 60` (the slider maximum in app.py line 320), `T - lookback` can
be zero or negative, and `np.array([])` is returned. The LSTM is then called with
`X_train.shape = (0, 60, 1)`, Keras raises `ValueError: Input 0 of layer ... is
incompatible with the layer: expected axis -1 of input shape to have value 60 but
received input with shape (None, 0, 1)` — or worse, trains on zero batches and
returns a model with untrained weights that produces plausible-looking output.

**Prevention:**
After `build_sequences`, assert `len(X_all) >= hyperparams["lookback"] * 2`
(a minimum sequence count) and raise a descriptive `ValueError` that surfaces to
the user: "Lookback of 60 days requires at least 120 model timesteps; your data
has only N." Add this guard in `pipeline.py` before the `train_val_split` call.

**Detection:**
- Job ERROR with `ValueError` containing "incompatible with the layer".
- Or: job completes but `best_val_loss` is `nan` (untrained model).

**Phase:** Input validation / generalization milestone.

---

### Pitfall 9: Model CSV Sub-Daily Resampling Drops Entire Days on Partial Data

**What goes wrong:**
`preprocessing.py` `resample_model_to_daily` calls `.resample("D").mean().dropna()`.
The `.dropna()` drops any calendar day that has at least one `NaN` in the mean.
For a model CSV that represents, e.g., a 6-hourly output where the first and last
days have only partial records (common for simulation outputs that start at 06:00
rather than 00:00), the first and last day are silently dropped. If the observation
CSV has data on those exact days, the overlap count is reduced. For monthly TN/TP
data with only ~24 annual observations, losing even 2 days can drop the overlap
below `min_overlap_days`, causing the pipeline to proceed with fewer anchor points
than the user expects.

**Prevention:**
Change `.dropna()` to `.dropna(how="all")` to drop only days with no data at all
rather than days with any NaN. Also log the number of days dropped during resampling
so the user can see it in the progress stream.

**Detection:**
- Model has 3650 expected daily rows but `resample_model_to_daily` returns 3648.
- `obs_count` in the results panel is lower than the number of rows in the
  observation CSV.

**Phase:** Generalization milestone; one-line fix in `preprocessing.py`.

---

### Pitfall 10: Docker Image Size Exceeds Practical Installer Threshold

**What goes wrong:**
TensorFlow 2.20 CPU-only wheel is approximately 500MB. Combined with NumPy 2.3,
pandas 2.3, scikit-learn 1.7, matplotlib 3.10, and Streamlit, the total installed
package footprint is approximately 1.5-2GB. A naive `FROM python:3.13` Docker
image (900MB base) plus these packages produces a 2.8-3.5GB image. Pushing this
to Docker Hub and asking a faculty committee member to `docker pull` it on demo
day is impractical on a conference wifi. Alternatively, building the image from
scratch on the demo laptop requires downloading all packages at installation time.

**Prevention:**
- Use `python:3.13-slim` base (~120MB) and install only CPU TensorFlow
  (`tensorflow-cpu`) rather than the full GPU wheel.
- Use Docker layer caching by separating `COPY requirements.txt` and
  `RUN pip install` into an early layer so rebuilds after code changes do not
  reinstall TensorFlow.
- Consider providing both a Docker option and a plain `pip install` option:
  for the demo, a pre-built local venv is more reliable than Docker pull on
  unknown wifi.
- If Docker is chosen, distribute the image as a `.tar` file via USB/local
  transfer rather than relying on pull from a registry.

**Detection:**
- `docker images` shows image > 3GB.
- `docker pull` takes > 15 minutes on conference wifi.

**Phase:** Packaging/installer milestone. Decision (Docker vs pip installer) must
be made early as it affects the entire release phase structure.

---

### Pitfall 11: `_obs_file_cache` Module-Level Dict in `data_loader.py` Leaks Across Streamlit Sessions

**What goes wrong:**
`data_loader.py` maintains `_obs_file_cache = {}` at module level (line 6) to
avoid re-reading large observation files. In a Jupyter context this is harmless.
In a Streamlit process, the module is imported once and its module-level state
persists for the entire server lifetime. If the legacy file-path-based loader is
ever called from the Streamlit context (e.g., if the bridge is extended to support
direct file paths rather than `UploadedFile` objects), the cache holds references
to DataFrames from previous users' uploads. This is a privacy concern and a memory
leak. More immediately, if two different uploads use observation files at the same
absolute path (impossible with temp paths, but plausible in a shared environment),
the cache returns stale data.

**Prevention:**
The bridge already bypasses `data_loader.py` entirely and reads files via
`io.BytesIO` buffers — the cache is never hit in the current dashboard flow.
Document this explicitly and add a comment in `data_loader.py` marking the cache
as notebook-only. If file-path loading is ever re-introduced, replace the
module-level dict with a `functools.lru_cache` on a function that accepts a
content hash, not a path.

**Detection:**
- Memory use growing proportionally to number of unique files uploaded across
  sessions.
- Stale observation data appearing in a new run (only in multi-user or re-path
  scenarios).

**Phase:** Documentation concern now; prevention needed if file-path loading
is ever re-enabled.

---

## Minor Pitfalls

---

### Pitfall 12: `time.sleep(2)` Polling in Main Thread Blocks Streamlit Reactivity

**What goes wrong:**
`render_step_running` ends with `time.sleep(2); st.rerun()` (app.py lines 458-459).
This polls for progress every 2 seconds. The `sleep` occupies Streamlit's main
thread, which means any other user interaction (button click, tab switch) is
queued behind the 2-second sleep. For a single-user local app this is acceptable,
but it means the UI cannot react faster than 2 seconds to job completion. If the
pipeline finishes in the first 100ms after the last rerun, the user waits up to
2 seconds of blank "Running..." screen before the results page appears.

**Prevention:**
Use `st.empty()` with a container and shorter polling intervals (0.5s), or use
Streamlit's `st.spinner` context manager with `st.rerun()` triggered by the
`__DONE__` sentinel check. The sleep duration can be reduced to 0.5 seconds
without meaningful CPU impact; the 2-second choice was likely conservative.

**Detection:**
- Results page appears with a 0-2 second delay after the pipeline finishes.
- User can see "Running..." for a moment after the job is done.

**Phase:** Polish milestone; not a blocker for demo.

---

### Pitfall 13: UTF-8 BOM Handling is Inconsistent Between Bridge and Legacy Loader

**What goes wrong:**
`pipeline_bridge.py` uses `encoding="utf-8-sig"` consistently for all CSV reads
(confirmed on lines 36, 43, 60, 81, 103), which correctly strips the BOM.
`data_loader.py` `load_model_data` (line 26) uses plain `pd.read_csv(model_path)`
with no encoding parameter. If the bridge is ever bypassed or the legacy loader
is called with a BOM-prefixed model CSV, the first column name becomes `\ufeffSimDate`
rather than `SimDate`, and `df["SimDate"]` raises a `KeyError`. This is an
invisible failure because `\ufeff` does not print in most terminals.

**Prevention:**
Add `encoding="utf-8-sig"` to all `pd.read_csv` calls in `data_loader.py` for
consistency, even though the current dashboard flow never calls them. The cost
is zero and it prevents a confusing future regression.

**Detection:**
- `KeyError: 'SimDate'` when the model CSV is opened in Excel and re-saved
  (Excel adds BOM by default on Windows).
- Column names display with a leading `?` or invisible character in pandas
  `.columns.tolist()` output.

**Phase:** Generalization milestone; one-line fix per affected read call.

---

### Pitfall 14: EnKF Produces Deterministic Output Despite `seed` Parameter When `tf.random.set_seed` is Called Too Late

**What goes wrong:**
`pipeline.py` calls `tf.random.set_seed(seed)` at line 43, before the LSTM is
built. However, `enkf.py` `run_enkf` also calls `np.random.seed(seed)` at line 57.
Between the call to `pipeline.py` and the call to `enkf.py`, `tf.random.set_seed`
in one thread does not affect NumPy's global random state in another thread that
may have already advanced it. In the single-threaded Jupyter context this produces
reproducible results. In the background thread context, the NumPy global RNG is
shared across all threads, and the order in which the main thread and the worker
thread advance it is nondeterministic. Two runs with the same seed may produce
slightly different ensemble members.

This is not a crash. It is a reproducibility violation that will be noticed if
a researcher tries to reproduce a result by running the same inputs twice and
gets different CI bounds.

**Prevention:**
Replace `np.random.seed(seed)` calls with `rng = np.random.default_rng(seed)` and
pass `rng` explicitly into all functions that need randomness. This uses per-instance
RNG state rather than the global state and is both thread-safe and reproducible.

**Detection:**
- Reanalysis run with identical inputs produces different `ci_mean_width` values
  on different runs.
- Ensemble percentiles shift slightly between runs with the same seed.

**Phase:** Can be deferred post-demo unless reproducibility is a grading criterion.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Pipeline generalization (column mapping) | Pitfall 3: hidden hardcoded column names in bridge and app step 0 | Replace column validation with dropdown selection; update `build_model_df` signature |
| Input validation | Pitfall 5: zero-variance obs scaler | Add pre-flight check before job launch; surface in Step 1 preview |
| Input validation | Pitfall 8: lookback > time series length | Assert minimum sequence count in `pipeline.py` before training |
| Input validation | Pitfall 9: partial-day resampling drops model rows | Change `.dropna()` to `.dropna(how="all")` in `preprocessing.py` |
| UI / bridge hardening | Pitfall 1: sys.stdout race | Replace global redirect with `contextlib.redirect_stdout` |
| UI / bridge hardening | Pitfall 4: UploadedFile buffer exhaustion on Back/Next | Store raw bytes in session_state, not UploadedFile reference |
| UI / bridge hardening | Pitfall 6: matplotlib global state | Add `plt.close("all")` in `visualization.py`; guard Agg backend call |
| Second-run reliability | Pitfall 2: TF memory accumulation across runs | Call `tf.keras.backend.clear_session()` at start of each worker thread |
| Packaging / installer | Pitfall 10: Docker image size | Use `python:3.13-slim` + `tensorflow-cpu`; consider plain pip installer as primary |
| Packaging / installer | Pitfall 7: tempfile accumulation | Add cleanup handler or fixed output directory with "Clear" button |
| Post-demo (reproducibility) | Pitfall 14: global NumPy RNG in background thread | Use `np.random.default_rng(seed)` per-instance |

---

## Sources

All findings are derived from direct code analysis of the following files at
commit `0f4c566` (2026-03-28):

- `Reanalysis_Dashboard/job_runner.py` — Thread design, stdout redirect (lines 75-95)
- `Reanalysis_Dashboard/pipeline_bridge.py` — Column hardcoding, encoding, Agg backend (lines 14, 36, 60-68)
- `Reanalysis_Dashboard/app.py` — Column validation (lines 100-103), variable selector (line 131), sleep polling (lines 458-459), buffer seeks (lines 246, 373)
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` — TF seed, scaler fit, run flow (lines 43, 87-93)
- `Sprint_2/Reanalysis_Pipeline/src/enkf.py` — tf.Variable allocation, tf.function, numpy seed (lines 57, 75, 87)
- `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py` — Resampling dropna (line 18), sequence length (line 96)
- `Sprint_2/Reanalysis_Pipeline/src/data_loader.py` — Module-level cache, encoding (lines 6, 26, 65)
- `.planning/PROJECT.md` — Known issues list, constraint context
- `.planning/codebase/STACK.md` — Dependency versions
