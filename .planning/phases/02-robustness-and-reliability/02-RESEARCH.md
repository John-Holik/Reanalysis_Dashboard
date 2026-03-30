# Phase 2: HTML App Migration and Reliability - Research

**Researched:** 2026-03-30
**Domain:** FastAPI + SSE + Alpine.js + Tailwind CSS (replacing Streamlit)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Backend: FastAPI with uvicorn as the ASGI server.
- **D-02:** Frontend: Alpine.js (CDN) + Tailwind CSS (CDN play script). No npm, no build step.
- **D-03:** App launches with `python server.py` or `uvicorn server:app --reload`.
- **D-04:** Entry point is `Reanalysis_Dashboard/server.py`.
- **D-05:** Static files served from `Reanalysis_Dashboard/static/` via `StaticFiles(directory="static")` mounted at `/static`.
- **D-06:** `GET /` returns `static/index.html` directly.
- **D-07:** Same 4-step wizard: Step 0 (Upload), Step 1 (Configure), Step 2 (Running), Step 3 (Results). Alpine.js `x-data` on `<body>` holds current step and form state.
- **D-08:** Alpine.js manages all step transitions via `x-show`, `x-bind`, `@click`.
- **D-09:** HTML `<input type="file" accept=".csv">` for uploads.
- **D-10:** On file selection, JS sends FormData POST to `/api/preview-csv` for columns + preview.
- **D-11:** CSV bytes held as `File` objects in Alpine state; re-sent in FormData POST to `/api/start-run`.
- **D-12:** Live streaming via SSE at `GET /api/run-stream`. Frontend uses `new EventSource('/api/run-stream')`.
- **D-13:** SSE replaces Streamlit `time.sleep(2)` + `st.rerun()` polling entirely.
- **D-14:** `job_runner.py` progress queue drained by SSE endpoint. Sentinels `__DONE__`, `__ERROR__`, `__CANCELLED__` forwarded as SSE event types.
- **D-15:** `threading.Event` stop-signal checked between each of the 11 pipeline steps.
- **D-16:** Frontend sends `POST /api/cancel` to signal cancellation. Server sets stop event. SSE sends `event: cancelled`.
- **D-17:** On `event: cancelled`, Alpine.js returns wizard to Step 0, preserving file + param state.
- **D-18:** Pipeline failure shows one plain-English message with traceback in `<details><summary>` collapsible.
- **D-19:** No per-error-type categorization.
- **D-20:** New run preserves uploaded File objects, column selections, dataset name, hyperparams in Alpine state.
- **D-21:** Server-side: `tf.keras.backend.clear_session()` + `gc.collect()` in main thread before new job; previous temp dir deleted via `shutil.rmtree(..., ignore_errors=True)`.
- **D-22:** `matplotlib.pyplot.close('all')` at end of each worker run. Agg backend already set in `pipeline_bridge.py`.

### Claude's Discretion

- Exact Tailwind CSS classes and visual polish.
- Whether JS lives inline in `index.html` or in a separate `static/app.js`.
- Whether `gc.collect()` is called once or twice after `clear_session()`.
- Exact wording of all UI messages.
- Session management: single global job slot is acceptable (single-user local tool).

### Deferred Ideas (OUT OF SCOPE)

- Per-error-type guidance (ValueError vs MemoryError).
- Progress percentage within a step (epoch progress during LSTM training).
- Concurrent run protection (disabling Start while job runs).
- Dark mode / theming.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXEC-01 | Pipeline runs in a background thread — UI remains responsive | Background thread via `job_runner.py`; SSE endpoint does not block the event loop via `asyncio.sleep(0)` polling |
| EXEC-02 | User sees live log output in browser during execution | FastAPI SSE with `StreamingResponse` / `EventSourceResponse`; `_QueueWriter` stdout redirect already in `job_runner.py` |
| EXEC-03 | User sees plain-English error message if pipeline fails | SSE sentinel `__ERROR__` triggers Alpine state update; `<details>` collapsible for raw traceback |
| EXEC-04 | User can cancel a running job with Stop/Cancel button | `POST /api/cancel` sets `threading.Event`; `run_single_reanalysis()` checks it at each of the 11 steps |
| REL-01 | TF graph cleared between runs — no memory accumulation | `tf.keras.backend.clear_session()` + `gc.collect()` before launching new job |
| REL-03 | Matplotlib uses Agg backend with explicit figure cleanup | `matplotlib.pyplot.close('all')` in worker finally block; Agg already set in `pipeline_bridge.py` |

</phase_requirements>

---

## Summary

Phase 2 replaces the Streamlit app entirely with a FastAPI backend serving a plain HTML/Alpine.js/Tailwind frontend. The pipeline core (`Sprint_2/Reanalysis_Pipeline/src/`) and bridge layer (`pipeline_bridge.py`) are unchanged. The job runner thread model from `job_runner.py` is reused with two additions: a `stop_event: threading.Event` parameter for cancellation, and a `matplotlib.pyplot.close('all')` call in the `finally` block for REL-03.

The SSE stream is the central architectural piece. An async generator in `GET /api/run-stream` polls the `queue.Queue` from `job_runner.py` using `queue.get_nowait()` inside an `asyncio.sleep(0)` loop. This yields log lines as SSE `data:` events and maps the three sentinel strings to named SSE events (`event: done`, `event: error`, `event: cancelled`). The frontend listens with `EventSource` and handles each event type.

