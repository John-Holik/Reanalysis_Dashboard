# Technology Stack

**Project:** Reanalysis Dashboard — packaging and distribution research
**Researched:** 2026-03-29
**Confidence:** MEDIUM — web tools unavailable; findings from training knowledge (cutoff Aug 2025) plus
direct codebase inspection. Confidence flags applied per claim.

---

## Context: What Already Exists

The codebase is NOT a greenfield project. The following is committed and working:

- `Reanalysis_Dashboard/app.py` — 547-line Streamlit app, 5-step wizard
- `Reanalysis_Dashboard/job_runner.py` — background daemon thread + stdout queue
- `Reanalysis_Dashboard/pipeline_bridge.py` — sys.path shim, DataFrame helpers
- `Reanalysis_Dashboard/requirements.txt` — loose version pins
- `Sprint_2/Reanalysis_Pipeline/src/` — 8 Python modules (LSTM + EnKF pipeline)

**Tech already committed (verified in codebase):**

| Package | Version in use | Role |
|---------|---------------|------|
| Python | 3.13.7 | Runtime |
| streamlit | >=1.35.0 (pinned in requirements.txt) | UI framework |
| tensorflow | >=2.20.0 | LSTM training + tf.function inference |
| pandas | >=2.0.0 (2.3.2 actual) | DataFrame I/O |
| numpy | >=1.26.0 (2.3.2 actual) | Ensemble arrays |
| scikit-learn | >=1.4.0 (1.7.1 actual) | StandardScaler |
| scipy | >=1.12.0 (1.16.1 actual) | trapezoid integral |
| matplotlib | >=3.8.0 (3.10.6 actual) | Agg-backend plots |
| pyyaml | >=6.0 | YAML config loading |

**DO NOT change this stack.** Framework swaps (FastAPI, Gradio, Panel) are out of scope for a 4–6
week demo deadline with a working codebase.

---

## Recommended Stack: Additions Needed

### Packaging Decision: Docker (Recommended)

**Verdict: Docker over pip installer, PyInstaller, or conda.**

#### Why Docker wins for this project

| Criterion | Docker | pip + venv | PyInstaller | conda |
|-----------|--------|------------|-------------|-------|
| TensorFlow 2.20 isolation | Full | Fragile (system TF conflict possible) | Broken (TF incompatible) | Works but ~2 GB env |
| Windows + macOS + Linux | Single image | Per-OS instructions | Per-OS binary | Per-OS env |
| One-step install for non-coders | `docker compose up` | Multiple shell steps | Double-click .exe | Install Miniconda first |
| Demo-day reliability | Locked image, never breaks | Depends on PyPI availability | Binary fragility | Conda solve flakiness |
| Installer file size | ~2.5 GB image (TF dominated) | ~600 MB env | ~1.5 GB + hidden deps | ~2 GB env |
| Maintenance burden | Dockerfile + compose.yml | requirements.txt | spec file (complex) | environment.yml |

**Confidence:** MEDIUM — Docker's advantages for TF-heavy apps are well-established; PyInstaller
incompatibility with TensorFlow is a documented, consistent limitation (HIGH confidence on that
specific claim based on multiple community sources in training data).

#### Why PyInstaller is explicitly ruled out

PyInstaller cannot reliably bundle TensorFlow because TF uses dynamic shared libraries, CUDA
drivers, and compiled C extensions that the PyInstaller import graph cannot fully trace.
Attempting it produces an executable that crashes at runtime on any machine other than the build
machine. Do not attempt this path.

#### Why a raw pip + venv approach is second-best, not first

A `requirements.txt` + `pip install` approach works but requires:
1. Python 3.13 to be installed first (non-trivial for non-coders)
2. Correct pip version
3. Internet access at install time
4. Correct CUDA/CPU TensorFlow variant selected by user

This adds friction that Docker eliminates. Keep pip+venv as the developer-facing install path
(already effectively in place), but don't ship it as the end-user install.

#### Why conda is not recommended

Conda is viable technically but adds friction for end users who don't already have it.
Conda environment solves are slower and more error-prone with recent TF packages because TF's
conda channel lags the pip release by weeks. The resulting `environment.yml` is also harder to
maintain than a Dockerfile.

---

### Core Framework: Additions to requirements.txt

The existing `requirements.txt` uses loose `>=` pins. For reproducible packaging, these should
be tightened to exact versions.

**Recommended: add `pip-tools` to the developer toolchain** (not a runtime dep).
Confidence: HIGH — pip-tools is the standard lightweight alternative to poetry for pin management.

```
pip-compile requirements.in  →  requirements.txt  (exact pins, hash-checked)
pip-sync requirements.txt                          (installs exactly those versions)
```

`requirements.in` holds the loose constraints already in requirements.txt.
`requirements.txt` (compiled) holds exact pins with hashes for Docker layer caching.

**No new runtime packages are required for the UI** — the existing stack handles all features.

---

