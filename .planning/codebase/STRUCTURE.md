# Codebase Structure

**Analysis Date:** 2026-03-28

## Directory Layout

```
Senior_Project/
├── Sprint_2/
│   ├── Model_Data/                   # Raw HSPF model simulation CSVs and calibration docs
│   ├── Observation_Data/             # Raw USGS/WQP observation CSVs (flow, TN, TP)
│   ├── Revised for clarity/          # Archived duplicate of Model_Data (clarity revision)
│   ├── Reanalysis_Pipeline/
│   │   ├── src/                      # All pipeline source modules (Python package)
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py           # Orchestration entry point
│   │   │   ├── data_loader.py        # CSV ingestion and filtering
│   │   │   ├── preprocessing.py      # Resampling, alignment, scaling, sequences
│   │   │   ├── lstm_model.py         # LSTM architecture, training, Q estimation
│   │   │   ├── enkf.py               # Ensemble Kalman Filter assimilation
│   │   │   ├── openloop.py           # No-DA baseline run
│   │   │   ├── postprocessing.py     # Inverse transform, CI, export
│   │   │   ├── visualization.py      # Matplotlib plot generation
│   │   │   └── config.py             # YAML config loader
│   │   ├── configs/
│   │   │   └── pipeline_config.yaml  # Station definitions and hyperparameters
│   │   ├── outputs/                  # Generated results (gitignore-able, runtime artifact)
│   │   │   ├── 02296750_Arcadia/
│   │   │   │   ├── discharge/        # CSVs + PNGs for discharge variable
│   │   │   │   ├── TN/               # CSVs + PNGs for Total Nitrogen
│   │   │   │   └── TP/               # CSVs + PNGs for Total Phosphorus
│   │   │   ├── 270318081593100_FtOgden_RM1482/
│   │   │   │   ├── TN/
│   │   │   │   └── TP/
│   │   │   └── summary/              # Cross-station summary CSVs and plots
│   │   ├── reanalysis_creation.ipynb # Single-station tutorial notebook (Arcadia discharge)
│   │   ├── multi_station_reanalysis.ipynb  # Full pipeline notebook (all stations × variables)
│   │   └── [legacy root-level CSVs/PNGs]   # Artifacts from earlier single-station runs
│   ├── flowchart.png                 # Pipeline architecture diagram
│   └── Uncertainty Analysis Methods.pdf   # Reference document
├── Reanalysis_Dashboard/             # Separate git submodule/repo (visualization dashboard)
├── CLAUDE.md                         # Project guidance for Claude Code
└── .planning/
    └── codebase/                     # GSD analysis documents
```

## Directory Purposes

**`Sprint_2/Model_Data/`:**
- Purpose: Raw HSPF model output CSVs for each station reach, plus observed discharge file for Arcadia
- Contains: Three station model CSVs (`Station 02296750 (ARCADIA)_reach000084_83.csv`, `Station 270318081593100_reach000004_3.csv`, `Station_2297330_reach000007_6.csv`), `Oserved flow_ARCADIA_FL.csv`, `Calibration information.docx`
- Key files: `Sprint_2/Model_Data/Station 02296750 (ARCADIA)_reach000084_83.csv`

**`Sprint_2/Observation_Data/`:**
- Purpose: USGS/WQP water quality observation CSVs organized by HUC8 watershed
- Contains: `HU8_03090205_Flow.csv`, `HU8_03090205_TN_TP.csv`, `HU8_03100101_Flow.csv`, `HU8_03100101_TN_TP.csv`, `peace_river_discharge_arcadia.csv`
- Key files: `Sprint_2/Observation_Data/HU8_03100101_TN_TP.csv` (primary TN/TP source for all configured stations)

**`Sprint_2/Reanalysis_Pipeline/src/`:**
- Purpose: The importable Python package containing all pipeline logic
- Contains: Nine `.py` modules covering every pipeline stage
- Key files: `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` (orchestrator)

**`Sprint_2/Reanalysis_Pipeline/configs/`:**
- Purpose: YAML configuration defining stations, file paths, observation metadata, and hyperparameters
- Key files: `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`

**`Sprint_2/Reanalysis_Pipeline/outputs/`:**
- Purpose: All generated artifacts from pipeline runs — CSVs and PNG plots per station-variable combination, plus cross-station summaries
- Contains: Subdirectories named `<station_id>_<name>/<variable>/` holding seven files each (3 CSVs + 3 PNGs + ensemble CSV)
- Generated: Yes — created at runtime by `postprocessing.py` and `visualization.py`
- Committed: Currently committed but could be gitignored

**`Sprint_2/Reanalysis_Pipeline/outputs/summary/`:**
- Purpose: Cross-station aggregated outputs
- Key files: `outputs/summary/ci_integral_summary.csv`, `outputs/summary/data_availability.csv`

**`Sprint_2/Revised for clarity/`:**
- Purpose: Archived duplicate of `Model_Data/` contents; appears to be a renamed copy kept for reference
- Generated: No — static archive