FastAPI, uvicorn, python-multipart, and aiofiles are not yet installed — they are all absent from the current environment and must be added to `requirements.txt` and installed before any implementation work.

**Primary recommendation:** Use `FastAPI` 0.135.x + `uvicorn` 0.42.x. SSE pattern: async generator with `asyncio.sleep(0)` + `queue.Queue.get_nowait()`. Alpine.js 3.x.x CDN + Tailwind CSS `@tailwindcss/browser@4` CDN.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.2 | ASGI web framework; all API routes | Native async, `StreamingResponse`, `UploadFile`, `FileResponse`, `StaticFiles` all built-in |
| uvicorn | 0.42.0 | ASGI server | Reference server for FastAPI; `uvicorn.run()` can be called from `server.py` directly |
| python-multipart | 0.0.22 | Parse `multipart/form-data` uploads | Required by FastAPI to process `UploadFile`; without it, file upload endpoints raise `RuntimeError` |
| aiofiles | 25.1.0 | Async file I/O | Required by FastAPI `StaticFiles` for serving static assets correctly; without it, static file serving silently fails |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alpine.js | 3.x.x (CDN) | Reactive wizard state, step transitions, SSE event handling | All frontend reactive logic; no build step |
| Tailwind CSS | @4 (CDN play) | Utility CSS; responsive layout | All styling; development/demo context — not intended for production minification |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `StreamingResponse` (raw SSE) | `sse-starlette` library | `sse-starlette` adds nicer abstractions but is an extra dependency; raw `StreamingResponse` with `text/event-stream` works cleanly for a single stream |
| `EventSourceResponse` (FastAPI 0.135+) | `StreamingResponse` | FastAPI 0.135+ ships a built-in `EventSourceResponse` via `from fastapi.sse import EventSourceResponse`; cleaner than raw `StreamingResponse` but both work |
| Tailwind v4 CDN | Tailwind v3 play CDN | v4 is current standard; v3 play CDN is at `https://cdn.tailwindcss.com` and still works but is maintenance track |

**Installation:**
```bash
pip install fastapi==0.135.2 uvicorn==0.42.0 python-multipart==0.0.22 aiofiles==25.1.0
```

**Version verification (confirmed against PyPI 2026-03-30):**
- `fastapi`: latest 0.135.2
- `uvicorn`: latest 0.42.0
- `python-multipart`: latest 0.0.22
- `aiofiles`: latest 25.1.0

---

## Architecture Patterns

### Recommended Project Structure
```
Reanalysis_Dashboard/
├── server.py            # FastAPI app, all API routes
├── pipeline_bridge.py   # Unchanged: CSV helpers + pipeline import
├── job_runner.py        # Adapted: add stop_event param + matplotlib cleanup
├── requirements.txt     # Updated: replace streamlit with fastapi stack
└── static/
    └── index.html       # Alpine.js + Tailwind wizard (single file)
```

### Pattern 1: Serving index.html at GET /

Two valid approaches; use the explicit `FileResponse` route when API routes must coexist with the static directory.

**Approach A — FileResponse route (recommended for this app):**
```python
# Source: https://fastapi.tiangolo.com/tutorial/static-files/
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Mount /static for assets (CSS, JS if split out)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
```

**Approach B — html=True on root mount (simpler but conflicts with /api routes):**
```python
app.mount("/", StaticFiles(directory="static", html=True), name="static")
# CAUTION: This catches ALL paths — API routes under "/" will be shadowed.
# Must register all API routes BEFORE the mount, or use Approach A.
```

Use Approach A. API routes at `/api/*` are registered before the static mount, so there is no conflict.

### Pattern 2: FastAPI SSE with Background queue.Queue

The key challenge is bridging a synchronous `queue.Queue` (written to by the pipeline thread) with the async FastAPI event loop. The pattern is:

1. Use `queue.Queue.get_nowait()` inside a try/except for `queue.Empty`.
2. Call `await asyncio.sleep(0)` when the queue is empty to yield control back to the event loop. Without this, the while loop spins at 100% CPU and blocks other requests.
3. Send SSE-formatted strings manually or use FastAPI's `EventSourceResponse`.

```python
# Source: pattern confirmed via FastAPI docs + threading gist
import asyncio
import queue as stdlib_queue
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

# Module-level state (single-user local tool)
_current_job = {
    "progress_queue": None,
    "stop_event": None,
    "result": None,
    "thread": None,
}

async def _sse_generator(request: Request):
    """Drain the progress queue, yield SSE-formatted strings."""
    q: stdlib_queue.Queue = _current_job["progress_queue"]
    while True:
        if await request.is_disconnected():
            break
        try:
            msg = q.get_nowait()
        except stdlib_queue.Empty:
            await asyncio.sleep(0)  # yield to event loop; avoid spin
            continue

        if msg == "__DONE__":
            yield "event: done\ndata: complete\n\n"
            break
        elif msg == "__ERROR__":
            error_text = _current_job["result"].error_message or ""
            yield f"event: error\ndata: {error_text}\n\n"
            break
        elif msg == "__CANCELLED__":
            yield "event: cancelled\ndata: cancelled\n\n"
            break
        else:
            # Escape newlines in log lines so SSE framing is intact
            safe = msg.replace("\n", " ")
            yield f"data: {safe}\n\n"

@app.get("/api/run-stream")
async def run_stream(request: Request):
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx/proxy buffering
        },
    )
```

