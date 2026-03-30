"""
server.py
---------
FastAPI backend for the Reanalysis Dashboard.

Serves the static HTML frontend (static/index.html) and exposes five API routes:

  GET  /                    -> FileResponse(static/index.html)
  POST /api/preview-csv     -> columns, numeric_columns, preview rows
  POST /api/start-run       -> start background reanalysis job
  GET  /api/run-stream      -> SSE stream of progress events
  POST /api/cancel          -> signal job cancellation
  GET  /api/result-summary  -> summary metrics after job completes

Launch with:
    python server.py
or:
    uvicorn server:app --reload
"""

import asyncio
import gc
import json
import os
import queue as stdlib_queue
import shutil
import threading

import uvicorn

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import pipeline_bridge
import job_runner


# ---- App setup -----------------------------------------------------------

app = FastAPI()

# Module-level single-job state (single-user local tool)
_current_job = {
    "progress_queue": None,
    "stop_event": None,
    "result": None,
    "thread": None,
}

# Default hyperparameters — copied from app.py / pipeline_config.yaml
DEFAULT_HYPERPARAMS = {
    "lookback": 12,
    "lstm_units": 64,
    "dense_units": 64,
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 200,
    "patience": 15,
    "n_ensemble": 50,
    "obs_error_factor": 0.2,
    "train_fraction": 0.8,
    "min_overlap_days": 30,
}


# ---- Route 1: Serve static index.html -----------------------------------

@app.get("/")
async def root():
    """Return the main HTML frontend."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(index_path)


# ---- Route 2: CSV column preview ----------------------------------------

@app.post("/api/preview-csv")
async def preview_csv(file: UploadFile):
    """
    Accept a CSV upload and return its columns, numeric columns, and a
    5-row preview. Uses _BytesShim to avoid double-consuming the file stream.

    Returns
    -------
    JSON: {"columns": [...], "numeric_columns": [...], "preview": [...]}
    """
    raw_bytes = await file.read()
    shim = pipeline_bridge._BytesShim(raw_bytes)
    cols = pipeline_bridge.get_csv_columns(shim)
    shim = pipeline_bridge._BytesShim(raw_bytes)
    numeric = pipeline_bridge.get_csv_numeric_columns(shim)
    shim = pipeline_bridge._BytesShim(raw_bytes)
    preview = pipeline_bridge.get_csv_preview(shim)
    return {
        "columns": cols,
        "numeric_columns": numeric,
        "preview": preview.to_dict(orient="records"),
    }


# ---- Route 3: Start pipeline run ----------------------------------------

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
    """
    Start a background reanalysis job.

    Performs cleanup (REL-01):
      1. Clear TF Keras session to release GPU/CPU memory from previous run.
      2. Force garbage collection.
      3. Delete previous job's temp output directory.

    Then reads both CSVs, builds DataFrames via pipeline_bridge, merges
    hyperparams, creates a stop_event, and launches job via job_runner.
    """
    # --- Step 1: Cleanup previous run (REL-01) ---
    import tensorflow as tf
    tf.keras.backend.clear_session()
    gc.collect()
    prev_result = _current_job.get("result")
    if prev_result and prev_result.output_dir:
        shutil.rmtree(prev_result.output_dir, ignore_errors=True)

    # --- Step 2: Read uploaded file bytes ---
    model_bytes = await model_file.read()
    obs_bytes = await obs_file.read()

    # --- Step 3: Build DataFrames via bridge ---
    model_df = pipeline_bridge.build_model_df_generic(
        pipeline_bridge._BytesShim(model_bytes),
        model_date_col,
        model_value_col,
    )
    obs_df = pipeline_bridge.build_obs_df_dedicated(
        pipeline_bridge._BytesShim(obs_bytes),
        obs_date_col,
        obs_value_col,
    )

    # --- Step 4: Merge hyperparams with defaults ---
    hp = {**DEFAULT_HYPERPARAMS, **json.loads(hyperparams)}

    # --- Step 5: Create stop event ---
    stop_event = threading.Event()

    # --- Step 6: Launch background job ---
    result, q, t = job_runner.launch_job(
        model_df=model_df,
        obs_df=obs_df,
        variable=model_value_col,
        station_name=station_name,
        hyperparams=hp,
        seed=seed,
        stop_event=stop_event,
    )

    # --- Step 7: Store job state ---
    _current_job["progress_queue"] = q
    _current_job["stop_event"] = stop_event
    _current_job["result"] = result
    _current_job["thread"] = t

    return {"status": "started"}


# ---- Route 4: SSE progress stream ----------------------------------------

@app.get("/api/run-stream")
async def run_stream(request: Request):
    """
    Stream pipeline progress as Server-Sent Events.

    Drains the job's progress_queue using get_nowait() in an async loop,
    yielding control to the event loop between polls via asyncio.sleep(0).

    Sentinel mapping:
      __DONE__      -> event: done
      __ERROR__     -> event: error (error message on data line)
      __CANCELLED__ -> event: cancelled

    Regular lines are sent as bare data: events.
    """
    async def generator():
        q = _current_job.get("progress_queue")
        if q is None:
            yield "event: error\ndata: no active job\n\n"
            return

        result = _current_job.get("result")

        while True:
            # Check for client disconnect
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
                error_text = ""
                if result and result.error_message:
                    error_text = result.error_message.replace("\n", "\\n")
                yield f"event: error\ndata: {error_text}\n\n"
                break
            elif msg == "__CANCELLED__":
                yield "event: cancelled\ndata: cancelled\n\n"
                break
            else:
                # Replace newlines with spaces to keep SSE format valid
                safe_msg = str(msg).replace("\n", " ")
                yield f"data: {safe_msg}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---- Route 5: Cancel current job ----------------------------------------

@app.post("/api/cancel")
async def cancel():
    """Signal the running pipeline to stop at its next checkpoint."""
    stop_event = _current_job.get("stop_event")
    if stop_event is not None:
        stop_event.set()
    return {"status": "cancelling"}


# ---- Route 6: Result summary --------------------------------------------

@app.get("/api/result-summary")
async def result_summary():
    """
    Return summary metrics and output directory after a successful run.

    Called by the frontend after receiving event: done on the SSE stream.
    """
    result = _current_job.get("result")
    if result and result.status == job_runner.JobStatus.DONE:
        return {
            "status": "done",
            "metrics": result.summary_metrics,
            "output_dir": result.output_dir,
        }
    return {"status": str(result.status.value) if result else "no_job"}


# ---- Static file mount (MUST come after all route definitions) ----------

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---- Entry point --------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