### Packaging: Docker + Docker Compose

**Base image recommendation:** `python:3.13-slim`

Rationale:
- `slim` variant strips test files and documentation, saving ~200 MB vs `python:3.13`
- Avoids debian-full (no X11 headers needed — Matplotlib uses Agg backend already)
- TensorFlow CPU-only install works cleanly on slim
- Confidence: HIGH — this is the standard pattern for TF CPU apps in Docker

**Do NOT use:** `python:3.13-alpine`. Alpine uses musl libc, which breaks TensorFlow's
precompiled wheels. TF requires glibc. This is a documented incompatibility.
Confidence: HIGH.

**Docker Compose:** Use version `compose.yml` (no version key, modern syntax).
Single service, single port (8501 — Streamlit default), volume mount for uploads/outputs.

**Key Dockerfile structure:**

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Layer: system deps (rare change — cached)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Layer: Python deps (changes when requirements change — cached separately)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer: application code (changes most often)
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "Reanalysis_Dashboard/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
```

**Key Compose structure:**

```yaml
services:
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./outputs:/app/outputs
    environment:
      - STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
```

`STREAMLIT_SERVER_FILE_WATCHER_TYPE=none` disables the inotify watcher inside Docker,
which prevents spurious restarts and errors on Windows/WSL hosts.
Confidence: MEDIUM — this is a known Docker-on-Windows Streamlit issue from community reports.

---

### Streamlit: Specific Version Recommendation

Pin to **Streamlit 1.43.x** (latest stable as of training cutoff, August 2025).

The existing requirements.txt has `streamlit>=1.35.0`. Tighten to `streamlit==1.43.x` for Docker.

Key features confirmed present at 1.35+ that the existing codebase already uses:
- `st.session_state` dict-style access
- `st.file_uploader` with `type=["csv"]`
- `st.download_button`
- `st.rerun()` (replaced deprecated `st.experimental_rerun` in 1.27)
- `st.code()` for log display
- `use_container_width=True` on `st.image()`

**Confidence on specific version number:** LOW — verify on https://pypi.org/project/streamlit/
before writing requirements.txt. The 1.43.x figure is based on training data; actual latest
may differ. The >=1.35.0 floor is safe and already validated in the codebase.

---

## Streamlit-Specific Patterns: Prescriptive Recommendations

### Session State (existing app uses this correctly)

The existing `_init_state()` pattern is correct:

```python
def _init_state():
    defaults = {"step": 0, "job_result": None, ...}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()  # called at module top level, every rerun
```

**Rule:** Never write to session state unconditionally at module level. Always guard with
`if k not in st.session_state`. Unconditional writes reset state on every rerun.
Confidence: HIGH — this is the documented Streamlit pattern.

**Threading and session state:** `st.session_state` is NOT thread-safe. The existing code
correctly avoids writing to session_state from the background thread — it writes only to
a `JobResult` dataclass and a `queue.Queue`, both of which are thread-safe. The Streamlit
main thread reads from the queue on each rerun. This is the correct pattern. Do not change it.
Confidence: HIGH — Streamlit's execution model is single-threaded per user session; the
background thread must communicate via thread-safe primitives, not session_state directly.

### Background Threading (existing approach is correct)

The existing `job_runner.py` pattern — daemon thread + `queue.Queue` + sentinel values
(`__DONE__`, `__ERROR__`) — is the right approach for Streamlit.

**One improvement to consider:** `st.fragment` (introduced in Streamlit ~1.37) allows partial
page rerenders without full-page refresh. The progress polling loop currently does:

```python
time.sleep(2)
st.rerun()   # full-page rerender every 2 seconds
```

With `@st.fragment(run_every=2)`, the progress display could rerender independently without
re-executing steps 0–2. This reduces visible flicker during the running step.
Confidence: MEDIUM — `st.fragment` with `run_every` is documented as of ~1.37; verify API
before implementing as it was relatively new at training cutoff.

**Do NOT use `st.empty()` + repeated `.write()` calls inside a loop** — this is a common
anti-pattern that blocks the Streamlit thread and freezes the browser. The existing polling
approach (drain queue, sleep, rerun) is correct.

### File Uploads

The existing pattern (`io.BytesIO(uploaded_file.read())` + `uploaded_file.seek(0)`) is correct
for re-reading Streamlit uploaded files multiple times in the same session.

**Key rule:** Streamlit's `UploadedFile` object behaves like a seekable BytesIO buffer within
a single session, but it is NOT preserved across browser refreshes. The existing code correctly
copies it to a BytesIO before passing to pandas — this prevents double-read exhaustion.

**File size limit:** Streamlit's default upload limit is 200 MB. For CSVs this is unlikely to be
hit, but it can be raised in `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 500
```

This should be set to a reasonable ceiling and documented in user instructions.
Confidence: HIGH — this is a long-standing Streamlit config option.

### Live Log Streaming

The existing pattern (stdout redirection via `_QueueWriter` + queue drain on each rerun) works
correctly. One concrete improvement for the UI: replace `st.code("\n".join(log[-30:]))` with
a fixed-height scrollable container.

The `st.code()` approach (already in app.py line 448) is acceptable. An alternative that
auto-scrolls to the bottom is:

```python
log_container = st.container(height=300)
log_container.code("\n".join(st.session_state.progress_log[-50:]))
```

`st.container(height=...)` was introduced in Streamlit 1.37 and creates a fixed-height
scrollable div. This is more user-friendly than a growing code block.
Confidence: MEDIUM — `st.container(height=...)` is documented; verify exact version availability.

**Do NOT redirect TensorFlow's own stderr logging** (the epoch loss printouts) through the
queue unless tensorflow's verbose output is explicitly wanted. TF writes training progress to
stderr by default; the `_QueueWriter` only captures stdout (`sys.stdout = _QueueWriter(q)`).
If TF verbose logging is wanted, set `tf.keras.callbacks.Callback` to emit via `print()` instead
of relying on Keras's default stderr output. This is relevant because the user-visible log will
otherwise be missing LSTM epoch lines.
Confidence: HIGH — `sys.stdout` redirect does not capture `sys.stderr`; TF Keras logs to stderr.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Distribution | Docker | pip + venv | More steps for non-coders; no environment isolation |
| Distribution | Docker | PyInstaller | TensorFlow incompatible with PyInstaller bundling |
| Distribution | Docker | conda | Slower solves; TF conda channel lags pip; more user friction |
| Distribution | Docker | Streamlit Community Cloud | Requires cloud; out of scope per PROJECT.md |
| Pin management | pip-tools | poetry | Poetry is heavier; no need for full pyproject.toml here |
| Pin management | pip-tools | manual requirements.txt | Unpinned transitive deps cause environment drift |
| Base image | python:3.13-slim | python:3.13-alpine | Alpine musl libc breaks TensorFlow wheels |
| Base image | python:3.13-slim | python:3.13 (full) | ~200 MB larger; no benefit for this app |
| Progress display | queue + polling | Streamlit websocket push | Not exposed in public Streamlit API |
| Progress display | queue + polling | st.status / st.spinner | No streaming text; just spinner animation |

---

## Installation

### Developer path (local, no Docker)

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r Reanalysis_Dashboard/requirements.txt
streamlit run Reanalysis_Dashboard/app.py
```