**Why `asyncio.sleep(0)` and not `asyncio.sleep(0.05)`:** `sleep(0)` yields exactly one event loop tick. For a local tool where latency matters (user watching logs), this minimizes delay. It does not block because it immediately returns control.

**Alternative using FastAPI 0.135+ built-in EventSourceResponse:**
```python
# FastAPI 0.135+ ships fastapi.sse.EventSourceResponse natively
from fastapi.sse import EventSourceResponse, ServerSentEvent
from collections.abc import AsyncIterable

@app.get("/api/run-stream", response_class=EventSourceResponse)
async def run_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    q = _current_job["progress_queue"]
    while True:
        if await request.is_disconnected():
            break
        try:
            msg = q.get_nowait()
        except stdlib_queue.Empty:
            await asyncio.sleep(0)
            continue

        if msg == "__DONE__":
            yield ServerSentEvent(data="complete", event="done")
            break
        elif msg == "__ERROR__":
            yield ServerSentEvent(data=_current_job["result"].error_message, event="error")
            break
        elif msg == "__CANCELLED__":
            yield ServerSentEvent(data="cancelled", event="cancelled")
            break
        else:
            yield ServerSentEvent(data=msg)
```

Both work. `EventSourceResponse` is cleaner — use it if FastAPI 0.135.2 is pinned (it is). Verify `from fastapi.sse import EventSourceResponse` works at that version before committing to it. The raw `StreamingResponse` pattern is the safe fallback that works on every version.

### Pattern 3: File Upload Endpoint (pipeline_bridge shim)

The bridge functions (`get_csv_columns`, `get_csv_preview`, `get_csv_numeric_columns`, `build_model_df_generic`, `build_obs_df_dedicated`) all use this pattern:

```python
buf = io.BytesIO(uploaded_file.read())
# ... use buf ...
uploaded_file.seek(0)
```

`uploaded_file` is expected to have `.read()` and `.seek()`. FastAPI's `UploadFile` exposes `await file.read()` (async). The shim is:

```python
# In server.py endpoint:
from fastapi import UploadFile
import io

@app.post("/api/preview-csv")
async def preview_csv(file: UploadFile):
    raw_bytes: bytes = await file.read()
    buf = io.BytesIO(raw_bytes)       # buf has .read() and .seek()
    cols = pipeline_bridge.get_csv_columns(buf)   # pass buf directly
    preview = pipeline_bridge.get_csv_preview(buf)
    return {"columns": cols, "preview": preview.to_dict(orient="records")}
```

**Critical observation from reading `pipeline_bridge.py`:** Every bridge function wraps its argument in `io.BytesIO(uploaded_file.read())` internally and then calls `uploaded_file.seek(0)`. If you pass a `BytesIO` instead of a Streamlit `UploadedFile`, the `seek(0)` after the read is a no-op call on the passed-in buffer, not on the internal `buf`. This means the buffer passed in is NOT rewound.

Two options:
1. **Pass a `BytesIO` that you control** and ignore the seek on it (since you own the bytes already).
2. **Pass the raw `bytes`** and have a thin shim class:

```python
class _BytesShim:
    """Minimal shim so bridge functions accept raw bytes like a Streamlit UploadedFile."""
    def __init__(self, data: bytes):
        self._data = data
    def read(self) -> bytes:
        return self._data
    def seek(self, pos: int) -> None:
        pass  # no-op; bridge functions wrap in BytesIO internally
```

The `_BytesShim` approach requires zero changes to `pipeline_bridge.py`. Pass `_BytesShim(raw_bytes)` wherever the bridge expects an `uploaded_file`.

### Pattern 4: Alpine.js File State and FormData Re-submission

Alpine.js can hold a `File` object in reactive state and re-submit it later in a `FormData` POST.

```javascript
// In index.html — x-data on <body>
{
  modelFile: null,    // holds the File object from <input type="file">
  obsFile: null,
  // ... other state

  handleModelFileSelect(event) {
    this.modelFile = event.target.files[0];
    // Immediately POST for preview
    const fd = new FormData();
    fd.append('file', this.modelFile);
    fetch('/api/preview-csv', { method: 'POST', body: fd })
      .then(r => r.json())
      .then(data => {
        this.modelColumns = data.columns;
        this.modelPreview = data.preview;
      });
  },

  startRun() {
    const fd = new FormData();
    fd.append('model_file', this.modelFile);   // re-send the held File object
    fd.append('obs_file', this.obsFile);
    fd.append('model_date_col', this.modelDateCol);
    fd.append('model_value_col', this.modelValueCol);
    fd.append('obs_date_col', this.obsDateCol);
    fd.append('obs_value_col', this.obsValueCol);
    fd.append('station_name', this.stationName);
    fd.append('hyperparams', JSON.stringify(this.hyperparams));
    fd.append('seed', this.seed);
    fetch('/api/start-run', { method: 'POST', body: fd })
      .then(r => r.json())
      .then(() => {
        this.step = 2;
        this.connectSSE();
      });
  },

  connectSSE() {
    const es = new EventSource('/api/run-stream');
    es.onmessage = (e) => { this.logLines.push(e.data); };
    es.addEventListener('done', () => { es.close(); this.step = 3; });
    es.addEventListener('error', (e) => { es.close(); this.errorTrace = e.data; this.step = 'error'; });
    es.addEventListener('cancelled', () => { es.close(); this.step = 0; });
    this.eventSource = es;
  }
}
```

