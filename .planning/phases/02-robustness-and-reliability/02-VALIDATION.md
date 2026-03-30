---
phase: 2
slug: robustness-and-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + httpx (FastAPI test client) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `cd Reanalysis_Dashboard && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd Reanalysis_Dashboard && python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds (no pipeline execution — mocked) |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 02-01-01 | 01 | 0 | EXEC-01 | import | `python -c "import fastapi, uvicorn, aiofiles; print('ok')"` | ⬜ pending |
| 02-01-02 | 01 | 1 | EXEC-01/02 | API | `pytest tests/test_server.py::test_root_returns_html` | ⬜ pending |
| 02-01-03 | 01 | 1 | EXEC-02 | API | `pytest tests/test_server.py::test_preview_csv_returns_columns` | ⬜ pending |
| 02-01-04 | 01 | 2 | EXEC-01/02 | API | `pytest tests/test_server.py::test_sse_stream_emits_events` | ⬜ pending |
| 02-01-05 | 01 | 2 | EXEC-04 | API | `pytest tests/test_server.py::test_cancel_sets_stop_event` | ⬜ pending |
| 02-02-01 | 02 | 1 | EXEC-03 | API | `pytest tests/test_server.py::test_error_response_no_traceback` | ⬜ pending |
| 02-02-02 | 02 | 1 | REL-01 | unit | `pytest tests/test_job_runner.py::test_tf_cleared_before_second_run` | ⬜ pending |
| 02-02-03 | 02 | 1 | REL-03 | unit | `pytest tests/test_job_runner.py::test_matplotlib_closed_after_run` | ⬜ pending |
| 02-03-01 | 03 | 2 | EXEC-01 | manual | Load app in browser; run pipeline; observe live log updates | ⬜ pending |
| 02-03-02 | 03 | 2 | EXEC-04 | manual | Click Stop mid-run; verify return to Step 0 with state preserved | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Reanalysis_Dashboard/tests/__init__.py` — empty, marks tests directory
- [ ] `Reanalysis_Dashboard/tests/conftest.py` — FastAPI TestClient fixture, mock pipeline bridge
- [ ] `Reanalysis_Dashboard/tests/test_server.py` — stubs for EXEC-01, EXEC-02, EXEC-03, EXEC-04
- [ ] `Reanalysis_Dashboard/tests/test_job_runner.py` — stubs for REL-01, REL-03
- [ ] `pip install fastapi uvicorn python-multipart aiofiles pytest httpx` — Wave 0 install step

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live log lines appear in browser during LSTM training | EXEC-02 | Requires real pipeline execution + browser EventSource | `python server.py`, upload CSVs, run, watch Step 2 log panel update in real-time |
| Stop button cancels job and returns to Step 0 with state | EXEC-04 | Requires real pipeline execution + UI interaction | Run pipeline, click Stop within first 30s, verify file names still shown in Step 0 |
| Page is not frozen/blank during pipeline run | EXEC-01 | Browser responsiveness not testable with httpx | While pipeline runs (Step 2), click other browser tabs and return — page should still show running state |
| Second run same speed as first | REL-01 | Requires real TF session and timing | Run pipeline twice sequentially; second run should not be measurably slower |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
