# Project Research Summary

**Project:** Reanalysis Dashboard — LSTM + EnKF hydrological data assimilation web app
**Domain:** Scientific ML pipeline packaged as a local single-user web application
**Researched:** 2026-03-29
**Confidence:** HIGH (architecture, features, pitfalls from direct code analysis) / MEDIUM (stack additions)

## Executive Summary

The Reanalysis Dashboard is a substantially built product, not a greenfield project. The LSTM + EnKF pipeline core (`Sprint_2/Reanalysis_Pipeline/src/`) is complete and correct. The Streamlit dashboard (`Reanalysis_Dashboard/`) is functional for Peace River data but is hardcoded to specific column names (`SimDate`, `Flow`, `TN`, `TP`) throughout the bridge and UI layers. The central engineering challenge is generalization: replacing those hardcoded column assumptions with user-driven column selection, without disrupting the working algorithm core. All research agrees that `pipeline.py` itself is already generic — it accepts normalized DataFrames and a `variable` string. The coupling is isolated to `pipeline_bridge.py` and `app.py` Step 0, which makes the generalization a targeted refactor rather than a rebuild.

The recommended approach is: generalize the bridge and UI first, harden robustness second (validation, error messages, known pitfalls), then package last. Docker with `python:3.13-slim` is the right distribution target for reliability on demo day, but the plain pip + venv path is essential for developer iteration and as a fallback if Docker pull on conference wifi is impractical. The packaging decision should be made early because it affects the final phase's structure, but it must not block the core generalization work.

The highest-risk areas are the six critical pitfalls identified from direct code inspection: global `sys.stdout` mutation in the background thread, TensorFlow graph state accumulation across multiple runs, hardcoded column name assumptions spread across three locations, Streamlit UploadedFile buffer exhaustion on Back/Next navigation, zero-variance observation scaler producing all-NaN output silently, and matplotlib figure registry contamination in threaded execution. All six are preventable with targeted, well-scoped fixes. The most demo-threatening are the TF memory accumulation (degrades with repeated runs), the UploadedFile buffer issue (fails silently after Back navigation), and the stdout race (corrupts log display on browser reload). These must be addressed before any public demo run.

---

## Key Findings

### Recommended Stack

The existing stack is locked and correct — do not swap frameworks. Python 3.13, TensorFlow 2.20, pandas 2.3, NumPy 2.3, scikit-learn 1.7, SciPy 1.16, Matplotlib 3.10 (Agg backend), Streamlit, and PyYAML are all in use and working. No new runtime dependencies are required for the UI improvements. PyInstaller is explicitly ruled out for distribution due to TensorFlow's dynamic library incompatibilities. The main addition needed is `pip-tools` for the developer toolchain to produce a pinned `requirements.txt` suitable for Docker layer caching.

For packaging, Docker with `python:3.13-slim` (not Alpine — musl libc breaks TF wheels) is the recommended end-user path. The image will be approximately 2.5 GB due to TensorFlow's size, which has practical implications for demo-day logistics: the image should be pre-built and transferred via USB/local network rather than pulled over conference wifi. A plain pip + venv path remains essential for developer use and as a backup.

**Core technologies:**
- **Python 3.13 + Streamlit**: UI framework — already committed, handles session state, file upload, background threading, progress display
- **TensorFlow 2.20**: LSTM training and `tf.function`-compiled EnKF inference — non-negotiable academic contribution
- **Docker (python:3.13-slim)**: Distribution packaging — provides environment isolation and one-step install for non-coders
- **pip-tools**: Developer dependency management — produces locked, hash-verified `requirements.txt` for reproducible Docker builds
- **`contextlib.redirect_stdout`**: Stdout capture replacement — thread-safe alternative to the current global `sys.stdout` mutation

### Expected Features

Research based on direct code analysis of the existing 780-line dashboard combined with known Streamlit scientific tool UX patterns.