**Key findings about Alpine.js file handling:**
- `x-model` does NOT work on `<input type="file">` (Alpine.js GitHub issue #219 — confirmed limitation).
- Use `@change="handleModelFileSelect($event)"` instead.
- A `File` object held in Alpine state survives step transitions within the same page session and can be re-appended to `FormData` at any time.
- `FormData.append(key, File_object)` sends the file bytes as multipart — no need to read or convert.

### Pattern 5: Stop Event Checkpoints in pipeline.py

`run_single_reanalysis()` has exactly 11 numbered steps. The signature addition needed:

```python
def run_single_reanalysis(model_df, obs_df, variable, station_name,
                          output_dir, hyperparams, seed=42,
                          stop_event=None):  # ADD THIS PARAMETER
```

Check pattern to insert after each step's print statement:

```python
    # --- Step 1: Resample model to daily ---
    mdl_daily = resample_model_to_daily(model_df)
    print(f"  Model: {len(mdl_daily)} daily rows ...")

    # --- STOP CHECK ---
    if stop_event is not None and stop_event.is_set():
        raise InterruptedError("Pipeline cancelled by user")
```

The 11 stop-check insertion points (line numbers from current `pipeline.py`):
- After Step 1 print (line ~57): after model resampling
- After Step 2 alignment prints (~74): after obs density detection and align
- After Step 3 standardization (~94): after scaler fit
- After Step 4 training (line ~118 after `print(f"  LSTM trained...")`): after LSTM train — this is the longest step and the most important checkpoint
- After Step 5 noise estimation (~123): after Q/R computation
- After Step 6 EnKF (~132): after EnKF complete print
- After Step 7 open-loop (~136): after open-loop complete print
- After Step 8 inverse transform (~156): after all inverse transforms
- After Step 9 CI computation (~162): after CI integral print
- After Step 10 CSV export (~168): after export
- After Step 11 plots (~183): after all three plots (final, pre-return)

`InterruptedError` propagates to `job_runner.py`'s except block, sets `result.error_message`, and puts `__CANCELLED__` instead of `__ERROR__`. This requires a small update to `job_runner.py`'s worker to distinguish `InterruptedError` from other exceptions.

### Pattern 6: Multi-Run Memory Safety (REL-01)

In `server.py`, before launching a new job:

```python
import gc
import shutil
import tensorflow as tf

def _cleanup_previous_job():
    """Clear TF graph and temp dir from a previous run."""
    # TF graph clear — prevents accumulation across runs
    tf.keras.backend.clear_session()
    gc.collect()  # one call is sufficient; two is harmless

    # Remove previous temp output dir
    if _current_job.get("result") and _current_job["result"].output_dir:
        shutil.rmtree(_current_job["result"].output_dir, ignore_errors=True)
```

Call this at the top of `POST /api/start-run` before constructing the new job.

### Pattern 7: Matplotlib Cleanup (REL-03)

In `job_runner.py`'s `_run_pipeline_in_thread`, in the `finally` block:

```python
    finally:
        sys.stdout = old_stdout
        import matplotlib.pyplot as plt
        plt.close('all')  # ADD THIS
```

Agg backend is already set in `pipeline_bridge.py` via `matplotlib.use("Agg")` at module import time — no change needed to that.

### Anti-Patterns to Avoid

- **Blocking the event loop in the SSE generator:** Never use `time.sleep()`, `queue.Queue.get(block=True)`, or any other blocking call inside an `async def` generator. Always use `queue.get_nowait()` + `await asyncio.sleep(0)`.
- **Mounting StaticFiles at "/" before registering API routes:** If `app.mount("/", StaticFiles(...), name="static")` appears before `@app.get("/api/...")`, FastAPI will route all requests to the static directory and the API will be unreachable. Register all API routes first, then mount at the end.
- **Using `asyncio.Queue` when the producer is a non-async thread:** The pipeline thread writes to `queue.Queue` (stdlib). `asyncio.Queue` is not thread-safe without `loop.call_soon_threadsafe()`. Use stdlib `queue.Queue` and poll with `get_nowait()`.
- **Forgetting `defer` on the Alpine.js script tag:** Without `defer`, Alpine initializes before the DOM is parsed and `x-data` bindings fail silently.
- **Forgetting `python-multipart`:** FastAPI raises `RuntimeError: Form data requires "python-multipart" to be installed` at runtime when a file upload endpoint is hit. It does NOT fail at import time.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multipart form parsing | Custom body parser | `python-multipart` (FastAPI requires it) | Handles boundary edge cases, large files, encoding |
| Static file serving with correct MIME types | Custom static route handler | `fastapi.staticfiles.StaticFiles` | Content-Type headers, etag caching, range requests |
| SSE framing (data:/event:/id: format) | Manual string concatenation | FastAPI `EventSourceResponse` / `ServerSentEvent` | Correct line endings (`\n\n` separation), keep-alive pings, proxy headers |
| Alpine.js wizard state | Custom JS state machine | Alpine.js `x-data` | Reactive binding, no DOM manipulation boilerplate |
| CSS utility classes | Custom stylesheet | Tailwind CSS CDN | Consistent spacing, responsive grid, no CSS specificity issues |

**Key insight:** The SSE framing is subtle — each event block must end with `\n\n` (two newlines), and field names are case-sensitive (`data:`, `event:`, `id:`). Multi-line data values must prefix every line with `data:`. The `EventSourceResponse` abstraction handles all of this.

---

## Common Pitfalls

### Pitfall 1: SSE Event Loop Starvation

**What goes wrong:** The SSE async generator loops tightly on `queue.get_nowait()` without yielding. The FastAPI event loop is single-threaded — a tight loop in one generator prevents other requests (including `POST /api/cancel`) from being handled. The Stop button appears to do nothing.

**Why it happens:** Forgetting that `async def` functions only yield control at `await` points.

**How to avoid:** Always include `await asyncio.sleep(0)` in the empty-queue branch. This yields one loop tick.

**Warning signs:** Cancel endpoint returns 200 but SSE stream does not close; browser spins indefinitely.

### Pitfall 2: python-multipart Not Installed

**What goes wrong:** App starts successfully, but any request to `/api/preview-csv` or `/api/start-run` raises `RuntimeError: Form data requires "python-multipart" to be installed`.

**Why it happens:** FastAPI does not declare `python-multipart` as a hard dependency in its own metadata — it fails at runtime, not at import time.

**How to avoid:** Add `python-multipart==0.0.22` to `requirements.txt` and verify it is installed before testing file upload.

**Warning signs:** App starts with no errors but crashes on first file upload.

### Pitfall 3: aiofiles Not Installed

**What goes wrong:** `StaticFiles` mounts without error, but serving any static file raises an internal server error.

**Why it happens:** Starlette's `StaticFiles` uses `aiofiles` internally for async file reads. It is an optional dependency of Starlette but is required at runtime when StaticFiles is used.

**How to avoid:** Add `aiofiles==25.1.0` to `requirements.txt`.

**Warning signs:** App starts cleanly, `GET /` returns 500, Uvicorn log shows `ModuleNotFoundError: No module named 'aiofiles'`.

### Pitfall 4: Alpine.js `x-model` on File Input

**What goes wrong:** Using `<input type="file" x-model="modelFile">` — Alpine.js v3 does not support `x-model` on file inputs. The `modelFile` binding will be empty.

**Why it happens:** `x-model` works by reading `value` — the browser prohibits reading file path from `input[type=file].value` for security.

**How to avoid:** Use `@change="modelFile = $event.target.files[0]"` instead.

**Warning signs:** `modelFile` is `null` after selecting a file; preview fetch sends no file.

### Pitfall 5: Windows Uvicorn and ProactorEventLoop

**What goes wrong:** On Windows + Python 3.13, uvicorn uses ProactorEventLoop by default in single-process mode. Certain subprocess-related operations may behave differently, but for this app (no subprocesses, pure threading) this is not an issue.

**Why it might matter:** The pipeline uses `threading.Thread`, not `asyncio.create_subprocess_*`. ProactorEventLoop is fully compatible with `threading.Thread` + `queue.Queue` patterns.

**How to avoid:** No action needed for this app's architecture. If future phases add subprocesses, revisit.

**Warning signs:** Not expected to manifest in Phase 2.

### Pitfall 6: StaticFiles Mount Shadowing API Routes

**What goes wrong:** If `app.mount("/", StaticFiles(directory="static", html=True))` is called before API route registration, all `/api/*` requests return 404 from the static handler.

**Why it happens:** `app.mount("/", ...)` is a catch-all. Starlette matches mounted paths before decorated routes.

**How to avoid:** Use Approach A (explicit `@app.get("/")` returning `FileResponse`). Register all `@app.get("/api/...")` and `@app.post("/api/...")` routes before any `app.mount()` call.

### Pitfall 7: SSE Proxy Buffering on Windows / localhost

**What goes wrong:** On some Windows setups with proxy tools (Fiddler, corporate proxies), SSE events are buffered and arrive in bursts rather than line-by-line.

**Why it happens:** HTTP proxies buffer responses by default.

**How to avoid:** Include `X-Accel-Buffering: no` header on the SSE response. For localhost development this is rarely an issue, but including the header costs nothing.

---

## Code Examples

### server.py skeleton
```python
# Source: FastAPI docs + patterns verified above
import asyncio
import gc
import io
import queue as stdlib_queue
import shutil
import threading
import tempfile
import uvicorn

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import pipeline_bridge
import job_runner

app = FastAPI()

# Module-level single-job state (single-user local tool)
_current_job = {
    "progress_queue": None,
    "stop_event": None,
    "result": None,
    "thread": None,
}

# --- Static files ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# --- API routes ---
@app.post("/api/preview-csv")
async def preview_csv(file: UploadFile):
    raw = await file.read()
    shim = pipeline_bridge._BytesShim(raw)  # or io.BytesIO(raw)
    cols = pipeline_bridge.get_csv_columns(shim)
    numeric = pipeline_bridge.get_csv_numeric_columns(shim)
    preview = pipeline_bridge.get_csv_preview(shim)
    return {"columns": cols, "numeric_columns": numeric,
            "preview": preview.to_dict(orient="records")}

@app.post("/api/start-run")
async def start_run(
    model_file: UploadFile,
    obs_file: UploadFile,
    model_date_col: str = Form(...),
    model_value_col: str = Form(...),
    obs_date_col: str = Form(...),
    obs_value_col: str = Form(...),
    station_name: str = Form("MyDataset"),
    hyperparams: str = Form("{}"),
    seed: int = Form(42),
):
    import json
    import tensorflow as tf

    # Cleanup previous run
    tf.keras.backend.clear_session()
    gc.collect()
    if _current_job["result"] and _current_job["result"].output_dir:
        shutil.rmtree(_current_job["result"].output_dir, ignore_errors=True)

    # Parse files
    model_bytes = await model_file.read()
    obs_bytes = await obs_file.read()
    model_df = pipeline_bridge.build_model_df_generic(
        pipeline_bridge._BytesShim(model_bytes), model_date_col, model_value_col)
    obs_df = pipeline_bridge.build_obs_df_dedicated(
        pipeline_bridge._BytesShim(obs_bytes), obs_date_col, obs_value_col)

    hp = json.loads(hyperparams)
    stop_event = threading.Event()
    result, q, t = job_runner.launch_job(
        model_df=model_df, obs_df=obs_df,
        variable=model_value_col, station_name=station_name,
        hyperparams=hp, seed=seed, stop_event=stop_event,
    )
    _current_job.update(progress_queue=q, stop_event=stop_event, result=result, thread=t)
    return {"status": "started"}

@app.get("/api/run-stream")
async def run_stream(request: Request):
    async def generator():
        q = _current_job["progress_queue"]
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = q.get_nowait()
            except stdlib_queue.Empty:
                await asyncio.sleep(0)
                continue

            if msg == "__DONE__":
                yield "event: done\ndata: complete\n\n"
                break
            elif msg == "__ERROR__":
                err = (_current_job["result"].error_message or "").replace("\n", "\\n")
                yield f"event: error\ndata: {err}\n\n"
                break
            elif msg == "__CANCELLED__":
                yield "event: cancelled\ndata: cancelled\n\n"
                break
            else:
                safe = msg.replace("\n", " ")
                yield f"data: {safe}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/api/cancel")
async def cancel():
    if _current_job["stop_event"]:
        _current_job["stop_event"].set()
    return {"status": "cancelling"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
```

### Alpine.js wizard skeleton (index.html)
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Reanalysis Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/[email protected]/dist/cdn.min.js"></script>
</head>
<body x-data="{
  step: 0,
  modelFile: null, obsFile: null,
  modelColumns: [], obsColumns: [],
  modelNumericCols: [], obsNumericCols: [],
  modelPreview: [], obsPreview: [],
  modelDateCol: '', modelValueCol: '',
  obsDateCol: '', obsValueCol: '',
  stationName: 'MyDataset',
  hyperparams: { lookback:12, lstm_units:64, dense_units:64,
                 learning_rate:0.001, batch_size:32, epochs:200,
                 patience:15, n_ensemble:50, obs_error_factor:0.2,
                 train_fraction:0.8, min_overlap_days:30 },
  seed: 42,
  logLines: [],
  errorTrace: '',
  eventSource: null,
  result: null,

  async pickFile(type, event) {
    const file = event.target.files[0];
    if (!file) return;
    if (type === 'model') this.modelFile = file;
    else this.obsFile = file;
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/preview-csv', { method: 'POST', body: fd });
    const data = await r.json();
    if (type === 'model') {
      this.modelColumns = data.columns;
      this.modelNumericCols = data.numeric_columns;
      this.modelPreview = data.preview;
      this.modelDateCol = data.columns[0] || '';
      this.modelValueCol = data.numeric_columns[0] || '';
    } else {
      this.obsColumns = data.columns;
      this.obsNumericCols = data.numeric_columns;
      this.obsPreview = data.preview;
      this.obsDateCol = data.columns[0] || '';
      this.obsValueCol = data.numeric_columns[0] || '';
    }
  },

  async startRun() {
    this.logLines = [];
    this.errorTrace = '';
    const fd = new FormData();
    fd.append('model_file', this.modelFile);
    fd.append('obs_file', this.obsFile);
    fd.append('model_date_col', this.modelDateCol);
    fd.append('model_value_col', this.modelValueCol);
    fd.append('obs_date_col', this.obsDateCol);
    fd.append('obs_value_col', this.obsValueCol);
    fd.append('station_name', this.stationName);
    fd.append('hyperparams', JSON.stringify(this.hyperparams));
    fd.append('seed', this.seed);
    await fetch('/api/start-run', { method: 'POST', body: fd });
    this.step = 2;
    this.connectSSE();
  },

  connectSSE() {
    const es = new EventSource('/api/run-stream');
    this.eventSource = es;
    es.onmessage = (e) => { this.logLines.push(e.data); };
    es.addEventListener('done', () => { es.close(); this.step = 3; });
    es.addEventListener('error', (e) => {
      es.close();
      this.errorTrace = e.data.replace(/\\n/g, '\n');
      this.step = 'error';
    });
    es.addEventListener('cancelled', () => { es.close(); this.step = 0; });
  },

  async cancel() {
    await fetch('/api/cancel', { method: 'POST' });
    if (this.eventSource) this.eventSource.close();
  }
}">
  <!-- Step 0: Upload -->
  <div x-show="step === 0"> ... </div>
  <!-- Step 1: Hyperparams -->
  <div x-show="step === 1"> ... </div>
  <!-- Step 2: Running -->
  <div x-show="step === 2">
    <pre x-text="logLines.slice(-30).join('\n')"></pre>
    <button @click="cancel()">Stop</button>
  </div>
  <!-- Step 3: Results -->
  <div x-show="step === 3"> ... </div>
  <!-- Error state -->
  <div x-show="step === 'error'">
    <p>The pipeline encountered an error.</p>
    <details>
      <summary>Show technical details</summary>
      <pre x-text="errorTrace"></pre>
    </details>
    <button @click="step = 0">Start Over</button>
  </div>
