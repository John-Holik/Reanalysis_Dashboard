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
import threading
import queue
import traceback
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class JobResult:
    status: JobStatus = JobStatus.PENDING
    output_dir: Optional[str] = None
    summary_metrics: Optional[dict] = None
    error_message: Optional[str] = None


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


def _run_pipeline_in_thread(
    model_df,
    obs_df,
    variable: str,
    station_name: str,
    hyperparams: dict,
    seed: int,
    result: JobResult,
    progress_queue: queue.Queue,
):
    """
    Worker executed in a background thread.

    Captures all print() output from run_single_reanalysis and writes each
    line to progress_queue. Sends '__DONE__' or '__ERROR__' as the final
    sentinel value so the UI knows when to advance to the results step.
    """
    output_dir = tempfile.mkdtemp(prefix="reanalysis_")
    result.output_dir = output_dir
    result.status = JobStatus.RUNNING

    old_stdout = sys.stdout
    sys.stdout = _QueueWriter(progress_queue)

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
        )
        result.summary_metrics = metrics
        result.status = JobStatus.DONE
        progress_queue.put("__DONE__")
    except Exception:
        result.error_message = traceback.format_exc()
        result.status = JobStatus.ERROR
        progress_queue.put("__ERROR__")
    finally:
        sys.stdout = old_stdout


def launch_job(model_df, obs_df, variable, station_name, hyperparams, seed):
    """
    Spawn a background daemon thread to run the reanalysis pipeline.

    Returns
    -------
    (JobResult, queue.Queue, threading.Thread)
        Store all three in st.session_state so they persist across reruns.
    """
    result = JobResult()
    q = queue.Queue()
    t = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(model_df, obs_df, variable, station_name,
              hyperparams, seed, result, q),
        daemon=True,
    )
    t.start()
    return result, q, t
