"""
server.py
---------
FastAPI backend for the Reanalysis Dashboard.

Serves the static HTML frontend (static/index.html) and exposes eight API routes:

  GET  /                    -> FileResponse(static/index.html)
  POST /api/preview-csv     -> columns, numeric_columns, preview rows
  POST /api/start-run       -> start background reanalysis job
  GET  /api/run-stream      -> SSE stream of progress events
  POST /api/cancel          -> signal job cancellation
  GET  /api/result-summary  -> summary metrics after job completes
  GET  /api/download-csv    -> zip of all output CSVs for download
  GET  /api/plots           -> list of generated plot filenames
  GET  /api/plot/{filename} -> serve a plot image from the output directory

Launch with:
    python server.py
or:
    uvicorn server:app --reload
"""

import asyncio
import gc
import io
import json
import os
import queue as stdlib_queue
import shutil
import threading
import zipfile

import numpy as np
import pandas as pd

import uvicorn

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import pipeline_bridge
import job_runner


# ---- App setup -----------------------------------------------------------

app = FastAPI()

# Persistent runs directory — lives next to server.py
RUNS_DIR = os.path.join(os.path.dirname(__file__), "runs")
os.makedirs(RUNS_DIR, exist_ok=True)

# Module-level single-job state (single-user local tool)
_current_job = {
    "progress_queue": None,
    "stop_event": None,
    "result": None,
    "thread": None,
}