</body>
</html>
```

### job_runner.py changes (minimal diff)

```python
# CHANGES to _run_pipeline_in_thread:
# 1. Add stop_event parameter
# 2. Pass stop_event to run_single_reanalysis
# 3. Distinguish InterruptedError (cancel) from other exceptions
# 4. Add matplotlib cleanup in finally

def _run_pipeline_in_thread(
    model_df, obs_df, variable, station_name, hyperparams, seed,
    result, progress_queue, stop_event,  # ADD stop_event
):
    ...
    try:
        metrics = run_single_reanalysis(
            ..., stop_event=stop_event  # PASS THROUGH
        )
        ...
        progress_queue.put("__DONE__")
    except InterruptedError:
        result.status = JobStatus.CANCELLED  # new status (add to enum)
        progress_queue.put("__CANCELLED__")
    except Exception:
        result.error_message = traceback.format_exc()
        result.status = JobStatus.ERROR
        progress_queue.put("__ERROR__")
    finally:
        sys.stdout = old_stdout
        import matplotlib.pyplot as plt
        plt.close('all')  # REL-03
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Streamlit `time.sleep(2) + st.rerun()` polling | SSE `EventSource` push | Phase 2 | Eliminates 2-second lag; no polling overhead |
| Streamlit `st.session_state` for file/param storage | Alpine.js `x-data` reactive state | Phase 2 | No server-side session storage needed; files stay in browser memory |
| Streamlit `st.file_uploader()` | HTML `<input type="file">` + `FormData` fetch | Phase 2 | Standard browser API; works without framework |
| Tailwind v3 play CDN | Tailwind v4 browser CDN (`@tailwindcss/browser@4`) | 2025 | Same CDN convenience; v4 is current default |

