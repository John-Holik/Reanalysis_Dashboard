# External Integrations

**Analysis Date:** 2026-03-28

## APIs & External Services

**None detected.**
- The pipeline is fully offline. All data is pre-downloaded and stored as local CSV files.
- No HTTP clients, REST API calls, or cloud SDK imports appear anywhere in the source modules.

## Data Storage

**Databases:**
- None. No database connections, ORMs, or connection strings.

**File Storage — Local Filesystem Only:**
- All I/O is via local CSV files read with `pandas.read_csv()` and written with `DataFrame.to_csv()`

**Input data roots (relative to `Sprint_2/`):**
- Model simulations: `Sprint_2/Model_Data/` — sub-daily CSVs with columns `SimDate`, `Flow`, `TN`, `TP`
  - `Station 02296750 (ARCADIA)_reach000084_83.csv`
  - `Station 270318081593100_reach000004_3.csv`
  - `Station_2297330_reach000007_6.csv`
- Observation discharge: `Sprint_2/Model_Data/Oserved flow_ARCADIA_FL.csv` — columns `Date`, `Discharge_CMS`
- Observation water quality: `Sprint_2/Observation_Data/HU8_03100101_TN_TP.csv` — columns `StationID`, `Parameter`, `SampleDate`, `Result_Value`
- Additional flow observations: `Sprint_2/Observation_Data/HU8_03090205_Flow.csv`, `HU8_03100101_Flow.csv`, `HU8_03090205_TN_TP.csv`

**Output data root:**
- `Sprint_2/Reanalysis_Pipeline/outputs/<station_id>_<name>/<variable>/` — per-station, per-variable CSVs and PNGs
  - `obs_<var>.csv`, `model_openloop_<var>.csv`, `reanalysis_<var>_mean.csv`, `reanalysis_<var>_ensemble.csv`
- Summary directory: `Sprint_2/Reanalysis_Pipeline/outputs/summary/`
  - `ci_integral_summary.csv`, `data_availability.csv`, cross-station CI plots

**Caching:**
- In-memory file cache in `data_loader.py` (`_obs_file_cache` dict) prevents re-reading large multi-station observation CSVs within a single pipeline run

## Data Formats and Protocols

**Input CSV schemas:**
- Model input: `SimDate` (mixed datetime), `Flow` (CMS float), `TN` (mg/L float), `TP` (mg/L float) — sub-daily rows
- Dedicated discharge observations: `Date` (parsed datetime), `Discharge_CMS` (float)
- Multi-station water quality observations: `StationID` (string), `Parameter` (string: `TN_ugl`, `TP_ugl`), `SampleDate` (mixed datetime), `Result_Value` (float, in µg/L), optional `Actual_StationID` fallback column

**Unit conversions (applied in config):**
- TN and TP observations: `convert_factor: 0.001` — converts µg/L to mg/L
- Discharge: no conversion (already in CMS)

**Output CSV schemas:**
- `obs_<var>.csv` / `model_openloop_<var>.csv` / `reanalysis_<var>_mean.csv`: wide format — DatetimeIndex `time`, single value column named by variable
- `reanalysis_<var>_ensemble.csv`: long format — columns `time`, `member` (0–49), `<variable>` (50 rows per time step)

**Plot outputs:**
- PNG at 300 DPI via `matplotlib.pyplot.savefig(..., dpi=300, bbox_inches="tight")`
- Three plot types per station-variable: `<var>_Comparison.png`, `CI_Area_<var>.png`, `Model_vs_Observed_<var>.png`

## Authentication & Identity

- None. No authentication required — fully local file-based system.

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or equivalent.

**Logs:**
- `print()` statements throughout source modules for progress reporting (epoch counts, EnKF time step progress, file save confirmations)
- No structured logging framework

## CI/CD & Deployment

**Hosting:**
- Not applicable — local research pipeline, no server deployment

**CI Pipeline:**
- None detected — no `.github/workflows/`, no CI config files

## Environment Configuration

**Required environment variables:**
- None. The pipeline uses no environment variables.
- All paths are resolved from the YAML config (`pipeline_config.yaml`) relative to `config_dir` via `config.resolve_path()`

**Secrets:**
- None. No API keys, tokens, or credentials anywhere in the codebase.

**Config file location:**
- `Sprint_2/Reanalysis_Pipeline/configs/pipeline_config.yaml` — single source of truth for paths, station definitions, and all ML hyperparameters

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## External Data Sources (Offline)

The observation data originates from these external agencies but is consumed as pre-downloaded CSV files — no live API calls are made at runtime:
- **USGS National Water Information System (NWIS)** — daily discharge at Arcadia gauge (station 02296750)
- **Florida Department of Environmental Protection (FDEP) / EPA STORET** — TN and TP water quality observations in HU8 watershed datasets (`HU8_03100101`, `HU8_03090205`)
- **Hydrological model output** — simulated sub-daily flow/nutrient data (SWAT or similar; model provenance documented in `Sprint_2/Model_Data/Calibration information.docx`)

---

*Integration audit: 2026-03-28*
