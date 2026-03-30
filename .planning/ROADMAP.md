# Roadmap: Reanalysis Dashboard

## Overview

The dashboard is already substantially built. The pipeline core is complete and the Python bridge layer is framework-agnostic. The work ahead is four targeted efforts: generalize the hardcoded column assumptions so any researcher's CSV works; migrate to a plain HTML/FastAPI app with full robustness (live streaming, cancellation, multi-run safety); deliver a clean downloadable result; then package everything into a one-step installer for demo day. Each phase delivers something a non-ML researcher can verify by using the app.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Pipeline Generalization** - Remove hardcoded Peace River column assumptions; users select date and value columns from dropdowns populated by their own CSV headers
- [ ] **Phase 2: HTML App Migration and Reliability** - Replace Streamlit with a FastAPI + Alpine.js + Tailwind CSS app; deliver live log streaming via SSE, plain-English error handling, stop/cancel, and multi-run memory safety
- [ ] **Phase 3: Output and Results** - Users can download the reanalysis CSV with mean and 95% CI bounds after a successful run
- [ ] **Phase 4: Packaging and Distribution** - App launches with a single `docker run` command; no Python or pip required on the target machine

## Phase Details

### Phase 1: Pipeline Generalization
**Goal**: Any researcher can upload their own model CSV and observation CSV, select their date and value columns from dropdowns, and run the pipeline on data that has nothing to do with Peace River
**Depends on**: Nothing (first phase)
**Requirements**: UPLOAD-01, UPLOAD-02, UPLOAD-03, REL-02
**Success Criteria** (what must be TRUE):
  1. User uploads a model CSV with arbitrary column names and the app does not reject it with a "wrong format" error
  2. User sees date column and value column dropdowns populated from their uploaded CSV headers (not a hardcoded list of Peace River variable names)
  3. User sees a preview of the first rows of both uploaded CSVs before clicking Run
  4. A synthetic non-Peace-River CSV (e.g., columns: timestamp, streamflow_cms, nitrate_mgl) runs end-to-end without a KeyError or column mismatch crash
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md -- Add generic bridge functions (get_csv_numeric_columns, get_csv_preview, build_model_df_generic)
- [ ] 01-02-PLAN.md -- Rework Step 0 UI for dynamic column selection and wire _start_job()
**UI hint**: yes

### Phase 2: HTML App Migration and Reliability
**Goal**: Replace the Streamlit UI with a FastAPI + Alpine.js + Tailwind CSS app that delivers the same 4-step wizard workflow — with live log streaming via SSE, plain-English error messages, stop/cancel, and multi-run memory safety. The pipeline core and bridge layer are reused unchanged.
**Depends on**: Phase 1
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04, REL-01, REL-03
**Success Criteria** (what must be TRUE):
  1. User sees live log output in the browser updating during LSTM training and EnKF execution — the page is not frozen or blank while the pipeline runs
  2. User sees a plain-English error message (not a Python traceback) when the pipeline fails due to a known input problem
  3. User can click Stop to cancel a running job and the app returns to a ready state without requiring a browser reload
  4. Running the pipeline a second time in the same session produces the same speed and memory footprint as the first run — no slowdown or OOM from TF graph accumulation
  5. Matplotlib-generated plots do not cause Windows display errors or figure-registry memory leaks across multiple runs
  6. App runs with `uvicorn server:app` (or `python server.py`) — no Streamlit dependency required
**Plans**: 4 plans
Plans:
- [ ] 02-01-PLAN.md -- Install FastAPI deps, add stop_event to pipeline.py, update job_runner.py, add _BytesShim
- [ ] 02-02-PLAN.md -- Create server.py with all API routes + test stubs
- [ ] 02-03-PLAN.md -- Create Alpine.js + Tailwind CSS wizard frontend (static/index.html)
- [ ] 02-04-PLAN.md -- Delete Streamlit app.py + human-verify full wizard flow

### Phase 3: Output and Results
**Goal**: Users can retrieve their reanalysis result as a downloadable CSV after a successful run
**Depends on**: Phase 2
**Requirements**: OUTPUT-01
**Success Criteria** (what must be TRUE):
  1. After a successful run, the results page shows a Download CSV button
  2. The downloaded CSV contains a time column, a reanalysis mean column, a lower 95% CI bound column, and an upper 95% CI bound column
  3. The file downloads to the user's machine without error when clicked
**Plans**: TBD
**UI hint**: yes

### Phase 4: Packaging and Distribution
**Goal**: A faculty committee member or researcher with no Python knowledge can launch the app by running a single command, on any machine with Docker installed
**Depends on**: Phase 3
**Requirements**: PKG-01
**Success Criteria** (what must be TRUE):
  1. A machine with only Docker Desktop installed (no Python, no pip, no conda) can launch the app with one command and reach the upload screen in a browser
  2. The Docker image builds reproducibly from the repository without manual dependency resolution
  3. Running `docker run` (or `docker compose up`) is the only step required beyond having Docker — no editing of config files or environment variables
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Generalization | 0/2 | Planned | - |
| 2. HTML App Migration and Reliability | 0/4 | Planned | - |
| 3. Output and Results | 0/TBD | Not started | - |
| 4. Packaging and Distribution | 0/TBD | Not started | - |