**Deprecated/outdated:**
- `streamlit` in `requirements.txt`: remove entirely after Phase 2; it is replaced by `fastapi` + `uvicorn`.
- The Tailwind v3 play CDN script (`https://cdn.tailwindcss.com`): still works but v4 is the current standard. The syntax for utility classes is compatible at the level this app needs.

---

## Open Questions

1. **`fastapi.sse.EventSourceResponse` availability in 0.135.2**
   - What we know: FastAPI 0.135.x added built-in SSE support via `from fastapi.sse import EventSourceResponse`.
   - What's unclear: Whether the exact import path is stable in 0.135.2 or only in later 0.135.x.
   - Recommendation: Attempt `from fastapi.sse import EventSourceResponse` in Wave 0; fall back to raw `StreamingResponse` pattern if the import fails (both patterns are documented above).

2. **Stop event granularity inside LSTM training (Step 4)**
   - What we know: Step 4 (LSTM training with `train_forecast_lstm()`) is the longest step (up to 10 minutes). The stop check fires once after the entire training call completes.
   - What's unclear: Whether a mid-training cancellation is needed for demo UX, or if waiting for the current epoch to finish is acceptable.
   - Recommendation: Per D-15, stop checks are between steps, not within steps. A training-step cancellation responds once the training function returns. This is acceptable for the demo scope. The deferred list confirms "Progress percentage within a step" is out of scope.

