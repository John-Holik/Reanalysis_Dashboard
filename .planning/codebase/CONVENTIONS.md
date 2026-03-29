# Coding Conventions

**Analysis Date:** 2026-03-28

## Naming Patterns

**Files:**
- Module names use `snake_case`: `data_loader.py`, `lstm_model.py`, `postprocessing.py`
- Output CSVs use `snake_case` with variable suffix: `reanalysis_TN_mean.csv`, `obs_discharge.csv`
- Output plots use `TitleCase` with variable suffix: `CI_Area_TN.png`, `Discharge_Comparison.png`

**Functions:**
- All public functions use `snake_case`: `load_model_data()`, `run_enkf()`, `build_sequences()`
- Private/internal helpers are prefixed with underscore: `_obs_file_cache`, `_make_fast_predict()`
- Boolean/predicate variables use descriptive names: `is_sparse`, `has_obs_mask`, `obs_valid`

**Variables:**
- `snake_case` throughout
- Abbreviated suffixes for data state: `_std` (standardized), `_phys` (physical units), `_daily` (daily resampled)
- `_all` suffix for pre-allocated full-length arrays: `proc_noise_all`, `obs_noise_all`
- Short single-letter names used only in tight loops or mathematical contexts: `T` (time steps), `Q`, `R`, `K`

**Constants:**
- Module-level constants in `UPPER_SNAKE_CASE` (see `visualization.py`: `UNITS`, `LABELS`)
- Hyperparameter keys in YAML config use `snake_case`: `lookback`, `lstm_units`, `obs_error_factor`

**Types/Classes:**
- No custom classes defined — the codebase uses a pure-function module design

## Code Style

**Indentation:**
- 4 spaces throughout (PEP 8 standard); no tabs observed

**Line Length:**
- Lines generally kept under 90 characters; long `print()` statements occasionally split with implicit continuation

**Formatting:**
- No automated formatter config detected (no `.prettierrc`, `pyproject.toml` `[tool.black]`, or `ruff.toml`)
- Style is manually consistent with PEP 8

**Linting:**
- No linting config detected (no `.flake8`, `.pylintrc`, `mypy.ini`)

**Blank Lines:**
- Two blank lines between top-level functions (PEP 8)
- One blank line between logical sections within a function, marked by inline section comments

## Import Organization

**Order:**
1. Standard library (`os`, `numpy`, etc.)
2. Third-party packages (`tensorflow`, `pandas`, `sklearn`, `scipy`, `matplotlib`)
3. Relative intra-package imports (`from .preprocessing import ...`)

**Pattern:**
- Module-level imports at the top of each file
- One late/deferred import used in `pipeline.py` inside a function: `from sklearn.preprocessing import StandardScaler` (pragmatic, not preferred pattern)

**Path Aliases:**
- None — no `__init__.py` re-exports; all modules imported directly via relative paths

## Documentation

**Docstrings:**
- NumPy-style docstrings used consistently on all public functions
- Format: one-line summary sentence, then `Parameters`, `Returns` sections with type annotations inline
- Example pattern from `preprocessing.py`:
  ```python
  def standardize(obs_values, mdl_values):
      """Fit StandardScaler on observations, transform both arrays.

      Parameters
      ----------
      obs_values : np.ndarray, shape (N,) or (N, 1)

      Returns
      -------
      obs_std : np.ndarray, shape (N, 1)
      scaler : StandardScaler (fitted)
      """
  ```
- Short utility functions (1-3 lines) receive a single-line docstring only: `inverse_transform()`, `resample_model_to_daily()`

**Inline Comments:**
- Used heavily to annotate pipeline steps with `# --- Step N: Description ---` headers
- Performance rationale is documented inline where non-obvious (e.g., `_make_fast_predict()` explains why `model.predict()` is avoided)
- Mathematical relationships documented inline: `# Q = Var(residuals)`, `# R = factor * Var(obs_std)`

## Error Handling

**Strategy:** Minimal defensive error handling; the pipeline is research/notebook-oriented and prefers `ValueError` for unsupported cases over silent failures.

**Patterns:**
- `raise ValueError(f"Unknown observation type: {obs_type}")` in `data_loader.py:load_observations()` for invalid config keys
- Early `return pd.DataFrame(columns=["value"])` for missing/empty data (e.g., `obs_cfg is None` or `subset.empty`)
- `print(f"  WARNING: ...")` used for non-fatal data issues instead of `logging.warning()` — see `data_loader.py:86`
- No `try/except` blocks present; I/O errors (missing files, bad CSV formats) propagate as unhandled exceptions

## Logging

**Framework:** None — all output uses `print()` directly

**Patterns:**
- Progress prints use a two-space indent: `print(f"  Model: {len(mdl_daily)} daily rows ...")`
- Section headers printed with `=` separators: `print(f"\n{'='*70}")`
- Periodic loop progress at every 2000 steps: `if (t + 1) % 2000 == 0: print(...)` (in `enkf.py`, `openloop.py`)
- File save confirmation uses an arrow: `print(f"  Saved → {path}")`
- No log levels, no timestamps, no structured logging

## Configuration Management

**Approach:** All pipeline settings live in `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`

**Loading:**
- `config.py:load_config()` reads the YAML via `yaml.safe_load()`
- `config.py:resolve_path()` converts relative paths in config to absolute using `os.path.abspath(os.path.join(base_dir, ...))`
- Hyperparameters are passed as a `dict` to `run_single_reanalysis()` via `hyperparams` arg
- Individual values extracted by key: `hyperparams["lookback"]`, `hyperparams["n_ensemble"]`

**Config keys consumed by code:**
- `paths.model_data_dir`, `paths.observation_data_dir`, `paths.output_dir`
- `hyperparameters.lookback`, `lstm_units`, `dense_units`, `learning_rate`, `batch_size`, `epochs`, `patience`, `n_ensemble`, `obs_error_factor`, `train_fraction`, `min_overlap_days`
- `seed` (top-level)
- Per-station: `station_id`, `name`, `model_file`, `observations.<variable>`

## Module Design

**Exports:**
- `src/__init__.py` is empty — no package-level re-exports
- All inter-module imports are explicit relative: `from .enkf import compute_obs_error, run_enkf`

**Function Size:**
- Most functions are small and single-purpose (5–30 lines)
- `run_single_reanalysis()` in `pipeline.py` is the largest (~175 lines), but is intentionally a sequential orchestrator with step comments

**Side Effects:**
- `data_loader.py` maintains a module-level file cache `_obs_file_cache = {}` to avoid re-reading large CSVs
- All I/O (CSV writes, plot saves) is centralized in `postprocessing.py` and `visualization.py`

---

*Convention analysis: 2026-03-28*