# Default hyperparameters — merged with user-supplied values on each run
DEFAULT_HYPERPARAMS = {
    # Universal (all models + filter)
    "model_type": "lstm",
    "filter_type": "enkf",
    "n_particles": 500,
    "lookback": 12,
    "n_ensemble": 50,
    "obs_error_factor": 0.2,
    "train_fraction": 0.8,
    "min_overlap_days": 30,
    # LSTM-specific
    "lstm_units": 64,
    "dense_units": 64,
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 200,
    "patience": 15,
    # XGBoost-specific
    "n_estimators": 100,
    "max_depth": 6,
    "xgb_learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    # Random Forest-specific (max_depth_rf=null means unlimited)
    "max_depth_rf": None,
    "min_samples_leaf": 5,
    "max_features": 0.7,
    # Ridge-specific
    "alpha": 1.0,
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
    # --- Step 1: Cleanup previous in-memory state (REL-01) ---
    # Note: output directories are now permanent (in RUNS_DIR) and NOT deleted.
    import tensorflow as tf
    tf.keras.backend.clear_session()
    gc.collect()

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
    run_id = job_runner.make_run_id(station_name)
    result, q, t = job_runner.launch_job(
        model_df=model_df,
        obs_df=obs_df,
        variable=model_value_col,
        station_name=station_name,
        hyperparams=hp,
        seed=seed,
        stop_event=stop_event,
        runs_dir=RUNS_DIR,
        run_id=run_id,
        model_filename=model_file.filename or "",
        obs_filename=obs_file.filename or "",
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


# ---- Route 6: Download all CSVs as a zip --------------------------------

@app.get("/api/download-csv")
async def download_csv():
    """Stream a zip of all CSV outputs from the most recent run."""
    result = _current_job.get("result")
    if not result or not result.output_dir or not os.path.isdir(result.output_dir):
        return JSONResponse({"error": "no run"}, status_code=404)
    csv_files = [f for f in os.listdir(result.output_dir) if f.lower().endswith(".csv")]
    if not csv_files:
        return JSONResponse({"error": "no csvs"}, status_code=404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in csv_files:
            zf.write(os.path.join(result.output_dir, fname), arcname=fname)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=reanalysis_outputs.zip"},
    )


# ---- Plot re-render helper ----------------------------------------------

def _rerender_plot(output_dir: str, filename: str,
                   title: str, xlabel: str, ylabel: str) -> bool:
    """
    Re-draw a pipeline PNG with custom axis labels and title.

    Reads the saved output CSVs from output_dir, reconstructs the figure,
    applies the new labels, and overwrites the original PNG file.

    Returns True on success, False on any error.
    """
    import matplotlib.pyplot as plt

    safe = os.path.basename(filename)
    name = safe.replace(".png", "").replace(".PNG", "")
    path = os.path.join(output_dir, safe)

    # --- Detect plot type and variable name ---
    if name.startswith("CI_Area_"):
        var, plot_type = name[len("CI_Area_"):], "ci"
    elif name.startswith("Model_vs_Observed_"):
        var, plot_type = name[len("Model_vs_Observed_"):], "scatter"
    elif name.endswith("_Comparison"):
        var, plot_type = name[: -len("_Comparison")], "comparison"
    else:
        return False

    try:
        if plot_type == "comparison":
            obs = pd.read_csv(os.path.join(output_dir, f"obs_{var}.csv"),
                              index_col="time", parse_dates=True)
            ol  = pd.read_csv(os.path.join(output_dir, f"model_openloop_{var}.csv"),
                              index_col="time", parse_dates=True)
            rm  = pd.read_csv(os.path.join(output_dir, f"reanalysis_{var}_mean.csv"),
                              index_col="time", parse_dates=True)
            time_idx = rm.index
            obs_arr = obs[var].reindex(time_idx).values
            ol_arr  = ol[var].reindex(time_idx).values
            rm_arr  = rm[var].values

            fig, ax = plt.subplots(figsize=(14, 5))
            obs_valid = ~np.isnan(obs_arr)
            if obs_valid.sum() < len(obs_arr) * 0.5:
                ax.scatter(time_idx[obs_valid], obs_arr[obs_valid],
                           s=12, color="#d62728", alpha=0.7, zorder=3, label="Observed")
            else:
                ax.plot(time_idx, obs_arr, label="Observed", linewidth=0.9, alpha=0.85)
            ax.plot(time_idx, ol_arr, label="Open-Loop (LSTM, no DA)",
                    linewidth=0.9, alpha=0.7)
            ax.plot(time_idx, rm_arr, label="Reanalysis Mean (LSTM+EnKF)",
                    linewidth=1.5)
            ax.legend(loc="upper right")
            ax.grid(alpha=0.3)

        elif plot_type == "ci":
            ens = pd.read_csv(os.path.join(output_dir, f"reanalysis_{var}_ensemble.csv"),
                              parse_dates=["time"])
            rm  = pd.read_csv(os.path.join(output_dir, f"reanalysis_{var}_mean.csv"),
                              index_col="time", parse_dates=True)
            time_idx = rm.index
            rm_arr   = rm[var].values
            pivot    = ens.pivot_table(index="time", columns="member", values=var)
            ci_lower = pivot.quantile(0.025, axis=1).reindex(time_idx).values
            ci_upper = pivot.quantile(0.975, axis=1).reindex(time_idx).values

            fig, ax = plt.subplots(figsize=(14, 6))
            ax.fill_between(time_idx, ci_lower, ci_upper,
                            color="#7FB3D8", alpha=0.55, edgecolor="none",
                            label="95% CI Region")
            ax.plot(time_idx, rm_arr, color="#8B0000", linewidth=1.2,
                    label="Reanalysis Mean")
            ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
            ax.grid(True, alpha=0.3)

        elif plot_type == "scatter":
            ol  = pd.read_csv(os.path.join(output_dir, f"model_openloop_{var}.csv"),
                              index_col="time", parse_dates=True)
            obs = pd.read_csv(os.path.join(output_dir, f"obs_{var}.csv"),
                              index_col="time", parse_dates=True)
            time_idx  = ol.index
            model_arr = ol[var].values
            obs_arr   = obs[var].reindex(time_idx).values

            fig, ax = plt.subplots(figsize=(14, 6))
            ax.plot(time_idx, model_arr, color="#1f77b4", linewidth=0.9,
                    label="Model Simulation")
            obs_valid = ~np.isnan(obs_arr)
            ax.scatter(time_idx[obs_valid], obs_arr[obs_valid],
                       s=4, color="#d62728", alpha=0.6, zorder=3, label="Observed")
            ax.legend(loc="upper left", fontsize=10, framealpha=0.9)
            ax.grid(True, alpha=0.3)

        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        plt.tight_layout()
        plt.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return True

    except Exception as exc:
        print(f"  ERROR re-rendering {filename}: {exc}")
        try:
            plt.close("all")
        except Exception:
            pass
        return False


# ---- Route 7: Re-render a plot with custom labels -----------------------

@app.post("/api/render-plot")
async def render_plot(request: Request):
    """
    Re-render a plot PNG with caller-supplied title, x-label, and y-label.

    Body (JSON): { filename, title, xlabel, ylabel }
    Returns: { ok: true } or error JSON.
    """
    body = await request.json()
    filename = body.get("filename", "")
    title    = body.get("title", "")
    xlabel   = body.get("xlabel", "")
    ylabel   = body.get("ylabel", "")

    result = _current_job.get("result")
    if not result or not result.output_dir:
        return JSONResponse({"error": "no run"}, status_code=404)

    ok = _rerender_plot(result.output_dir, filename, title, xlabel, ylabel)
    if not ok:
        return JSONResponse({"error": "render failed"}, status_code=500)
    return JSONResponse({"ok": True})


# ---- Route 8: List plots ------------------------------------------------

@app.get("/api/plots")
async def list_plots():
    """Return the filenames of all PNG plots from the most recent run."""
    result = _current_job.get("result")
    if not result or not result.output_dir or not os.path.isdir(result.output_dir):
        return JSONResponse({"plots": []})
    files = sorted(f for f in os.listdir(result.output_dir) if f.lower().endswith(".png"))
    return JSONResponse({"plots": files})


# ---- Route 9: Serve a single plot image ---------------------------------

@app.get("/api/plot/{filename}")
async def get_plot(filename: str):
    """Serve a PNG plot file from the current run's output directory."""
    result = _current_job.get("result")
    if not result or not result.output_dir:
        return JSONResponse({"error": "no run"}, status_code=404)
    # Prevent path traversal
    safe_name = os.path.basename(filename)
    path = os.path.join(result.output_dir, safe_name)
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="image/png")


# ---- History helpers -----------------------------------------------------

def _run_dir(run_id: str) -> str:
    """Return the absolute path for a run directory, preventing traversal."""
    return os.path.join(RUNS_DIR, os.path.basename(run_id))


# ---- Route 10: List past runs --------------------------------------------

@app.get("/api/history")
async def list_history():
    """Return all completed runs sorted newest-first."""
    runs = []
    if not os.path.isdir(RUNS_DIR):
        return JSONResponse({"runs": []})
    for name in sorted(os.listdir(RUNS_DIR), reverse=True):
        manifest_path = os.path.join(RUNS_DIR, name, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path) as fh:
                    runs.append(json.load(fh))
            except Exception:
                pass
    return JSONResponse({"runs": runs})


# ---- Route 11: List plots for a history run ------------------------------

@app.get("/api/history/{run_id}/plots")
async def history_plots(run_id: str):
    d = _run_dir(run_id)
    if not os.path.isdir(d):
        return JSONResponse({"plots": []})
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
    return JSONResponse({"plots": files})


# ---- Route 12: Serve a history plot image --------------------------------

@app.get("/api/history/{run_id}/plot/{filename}")
async def history_plot(run_id: str, filename: str):
    path = os.path.join(_run_dir(run_id), os.path.basename(filename))
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="image/png")