### End-user path (Docker, one step after Docker Desktop install)

```bash
# From repo root — first time (builds image, ~5-10 min on first run)
docker compose up --build

# Subsequent launches
docker compose up

# Open browser to http://localhost:8501
```

### Developer toolchain (pin management)

```bash
pip install pip-tools
pip-compile Reanalysis_Dashboard/requirements.in \
    --output-file Reanalysis_Dashboard/requirements.txt \
    --generate-hashes
```

---

## Open Questions / Confidence Gaps

1. **Streamlit exact latest version** — Verify current version at https://pypi.org/project/streamlit/
   before pinning. Training data suggests ~1.43; actual may differ. (LOW confidence on version number)

2. **`st.fragment(run_every=N)` API stability** — Verify this is not still experimental in the
   current Streamlit release. If experimental, stick with the existing `time.sleep(2) + st.rerun()`
   pattern. (MEDIUM confidence on stability)

3. **`st.container(height=...)` availability** — Verify this is present in whatever Streamlit
   version is pinned. (MEDIUM confidence)

4. **TensorFlow CPU Docker image size** — The `python:3.13-slim` + `tensorflow` install will
   produce a large image (~2.5 GB). This is unavoidable given TF as a dependency. Docker image
   pull time on a fresh machine will be significant (~5–15 min on a slow connection). Flag this
   in user documentation so demo-day setup is done in advance. (HIGH confidence on size estimate)

5. **Windows Docker Desktop requirement** — End users on Windows need Docker Desktop installed
   (requires WSL2 on Windows 10/11). This is a prerequisite that must be documented. Docker Desktop
   is free for personal/educational use. (HIGH confidence)

---

## Sources

- Codebase inspection: `Reanalysis_Dashboard/requirements.txt`, `app.py`, `job_runner.py`,
  `pipeline_bridge.py` — direct read, HIGH confidence
- PROJECT.md constraints (local execution, Docker vs installer TBD, 4–6 week deadline) — HIGH
- Streamlit session state / threading patterns — training knowledge, MEDIUM confidence
- TensorFlow + PyInstaller incompatibility — training knowledge from multiple consistent community
  sources, HIGH confidence on the incompatibility claim
- Docker python:3.13-slim vs alpine incompatibility with TF — training knowledge, HIGH confidence
- pip-tools as pip ecosystem standard — training knowledge, HIGH confidence
- `st.fragment`, `st.container(height=...)` — training knowledge, MEDIUM confidence (verify versions)

*Stack research: 2026-03-29*
