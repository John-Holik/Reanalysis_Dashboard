# Testing Patterns

**Analysis Date:** 2026-03-28

## Test Framework

**Runner:**
- None — no test framework is installed or configured.
- No `pytest.ini`, `setup.cfg`, `tox.ini`, `pyproject.toml`, or `jest.config.*` present.

**Assertion Library:**
- None.

**Run Commands:**
```bash
# No test commands exist. The closest validation available is:
jupyter notebook Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb   # manual end-to-end run
jupyter notebook Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb  # multi-station run
```

## Test File Organization

**Location:**
- No test files exist. There are no `test_*.py`, `*_test.py`, `*.spec.*`, or `*.test.*` files anywhere in the repository.

**Naming:**
- No convention established.

**Structure:**
```
Sprint_2/Reanalysis_Pipeline/
├── src/                    # All source modules — zero test coverage
│   ├── data_loader.py
│   ├── preprocessing.py
│   ├── lstm_model.py
│   ├── enkf.py
│   ├── openloop.py
│   ├── postprocessing.py
│   ├── visualization.py
│   ├── config.py
│   └── pipeline.py
├── reanalysis_creation.ipynb     # Manual validation notebook (single station)
└── multi_station_reanalysis.ipynb  # Manual validation notebook (all stations)
```

## Test Structure

**Suite Organization:**
- Not applicable — no test suites exist.

**Patterns:**
- Validation is performed by running notebooks end-to-end and visually inspecting outputs (plots and CSVs).
- Intermediate `print()` statements serve as the only runtime assertions, e.g.:
  ```python
  print(f"Model: {len(mdl_daily)} daily rows ({mdl_daily.index[0].date()} → {mdl_daily.index[-1].date()})")
  print(f"Q = {Q:.6f} (std={np.sqrt(Q):.4f}), R = {R:.6f} (std={np.sqrt(R):.4f})")
  ```
- A `WARNING:` print in `data_loader.py` is the only defensive guard:
  ```python
  # Sprint_2/Reanalysis_Pipeline/src/data_loader.py, line 86
  print(f"  WARNING: No observations found for station={station_filter}, param={param_filter}")
  return pd.DataFrame(columns=["value"])
  ```

## Mocking

**Framework:** None.

**Patterns:**
- No mocking infrastructure exists.
- Functions that load from disk (`load_model_data`, `load_observations`) are untested in isolation.

**What to Mock (when tests are added):**
- `pd.read_csv` calls in `data_loader.py` — use small in-memory DataFrames.
- Trained Keras LSTM model in `enkf.py` and `openloop.py` — substitute a fixed-output lambda or stub model to avoid TensorFlow training overhead in tests.
- File system writes in `postprocessing.export_results` — use `tmp_path` (pytest fixture).

**What NOT to Mock:**
- NumPy array math in `preprocessing.py`, `postprocessing.py`, `enkf.py` — these are pure functions and should be tested with real arrays.

## Fixtures and Factories

**Test Data:**
- No fixtures exist. When tests are added, recommended synthetic fixtures:
  ```python
  # Minimal model DataFrame (sub-daily, 30 days)
  import pandas as pd, numpy as np
  dates = pd.date_range("2000-01-01", periods=60, freq="12h")
  model_df = pd.DataFrame({"value": np.random.uniform(1, 10, 60)}, index=dates)

  # Minimal sparse obs DataFrame (monthly)
  obs_dates = pd.date_range("2000-01-15", periods=3, freq="MS")
  obs_df = pd.DataFrame({"value": [3.0, 4.5, 2.1]}, index=obs_dates)
  ```

**Location:**
- No fixtures directory. Recommend `Sprint_2/Reanalysis_Pipeline/tests/fixtures/` when created.

## Coverage

**Requirements:** None enforced.

**View Coverage:**
```bash
# Not yet configured. Once pytest is installed:
pytest --cov=Sprint_2/Reanalysis_Pipeline/src --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- None exist. The following pure functions are the highest-value targets because they have no I/O or ML dependencies:
  - `preprocessing.resample_model_to_daily` — `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py`
  - `preprocessing.align_dense` — verifies inner-join date intersection logic
  - `preprocessing.align_sparse` — verifies NaN-fill behavior for missing obs dates
  - `preprocessing.standardize` — verifies Z-score output properties (mean≈0, std≈1)
  - `preprocessing.build_sequences` — verifies output shapes `(T-lookback, lookback, 1)` and `(T-lookback, 1)`
  - `preprocessing.train_val_split` — verifies no temporal shuffling and correct split index
  - `postprocessing.compute_ci_bounds` — verifies percentile outputs, shape `(T,)` each
  - `postprocessing.compute_ci_integral` — verifies trapezoidal integral returns expected dict keys
  - `postprocessing.inverse_transform` — verifies round-trip with `StandardScaler`
  - `enkf.compute_obs_error` — verifies `R = 0.2 * var(valid_obs)` ignoring NaN
  - `lstm_model.estimate_process_noise` — verifies `Q = var(residuals, ddof=1)`

**Integration Tests:**
- None exist. Recommended integration test: run `pipeline.run_single_reanalysis()` with a minimal synthetic dataset (30 days, monthly obs) and assert output CSVs are created and contain the expected columns.
  - Entry point: `Sprint_2/Reanalysis_Pipeline/src/pipeline.py`

**E2E Tests:**
- Not formalized. Manual notebook execution (`reanalysis_creation.ipynb`) is the de facto E2E test.

## Common Patterns

**Async Testing:**
- Not applicable — all code is synchronous.

**Numerical Assertion Pattern (recommended when tests are added):**
```python
import numpy as np
# Use np.testing for floating-point array comparisons
np.testing.assert_allclose(actual, expected, rtol=1e-5)
# For shape checks
assert result.shape == (T - lookback, lookback, 1)
# For NaN preservation
assert np.isnan(obs_aligned["value"].iloc[5])
```

**Error Testing (recommended):**
```python
import pytest
# Verify ValueError on unknown observation type
with pytest.raises(ValueError, match="Unknown observation type"):
    load_observations(obs_dir, {"type": "invalid_type"})
```

**Seed Reproducibility Pattern (existing in source):**
- All stochastic modules accept a `seed` parameter defaulting to `42`.
- `pipeline.run_single_reanalysis` calls `np.random.seed(seed)` and `tf.random.set_seed(seed)` before any computation.
- Tests must set the same seed to get deterministic outputs from `enkf.run_enkf` and `openloop.run_openloop`.

---

*Testing analysis: 2026-03-28*
