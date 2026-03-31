"""
job_runner.py
-------------
Background thread management for the long-running reanalysis pipeline.

The LSTM training step can take 2-10 minutes. This module spawns a daemon
thread so Streamlit's main thread stays responsive while the pipeline runs.
Progress messages are captured from stdout and delivered via a Queue.
"""

import sys
import io
import json
import os
import re
import threading
import queue
import traceback
import tempfile
import datetime
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy scalar/array types to Python natives."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    status: JobStatus = JobStatus.PENDING
    output_dir: Optional[str] = None
    summary_metrics: Optional[dict] = None
    error_message: Optional[str] = None
    cancelled: bool = False
    run_id: Optional[str] = None


class _QueueWriter(io.TextIOBase):
    """Redirects print() calls from the pipeline to a Queue."""

    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, s: str) -> int:
        if s.strip():
            self._q.put(s.rstrip())
        return len(s)

    def flush(self):
        pass


def make_run_id(station_name: str) -> str:
    """Generate a human-readable, filesystem-safe run ID."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", station_name)[:32].strip("_")
    return f"{ts}_{slug}" if slug else ts


def _run_pipeline_in_thread(
    model_df,
    obs_df,
    variable: str,
    station_name: str,
    hyperparams: dict,
    seed: int,
    result: JobResult,
    progress_queue: queue.Queue,
    stop_event,
    runs_dir: Optional[str],
    run_id: str,
    model_filename: str = "",
    obs_filename: str = "",
):
    """
    Worker executed in a background thread.

    Captures all print() output from run_single_reanalysis and writes each
    line to progress_queue. Sends '__DONE__', '__CANCELLED__', or '__ERROR__'
    as the final sentinel value so the UI knows when to advance to the results step.

    When runs_dir is provided, output is written to runs_dir/run_id/ (permanent).
    Otherwise falls back to a temp directory.
    """
    if runs_dir:
        output_dir = os.path.join(runs_dir, run_id)
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = tempfile.mkdtemp(prefix="reanalysis_")

    result.output_dir = output_dir
    result.run_id = run_id
    result.status = JobStatus.RUNNING

    old_stdout = sys.stdout
    sys.stdout = _QueueWriter(progress_queue)

    job_start = time.time()
    try:
        from pipeline_bridge import run_single_reanalysis
        metrics = run_single_reanalysis(
            model_df=model_df,
            obs_df=obs_df,
            variable=variable,
            station_name=station_name,
            output_dir=output_dir,
            hyperparams=hyperparams,
            seed=seed,
            stop_event=stop_event,
        )
        result.summary_metrics = metrics
        result.status = JobStatus.DONE

        # Write persistent manifest so the run is discoverable in history
        manifest = {
            "run_id": run_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "station_name": station_name,
            "variable": variable,
            "model_filename": model_filename,
            "obs_filename": obs_filename,
            "hyperparams": hyperparams,
            "seed": seed,
            "metrics": metrics or {},
            "elapsed_seconds": round(time.time() - job_start),
        }
        try:
            with open(os.path.join(output_dir, "manifest.json"), "w") as fh:
                json.dump(manifest, fh, indent=2, cls=_NumpyEncoder)
        except Exception:
            pass  # Non-fatal — run still completes

        progress_queue.put("__DONE__")
    except InterruptedError:
        result.status = JobStatus.CANCELLED
        result.cancelled = True
        progress_queue.put("__CANCELLED__")
    except Exception:
        result.error_message = traceback.format_exc()
        result.status = JobStatus.ERROR
        progress_queue.put("__ERROR__")
    finally:
        sys.stdout = old_stdout
        import matplotlib.pyplot as plt
        plt.close('all')


def launch_job(model_df, obs_df, variable, station_name, hyperparams, seed,
               stop_event=None, runs_dir=None, run_id=None,
               model_filename="", obs_filename=""):
    """
    Spawn a background daemon thread to run the reanalysis pipeline.

    Parameters
    ----------
    stop_event : threading.Event or None
        When set, signals the pipeline to raise InterruptedError at the next
        checkpoint, allowing graceful cancellation.
    runs_dir : str or None
        If provided, output is written to runs_dir/run_id/ permanently.
        If None, a temp directory is used (legacy behaviour).
    run_id : str or None
        Identifier for this run. Auto-generated if not supplied.

    Returns
    -------
    (JobResult, queue.Queue, threading.Thread)
    """
    if run_id is None:
        run_id = make_run_id(station_name)

    result = JobResult(run_id=run_id)
    q = queue.Queue()
    t = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(model_df, obs_df, variable, station_name,
              hyperparams, seed, result, q, stop_event, runs_dir, run_id,
              model_filename, obs_filename),
        daemon=True,
    )
    t.start()
    return result, q, t