3. **`_BytesShim` placement in pipeline_bridge.py vs server.py**
   - What we know: The shim is trivial (4 lines) and solves the Streamlit `UploadedFile` interface dependency without changing bridge functions.
   - What's unclear: Whether to add `_BytesShim` to `pipeline_bridge.py` (co-location) or define it inline in `server.py` (isolation).
   - Recommendation: Add to `pipeline_bridge.py` as a private class so it stays with the bridge code it serves. Prefix with `_` to signal it is not part of the public API.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13.7 | All | Yes | 3.13.7 | — |
| fastapi | server.py, all API routes | No | — | None; must install |
| uvicorn | App launch | No | — | None; must install |
| python-multipart | File upload endpoints | No | — | None; file upload fails at runtime without it |
| aiofiles | StaticFiles serving | No | — | None; static file serving fails at runtime without it |
| tensorflow | pipeline_bridge import | Yes | 2.21.0 | — |
| pandas | pipeline_bridge | Yes | 2.3.2 | — |
| numpy | pipeline core | Yes | 2.3.2 | — |
| matplotlib | visualization.py | Yes | 3.10.6 | — |
| scikit-learn | preprocessing.py | Yes | 1.7.1 | — |
| scipy | postprocessing.py | Yes | 1.16.1 | — |
| streamlit | app.py (being deleted) | Yes | 1.55.0 | Removed after Phase 2 |