**Must have (table stakes — blocks basic usability without these):**
- Flexible model CSV ingestion — remove the hardcoded `{"SimDate", "Flow", "TN", "TP"}` validation gate that rejects any non-Peace-River CSV
- User-driven date column + value column selection — dropdowns populated from uploaded CSV headers, same pattern the obs CSV path already uses correctly
- Meaningful error messages on pipeline failure — map known exception types (empty obs match, short train set, zero-variance obs) to actionable user guidance instead of raw tracebacks
- Validation feedback before run — at minimum: obs match count, date overlap check, row count and date range display

**Should have (raise quality from demo to genuinely usable):**
- Structured progress with LSTM training epoch counter — transforms a 10-minute black-box wait into observable progress
- Pre-run data quality report — catches the known silent failure causes (empty obs match, R=NaN risk, too-short train set) before the job launches
- Graceful job cancellation — without this, users reload the browser and lose all session state as the only recovery path

**Defer (v2+):**
- Session state persistence across browser reload — high complexity, low demo-day value
- Interactive Plotly chart — valuable for researchers but not blocking; static PNG is acceptable for demo scope
- Run summary export (plain-text report) — useful for thesis appendix; achievable quickly if time allows but not critical path
- Side-by-side run comparison, multi-station batch UI, authentication, cloud deployment — all explicitly out of scope

### Architecture Approach

The architecture is three-zone with clear separation of concerns: Zone 1 (UI — `app.py`) collects user input and renders output; Zone 2 (Bridge — `pipeline_bridge.py`) translates user-provided files and column selections into normalized DataFrames with a `DatetimeIndex` and a single `"value"` column; Zone 3 (Pipeline Core — `src/`) executes the LSTM + EnKF algorithm on normalized DataFrames. This boundary is 90% enforced already. The refactor enforces it completely by replacing `build_model_df()` (hardcoded column names) with `build_model_df_generic(uploaded_file, date_col, value_col)` in the bridge, and updating `app.py` Step 0 to populate its column selectors from the CSV headers rather than a static list. The pipeline core does not need to change — `run_single_reanalysis()` already accepts generic DataFrames.

**Major components:**
1. **app.py (Zone 1 — UI)**: Wizard step routing, Streamlit session state, validation feedback display, polling loop, results display. Does not touch file parsing or DataFrame construction directly.
2. **pipeline_bridge.py (Zone 2 — Bridge)**: Format adapter. Translates `UploadedFile` + user column selections into normalized DataFrames. Owns encoding, date parsing, resampling contract. Re-exports `run_single_reanalysis` so Zone 1 never imports from `src/` directly.
3. **job_runner.py (Zone 2 — Threading)**: Daemon thread lifecycle, `Queue`-based log streaming, sentinel-value protocol (`__DONE__` / `__ERROR__`). Design is structurally correct; replace global `sys.stdout` redirect with `contextlib.redirect_stdout`.
4. **src/pipeline.py + modules (Zone 3 — Core)**: LSTM training, EnKF execution, postprocessing, visualization. Already generic. Only `visualization.py` needs a minor fix (fallback labels for unknown variable names).

### Critical Pitfalls

All six critical pitfalls are derived from direct code inspection at commit `0f4c566`.

1. **`sys.stdout` global race in background thread** — Replace `sys.stdout = _QueueWriter(q)` with `contextlib.redirect_stdout(_QueueWriter(q))` scoped to the `run_single_reanalysis` call. Prevents log corruption on browser reload mid-run.

2. **TensorFlow graph state accumulation across runs** — Call `tf.keras.backend.clear_session()` at the start of each worker thread before any TF code executes. Without this, memory grows and training slows with each "Run Another Analysis" click; OOM is possible after 4-5 runs.

3. **Hardcoded column names in three coupled locations** — `pipeline_bridge.py:build_model_df()`, `app.py:render_step_upload()` column validation, and `app.py` variable selectbox must all be updated together. Updating one without the others causes silent wrong-variable selection or mid-run `KeyError`.

4. **Streamlit UploadedFile buffer exhaustion** — Store raw `bytes` in `session_state` after upload (not the `UploadedFile` reference). Reconstruct `io.BytesIO` for each read. Fails reliably when user navigates Back then Next without re-uploading.

