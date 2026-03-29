"""
app.py
------
Streamlit web application for the hydrological reanalysis pipeline.

5-step wizard:
  0 — Upload model + observation CSVs
  1 — Configure observation CSV column mapping
  2 — Configure hyperparameters (optional)
  3 — Running (progress display)
  4 — Results (inline plots + CSV downloads)
"""

import os
import queue
import time

import streamlit as st

import pipeline_bridge
import job_runner

st.set_page_config(
    page_title="Reanalysis Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---- Default hyperparameters (mirror pipeline_config.yaml) -----------
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


def _init_state():
    defaults = {
        "step": 0,
        "model_file": None,
        "obs_file": None,
        "obs_columns": [],
        "obs_config": {},
        "variable": None,
        "model_date_col": None,
        "model_value_col": None,
        "station_name": "MyStation",
        "hyperparams": DEFAULT_HYPERPARAMS.copy(),
        "seed": 42,
        "job_result": None,
        "progress_queue": None,
        "job_thread": None,
        "progress_log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


def _best_guess_index(cols: list, candidates: list) -> int:
    """Return the index of the first column whose lowercase name matches a candidate."""
    lower_cols = [c.lower() for c in cols]
    for candidate in candidates:
        if candidate in lower_cols:
            return lower_cols.index(candidate)
    return 0


# ======================================================================
# STEP 0: File Upload
# ======================================================================
def render_step_upload():
    st.title("Hydrology Reanalysis Dashboard")
    st.markdown(
        "Upload your model simulation and observation CSVs to generate a "
        "reanalysis dataset using LSTM + Ensemble Kalman Filter."
    )
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Model CSV")
        st.caption("Upload any CSV with a date column and a numeric value column.")
        model_file = st.file_uploader(
            "Upload model CSV", type=["csv"], key="upload_model",
            label_visibility="collapsed",
        )
        if model_file:
            try:
                cols = pipeline_bridge.get_csv_columns(model_file)
                numeric_cols = pipeline_bridge.get_csv_numeric_columns(model_file)
                if not numeric_cols or numeric_cols == cols:
                    st.warning("No numeric columns detected -- verify your value column selection carefully.")
                st.success(f"{len(cols)} columns detected")
                preview_df = pipeline_bridge.get_csv_preview(model_file)
                st.dataframe(preview_df, hide_index=False)
                st.selectbox(
                    "Date column",
                    cols,
                    index=_best_guess_index(cols, ["date", "time", "datetime", "simdate", "timestamp"]),
                    key="model_date_col",
                )
                st.selectbox(
                    "Value column (variable to reanalyse)",
                    numeric_cols,
                    index=_best_guess_index(numeric_cols, ["value", "flow", "discharge", "streamflow"]),
                    key="model_value_col",
                )
                st.session_state.model_file = model_file
            except Exception:
                st.error("Could not read this CSV. Check that the file is UTF-8 encoded and comma-separated.")
                model_file = None

    with col2:
        st.subheader("Observation CSV")
        st.caption("Flexible format — you will map columns in the next step")
        obs_file = st.file_uploader(
            "Upload observation CSV", type=["csv"], key="upload_obs",
            label_visibility="collapsed",
        )
        if obs_file:
            try:
                cols = pipeline_bridge.get_csv_columns(obs_file)
                st.success(
                    f"Loaded -- columns: `{'`, `'.join(cols[:6])}`"
                    + (f" (+{len(cols)-6} more)" if len(cols) > 6 else "")
                )
                obs_preview_df = pipeline_bridge.get_csv_preview(obs_file)
                st.dataframe(obs_preview_df, hide_index=False)
                st.session_state.obs_file = obs_file
                st.session_state.obs_columns = cols
            except Exception:
                st.error("Could not read this CSV. Check that the file is UTF-8 encoded and comma-separated.")
                obs_file = None

    st.divider()

    station_name = st.text_input(
        "Station name (used as label in outputs)",
        value=st.session_state.station_name,
    )
    st.session_state.station_name = station_name

    can_proceed = (
        st.session_state.model_file is not None
        and st.session_state.obs_file is not None
        and st.session_state.get("model_date_col") is not None
        and st.session_state.get("model_value_col") is not None
        and station_name.strip() != ""
    )
    if st.button("Next: Configure Observation CSV →", disabled=not can_proceed, type="primary"):
        st.session_state.step = 1
        st.rerun()


# ======================================================================
# STEP 1: Observation CSV Configuration
# ======================================================================
def _preview_obs(obs_config: dict):
    try:
        st.session_state.obs_file.seek(0)
        if obs_config["type"] == "dedicated_discharge":
            df = pipeline_bridge.build_obs_df_dedicated(
                st.session_state.obs_file,
                date_col=obs_config["date_col"],
                value_col=obs_config["value_col"],
                convert_factor=obs_config["convert_factor"],
            )
        else:
            df = pipeline_bridge.build_obs_df_multi_station(
                st.session_state.obs_file,
                date_col=obs_config["date_col"],
                value_col=obs_config["value_col"],
                station_col=obs_config["station_col"],
                station_filter=obs_config["station_filter"],
                param_col=obs_config["param_col"],
                param_filter=obs_config["param_filter"],
                convert_factor=obs_config["convert_factor"],
            )
        if len(df) == 0:
            st.warning(
                "No rows matched the current filter settings. "
                "Check station ID and parameter values."
            )
        else:
            st.success(f"Parsed {len(df):,} observation rows. Preview:")
            st.dataframe(df.head(10))
    except Exception as e:
        st.error(f"Parse error: {e}")


def render_step_obs_config():
    st.title("Hydrology Reanalysis Dashboard")
    st.subheader("Step 2: Configure Observation CSV Parsing")
    st.divider()

    cols = st.session_state.obs_columns

    # Auto-detect format from column names
    lower_cols = [c.lower() for c in cols]
    has_station = any(c in lower_cols for c in ("stationid", "station_id", "station"))
    has_param = any(c in lower_cols for c in ("parameter", "param"))
    auto_type = "multi_station" if (has_station and has_param) else "dedicated_discharge"

    format_label = "Multi-station water quality" if auto_type == "multi_station" else "Dedicated single-variable"
    st.info(f"Auto-detected format: **{format_label}** (based on column names)")

    obs_type = st.radio(
        "Observation CSV format",
        ["dedicated_discharge", "multi_station"],
        index=0 if auto_type == "dedicated_discharge" else 1,
        format_func=lambda x: {
            "dedicated_discharge": "Dedicated  —  single station/variable (date + value columns only)",
            "multi_station": "Multi-station  —  StationID, Parameter, SampleDate, Result_Value style",
        }[x],
        horizontal=True,
    )

    st.divider()
    obs_config = {"type": obs_type}

    col1, col2 = st.columns(2)
    with col1:
        obs_config["date_col"] = st.selectbox(
            "Date column",
            cols,
            index=_best_guess_index(cols, ["date", "sampledate", "time", "datetime"]),
        )
    with col2:
        obs_config["value_col"] = st.selectbox(
            "Value column",
            cols,
            index=_best_guess_index(
                cols, ["value", "result_value", "discharge_cms", "discharge", "flow"]
            ),
        )

    if obs_type == "multi_station":
        st.markdown("**Multi-station filters**")
        col3, col4 = st.columns(2)

        with col3:
            station_col_name = st.selectbox(
                "Station ID column",
                cols,
                index=_best_guess_index(cols, ["stationid", "station_id", "station"]),
            )
            obs_config["station_col"] = station_col_name
            st.session_state.obs_file.seek(0)
            station_values = pipeline_bridge.get_csv_unique_values(
                st.session_state.obs_file, station_col_name
            )
            obs_config["station_filter"] = st.selectbox(
                "Filter by Station ID", station_values
            )

        with col4:
            param_col_name = st.selectbox(
                "Parameter column",
                cols,
                index=_best_guess_index(cols, ["parameter", "param"]),
            )
            obs_config["param_col"] = param_col_name
            st.session_state.obs_file.seek(0)
            param_values = pipeline_bridge.get_csv_unique_values(
                st.session_state.obs_file, param_col_name
            )
            obs_config["param_filter"] = st.selectbox(
                "Filter by Parameter", param_values
            )

    st.divider()
    convert_factor = st.number_input(
        "Unit conversion factor  (multiply raw values by this; 1.0 = no conversion, 0.001 = µg/L → mg/L)",
        min_value=0.0,
        value=1.0,
        step=0.001,
        format="%.4f",
    )
    obs_config["convert_factor"] = convert_factor

    if st.button("Preview parsed observations"):
        _preview_obs(obs_config)

    st.session_state.obs_config = obs_config

    st.divider()
    col_back, col_next = st.columns([1, 5])
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 0
            st.rerun()
    with col_next:
        if st.button("Next: Hyperparameters →", type="primary"):
            st.session_state.step = 2
            st.rerun()


# ======================================================================
# STEP 2: Hyperparameter Configuration
# ======================================================================
def render_step_hyperparams():
    st.title("Hydrology Reanalysis Dashboard")
    st.subheader("Step 3: Hyperparameters")
    st.caption("Defaults are tuned for daily hydrological data. Adjust only if needed.")
    st.divider()

    hp = st.session_state.hyperparams

    with st.expander("LSTM Architecture & Training", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            hp["lookback"] = st.slider(
                "Lookback window (days)", 5, 60, hp["lookback"],
                help="Number of past days fed as input to the LSTM",
            )
            hp["lstm_units"] = st.select_slider(
                "LSTM units", [32, 64, 128, 256], hp["lstm_units"]
            )
            hp["dense_units"] = st.select_slider(
                "Dense units", [32, 64, 128], hp["dense_units"]
            )
        with col2:
            hp["learning_rate"] = st.select_slider(
                "Learning rate", [0.0001, 0.0005, 0.001, 0.005, 0.01], hp["learning_rate"]
            )
            hp["batch_size"] = st.select_slider("Batch size", [16, 32, 64], hp["batch_size"])
            hp["epochs"] = st.slider("Max epochs", 50, 500, hp["epochs"])
            hp["patience"] = st.slider(
                "Early stopping patience", 5, 50, hp["patience"],
                help="Stop training if validation loss does not improve for this many epochs",
            )

    with st.expander("EnKF Settings", expanded=False):
        col3, col4 = st.columns(2)
        with col3:
            hp["n_ensemble"] = st.slider(
                "Ensemble members", 10, 200, hp["n_ensemble"],
                help="More members = better uncertainty estimate but slower",
            )
            hp["obs_error_factor"] = st.slider(
                "Observation error factor (R)", 0.05, 1.0, hp["obs_error_factor"], step=0.05,
                help="R = factor × Var(obs). Higher = trust model more, trust observations less",
            )
        with col4:
            hp["train_fraction"] = st.slider(
                "Train fraction", 0.5, 0.9, hp["train_fraction"], step=0.05
            )
            hp["min_overlap_days"] = st.slider(
                "Min overlap days", 10, 100, hp["min_overlap_days"],
                help="Minimum days where model and observations overlap to proceed",
            )

    seed = st.number_input("Random seed", min_value=0, value=st.session_state.seed, step=1)
    st.session_state.seed = int(seed)
    st.session_state.hyperparams = hp

    st.divider()
    col_back, col_run = st.columns([1, 5])
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col_run:
        if st.button("Run Reanalysis", type="primary"):
            _start_job()
            st.session_state.step = 3
            st.rerun()


def _start_job():
    """Build DataFrames and launch the background pipeline thread."""
    obs_config = st.session_state.obs_config

    # Build model DataFrame for the selected variable
    st.session_state.model_file.seek(0)
    model_dfs = pipeline_bridge.build_model_df(st.session_state.model_file)
    model_df = model_dfs[st.session_state.variable]

    # Build observation DataFrame
    st.session_state.obs_file.seek(0)
    if obs_config["type"] == "dedicated_discharge":
        obs_df = pipeline_bridge.build_obs_df_dedicated(
            st.session_state.obs_file,
            date_col=obs_config["date_col"],
            value_col=obs_config["value_col"],
            convert_factor=obs_config["convert_factor"],
        )
    else:
        obs_df = pipeline_bridge.build_obs_df_multi_station(
            st.session_state.obs_file,
            date_col=obs_config["date_col"],
            value_col=obs_config["value_col"],
            station_col=obs_config["station_col"],
            station_filter=obs_config["station_filter"],
            param_col=obs_config["param_col"],
            param_filter=obs_config["param_filter"],
            convert_factor=obs_config["convert_factor"],
        )

    result, q, t = job_runner.launch_job(
        model_df=model_df,
        obs_df=obs_df,
        variable=st.session_state.variable,
        station_name=st.session_state.station_name,
        hyperparams=st.session_state.hyperparams,
        seed=st.session_state.seed,
    )
    st.session_state.job_result = result
    st.session_state.progress_queue = q
    st.session_state.job_thread = t
    st.session_state.progress_log = []


# ======================================================================
# STEP 3: Running — Progress Display
# ======================================================================
def render_step_running():
    st.title("Hydrology Reanalysis Dashboard")
    st.subheader("Running Pipeline...")

    result = st.session_state.job_result
    q = st.session_state.progress_queue

    # Drain the queue into the persistent log
    try:
        while True:
            msg = q.get_nowait()
            if msg == "__DONE__":
                st.session_state.step = 4
                st.rerun()
                return
            elif msg == "__ERROR__":
                st.error("The pipeline encountered an error.")
                if result.error_message:
                    st.code(result.error_message, language="python")
                if st.button("Start Over"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
                return
            else:
                st.session_state.progress_log.append(msg)
    except queue.Empty:
        pass

    # Progress display
    col1, col2 = st.columns([3, 1])
    with col1:
        log = st.session_state.progress_log
        if log:
            st.code("\n".join(log[-30:]))  # show last 30 lines
        else:
            st.info("Initializing TensorFlow and loading data...")
    with col2:
        st.metric("Log lines", len(st.session_state.progress_log))
        st.caption("Status: running")
        st.caption("LSTM training typically takes 2–10 minutes.")

    # Poll for updates every 2 seconds
    time.sleep(2)
    st.rerun()


# ======================================================================
# STEP 4: Results
# ======================================================================
def render_step_results():
    st.title("Hydrology Reanalysis Dashboard")
    st.subheader("Results")

    result = st.session_state.job_result
    variable = st.session_state.variable
    output_dir = result.output_dir

    # Summary metrics
    if result.summary_metrics:
        m = result.summary_metrics
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Time Steps", f"{m['T']:,}")
        col2.metric("Observations", f"{m['obs_count']:,}")
        col3.metric("Sparse?", "Yes" if m.get("is_sparse") else "No")
        col4.metric("Best Val Loss", f"{m['best_val_loss']:.5f}")
        col5.metric("Stopped Epoch", m["stopped_epoch"])
        col6.metric("CI Mean Width", f"{m['ci_mean_width']:.4f}")

    st.divider()

    # Inline plots
    st.subheader("Plots")
    plot_files = {
        "Comparison (Observations vs Open-Loop vs Reanalysis)": f"{variable}_Comparison.png",
        "95% Confidence Interval Area": f"CI_Area_{variable}.png",
        "Model vs Observed": f"Model_vs_Observed_{variable}.png",
    }

    for title, filename in plot_files.items():
        path = os.path.join(output_dir, filename)
        if os.path.exists(path):
            st.markdown(f"**{title}**")
            st.image(path, use_container_width=True)
        else:
            st.warning(f"Plot not generated: {filename}")

    st.divider()

    # CSV Downloads
    st.subheader("Download Results")
    csv_files = {
        f"Observations": f"obs_{variable}.csv",
        f"Open-Loop Baseline": f"model_openloop_{variable}.csv",
        f"Reanalysis Mean": f"reanalysis_{variable}_mean.csv",
        f"Reanalysis Ensemble": f"reanalysis_{variable}_ensemble.csv",
    }

    dl_cols = st.columns(len(csv_files))
    for col, (label, filename) in zip(dl_cols, csv_files.items()):
        path = os.path.join(output_dir, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                col.download_button(
                    label=label,
                    data=f,
                    file_name=filename,
                    mime="text/csv",
                )
        else:
            col.warning(f"Not found: {filename}")

    st.divider()
    if st.button("Run Another Analysis"):
        for key in ["job_result", "progress_queue", "job_thread", "progress_log"]:
            st.session_state[key] = None if key != "progress_log" else []
        st.session_state.step = 0
        st.rerun()


# ======================================================================
# ROUTER
# ======================================================================
STEP_RENDERERS = {
    0: render_step_upload,
    1: render_step_obs_config,
    2: render_step_hyperparams,
    3: render_step_running,
    4: render_step_results,
}

STEP_RENDERERS[st.session_state.step]()
