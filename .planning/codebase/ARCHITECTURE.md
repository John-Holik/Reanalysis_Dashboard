# Architecture

**Analysis Date:** 2026-03-28

## Pattern Overview

**Overall:** Sequential data-assimilation pipeline — a linear chain of processing stages where each module transforms data and passes results to the next.

**Key Characteristics:**
- No web server, no API layer: execution is triggered exclusively via Jupyter notebooks
- All state is passed explicitly through function arguments (no global mutable state between pipeline stages)
- Two parallel execution paths: EnKF (with data assimilation) and Open-loop (no assimilation), run back-to-back for comparison
- Fully re-runnable per station-variable pair; results are reproducible via fixed seeds

## Layers

**Orchestration (Notebooks):**
- Purpose: Entry point that drives the full pipeline
- Location: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb` (single-station) and `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb` (all stations)
- Contains: Config loading, station iteration, calls to `pipeline.run_single_reanalysis()`, summary CSV generation
- Depends on: `src/pipeline.py`, `src/config.py`, `src/data_loader.py`

**Pipeline Coordinator:**
- Purpose: Orchestrate the 11-step reanalysis sequence for one station-variable pair
- Location: `Sprint_2/Reanalysis_Pipeline/src/pipeline.py`
- Contains: `run_single_reanalysis()` — the only public function; calls all other modules in order
- Depends on: All other `src/` modules
- Used by: Notebooks only

**Data Ingestion:**
- Purpose: Load model CSVs and observation CSVs; normalize to a standard `pd.DataFrame(DatetimeIndex, value)` schema
- Location: `Sprint_2/Reanalysis_Pipeline/src/data_loader.py`
- Contains: `load_model_data()`, `load_obs_dedicated_discharge()`, `load_obs_multi_station()`, `load_observations()`, `check_data_availability()`
- Key detail: Observation files are cached in `_obs_file_cache` dict to avoid re-reading large HU8 CSVs across multiple stations

**Preprocessing:**
- Purpose: Resample, align, standardize, and build sliding-window sequences for LSTM input
- Location: `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py`
- Contains: `resample_model_to_daily()`, `align_dense()`, `align_sparse()`, `standardize()`, `build_sequences()`, `train_val_split()`
- Key detail: `align_sparse()` fills missing observation days with NaN (preserving the full model time axis); `align_dense()` uses inner-join

**LSTM Model:**
- Purpose: Build, train, and extract process noise from the neural network
- Location: `Sprint_2/Reanalysis_Pipeline/src/lstm_model.py`
- Contains: `build_forecast_lstm()`, `train_forecast_lstm()`, `estimate_process_noise()`
- Architecture: `LSTM(64) → Dense(64, relu) → Dense(1, linear)`, compiled with Adam + MSE
- Key detail: `estimate_process_noise()` computes `Q = Var(y_true - y_pred)` on training set (GUM Type A)

**Ensemble Kalman Filter:**
- Purpose: Fuse LSTM forecasts with observations using a 50-member perturbed-observation EnKF
- Location: `Sprint_2/Reanalysis_Pipeline/src/enkf.py`
- Contains: `compute_obs_error()`, `run_enkf()`
- Key detail: Analysis step is skipped on NaN observation days (intermittent assimilation); `tf.function`-compiled `fast_predict` avoids per-step Keras overhead

**Open-Loop Baseline:**
- Purpose: Run the trained LSTM forward with process noise but without any data assimilation
- Location: `Sprint_2/Reanalysis_Pipeline/src/openloop.py`
- Contains: `run_openloop()`
- Used by: `pipeline.run_single_reanalysis()` for comparison against EnKF output

**Postprocessing:**
- Purpose: Invert standardization, compute CI bounds from ensemble, calculate uncertainty metric, export CSVs
- Location: `Sprint_2/Reanalysis_Pipeline/src/postprocessing.py`
- Contains: `inverse_transform()`, `compute_ci_bounds()`, `compute_ci_integral()`, `export_results()`
- Key detail: CI integral (trapezoidal, `scipy.integrate.trapezoid`) is the primary scalar uncertainty metric

**Visualization:**
- Purpose: Generate three standard plots per station-variable run
- Location: `Sprint_2/Reanalysis_Pipeline/src/visualization.py`
- Contains: `plot_comparison()`, `plot_ci_area()`, `plot_model_vs_observed()`

**Configuration:**
- Purpose: YAML loading and path resolution
- Location: `Sprint_2/Reanalysis_Pipeline/src/config.py`
- Contains: `load_config()`, `resolve_path()`

## Data Flow

**Full Pipeline Sequence (inside `run_single_reanalysis()`):**

1. `resample_model_to_daily(model_df)` — sub-daily CSV → daily DataFrame
2. `align_sparse()` or `align_dense()` — merge model and obs onto common time axis
3. `standardize()` — Z-score scaling; scaler fitted on obs (or non-NaN obs for sparse)
4. `build_sequences(mdl_std, lookback=12)` → `train_val_split()` — sliding windows for LSTM
5. `build_forecast_lstm()` + `train_forecast_lstm()` — LSTM trained on standardized model sequences
6. `estimate_process_noise()` → `Q`; `compute_obs_error()` → `R`
7. `run_enkf(lstm, obs_std, mdl_std, Q, R, lookback, n_ensemble=50)` → ensemble arrays (T, 50)
8. `run_openloop(lstm, mdl_std, Q, lookback)` → baseline array (T,)
9. `inverse_transform()` on ensemble mean, open-loop, each member — back to physical units
10. `compute_ci_bounds()` (2.5th/97.5th percentile) + `compute_ci_integral()` — uncertainty metric
11. `export_results()` → CSVs; `plot_comparison()`, `plot_ci_area()`, `plot_model_vs_observed()` → PNGs

**EnKF Inner Loop (per time step `t`):**
- Batch LSTM predict all 50 members simultaneously
- Add process noise: `x_f = pred + N(0, sqrt(Q))`
- If obs available: `K = P_f / (P_f + R)`, `x_a = x_f + K * (y_pert - x_f)`
- Shift history buffer left and append `x_a`

**Sparse vs Dense Observation Handling:**
- Detected in `pipeline.py`: `is_sparse = obs_count < model_days * 0.5`
- Dense path: inner-join; scaler fit on all obs
- Sparse path: full model time axis with NaN gaps; scaler fit only on non-NaN obs values; physical obs values preserved (not re-standardized for output)

## Key Algorithms

**LSTM Architecture:** Sequential Keras model; `lookback=12` day sliding window; single-output regression
**EnKF Noise Parameters:** `Q = Var(training residuals)` (GUM Type A); `R = 0.2 * Var(obs_std)`
**Uncertainty Metric:** `∫(CI_upper - CI_lower) dt` via trapezoidal rule — scalar summary of total uncertainty over time
**Performance:** Random noise pre-generated before loop; `@tf.function` for fast batch inference; persistent `tf.Variable` to avoid tensor re-allocation

## Entry Points

**Single-Station Tutorial:**
- Location: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb`
- Triggers: Manual Jupyter execution
- Responsibilities: Demonstrates pipeline on Arcadia discharge; inline outputs

**Multi-Station Production Run:**
- Location: `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb`
- Triggers: Manual Jupyter execution
- Responsibilities: Reads `configs/pipeline_config.yaml`, iterates over all stations and variables, skips pairs with insufficient overlap, writes all outputs, generates cross-station summary plots and `ci_integral_summary.csv`

## Error Handling

**Strategy:** Fail-fast with informative prints; no try/except wrapping of core algorithm steps

**Patterns:**
- Data availability check via `check_data_availability()` before pipeline runs
- `obs_count < min_overlap_days` (default 30) triggers skip of a station-variable pair
- Missing observation config (`null` in YAML) returns empty DataFrame from `load_observations()`
- `load_obs_multi_station()` prints WARNING and returns empty DataFrame when no records match filters

## Cross-Cutting Concerns

**Logging:** `print()` statements throughout `pipeline.py` with step-by-step progress; no structured logging library
**Validation:** Observation-model overlap checked pre-run via `data_availability.csv`; sparse/dense branching in pipeline
**Reproducibility:** `numpy.random.seed(seed)` + `tf.random.set_seed(seed)` at start of `run_single_reanalysis()`; default `seed=42`

---

*Architecture analysis: 2026-03-28*