5. **Zero-variance observation scaler produces all-NaN output silently** — Add a pre-flight check: if `obs_df["value"].nunique() < 2` or `std == 0`, raise a descriptive `ValueError` before launching the job. The pipeline currently completes with status DONE but all outputs are NaN.

6. **Matplotlib figure registry contamination in threaded execution** — Add `plt.close("all")` after every `savefig()` in `visualization.py`. Guard the `matplotlib.use("Agg")` call with `if matplotlib.get_backend() != "Agg"`. Prevents `RuntimeError: dictionary changed size during iteration` and a 5-10MB per-run memory leak.

---

## Implications for Roadmap

Based on combined research, a four-phase structure is recommended. Dependencies flow cleanly: the bridge generalization is the foundation everything else depends on; input validation depends on having a working generic bridge; packaging depends on a stable, reliable pipeline.

### Phase 1: Pipeline Generalization

**Rationale:** The hardcoded column assumptions in `pipeline_bridge.py` and `app.py` are the single blocker that prevents the tool from working on any data except the original Peace River CSVs. This is the stated top Active requirement in `PROJECT.md`. Everything else — error messages, progress display, packaging — is meaningless if the pipeline rejects any non-Peace-River CSV. The architecture research confirms the pipeline core is already generic, making this refactor narrowly scoped.

**Delivers:** A dashboard that accepts any well-formed model CSV with any column names. Users can upload arbitrary simulation outputs and select their date and value columns via dropdowns.