**`Reanalysis_Dashboard/`:**
- Purpose: Separate git repository (submodule) for an interactive visualization dashboard consuming pipeline outputs
- Contains: Independent git history and `.gitignore`

## Key File Locations

**Entry Points (notebooks):**
- `Sprint_2/Reanalysis_Pipeline/reanalysis_creation.ipynb`: Single-station Arcadia discharge tutorial; self-contained walkthrough
- `Sprint_2/Reanalysis_Pipeline/multi_station_reanalysis.ipynb`: Production pipeline; reads `pipeline_config.yaml`, iterates all stations × variables, writes all outputs

**Pipeline Orchestrator:**
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py`: `run_single_reanalysis()` — the single function that runs all 11 pipeline steps for one station-variable pair

**Configuration:**
- `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml`: Station definitions, observation file mappings, unit conversions, all hyperparameters

**Core ML Modules:**
- `Sprint_2/Reanalysis_Pipeline/src/lstm_model.py`: LSTM build, train, Q estimation
- `Sprint_2/Reanalysis_Pipeline/src/enkf.py`: EnKF with sparse assimilation logic
- `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py`: Resampling, alignment (dense/sparse), Z-score, sequence builder

**Output Modules:**
- `Sprint_2/Reanalysis_Pipeline/src/postprocessing.py`: Inverse transform, 95% CI percentiles, CI integral
- `Sprint_2/Reanalysis_Pipeline/src/visualization.py`: Three plot types per station-variable

**Package Init:**
- `Sprint_2/Reanalysis_Pipeline/src/__init__.py`: Makes `src/` importable as a package from the notebooks

## Naming Conventions

**Source modules:**
- All lowercase, underscore-separated: `data_loader.py`, `lstm_model.py`, `postprocessing.py`

**Output directories:**
- Pattern: `<station_id>_<station_name>/` — e.g., `02296750_Arcadia/`, `270318081593100_FtOgden_RM1482/`

**Output CSV files:**
- `obs_<variable>.csv` — filtered observations
- `model_openloop_<variable>.csv` — no-DA baseline
- `reanalysis_<variable>_mean.csv` — EnKF posterior mean
- `reanalysis_<variable>_ensemble.csv` — all 50 ensemble members (long format: time, member, value)

**Output PNG files:**
- `<Variable>_Comparison.png` — obs vs. open-loop vs. reanalysis mean time series
- `CI_Area_<variable>.png` — 95% confidence interval shading
- `Model_vs_Observed_<variable>.png` — scatter/time comparison of model and obs

**Config YAML keys:**
- Station-level: `station_id`, `name`, `model_file`, `observations`
- Variable-level observation keys: `file`, `type`, `station_id_filter`, `parameter_filter`, `date_col`, `value_col`, `convert_factor`

## Where to Add New Code

**New pipeline stage (e.g., bias correction, post-processing step):**
- Implementation: `Sprint_2/Reanalysis_Pipeline/src/<new_module>.py`
- Wire it in: `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` inside `run_single_reanalysis()`

**New station:**
- Add a station block to `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml` following the existing pattern
- Place model CSV in `Sprint_2/Model_Data/`
- Place observation CSV in `Sprint_2/Observation_Data/` (or reference an existing one with a new `station_id_filter`)

**New variable (e.g., Total Suspended Solids):**
- Add variable entry under the station's `observations:` block in `pipeline_config.yaml`
- Confirm `data_loader.py` handles the new `parameter_filter` value
- No source code changes required if data format matches existing convention

**New visualization type:**
- Add function to `Sprint_2/Reanalysis_Pipeline/src/visualization.py`
- Call it from the Step 11 block in `Sprint_2/Reanalysis_Pipeline/src/pipeline.py`

**Utility / shared helper:**
- Place in `Sprint_2/Reanalysis_Pipeline/src/` as a new module, or add to the most relevant existing module (e.g., data utilities in `data_loader.py`, numeric helpers in `preprocessing.py`)

**Tests (if introduced):**
- No test directory exists yet; create `Sprint_2/Reanalysis_Pipeline/tests/` with `test_<module>.py` files mirroring the `src/` structure

## Special Directories

**`Sprint_2/Reanalysis_Pipeline/src/__pycache__/`:**
- Purpose: Python bytecode cache for the `src` package
- Generated: Yes — by Python interpreter at import time
- Committed: Currently committed; should be added to `.gitignore`

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents consumed by `/gsd:plan-phase` and `/gsd:execute-phase`
- Generated: Yes — by GSD map-codebase command
- Committed: Yes — serves as persistent project knowledge

**`Reanalysis_Dashboard/`:**
- Purpose: Nested git repository for the dashboard; tracked as a submodule or standalone repo
- Generated: No
- Committed: Tracked by outer repo (at minimum the `.git` reference)

---

*Structure analysis: 2026-03-28*
