"""
test_server.py
--------------
API route tests for server.py using httpx AsyncClient + pytest-anyio.

Covers:
  - GET /               -> returns 200 (test_root_returns_html)
  - POST /api/preview-csv -> columns + numeric_columns (test_preview_csv_returns_columns)
  - POST /api/cancel    -> sets stop_event (test_cancel_sets_stop_event)
  - POST /api/start-run -> calls clear_session (test_tf_cleared_before_second_run)
"""

import io
import os
import threading
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def _minimal_model_csv() -> bytes:
    return _make_csv_bytes("date,value\n2020-01-01,1.0\n2020-01-02,2.0\n2020-01-03,3.0\n")


def _minimal_obs_csv() -> bytes:
    return _make_csv_bytes("date,value\n2020-01-01,1.0\n2020-01-02,2.0\n")


# ---------------------------------------------------------------------------
# test_root_returns_html
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_root_returns_html(tmp_path, client):
    """GET / should return 200 when static/index.html exists."""
    import server

    # Write a minimal index.html into the real static dir so FileResponse works
    static_dir = os.path.join(os.path.dirname(server.__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    index_path = os.path.join(static_dir, "index.html")
    wrote_file = not os.path.exists(index_path)
    if wrote_file:
        with open(index_path, "w") as f:
            f.write("<!DOCTYPE html><html><body>placeholder</body></html>")

    try:
        response = await client.get("/")
        assert response.status_code == 200
    finally:
        # Remove the placeholder only if we created it
        if wrote_file and os.path.exists(index_path):
            os.remove(index_path)


# ---------------------------------------------------------------------------
# test_preview_csv_returns_columns
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_preview_csv_returns_columns(client):
    """POST /api/preview-csv should return columns, numeric_columns, and preview."""
    csv_bytes = _make_csv_bytes("date,value\n2020-01-01,1.0\n2020-01-02,2.0\n")

    response = await client.post(
        "/api/preview-csv",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "numeric_columns" in data
    assert "preview" in data
    assert "date" in data["columns"]
    assert "value" in data["numeric_columns"]


# ---------------------------------------------------------------------------
# test_cancel_sets_stop_event
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_cancel_sets_stop_event(client):
    """POST /api/cancel should call .set() on the current job's stop_event."""
    import server

    stop_event = threading.Event()
    server._current_job["stop_event"] = stop_event

    response = await client.post("/api/cancel")

    assert response.status_code == 200
    assert stop_event.is_set()
    assert response.json()["status"] == "cancelling"

    # Cleanup
    server._current_job["stop_event"] = None


# ---------------------------------------------------------------------------
# test_tf_cleared_before_second_run
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tf_cleared_before_second_run(client):
    """POST /api/start-run should call tf.keras.backend.clear_session()."""
    import server
    import job_runner
    import pandas as pd
    import queue
    import threading

    model_csv = _minimal_model_csv()
    obs_csv = _minimal_obs_csv()

    # Build a mock JobResult that looks like a prior job completed
    prior_result = job_runner.JobResult(status=job_runner.JobStatus.DONE)
    server._current_job["result"] = prior_result

    # Mock the heavy dependencies so no real pipeline runs
    mock_result = job_runner.JobResult(status=job_runner.JobStatus.RUNNING)
    mock_queue = queue.Queue()
    mock_thread = MagicMock(spec=threading.Thread)

    with patch("tensorflow.keras.backend.clear_session") as mock_clear, \
         patch("job_runner.launch_job", return_value=(mock_result, mock_queue, mock_thread)):

        response = await client.post(
            "/api/start-run",
            files={
                "model_file": ("model.csv", io.BytesIO(model_csv), "text/csv"),
                "obs_file": ("obs.csv", io.BytesIO(obs_csv), "text/csv"),
            },
            data={
                "model_date_col": "date",
                "model_value_col": "value",
                "obs_date_col": "date",
                "obs_value_col": "value",
                "station_name": "TestStation",
                "hyperparams": "{}",
                "seed": "42",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    mock_clear.assert_called_once()

    # Cleanup
    server._current_job["result"] = None
    server._current_job["stop_event"] = None
    server._current_job["progress_queue"] = None
    server._current_job["thread"] = None
