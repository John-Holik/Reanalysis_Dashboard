# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **hydrological data assimilation and reanalysis system** for Peace River, Florida. It fuses imperfect model simulations with sparse observations (discharge, Total Nitrogen, Total Phosphorus) using **LSTM neural networks + Ensemble Kalman Filter (EnKF)** to produce optimal reanalysis datasets with uncertainty quantification.

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
