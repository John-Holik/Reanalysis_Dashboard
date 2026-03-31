# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Data assimilation and reanalysis system** for csv datasets. It fuses imperfect model simulations with sparse observations using **LSTM neural networks + Ensemble Kalman Filter (EnKF)** to produce optimal reanalysis datasets with uncertainty quantification.

## Running the Pipeline

All execution is via Jupyter notebooks — there is no build system or CLI entrypoint.

```bash
# Single-station tutorial (Arcadia discharge)
jupyter notebook Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb

# Full multi-station pipeline (all stations × all variables)
jupyter notebook Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb
```

The multi-station notebook reads `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml` and writes outputs to `Sprint_2/Reanalysis_Pipeline/outputs/<station_id>_<name>/<variable>/`.

**Dependencies:** `tensorflow>=2.20.0`, `numpy`, `pandas`, `scikit-learn`, `scipy`, `matplotlib`, `pyyaml`

## Architecture

All source modules live in `Sprint_2/Reanalysis_Pipeline/src/`. The orchestration entry point is `pipeline.py:run_single_reanalysis()`, which calls the other modules in sequence:

```
Model CSV (sub-daily) ──┐
                         ├─→ data_loader.py → preprocessing.py → lstm_model.py
Observation CSV ─────────┘                                            │
                                                                       ↓
                                                  enkf.py  ←── Q, R from lstm residuals
                                                       │
                                                  openloop.py (baseline, no DA)
                                                       │
                                              postprocessing.py → CSVs
                                              visualization.py  → plots
```

### Key Module Responsibilities

- **`data_loader.py`** — Loads model CSVs (SimDate, Flow, TN, TP columns) and observation CSVs with flexible filtering by StationID, Parameter, date range, and unit conversion (e.g., µg/L → mg/L).
- **`preprocessing.py`** — Sub-daily → daily resampling, inner-join or sparse alignment, Z-score standardization, sliding-window sequence generation (lookback=12), train/val split.
- **`lstm_model.py`** — Sequential LSTM (input→LSTM 64 units→Dense 64 ReLU→Dense 1). Trains with Adam+MSE+early stopping. Estimates process noise Q from training residuals (GUM Type A: `Q = Var(residuals)`).
- **`enkf.py`** — 50-member perturbed-observation EnKF. Observation error `R = 0.2 × Var(obs_std)`. Only performs analysis step on days with observations (intermittent assimilation for sparse monthly TN/TP data). Uses `tf.function`-compiled LSTM prediction for performance.
- **`openloop.py`** — Single-member LSTM run without assimilation; serves as the no-DA baseline.
- **`postprocessing.py`** — Inverse Z-score transform, 95% CI (2.5th/97.5th percentiles), trapezoidal integration of CI width as a scalar uncertainty metric.
- **`visualization.py`** — Time-series comparison plots, CI shading area plots, model vs. observation scatter.
- **`config.py`** — YAML config loader.

### Configuration (`pipeline_config.yaml`)

Key hyperparameters:
- `lookback: 12` days
- `lstm_units: 64`, `dense_units: 64`
- `n_ensemble: 50`
- `obs_error_factor: 0.2`
- `train_fraction: 0.8`, `patience: 15`

Stations are defined with per-variable observation metadata (file path, filter criteria, unit conversions).

### Data Formats

- **Model input:** CSV with columns `SimDate`, `Flow` (CMS), `TN` (mg/L), `TP` (mg/L), sub-daily frequency
- **Observation input:** CSV with columns `StationID`, `Parameter`, `SampleDate`, `Result_Value` (sparse, monthly)
- **Outputs per station-variable:**
  - `obs_<var>.csv`, `model_openloop_<var>.csv`, `reanalysis_<var>_mean.csv`, `reanalysis_<var>_ensemble.csv` (long format: time, member, value)

## Stations Configured

| Station ID | Name | Variables |
|---|---|---|
| 02296750 | Arcadia | discharge (daily), TN (monthly), TP (monthly) |
| 270318081593100 | Ft Ogden RM14.82 | TN (monthly), TP (monthly) |
| 02297330 | Ft Ogden | TN/TP (missing data) |


<!-- GSD:project-start source:PROJECT.md -->
## Project

**Reanalysis Dashboard**

A general-purpose data assimilation app that lets any researcher upload two CSVs (model output + observations), select their target variable from a dropdown, and run an LSTM + Ensemble Kalman Filter reanalysis on their local machine. The app streams live progress logs during execution and delivers a downloadable reanalysis CSV with confidence intervals plus inline visualization. It is designed to be installable in one step — no coding required.

**Core Value:** A researcher with no ML background can go from raw CSVs to a calibrated reanalysis dataset with uncertainty bounds in under 30 minutes, entirely in a browser.

### Constraints

