# Technology Stack

**Analysis Date:** 2026-03-28

## Languages

**Primary:**
- Python 3.13.7 — All pipeline logic, data processing, modeling, and notebooks

**Secondary:**
- YAML — Pipeline configuration (`Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`)

## Runtime

**Environment:**
- Python 3.13.7 (local interpreter, confirmed via `python --version`)
- No `.python-version` or `pyproject.toml` version pins found; environment managed ad-hoc

**Package Manager:**
- pip (assumed — no `requirements.txt`, `Pipfile`, `pyproject.toml`, or `environment.yml` present in repo)
- Lockfile: **absent** — no pinned dependency file committed

## Frameworks

**Core ML/DL:**
- TensorFlow >= 2.20.0 — LSTM neural network training and inference; confirmed via notebook output: `TensorFlow 2.20.0`
  - Uses `tensorflow.keras` submodule: `layers`, `models`, `callbacks`, `optimizers.Adam`
  - Uses `tf.function` and `tf.Variable` for performance-optimized inference in EnKF loop

**Data Science / Numerics:**
- NumPy 2.3.2 — Array operations, random seeding, ensemble arrays, percentile computation
- pandas 2.3.2 — DataFrame I/O, DatetimeIndex, resampling (`.resample("D")`), CSV read/write
- scikit-learn 1.7.1 — `StandardScaler` for Z-score standardization in `preprocessing.py`
- SciPy 1.16.1 — `scipy.integrate.trapezoid` for CI area integral in `postprocessing.py`
- Matplotlib 3.10.6 — All visualization (time-series, CI shading, scatter plots) in `visualization.py`

**Configuration:**
- PyYAML (version not pinned) — YAML config loading in `config.py` via `yaml.safe_load()`

**Notebook Environment:**
- Jupyter (jupyter_client 8.6.3, jupyter_core 5.8.1) — Primary execution interface for both notebooks
- ipykernel 6.29.5 — Kernel for Jupyter notebooks

## Key Dependencies

**Critical:**
- `tensorflow` >= 2.20.0 — The LSTM model (`lstm_model.py`) and fast inference (`enkf.py`, `openloop.py`) depend entirely on Keras Sequential API and `tf.function` compilation
- `pandas` 2.3.2 — All data loading, alignment, resampling, and CSV export rely on pandas DataFrames with DatetimeIndex
- `numpy` 2.3.2 — Ensemble arrays `(T, M)`, random noise generation, residual computation

**Infrastructure:**
- `scikit-learn` 1.7.1 — `StandardScaler` fitted on observations, used to transform both obs and model data; inverse transform on all outputs
- `scipy` 1.16.1 — `integrate.trapezoid` for the CI uncertainty metric (only scipy usage)
- `matplotlib` 3.10.6 — Produces all three plot types: comparison, CI shading, model-vs-observed scatter
- `pyyaml` — Required for `config.py` and multi-station pipeline; single point of YAML parsing

## Configuration

**Pipeline Hyperparameters (YAML-driven):**
- Config file: `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`
- Key parameters: `lookback: 12`, `lstm_units: 64`, `dense_units: 64`, `learning_rate: 0.001`, `batch_size: 32`, `epochs: 200`, `patience: 15`, `n_ensemble: 50`, `obs_error_factor: 0.2`, `train_fraction: 0.8`, `min_overlap_days: 30`, `seed: 42`

**Build:**
- No build system — execution is purely via Jupyter notebooks
- Single-station tutorial: `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb`
- Multi-station pipeline: `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb`

## Platform Requirements

**Development:**
- Python 3.13.7
- TensorFlow >= 2.20.0 (GPU optional; CPU execution confirmed in notebook outputs)
- Jupyter-compatible environment (classic Notebook or JupyterLab)
- All `pip` dependencies listed above

**Production:**
- No deployment target — this is a research/analysis pipeline run locally via Jupyter
- Outputs (CSVs and PNGs) written to `Sprint_2/Reanalysis_Pipeline/outputs/<station_id>_<name>/<variable>/`

---

*Stack analysis: 2026-03-28*
