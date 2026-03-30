# Phase 2: Robustness and Reliability - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the running and completion experience so the app is safe to demonstrate. Targets:
pipeline error messages are legible to non-technical users; running jobs can be cancelled
cleanly; repeated runs in the same session do not degrade performance due to TF graph
accumulation or Matplotlib figure leaks. The pipeline core (`src/`) is not touched — all
changes are in `Reanalysis_Dashboard/app.py`, `Reanalysis_Dashboard/job_runner.py`, and
`Reanalysis_Dashboard/pipeline_bridge.py`.

</domain>

<decisions>
## Implementation Decisions

### Error Display (EXEC-03)

- **D-01:** When the pipeline fails, show a single generic plain-English message: "The
  pipeline encountered an error." No error categorization or specific guidance per error type.
- **D-02:** The full Python traceback is placed in a collapsible `st.expander("Show technical
  details")` below the generic message — visible to technical users for debugging, hidden by
  default for non-technical users.
- **D-03:** No attempt to parse or classify the exception type for a custom message. One
  message covers all failures.

### Stop / Cancel (EXEC-04)

- **D-04:** A `threading.Event` stop-signal is passed into the worker thread at launch. The
  worker checks this event between pipeline steps (after each of the 11 numbered steps in
  `pipeline.py`). When signaled, the worker exits early and sends `__CANCELLED__` to the
  progress queue rather than `__DONE__` or `__ERROR__`.
- **D-05:** The UI shows a "Cancelling..." state while waiting for the thread to acknowledge
  the stop signal. The Stop button is replaced with a spinner + "Waiting for pipeline to reach
  a safe checkpoint..." message.
- **D-06:** Once `__CANCELLED__` is received, the app returns to **Step 0** (upload screen).
  All uploaded files, column selections, dataset name, and hyperparams are preserved — the
  user can immediately re-run with different settings without re-uploading.
- **D-07:** A daemon thread that has been signalled to stop but hasn't yet acknowledged (e.g.,
  mid-LSTM training epoch) cannot be forcefully killed. The UI must wait. This is acceptable
  — LSTM typically exits within seconds of an epoch completing.

### State Preservation Between Runs (REL-01 / multi-run UX)

- **D-08:** When starting a new run (either after Stop or via "Run Another Analysis"),
  **preserve**: uploaded file objects, column selections (`model_date_col`, `model_value_col`,
  `obs_date_col`, `obs_value_col`), dataset name, and hyperparams.
- **D-09:** **Clear before new run**: `job_result`, `progress_queue`, `job_thread`,
  `progress_log`, any previous `output_dir` temp directory contents, and TF graph state.
- **D-10:** TF graph state cleared via `tf.keras.backend.clear_session()` followed by
  `gc.collect()`. This must happen in the **main thread** before launching the new background
  thread (calling it from the worker thread risks clearing a graph the worker is still using).
- **D-11:** Previous temp output dir is deleted (`shutil.rmtree`) before the new job launches
  to prevent disk accumulation across multiple runs.

### Matplotlib Cleanup (REL-03)

- **D-12:** `matplotlib.pyplot.close('all')` is called after each run completes (in the
  worker thread, after `visualization.py` finishes). This clears the figure registry and
  prevents memory leaks across runs.
- **D-13:** The Agg backend is already set in `pipeline_bridge.py` (`matplotlib.use("Agg")`
  before any other import). No change needed there.

### Claude's Discretion

- Exact checkpoint locations within the worker thread where the stop-event is checked
  (between pipeline steps is sufficient — no need to interrupt mid-step).