**Missing dependencies with no fallback:**
- `fastapi 0.135.2` — blocks all server functionality
- `uvicorn 0.42.0` — blocks app launch
- `python-multipart 0.0.22` — blocks file upload endpoints
- `aiofiles 25.1.0` — blocks static file serving

**Wave 0 install task required:**
```bash
pip install fastapi==0.135.2 uvicorn==0.42.0 python-multipart==0.0.22 aiofiles==25.1.0
```
Update `requirements.txt`: replace `streamlit>=1.35.0` with `fastapi>=0.135.0`, `uvicorn>=0.42.0`, `python-multipart>=0.0.22`, `aiofiles>=25.1.0`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected (no pytest.ini, no test/ directory) |
| Config file | None — Wave 0 must create minimal smoke tests |
| Quick run command | `python -c "import server; print('import ok')"` (pre-pytest) |
| Full suite command | `pytest tests/ -x -q` (Wave 0 creates tests/) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXEC-01 | Pipeline runs in background thread; UI not blocked | smoke | `pytest tests/test_server.py::test_start_run_returns_immediately -x` | Wave 0 |
| EXEC-02 | SSE endpoint yields log lines from queue | unit | `pytest tests/test_sse.py::test_sse_yields_log_lines -x` | Wave 0 |
| EXEC-03 | SSE yields `event: error` on pipeline failure | unit | `pytest tests/test_sse.py::test_sse_error_event -x` | Wave 0 |
| EXEC-04 | Cancel sets stop_event; SSE yields `event: cancelled` | unit | `pytest tests/test_server.py::test_cancel_sets_stop_event -x` | Wave 0 |
| REL-01 | TF session cleared before new job | unit | `pytest tests/test_server.py::test_tf_cleared_between_runs -x` | Wave 0 |
| REL-03 | plt.close('all') called in worker finally | unit | `pytest tests/test_job_runner.py::test_matplotlib_cleanup -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -c "import server"` (import smoke test; no uvicorn required)
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green + manual browser test: upload two CSVs, run pipeline, verify live logs, click Stop, verify wizard returns to Step 0

### Wave 0 Gaps
- [ ] `tests/__init__.py` — empty, makes tests/ a package
- [ ] `tests/test_server.py` — covers EXEC-01, EXEC-04, REL-01
- [ ] `tests/test_sse.py` — covers EXEC-02, EXEC-03 (mock queue)
- [ ] `tests/test_job_runner.py` — covers REL-03 (matplotlib close call)
- [ ] Framework install: `pip install pytest pytest-anyio httpx` — `httpx` needed for FastAPI `TestClient`

---

## Sources

### Primary (HIGH confidence)
- [FastAPI SSE documentation](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — `EventSourceResponse`, `ServerSentEvent`, keep-alive behavior
- [FastAPI static files documentation](https://fastapi.tiangolo.com/tutorial/static-files/) — `StaticFiles` mount, `html=True` parameter
- [Alpine.js installation documentation](https://alpinejs.dev/essentials/installation) — CDN script tag, `defer` requirement
- [Tailwind CSS Play CDN documentation](https://tailwindcss.com/docs/installation/play-cdn) — `@tailwindcss/browser@4` script tag
- PyPI `pip index versions` — fastapi 0.135.2, uvicorn 0.42.0, python-multipart 0.0.22, aiofiles 25.1.0 (verified 2026-03-30)

### Secondary (MEDIUM confidence)
- [Thread-safe queue + WebSocket async generator gist](https://gist.github.com/vinroger/5a6a7d311168602c5b3e093f054dd481) — `queue.get_nowait()` + `asyncio.sleep(0)` pattern, verified against FastAPI async docs
- [FastAPI discussions: python-multipart required](https://github.com/fastapi/fastapi/discussions/5144) — runtime requirement confirmed
- [Alpine.js `x-model` file input limitation](https://github.com/alpinejs/alpine/issues/219) — confirmed does not work; `@change` workaround

### Tertiary (LOW confidence — flag for validation)
- `from fastapi.sse import EventSourceResponse` import path stability in 0.135.2: reported available but should be verified by import test in Wave 0

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against PyPI on 2026-03-30
- Architecture patterns: HIGH — verified against official FastAPI and Alpine.js docs
- SSE queue-draining pattern: MEDIUM-HIGH — verified against threading gist and FastAPI async docs; `asyncio.sleep(0)` pattern is widely confirmed
- Pitfalls: HIGH — python-multipart and aiofiles requirements confirmed via FastAPI GitHub discussions; Alpine.js x-model limitation confirmed in official issue tracker
- `EventSourceResponse` import path: LOW — reported available in FastAPI 0.135+; needs Wave 0 verification

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (FastAPI and Alpine.js are stable; Tailwind v4 CDN URL may change if major version bumps)