**Addresses (from FEATURES.md):**
- Flexible model CSV ingestion (table stakes #1)
- User-driven date column selection (table stakes #2)
- Generalized variable dropdown from CSV headers (differentiator #7)

**Avoids (from PITFALLS.md):**
- Pitfall 3: Hardcoded column names in three coupled locations — must update all three simultaneously
- Pitfall 13: UTF-8 BOM inconsistency — fix `data_loader.py` encoding during same pass
- Pitfall 9: Partial-day resampling dropping model rows — one-line fix in `preprocessing.py` during same pass

**Build order within phase:** (1) Add `build_model_df_generic` + `get_csv_numeric_columns` to bridge (pure addition, no deletions); (2) Fix `visualization.py` UNITS/LABELS fallbacks (independent, 4-line change); (3) Update `app.py` Step 0 column validation and variable dropdown; (4) Smoke-test end-to-end with a synthetic non-Peace-River CSV.

---

### Phase 2: Robustness and Validation

**Rationale:** A generalized pipeline that crashes silently or shows raw tracebacks is not usable by a non-ML researcher. The features research identifies three "should have" items (progress with epoch counter, pre-run data quality report, graceful cancellation) and four "table stakes" items (validation feedback, meaningful error messages) that all address robustness. The pitfalls research identifies six critical issues to fix before any demo. This phase bundles them together because they all touch the same layer (bridge and UI hardening, job runner improvements) and they are independent of the packaging decision.

**Delivers:** A dashboard that catches configuration errors before the 10-minute job starts, shows structured training progress, handles "Run Another Analysis" without performance degradation, and doesn't crash on Back/Next navigation.

**Addresses (from FEATURES.md):**
- Validation feedback before run (table stakes #3)
- Meaningful error messages on pipeline failure (table stakes #4)
- Persistent progress indicator with phase labels (table stakes #5)
- Graceful job cancellation (table stakes #6)
- Data preview before committing to run (table stakes #7)
- Structured progress with training epoch counter (differentiator #1)
- Pre-run data quality report (differentiator #2)

**Avoids (from PITFALLS.md):**
- Pitfall 1: `sys.stdout` global race — replace with `contextlib.redirect_stdout`
- Pitfall 2: TF graph state accumulation — add `clear_session()` at thread start
- Pitfall 4: UploadedFile buffer exhaustion — store raw bytes in session state
- Pitfall 5: Zero-variance obs scaler — add pre-flight validation check
- Pitfall 6: Matplotlib figure registry — add `plt.close("all")` + backend guard
- Pitfall 8: Lookback exceeds time series length — add minimum sequence count assertion
- Pitfall 12: 2-second sleep reduces polling responsiveness — reduce to 0.5s

---

### Phase 3: UI Polish and Results Experience

**Rationale:** With a working generic pipeline and a robust execution path, this phase improves what researchers see before and after running. An interactive chart and a run summary export have clear value for demo day and thesis use. These are deferred until Phase 2 is complete to avoid wasting effort on display layer improvements that might need rework if the underlying pipeline is still changing.

**Delivers:** Interactive results visualization (Plotly), configurable output column headers, and a plain-text run summary download. The experience graduates from "functional demo" to "genuinely usable research tool."

**Addresses (from FEATURES.md):**
- Interactive results chart (differentiator #3) — Plotly in display layer, keep Matplotlib for saved PNG
- Configurable output column names in downloaded CSVs (differentiator #5)
- Run summary export, plain text (differentiator #6)
- Output file presence check with fallback message (table stakes #8)

**Avoids (from PITFALLS.md):**
- Pitfall 7: Tempfile accumulation — add cleanup handler or fixed output directory with Clear button (low effort, should be here)

---

### Phase 4: Packaging and Distribution

**Rationale:** Packaging is explicitly last because (a) a Docker image of a buggy pipeline is still a buggy pipeline, and (b) the packaging decision (Docker vs pip installer) does not affect any code in Phases 1-3. Research strongly recommends Docker with `python:3.13-slim` as the primary distribution path, with pip + venv as developer and fallback path. The Docker image will be approximately 2.5 GB; demo-day logistics require pre-building and distributing via USB/local transfer, not Docker Hub pull on conference wifi. This is the lowest-confidence phase because it depends on external environment factors (Docker Desktop on demo machine, wifi availability).

**Delivers:** A one-step installer (`docker compose up --build`) that any faculty committee member can run without Python knowledge. Pinned dependency versions via pip-tools. Documentation for both the Docker path and the fallback pip path.

**Addresses (from FEATURES.md — packaging context from PROJECT.md):**
- One-step installation (Active requirement in PROJECT.md)

**Avoids (from PITFALLS.md):**
- Pitfall 10: Docker image size — use `python:3.13-slim` + `tensorflow-cpu`; distribute image file via USB for demo day
- Pitfall 7: Tempfile accumulation — ensure cleanup is in place before public distribution

---

### Phase Ordering Rationale

- Phase 1 before Phase 2: You cannot validate robustness of a pipeline that rejects most input CSVs. The generalization creates the surface area that robustness testing exercises.
- Phase 2 before Phase 3: UI polish on top of an unreliable job runner wastes effort; the epoch counter and progress bar require the `contextlib.redirect_stdout` fix from Phase 2 to work correctly.
- Phase 3 before Phase 4: Package a stable, polished product. Running packaging in parallel with active code changes forces repeated image rebuilds and creates demo-day risk.
- Within Phase 1: Bridge additions before UI changes (pure addition, zero risk) before smoke testing with synthetic data.

---

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 4 (Packaging):** Docker Desktop prerequisites on Windows (WSL2 requirement), `tensorflow-cpu` vs full TF package availability on PyPI for Python 3.13, and exact `st.fragment` / `st.container(height=...)` API availability in the pinned Streamlit version all need verification against live package registries before implementation. Consider a brief research pass when this phase begins.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Generalization):** Fully grounded in direct code inspection. The refactor targets are precisely identified. No external API uncertainty.
- **Phase 2 (Robustness):** All fixes are internal. `contextlib.redirect_stdout`, `tf.keras.backend.clear_session()`, `io.BytesIO` patterns are well-documented stdlib / TF behaviors.
- **Phase 3 (UI Polish):** Plotly + Streamlit integration is well-documented with abundant examples. No research needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Existing stack is HIGH confidence (direct codebase inspection). Docker packaging recommendation is MEDIUM (well-established pattern but specific version numbers unverified). `st.fragment` and `st.container(height=...)` Streamlit API availability is LOW — verify before implementing. |
| Features | HIGH | Based on direct analysis of 780-line codebase + CONCERNS.md + PROJECT.md. No external sources needed; all feature gaps are visible in the existing code. |
| Architecture | HIGH | All architectural claims derive from direct code inspection of every module. The three-zone separation is already 90% in place. The exact refactor targets (3 locations, specific line numbers) are precisely identified. |
| Pitfalls | HIGH | All 14 pitfalls cite specific file paths and line numbers. Validated against commit `0f4c566`. Zero speculation; all issues are observable in the current code. |

**Overall confidence:** HIGH for the engineering work (Phases 1-3). MEDIUM for packaging specifics (Phase 4).

### Gaps to Address

- **Streamlit exact version to pin**: Training data suggests ~1.43; verify against `https://pypi.org/project/streamlit/` before writing the Docker `requirements.txt`. Use `>=1.35.0` as safe floor in the interim.
- **`st.fragment(run_every=N)` stability**: Verify this is not still marked experimental in the pinned Streamlit version before building the progress polling improvement around it. If experimental, the existing `time.sleep(0.5) + st.rerun()` pattern (reduced from 2s) is the correct fallback.
- **`tensorflow-cpu` vs `tensorflow` package name**: TensorFlow renamed packages across versions. Verify the exact installable name for TF 2.20 CPU-only on Python 3.13 before writing the Docker `requirements.txt`.
- **Demo laptop Docker Desktop**: Confirm Docker Desktop with WSL2 is or will be installed on the demo machine before committing to Docker as the sole distribution path. Have the pip + venv fallback documented and tested as a backup.

---

## Sources

### Primary (HIGH confidence — direct code inspection)

- `Reanalysis_Dashboard/app.py` (lines 81-546) — UI wizard, column validation, variable selector, polling loop, buffer seeks
- `Reanalysis_Dashboard/pipeline_bridge.py` (lines 14-110) — Column hardcoding, encoding, Agg backend, bridge functions
- `Reanalysis_Dashboard/job_runner.py` (lines 69-95) — Thread design, stdout redirect, sentinel protocol, tempdir creation
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` (lines 43-93) — TF seed, scaler fit, generic DataFrame contract
- `Sprint_2/Reanalysis_Pipeline/src/enkf.py` (lines 57-104) — tf.Variable allocation, tf.function, numpy seed
- `Sprint_2/Reanalysis_Pipeline/src/preprocessing.py` (lines 18, 96) — Resampling dropna, sequence length
- `Sprint_2/Reanalysis_Pipeline/src/visualization.py` (lines 6-16) — UNITS/LABELS coupling
- `Sprint_2/Reanalysis_Pipeline/src/data_loader.py` (lines 6, 26, 65) — Module-level cache, encoding
- `.planning/PROJECT.md` — Active requirements, constraints, known issues, demo timeline
- `.planning/codebase/CONCERNS.md` — Silent failure modes audit

### Secondary (MEDIUM confidence — training knowledge, consistent community sources)

- TensorFlow + PyInstaller incompatibility — multiple consistent community reports confirm TF dynamic library incompatibility
- Docker `python:3.13-slim` vs Alpine for TF — documented musl libc incompatibility with TF precompiled wheels
- Streamlit session state / threading patterns — documented Streamlit execution model
- `contextlib.redirect_stdout` as thread-safe stdout capture — standard library behavior, well-documented

### Tertiary (LOW confidence — training data, needs verification)

- Streamlit 1.43.x as current latest version — verify at `https://pypi.org/project/streamlit/`
- `st.fragment(run_every=N)` API stability in current Streamlit release — verify before implementing
- `st.container(height=...)` availability in pinned Streamlit version — verify before implementing
- `tensorflow-cpu` exact package name for TF 2.20 on Python 3.13 — verify at `https://pypi.org/project/tensorflow-cpu/`

---

*Research completed: 2026-03-29*
*Ready for roadmap: yes*
