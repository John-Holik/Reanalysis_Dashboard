# Phase 2: HTML App Migration and Reliability - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the Streamlit UI (`Reanalysis_Dashboard/app.py`) with a FastAPI + Alpine.js +
Tailwind CSS web app that delivers the same 4-step wizard workflow. At the same time,
deliver all Phase 2 reliability features: live log streaming via SSE, plain-English error
messages, stop/cancel, and multi-run memory safety.

**What changes:**
- `Reanalysis_Dashboard/app.py` → deleted / replaced by `Reanalysis_Dashboard/server.py`
- New `Reanalysis_Dashboard/static/index.html` (Alpine.js wizard UI)
- New `Reanalysis_Dashboard/static/app.js` (optional — JS may be inline)
- New `Reanalysis_Dashboard/static/style.css` (optional — Tailwind handles most styling)

**What is UNCHANGED (reused as-is or with minor adaptation):**
- `Reanalysis_Dashboard/pipeline_bridge.py` — all bridge helpers reusable
- `Reanalysis_Dashboard/job_runner.py` — thread + queue pattern is framework-agnostic
- `Sprint_2/Reanalysis_Pipeline/src/` — pipeline core is completely untouched

</domain>

<decisions>
## Implementation Decisions

### Framework Choice

- **D-01:** Backend: **FastAPI** with `uvicorn` as the ASGI server. Chosen for native async
  support and first-class SSE, which is the cleanest mechanism for streaming pipeline logs.
- **D-02:** Frontend: **Alpine.js** (CDN) for reactive wizard state management and
  **Tailwind CSS** (CDN play script) for styling. No npm, no build step — all dependencies
  are `<script>` tags in `index.html`.
- **D-03:** App launches with `python server.py` (uvicorn embedded) or
  `uvicorn server:app --reload`. Streamlit is no longer required or used.

### File Structure

- **D-04:** Entry point is `Reanalysis_Dashboard/server.py` — FastAPI app with all API routes.
- **D-05:** Static files served from `Reanalysis_Dashboard/static/` via
  `StaticFiles(directory="static")` mounted at `/static`.
- **D-06:** `GET /` returns `static/index.html` directly.

### Wizard Structure (4 Steps)

- **D-07:** Same 4-step wizard preserved: Step 0 (Upload), Step 1 (Configure), Step 2
  (Running), Step 3 (Results). Alpine.js `x-data` on `<body>` holds current step and all
  form state (replaces `st.session_state`).
- **D-08:** Alpine.js manages all step transitions, form state, and conditional rendering via
  `x-show`, `x-bind`, and `@click` directives. No page reloads.

### File Upload

- **D-09:** HTML `<input type="file" accept=".csv">` for model and observation CSV uploads.
- **D-10:** On file selection, JS sends a `FormData` POST to `/api/preview-csv` to get column
  names + first-5-rows preview. Response populates the Alpine state (column dropdowns + preview
  table). This replaces the Streamlit `st.file_uploader()` + `get_csv_columns()` pattern.
- **D-11:** The actual CSV bytes are held in Alpine state (as `File` objects) and re-sent when
  the user submits the run in a `FormData` POST to `/api/start-run`.

### Live Log Streaming (EXEC-01, EXEC-02)

- **D-12:** Live streaming is implemented as **Server-Sent Events (SSE)** via a
  `GET /api/run-stream` endpoint. The frontend connects with `new EventSource('/api/run-stream')`.
- **D-13:** SSE replaces the Streamlit `time.sleep(2)` + `st.rerun()` polling pattern entirely.
  The `EventSource` connection pushes log lines to the browser as they arrive — no polling.
- **D-14:** `job_runner.py`'s progress queue is drained by the SSE endpoint's async generator.
  The `__DONE__`, `__ERROR__`, and `__CANCELLED__` sentinel strings are forwarded as SSE
  event types (`event: done`, `event: error`, `event: cancelled`) so the frontend can react.

### Stop / Cancel (EXEC-04)

- **D-15:** Same threading.Event stop-signal pattern as originally designed: a
  `threading.Event` is passed into the worker thread at launch and checked between each of
  the 11 pipeline steps in `run_single_reanalysis()`.
- **D-16:** The frontend sends `POST /api/cancel` to signal cancellation. The server sets the
  stop event. The SSE stream sends `event: cancelled` when the worker acknowledges.
