"""
test_job_runner.py
------------------
Unit tests for job_runner.py background thread behavior.

Covers:
  - matplotlib.pyplot.close('all') called in finally block (test_matplotlib_closed_after_run)
  - InterruptedError results in CANCELLED status + __CANCELLED__ sentinel (test_cancelled_status_on_interrupted_error)
"""

import queue
import threading
from unittest.mock import patch, MagicMock

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from job_runner import _run_pipeline_in_thread, JobResult, JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_empty_df():
    """Return a minimal DataFrame suitable for pipeline args."""
    import pandas as pd
    return pd.DataFrame({"value": [1.0, 2.0]},
                        index=pd.to_datetime(["2020-01-01", "2020-01-02"]))


# ---------------------------------------------------------------------------
# test_matplotlib_closed_after_run
# ---------------------------------------------------------------------------

def test_matplotlib_closed_after_run():
    """plt.close('all') must be called even when the pipeline raises immediately."""
    result = JobResult()
    progress_queue = queue.Queue()

    with patch("pipeline_bridge.run_single_reanalysis", side_effect=Exception("boom")), \
         patch("matplotlib.pyplot.close") as mock_close:
        _run_pipeline_in_thread(
            model_df=_make_empty_df(),
            obs_df=_make_empty_df(),
            variable="value",
            station_name="Test",
            hyperparams={},
            seed=42,
            result=result,
            progress_queue=progress_queue,
            stop_event=threading.Event(),
        )

    mock_close.assert_called_with("all")
    assert result.status == JobStatus.ERROR


# ---------------------------------------------------------------------------
# test_cancelled_status_on_interrupted_error
# ---------------------------------------------------------------------------

def test_cancelled_status_on_interrupted_error():
    """InterruptedError must produce CANCELLED status and __CANCELLED__ sentinel."""
    result = JobResult()
    progress_queue = queue.Queue()

    with patch("pipeline_bridge.run_single_reanalysis", side_effect=InterruptedError()):
        _run_pipeline_in_thread(
            model_df=_make_empty_df(),
            obs_df=_make_empty_df(),
            variable="value",
            station_name="Test",
            hyperparams={},
            seed=42,
            result=result,
            progress_queue=progress_queue,
            stop_event=threading.Event(),
        )

    assert result.status == JobStatus.CANCELLED
    assert result.cancelled is True

    # Drain the queue and check the sentinel is present
    messages = []
    while not progress_queue.empty():
        messages.append(progress_queue.get_nowait())
    assert "__CANCELLED__" in messages