- Whether to show a progress spinner or a static text message during "Cancelling..." state.
- Exact wording of the "Cancelling..." UI message.
- Whether `gc.collect()` is called once or twice (common pattern after `clear_session()`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Dashboard Code
- `Reanalysis_Dashboard/job_runner.py` — Worker thread, `_QueueWriter`, `launch_job()`;
  primary target for stop-event and TF cleanup changes
- `Reanalysis_Dashboard/app.py` — `render_step_running()` (Stop button UI, Cancelling state),
  `_start_job()` (TF clear + temp dir cleanup before launch), `render_step_results()`
  ("Run Another Analysis" state reset logic)
- `Reanalysis_Dashboard/pipeline_bridge.py` — Matplotlib Agg backend already set here;
  `plt.close('all')` cleanup should be called from worker after visualization completes

### Pipeline Core (read-only)
- `Sprint_2/Reanalysis_Pipeline/src/pipeline.py` — 11 numbered steps
  (`# --- Step N: ... ---`) are the natural checkpoint locations for stop-event checks;
  `run_single_reanalysis()` signature must be extended to accept a stop event

### Requirements
- `.planning/REQUIREMENTS.md` — EXEC-01 through EXEC-04, REL-01, REL-03

### Known Concerns (relevant to this phase)
- `.planning/codebase/CONCERNS.md` — "No error handling for empty val set after train/val
  split" and "compute_obs_error can produce R=0 if only one observation" — these surface as
  pipeline crashes that will be caught by the new generic error handler

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `job_runner.py:_QueueWriter` — Already redirects stdout to queue; extend rather than replace
- `job_runner.py:JobStatus` enum — Add `CANCELLED` status alongside existing `DONE`/`ERROR`
- `job_runner.py:JobResult` — Add `cancelled: bool = False` field
- `app.py:render_step_running()` — Already drains queue on each rerun; add `__CANCELLED__`
  sentinel handling alongside existing `__DONE__` and `__ERROR__` branches

### Established Patterns
- `time.sleep(2)` + `st.rerun()` polling loop — keep this; `st.fragment(run_every=N)` is
  flagged as LOW confidence in STATE.md
- `st.session_state` for all inter-step state — all new state (stop_event, cancelling flag)
  must go through session state to persist across reruns
- Sentinel strings in queue (`__DONE__`, `__ERROR__`) — add `__CANCELLED__` as third sentinel

### Integration Points
- `launch_job()` must accept and thread the stop `threading.Event` through to
  `_run_pipeline_in_thread`, which passes it to `run_single_reanalysis()`
- `run_single_reanalysis()` signature change: add `stop_event: threading.Event = None`
  parameter; check `stop_event.is_set()` at each of the 11 step boundaries
- `_start_job()` in `app.py` is where TF `clear_session()` + `gc.collect()` + temp dir
  cleanup must happen before `launch_job()` is called

</code_context>

<specifics>
## Specific Ideas

- The stop-event check in `run_single_reanalysis()` should raise a custom
  `PipelineCancelledError` (or just `InterruptedError`) that the worker thread catches
  separately from other exceptions — so it sends `__CANCELLED__` rather than `__ERROR__`.
- The "Cancelling..." UI state needs its own session state flag (`st.session_state.cancelling
  = True`) set when the Stop button is clicked, so the rerun loop shows the waiting message
  instead of the normal log display.
- `shutil.rmtree(output_dir, ignore_errors=True)` is the safe way to delete the previous
  temp dir — `ignore_errors=True` handles the case where some files are still locked by
  the OS after the run.

</specifics>

<deferred>
## Deferred Ideas

- **Per-error-type guidance** — Detecting ValueError vs MemoryError vs data shape errors and
  showing specific fix suggestions. Deferred: generic fallback covers the demo use case, and
  specific categorization requires mapping many exception types.
- **Progress percentage within a step** — Showing epoch progress during LSTM training (e.g.,
  "Epoch 47/200"). The pipeline already prints per-epoch loss via Keras verbose mode — could
  be captured. Deferred to keep Phase 2 scope tight; the step counter added in Phase 1 is
  sufficient for the demo.
- **Concurrent run protection** — Disabling the Run button while a job is in progress
  (separate from cancellation). Currently a user could theoretically trigger two jobs by
  navigating back and hitting Run again. Deferred: the stop-event approach makes this safe
  enough for a demo context.

</deferred>

---

*Phase: 02-robustness-and-reliability*
*Context gathered: 2026-03-29*
*Next step: `/gsd:plan-phase 2`*