- **D-17:** On `event: cancelled`, Alpine.js returns the wizard to Step 0, preserving all
  uploaded files and hyperparameter state.

### Error Display (EXEC-03)

- **D-18:** On pipeline failure, show one plain-English message: "The pipeline encountered an
  error." with the Python traceback hidden in a `<details>` / `<summary>` collapsible element.
- **D-19:** No per-error-type categorization. One generic message covers all failures.

### State Preservation Between Runs (REL-01)

- **D-20:** When starting a new run (after cancel or after completing a run), Alpine.js
  **preserves**: uploaded File objects, column selections, dataset name, hyperparams.
- **D-21:** Server-side: TF graph cleared via `tf.keras.backend.clear_session()` + `gc.collect()`
  in the main thread before launching a new job. Previous temp output dir deleted via
  `shutil.rmtree(..., ignore_errors=True)`.

### Matplotlib Cleanup (REL-03)

- **D-22:** `matplotlib.pyplot.close('all')` called at end of each worker run (success, error,
  or cancelled). The Agg backend is already set in `pipeline_bridge.py` — no change needed.

### Claude's Discretion

- Exact Tailwind CSS classes and visual polish for the wizard steps.
- Whether JS lives inline in `index.html` or in a separate `static/app.js`.
- Whether `gc.collect()` is called once or twice after `clear_session()`.
- Exact wording of all UI messages (uploading, running, cancelling, done, error).
- Session management: whether `/api/start-run` accepts a session token or the server
  maintains a single global job slot (acceptable for single-user local tool).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Bridge + Runner (primary targets for adaptation)
- `Reanalysis_Dashboard/pipeline_bridge.py` — Reuse all CSV helpers; adapt to accept
  `bytes`/`io.BytesIO` instead of Streamlit's `UploadedFile` objects (or wrap bytes in
  a BytesIO shim with `.read()` and `.seek()` to maintain compatibility)
- `Reanalysis_Dashboard/job_runner.py` — Reuse thread + queue pattern; SSE endpoint
  reads from `progress_queue`; adapt `launch_job()` to also accept a `stop_event`

### Pipeline Core (read-only reference)
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` — 11 numbered steps are natural
  stop-event checkpoint locations; `run_single_reanalysis()` signature must accept
  `stop_event: threading.Event = None`

### Requirements
- `.planning/REQUIREMENTS.md` — EXEC-01 through EXEC-04, REL-01, REL-03

### Existing App (for reference, will be replaced)
- `Reanalysis_Dashboard/app.py` — Current Streamlit app; reference for wizard step
  structure, hyperparameter defaults, column mapping logic, and session state keys

</canonical_refs>

<specifics>
## Specific Ideas

- FastAPI `StreamingResponse` with `media_type="text/event-stream"` is the SSE mechanism.
- Alpine.js `x-data="{ step: 0, modelFile: null, obsFile: null, columns: {}, params: {...} }"`
  on `<body>` gives a single reactive state tree.
- `<details><summary>Show technical details</summary><pre>{{ errorTrace }}</pre></details>`
  is the collapsible traceback pattern — works in all browsers, zero JS required.
- `pipeline_bridge.py` functions that accept `file` arguments expect an object with `.read()`
  and `.seek()` — wrapping `bytes` in `io.BytesIO` is a one-line shim.
- For single-user local tool, a module-level `_current_job` dict in `server.py` is sufficient
  state management (no Redis, no sessions).

</specifics>

<deferred>
## Deferred Ideas

- **Per-error-type guidance** — Detecting ValueError vs MemoryError and showing specific fix
  suggestions. Generic fallback covers the demo use case.
- **Progress percentage within a step** — Epoch progress during LSTM training. Step-level
  streaming via SSE is sufficient for the demo.
- **Concurrent run protection** — Disabling Start while a job is running. Acceptable for
  single-user local tool; the cancel endpoint makes double-run safe enough.
- **Dark mode / theming** — Tailwind makes this easy to add later but out of scope for Phase 2.

</deferred>

---

*Phase: 02-robustness-and-reliability*
*Context updated: 2026-03-30 (replaced Streamlit hardening context with HTML migration context)*
*Next step: `/gsd:plan-phase 2`*
