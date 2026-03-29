# Requirements: Reanalysis Dashboard

**Defined:** 2026-03-29
**Core Value:** A researcher with no ML background can go from raw CSVs to a calibrated reanalysis dataset with uncertainty bounds in under 30 minutes, entirely in a browser.

## v1 Requirements

### Data Upload

- [ ] **UPLOAD-01**: User can upload a model CSV and an observation CSV from their local machine
- [ ] **UPLOAD-02**: User can select the date column and target variable column from dropdowns auto-populated from uploaded CSV headers (model CSV) and from uploaded observation CSV headers
- [ ] **UPLOAD-03**: User can preview the first rows of each uploaded CSV before proceeding to run

### Pipeline Execution

- [ ] **EXEC-01**: Pipeline runs in a background thread — UI remains responsive during execution
- [ ] **EXEC-02**: User sees live log output in the browser during LSTM training and EnKF execution
- [ ] **EXEC-03**: User sees a readable, plain-English error message if the pipeline fails (not a raw Python traceback)
- [ ] **EXEC-04**: User can cancel a running job with a Stop/Cancel button

### Output

- [ ] **OUTPUT-01**: User can download the reanalysis result as a CSV containing the time series mean and 95% confidence interval bounds

### Distribution

- [ ] **PKG-01**: App launches with a single `docker run` command on any machine with Docker installed (no Python, no pip, no conda required)

### Reliability

- [ ] **REL-01**: TensorFlow graph state is cleared between runs — no memory accumulation or slowdown after multiple jobs in the same session
- [ ] **REL-02**: Pipeline accepts arbitrary CSV column names for both model and observation inputs — not hardcoded to SimDate/Flow/TN/TP or any Peace River–specific naming
- [ ] **REL-03**: Matplotlib uses Agg backend with explicit figure cleanup — no Windows display errors or figure registry memory leaks

## v2 Requirements

### Results Visualization

- **VIZ-01**: Inline time-series chart showing reanalysis mean and 95% CI shading in the browser
- **VIZ-02**: Model vs observed scatter plot shown inline on the results page
- **VIZ-03**: Interactive (zoom/pan) Plotly charts for exploring results

### Distribution

- **PKG-02**: README with step-by-step installation instructions for non-technical users
- **PKG-03**: pip-based install path for users who already have Python

### Robustness

- **ROB-01**: Pre-flight validation warns user if lookback window exceeds available time series length
- **ROB-02**: Pre-flight validation warns user if observation CSV has near-zero variance (would produce silent NaN output)
- **ROB-03**: Data quality summary shown after upload (row count, date range, null values)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-station batch runs in UI | Complexity out of scope for demo; pipeline.py supports it internally |
| Authentication / user accounts | Single-user local tool — no server, no identity |
| Cloud deployment / hosted version | Runs on local resources by design; cloud hosting is a different product |
| Real-time database / API ingestion | CSV upload is the input interface |
| AutoML / automatic hyperparameter tuning | Out of scope; users set hyperparameters manually |
| In-app data editing | Out of scope; users edit CSVs externally |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UPLOAD-01 | Phase 1 | Pending |
| UPLOAD-02 | Phase 1 | Pending |
| UPLOAD-03 | Phase 1 | Pending |
| REL-02 | Phase 1 | Pending |
| EXEC-01 | Phase 2 | Pending |
| EXEC-02 | Phase 2 | Pending |
| EXEC-03 | Phase 2 | Pending |
| EXEC-04 | Phase 2 | Pending |
| REL-01 | Phase 2 | Pending |
| REL-03 | Phase 2 | Pending |
| OUTPUT-01 | Phase 3 | Pending |
| PKG-01 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after roadmap creation — all 12 v1 requirements mapped*