# ---- Route 13: Download reanalysis mean CSV for a history run ------------

@app.get("/api/history/{run_id}/download-csv")
async def history_download_csv(run_id: str):
    d = _run_dir(run_id)
    if not os.path.isdir(d):
        return JSONResponse({"error": "run not found"}, status_code=404)
    # Prefer the reanalysis mean CSV; fall back to any CSV in the directory
    manifest_path = os.path.join(d, "manifest.json")
    csv_path = None
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path) as fh:
                manifest = json.load(fh)
            variable = manifest.get("variable", "")
            candidate = os.path.join(d, f"reanalysis_{variable}_mean.csv")
            if os.path.isfile(candidate):
                csv_path = candidate
        except Exception:
            pass
    if csv_path is None:
        csvs = [f for f in os.listdir(d) if f.lower().endswith(".csv")]
        if not csvs:
            return JSONResponse({"error": "no csvs"}, status_code=404)
        csv_path = os.path.join(d, sorted(csvs)[0])
    filename = os.path.basename(csv_path)
    return FileResponse(csv_path, media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})


# ---- Route 13b: Download full artifact zip for a history run -------------

@app.get("/api/history/{run_id}/download-zip")
async def history_download_zip(run_id: str):
    d = _run_dir(run_id)
    if not os.path.isdir(d):
        return JSONResponse({"error": "run not found"}, status_code=404)
    include_exts = {".csv", ".png", ".json"}
    files = [f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in include_exts]
    if not files:
        return JSONResponse({"error": "no files"}, status_code=404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files:
            zf.write(os.path.join(d, fname), arcname=fname)
    buf.seek(0)
    safe_id = os.path.basename(run_id)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={safe_id}_full.zip"})


# ---- Route 14: Re-render a history plot with custom labels ---------------

@app.post("/api/history/{run_id}/render-plot")
async def history_render_plot(run_id: str, request: Request):
    body = await request.json()
    ok = _rerender_plot(_run_dir(run_id), body.get("filename", ""),
                        body.get("title", ""), body.get("xlabel", ""), body.get("ylabel", ""))
    if not ok:
        return JSONResponse({"error": "render failed"}, status_code=500)
    return JSONResponse({"ok": True})


# ---- Route 15: Delete a history run --------------------------------------

@app.delete("/api/history/{run_id}")
async def delete_history_run(run_id: str):
    shutil.rmtree(_run_dir(run_id), ignore_errors=True)
    return JSONResponse({"ok": True})


# ---- Route 16: Rename a history run --------------------------------------

@app.patch("/api/history/{run_id}/rename")
async def rename_history_run(run_id: str, request: Request):
    body = await request.json()
    new_name = str(body.get("station_name", "")).strip()
    if not new_name:
        return JSONResponse({"ok": False, "error": "Name cannot be empty"}, status_code=400)
    manifest_path = os.path.join(_run_dir(run_id), "manifest.json")
    if not os.path.isfile(manifest_path):
        return JSONResponse({"ok": False, "error": "Run not found"}, status_code=404)
    try:
        with open(manifest_path) as fh:
            manifest = json.load(fh)
        manifest["station_name"] = new_name
        with open(manifest_path, "w") as fh:
            json.dump(manifest, fh, indent=2)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return JSONResponse({"ok": True, "station_name": new_name})


# ---- Static file mount (MUST come after all route definitions) ----------

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---- Entry point --------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