- **Timeline**: Demo day in ~4–6 weeks — scope must be achievable in that window
- **Tech Stack**: Python + Streamlit — no framework changes; already committed
- **Local execution**: Pipeline must run on user's hardware — no cloud dependency
- **TensorFlow**: Required for LSTM; large dependency (~500MB) affects installer size
- **Packaging TBD**: Docker vs downloadable installer not yet decided — affects Phase structure
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.13.7 — All pipeline logic, data processing, modeling, and notebooks
- YAML — Pipeline configuration (`Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`)
## Runtime
- Python 3.13.7 (local interpreter, confirmed via `python --version`)
- No `.python-version` or `pyproject.toml` version pins found; environment managed ad-hoc
- pip (assumed — no `requirements.txt`, `Pipfile`, `pyproject.toml`, or `environment.yml` present in repo)
- Lockfile: **absent** — no pinned dependency file committed
## Frameworks
- TensorFlow >= 2.20.0 — LSTM neural network training and inference; confirmed via notebook output: `TensorFlow 2.20.0`
- NumPy 2.3.2 — Array operations, random seeding, ensemble arrays, percentile computation
- pandas 2.3.2 — DataFrame I/O, DatetimeIndex, resampling (`.resample("D")`), CSV read/write
- scikit-learn 1.7.1 — `StandardScaler` for Z-score standardization in `preprocessing.py`
- SciPy 1.16.1 — `scipy.integrate.trapezoid` for CI area integral in `postprocessing.py`
- Matplotlib 3.10.6 — All visualization (time-series, CI shading, scatter plots) in `visualization.py`
- PyYAML (version not pinned) — YAML config loading in `config.py` via `yaml.safe_load()`
- Jupyter (jupyter_client 8.6.3, jupyter_core 5.8.1) — Primary execution interface for both notebooks
- ipykernel 6.29.5 — Kernel for Jupyter notebooks
## Key Dependencies
- `tensorflow` >= 2.20.0 — The LSTM model (`lstm_model.py`) and fast inference (`enkf.py`, `openloop.py`) depend entirely on Keras Sequential API and `tf.function` compilation
- `pandas` 2.3.2 — All data loading, alignment, resampling, and CSV export rely on pandas DataFrames with DatetimeIndex
- `numpy` 2.3.2 — Ensemble arrays `(T, M)`, random noise generation, residual computation
- `scikit-learn` 1.7.1 — `StandardScaler` fitted on observations, used to transform both obs and model data; inverse transform on all outputs
- `scipy` 1.16.1 — `integrate.trapezoid` for the CI uncertainty metric (only scipy usage)
- `matplotlib` 3.10.6 — Produces all three plot types: comparison, CI shading, model-vs-observed scatter
- `pyyaml` — Required for `config.py` and multi-station pipeline; single point of YAML parsing
## Configuration
- Config file: `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`
- Key parameters: `lookback: 12`, `lstm_units: 64`, `dense_units: 64`, `learning_rate: 0.001`, `batch_size: 32`, `epochs: 200`, `patience: 15`, `n_ensemble: 50`, `obs_error_factor: 0.2`, `train_fraction: 0.8`, `min_overlap_days: 30`, `seed: 42`
- No build system — execution is purely via Jupyter notebooks
- Single-station tutorial: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb`
- Multi-station pipeline: `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb`
## Platform Requirements
- Python 3.13.7
- TensorFlow >= 2.20.0 (GPU optional; CPU execution confirmed in notebook outputs)
- Jupyter-compatible environment (classic Notebook or JupyterLab)
- All `pip` dependencies listed above
- No deployment target — this is a research/analysis pipeline run locally via Jupyter
- Outputs (CSVs and PNGs) written to `Sprint_2/Reanalysis_Pipeline/outputs/<station_id>_<name>/<variable>/`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Module names use `snake_case`: `data_loader.py`, `lstm_model.py`, `postprocessing.py`
- Output CSVs use `snake_case` with variable suffix: `reanalysis_TN_mean.csv`, `obs_discharge.csv`
- Output plots use `TitleCase` with variable suffix: `CI_Area_TN.png`, `Discharge_Comparison.png`
- All public functions use `snake_case`: `load_model_data()`, `run_enkf()`, `build_sequences()`
- Private/internal helpers are prefixed with underscore: `_obs_file_cache`, `_make_fast_predict()`
- Boolean/predicate variables use descriptive names: `is_sparse`, `has_obs_mask`, `obs_valid`
- `snake_case` throughout
- Abbreviated suffixes for data state: `_std` (standardized), `_phys` (physical units), `_daily` (daily resampled)
- `_all` suffix for pre-allocated full-length arrays: `proc_noise_all`, `obs_noise_all`
- Short single-letter names used only in tight loops or mathematical contexts: `T` (time steps), `Q`, `R`, `K`
- Module-level constants in `UPPER_SNAKE_CASE` (see `visualization.py`: `UNITS`, `LABELS`)
- Hyperparameter keys in YAML config use `snake_case`: `lookback`, `lstm_units`, `obs_error_factor`
- No custom classes defined — the codebase uses a pure-function module design
## Code Style
- 4 spaces throughout (PEP 8 standard); no tabs observed
- Lines generally kept under 90 characters; long `print()` statements occasionally split with implicit continuation
- No automated formatter config detected (no `.prettierrc`, `pyproject.toml` `[tool.black]`, or `ruff.toml`)
- Style is manually consistent with PEP 8
- No linting config detected (no `.flake8`, `.pylintrc`, `mypy.ini`)
- Two blank lines between top-level functions (PEP 8)
- One blank line between logical sections within a function, marked by inline section comments
## Import Organization
- Module-level imports at the top of each file
- One late/deferred import used in `pipeline.py` inside a function: `from sklearn.preprocessing import StandardScaler` (pragmatic, not preferred pattern)
- None — no `__init__.py` re-exports; all modules imported directly via relative paths
## Documentation
- NumPy-style docstrings used consistently on all public functions
- Format: one-line summary sentence, then `Parameters`, `Returns` sections with type annotations inline
- Example pattern from `preprocessing.py`:
- Short utility functions (1-3 lines) receive a single-line docstring only: `inverse_transform()`, `resample_model_to_daily()`
- Used heavily to annotate pipeline steps with `# --- Step N: Description ---` headers
- Performance rationale is documented inline where non-obvious (e.g., `_make_fast_predict()` explains why `model.predict()` is avoided)
- Mathematical relationships documented inline: `# Q = Var(residuals)`, `# R = factor * Var(obs_std)`
## Error Handling
- `raise ValueError(f"Unknown observation type: {obs_type}")` in `data_loader.py:load_observations()` for invalid config keys
- Early `return pd.DataFrame(columns=["value"])` for missing/empty data (e.g., `obs_cfg is None` or `subset.empty`)
- `print(f"  WARNING: ...")` used for non-fatal data issues instead of `logging.warning()` — see `data_loader.py:86`
- No `try/except` blocks present; I/O errors (missing files, bad CSV formats) propagate as unhandled exceptions
## Logging
- Progress prints use a two-space indent: `print(f"  Model: {len(mdl_daily)} daily rows ...")`
- Section headers printed with `=` separators: `print(f"\n{'='*70}")`
- Periodic loop progress at every 2000 steps: `if (t + 1) % 2000 == 0: print(...)` (in `enkf.py`, `openloop.py`)
- File save confirmation uses an arrow: `print(f"  Saved → {path}")`
- No log levels, no timestamps, no structured logging
## Configuration Management
- `config.py:load_config()` reads the YAML via `yaml.safe_load()`
- `config.py:resolve_path()` converts relative paths in config to absolute using `os.path.abspath(os.path.join(base_dir, ...))`
- Hyperparameters are passed as a `dict` to `run_single_reanalysis()` via `hyperparams` arg
- Individual values extracted by key: `hyperparams["lookback"]`, `hyperparams["n_ensemble"]`
- `paths.model_data_dir`, `paths.observation_data_dir`, `paths.output_dir`
- `hyperparameters.lookback`, `lstm_units`, `dense_units`, `learning_rate`, `batch_size`, `epochs`, `patience`, `n_ensemble`, `obs_error_factor`, `train_fraction`, `min_overlap_days`
- `seed` (top-level)
- Per-station: `station_id`, `name`, `model_file`, `observations.<variable>`
## Module Design
- `src/__init__.py` is empty — no package-level re-exports
- All inter-module imports are explicit relative: `from .enkf import compute_obs_error, run_enkf`
- Most functions are small and single-purpose (5–30 lines)
- `run_single_reanalysis()` in `pipeline.py` is the largest (~175 lines), but is intentionally a sequential orchestrator with step comments
- `data_loader.py` maintains a module-level file cache `_obs_file_cache = {}` to avoid re-reading large CSVs
- All I/O (CSV writes, plot saves) is centralized in `postprocessing.py` and `visualization.py`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- No web server, no API layer: execution is triggered exclusively via Jupyter notebooks
- All state is passed explicitly through function arguments (no global mutable state between pipeline stages)
- Two parallel execution paths: EnKF (with data assimilation) and Open-loop (no assimilation), run back-to-back for comparison
- Fully re-runnable per station-variable pair; results are reproducible via fixed seeds
## Layers
- Purpose: Entry point that drives the full pipeline
- Location: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb` (single-station) and `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb` (all stations)
- Contains: Config loading, station iteration, calls to `pipeline.run_single_reanalysis()`, summary CSV generation
- Depends on: `src/pipeline.py`, `src/config.py`, `src/data_loader.py`
- Purpose: Orchestrate the 11-step reanalysis sequence for one station-variable pair
- Location: `Sprint_2/Reanalysis_Pipeline/src/pipeline.py`
- Contains: `run_single_reanalysis()` — the only public function; calls all other modules in order
- Depends on: All other `src/` modules
- Used by: Notebooks only
- Purpose: Load model CSVs and observation CSVs; normalize to a standard `pd.DataFrame(DatetimeIndex, value)` schema
- Location: `Sprint_2/Reanalysis_Pipeline/src/data_loader.py`
- Contains: `load_model_data()`, `load_obs_dedicated_discharge()`, `load_obs_multi_station()`, `load_observations()`, `check_data_availability()`
- Key detail: Observation files are cached in `_obs_file_cache` dict to avoid re-reading large HU8 CSVs across multiple stations
- Purpose: Resample, align, standardize, and build sliding-window sequences for LSTM input
- Location: `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py`
- Contains: `resample_model_to_daily()`, `align_dense()`, `align_sparse()`, `standardize()`, `build_sequences()`, `train_val_split()`
- Key detail: `align_sparse()` fills missing observation days with NaN (preserving the full model time axis); `align_dense()` uses inner-join
- Purpose: Build, train, and extract process noise from the neural network
- Location: `Sprint_2/Reanalysis_Pipeline/src/lstm_model.py`
- Contains: `build_forecast_lstm()`, `train_forecast_lstm()`, `estimate_process_noise()`
- Architecture: `LSTM(64) → Dense(64, relu) → Dense(1, linear)`, compiled with Adam + MSE
- Key detail: `estimate_process_noise()` computes `Q = Var(y_true - y_pred)` on training set (GUM Type A)
- Purpose: Fuse LSTM forecasts with observations using a 50-member perturbed-observation EnKF
- Location: `Sprint_2/Reanalysis_Pipeline/src/enkf.py`
- Contains: `compute_obs_error()`, `run_enkf()`
- Key detail: Analysis step is skipped on NaN observation days (intermittent assimilation); `tf.function`-compiled `fast_predict` avoids per-step Keras overhead
- Purpose: Run the trained LSTM forward with process noise but without any data assimilation
- Location: `Sprint_2/Reanalysis_Pipeline/src/openloop.py`
- Contains: `run_openloop()`
- Used by: `pipeline.run_single_reanalysis()` for comparison against EnKF output
- Purpose: Invert standardization, compute CI bounds from ensemble, calculate uncertainty metric, export CSVs
- Location: `Sprint_2/Reanalysis_Pipeline/src/postprocessing.py`
- Contains: `inverse_transform()`, `compute_ci_bounds()`, `compute_ci_integral()`, `export_results()`
- Key detail: CI integral (trapezoidal, `scipy.integrate.trapezoid`) is the primary scalar uncertainty metric
- Purpose: Generate three standard plots per station-variable run
- Location: `Sprint_2/Reanalysis_Pipeline/src/visualization.py`
- Contains: `plot_comparison()`, `plot_ci_area()`, `plot_model_vs_observed()`
- Purpose: YAML loading and path resolution
- Location: `Sprint_2/Reanalysis_Pipeline/src/config.py`
- Contains: `load_config()`, `resolve_path()`
## Data Flow
- Batch LSTM predict all 50 members simultaneously
- Add process noise: `x_f = pred + N(0, sqrt(Q))`
- If obs available: `K = P_f / (P_f + R)`, `x_a = x_f + K * (y_pert - x_f)`
- Shift history buffer left and append `x_a`
- Detected in `pipeline.py`: `is_sparse = obs_count < model_days * 0.5`
- Dense path: inner-join; scaler fit on all obs
- Sparse path: full model time axis with NaN gaps; scaler fit only on non-NaN obs values; physical obs values preserved (not re-standardized for output)
## Key Algorithms
## Entry Points
- Location: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb`
- Triggers: Manual Jupyter execution
- Responsibilities: Demonstrates pipeline on Arcadia discharge; inline outputs
- Location: `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb`
- Triggers: Manual Jupyter execution
- Responsibilities: Reads `configs/pipeline_config.yaml`, iterates over all stations and variables, skips pairs with insufficient overlap, writes all outputs, generates cross-station summary plots and `ci_integral_summary.csv`
## Error Handling
- Data availability check via `check_data_availability()` before pipeline runs
- `obs_count < min_overlap_days` (default 30) triggers skip of a station-variable pair
- Missing observation config (`null` in YAML) returns empty DataFrame from `load_observations()`
- `load_obs_multi_station()` prints WARNING and returns empty DataFrame when no records match filters
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
