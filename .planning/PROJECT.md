# Reanalysis Dashboard

## What This Is

A general-purpose data assimilation app that lets any researcher upload two CSVs (model output + observations), select their target variable from a dropdown, and run an LSTM + Ensemble Kalman Filter reanalysis on their local machine. The app streams live progress logs during execution and delivers a downloadable reanalysis CSV with confidence intervals plus inline visualization. It is designed to be installable in one step — no coding required.

## Core Value

A researcher with no ML background can go from raw CSVs to a calibrated reanalysis dataset with uncertainty bounds in under 30 minutes, entirely in a browser.

## Requirements

### Validated

- ✓ LSTM neural network training (64-unit, Adam+MSE, early stopping) — existing
- ✓ Ensemble Kalman Filter (50-member perturbed-observation, intermittent assimilation) — existing
- ✓ Data preprocessing (sub-daily → daily, Z-score standardization, sliding window) — existing
- ✓ Open-loop baseline run (no-DA comparison) — existing
- ✓ Postprocessing (inverse transform, 95% CI, uncertainty integral) — existing
- ✓ Visualization (time-series comparison, CI shading, model-vs-observed scatter) — existing
- ✓ Streamlit dashboard scaffold (file upload, column mapping, progress display, results) — existing

### Active

- [ ] Pipeline generalized to accept arbitrary CSV columns (not hardcoded Flow/TN/TP)
- [ ] User selects target variable via dropdown populated from uploaded CSV headers
- [ ] User selects observation column via dropdown populated from uploaded observation CSV
- [ ] Live log output streams to browser during LSTM training and EnKF execution
- [ ] Results page shows inline time-series chart with CI shading
- [ ] Results page provides downloadable reanalysis CSV (mean + CI bounds)
- [ ] One-step installation (Docker or packaged installer — TBD)
- [ ] End-to-end pipeline runs reliably without crashes on arbitrary well-formed CSVs

### Out of Scope

- Multi-station batch runs in the UI — complexity not needed for demo; pipeline.py supports it internally
- Authentication / user accounts — single-user local tool
- Cloud deployment / hosted version — runs on local resources by design
- Real-time database ingestion — CSV upload is the input interface
- Support for malformed or non-CSV data formats — inputs are expected to be well-formed

## Context

**Existing pipeline (Sprint_2/Reanalysis_Pipeline/src/):** Eight Python modules implementing the full LSTM+EnKF sequence. Currently hardcoded for Peace River, FL stations with specific column names (SimDate, Flow, TN, TP) and station ID / parameter filtering. Needs to be generalized to accept any DatetimeIndex column as model input and any numeric column as the observation target.

**Existing dashboard (Reanalysis_Dashboard/):** A 780-line Streamlit app (app.py + pipeline_bridge.py + job_runner.py) built as a first pass. Implements file upload, a five-step wizard, background threading for non-blocking execution, and a results display. Has tight coupling to the current column naming conventions — needs to be refactored alongside the pipeline generalization.

**Tech stack:** Python 3.13, TensorFlow 2.20, pandas 2.3, NumPy 2.3, scikit-learn 1.7, SciPy 1.16, Matplotlib 3.10, Streamlit (dashboard), PyYAML. No web server required — Streamlit handles everything.

**Demo audience:** Faculty committee (needs to work reliably on demo day), potential employers (portfolio quality), domain researchers (needs to be genuinely usable beyond demo). Demo day is approximately 4–6 weeks out.

**Known issues to address:**
- Pipeline uses hardcoded column names throughout data_loader.py and preprocessing.py
- YAML config (pipeline_config.yaml) has hardcoded station/file paths — needs to be bypassed or replaced for arbitrary uploads
- Matplotlib must use Agg backend to prevent Windows display errors
- UTF-8 BOM handling required for some observation CSVs (utf-8-sig encoding)

## Constraints

- **Timeline**: Demo day in ~4–6 weeks — scope must be achievable in that window
- **Tech Stack**: Python + Streamlit — no framework changes; already committed
- **Local execution**: Pipeline must run on user's hardware — no cloud dependency
- **TensorFlow**: Required for LSTM; large dependency (~500MB) affects installer size
- **Packaging TBD**: Docker vs downloadable installer not yet decided — affects Phase structure

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Streamlit for UI | Rapid development, Python-native, no frontend skills needed for senior project | — Pending |
| LSTM + EnKF | Core academic contribution — the algorithm itself is not up for change | — Pending |
| Variable selection via dropdown | User picks from CSV headers — no typing, handles arbitrary column names | — Pending |
| Docker or installer for packaging | Both provide one-step install; Docker more portable, installer more accessible | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-29 after initialization*
