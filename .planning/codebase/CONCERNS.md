# Codebase Concerns

**Analysis Date:** 2026-03-28

---

## Tech Debt

**Duplicate pipeline logic between notebook and src modules:**
- Issue: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb` reimplements the full pipeline inline (EnKF loop, open-loop loop, sequence building, standardization, export). The same logic was later extracted to `src/`. The notebook is not updated to use `src/` functions.
- Files: `reanalysis_creation.ipynb` (cells 3–20), `src/pipeline.py`, `src/preprocessing.py`, `src/enkf.py`
- Impact: Any bug fix or algorithm change made to `src/` is not reflected in the tutorial notebook. Two diverging implementations of the same algorithm.
- Fix approach: Refactor `reanalysis_creation.ipynb` to call `run_single_reanalysis()` from `src/pipeline.py`, keeping it as a thin demo wrapper.

**Notebook EnKF loop uses `model.predict()` in a Python for-loop:**
- Issue: `reanalysis_creation.ipynb` Step 6 calls `model.predict(batch_in, verbose=0)` inside a `for t in range(LOOKBACK, T)` loop. For ~9,000 steps this is extremely slow (each `predict()` call creates a new dataset graph internally).
- Files: `reanalysis_creation.ipynb` (EnKF loop cell)
- Impact: Notebook runs orders of magnitude slower than the optimized `src/enkf.py` which uses `tf.function`-compiled batched inference.
- Fix approach: Replace with the `_make_fast_predict` pattern from `src/enkf.py`.

**Ensemble CSV export uses a Python for-loop over rows:**
- Issue: `reanalysis_creation.ipynb` Step 8 builds the ensemble DataFrame with a nested `for m ... for i, t ...` loop, creating one dict per row. For 50 members × 9,131 steps = 456,550 iterations.
- Files: `reanalysis_creation.ipynb` (Step 8 cell)
- Impact: Slow export. The `src/postprocessing.py` already uses a vectorized `np.tile`/`np.repeat` approach.
- Fix approach: Notebook is superseded by `src/`; deprecate or refactor it.

---

## Missing Error Handling

**No validation of model CSV column names — [High]:**
- Issue: `src/data_loader.py:26` calls `pd.read_csv(model_path)` and immediately accesses `df["SimDate"]`, `df["Flow"]`, `df["TN"]`, `df["TP"]` via `col_map`. If a model CSV has different column names (e.g. a new station file), a `KeyError` is raised with no helpful message.
- Files: `src/data_loader.py` lines 23–29
- Fix approach: Validate required columns exist and raise a descriptive `ValueError`.

**No error handling for empty val set after train/val split — [High]:**
- Issue: `src/preprocessing.py:102` splits data purely by index arithmetic. If the time series is very short (near `min_overlap_days`), `X_val` could be empty, causing `train_forecast_lstm` to fail silently or with a cryptic Keras error.
- Files: `src/preprocessing.py` lines 102–110, `src/pipeline.py` lines 98–100
- Fix approach: Assert `len(X_val) > 0` before training and raise a descriptive error.

**Silent fallback when no observations match filters — [Medium]:**
- Issue: `src/data_loader.py:86` prints a WARNING but returns an empty DataFrame. The caller in `src/pipeline.py` proceeds to `run_single_reanalysis()` which then computes Q and R from zero observations, producing `nan` or `0.0` noise values.
- Files: `src/data_loader.py` lines 79–87, `src/pipeline.py`
- Fix approach: Raise a `ValueError` or skip the station-variable pair explicitly in `multi_station_reanalysis.ipynb`.

**`compute_obs_error` can produce R=0 if only one observation — [Medium]:**
- Issue: `src/enkf.py:11` computes `np.var(valid, ddof=1)` with `ddof=1`. If `len(valid) == 1`, the result is `nan`. If `len(valid) == 0`, `valid` is empty and `np.var` returns `nan`. R=nan or R=0 causes the Kalman gain to become undefined or 1.
- Files: `src/enkf.py` lines 5–12
- Fix approach: Guard with a minimum sample size check and a floor value for R.

---

## Performance Bottlenecks

**EnKF `tf.Variable.assign()` called every time step — [Medium]:**
- Issue: `src/enkf.py:96` calls `batch_tf.assign(histories.astype(np.float32))` at every step in the EnKF loop. The `.astype()` call allocates a new array on every iteration.
- Files: `src/enkf.py` lines 94–99
- Fix approach: Pre-cast `histories` to float32 at initialization and assign directly, or convert the history buffer to a tf.Variable natively.

**Open-loop runs sequentially, one timestep at a time — [Low]:**
- Issue: `src/openloop.py` runs a single-member sequential loop. For long time series (10,000+ steps) this is unavoidable given autoregressive dependencies, but the single-member design limits parallelism compared to running open-loop as a 1-member EnKF ensemble.
- Files: `src/openloop.py`

---

## Fragile Areas

**Relative paths in `pipeline_config.yaml` are CWD-sensitive — [High]:**
- Issue: `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml` lines 2–4 use `../../Model_Data` style relative paths. These only resolve correctly when the notebook is run from `Sprint_2/Reanalysis_Pipeline/`. Running from any other directory (e.g. project root) silently breaks all file loads.
- Files: `configs/pipeline_config.yaml`, `src/config.py:12`
- Fix approach: Always resolve paths relative to the config file location (already done in `src/config.py:resolve_path`), but the notebook must be launched from the correct directory. Document this constraint or use absolute paths via an environment variable.

**Station `02297330` (Ft Ogden) is configured but known to have missing data — [High]:**
- Issue: `pipeline_config.yaml` lines 57–76 configure station `02297330` with TN/TP observations, but `CLAUDE.md` documents this station as "missing data." The pipeline will run, print a WARNING, and produce an empty or degenerate reanalysis for this station without halting.
- Files: `configs/pipeline_config.yaml` lines 57–76
- Fix approach: Either remove this station from the config or add a `skip: true` flag and handle it in the orchestration notebook.

**`align_sparse` assumes model index granularity is exactly daily — [Medium]:**
- Issue: `src/preprocessing.py:49` uses `obs_df.index.isin(model_daily.index)` for date matching. If `resample_model_to_daily` produces a non-UTC DatetimeIndex and the observation CSV uses UTC timestamps, `.isin()` will produce zero matches silently.
- Files: `src/preprocessing.py` lines 49–55
- Fix approach: Normalize both indexes to `datetime.date` level before intersection to avoid timezone mismatch.

**Sparse scaler fitted on observations only, then applied to model — [Medium]:**
- Issue: `src/pipeline.py` lines 83–93 fit the `StandardScaler` only on non-NaN observation values for sparse variables. The model data is then transformed with this scaler. If TN/TP observations cover a very different value range than the model (common for nutrient data with reporting limits), the standardized model values may be far outside the scaler's fitted range, destabilizing LSTM training.
- Files: `src/pipeline.py` lines 82–94
- Fix approach: Consider fitting the scaler on model data for sparse variables, or using a combined obs+model fit, and document the choice.

---

## Code Quality Issues

**`StandardScaler` imported in two places — [Low]:**
- Issue: `src/preprocessing.py:3` imports `StandardScaler` at module level. `src/pipeline.py:85` also imports it inline inside a conditional branch (`from sklearn.preprocessing import StandardScaler`). The inline import works but is inconsistent.
- Files: `src/pipeline.py` line 85, `src/preprocessing.py` line 3
- Fix approach: Move the import to the top of `src/pipeline.py`.

**No unit tests exist — [High]:**
- Issue: There is no `tests/` directory and no test files anywhere in the repository. Core numerical functions (`standardize`, `build_sequences`, `compute_obs_error`, `compute_ci_integral`) have no automated verification. Silent numerical regressions are possible.
- Files: Entire `src/` directory
- Fix approach: Add at minimum unit tests for `preprocessing.py`, `postprocessing.py`, and `enkf.py` functions using synthetic data.

**`_obs_file_cache` is a module-level global mutable dict — [Low]:**
- Issue: `src/data_loader.py:6` uses a module-level cache. In a long-running Jupyter session, stale data persists in cache across kernel reuse. Kernel restart clears it, but mid-session config changes (e.g. changing a file path) will silently use the old cached data.
- Files: `src/data_loader.py` line 6
- Fix approach: Accept this tradeoff (documented) or use `functools.lru_cache` with an explicit cache-clear mechanism.

---

## Missing Documentation

**No `requirements.txt` or `environment.yml` — [High]:**
- Issue: No pinned dependency file exists. `CLAUDE.md` lists `tensorflow>=2.20.0, numpy, pandas, scikit-learn, scipy, matplotlib, pyyaml` but gives no pinned versions. Reproducing the environment requires manual package installation.
- Files: Project root (missing)
- Fix approach: Add a `requirements.txt` with pinned versions or an `environment.yml` for conda.

**No docstring on `src/__init__.py` or module-level package purpose — [Low]:**
- Issue: `src/__init__.py` is empty (0 bytes). There is no package-level `__all__` export list.
- Files: `src/__init__.py`

**`Revised for clarity` folder contains duplicate data files with no explanation — [Low]:**
- Issue: `Sprint_2/Revised for clarity/Revised for clarity/` contains exact copies of all model CSV files. No README or commit message explains why these duplicates exist or which copy is authoritative.
- Files: `Sprint_2/Revised for clarity/Revised for clarity/`
- Fix approach: Remove duplicates or add a README explaining the provenance.

---

## Hardcoded Values

**`obs_error_factor = 0.2` has no scientific justification in code — [Medium]:**
- Issue: R is computed as `0.2 × Var(obs_std)` everywhere. The 0.2 factor is configurable in `pipeline_config.yaml`, but no comment in `src/enkf.py` or `src/pipeline.py` explains the physical basis. Different variables (discharge vs TN vs TP) may warrant different R values.
- Files: `src/enkf.py` lines 5–12, `configs/pipeline_config.yaml` line 87
- Fix approach: Allow per-variable `obs_error_factor` overrides in config; add a comment citing the uncertainty basis.

**`min_overlap_days: 30` threshold is arbitrary — [Low]:**
- Issue: `pipeline_config.yaml` line 89 sets `min_overlap_days: 30` as a hard cutoff. No scientific rationale is documented. For monthly TN/TP data, 30 matching days could represent only 1 month of assimilation data.
- Files: `configs/pipeline_config.yaml` line 89

---

*Concerns audit: 2026-03-28*
