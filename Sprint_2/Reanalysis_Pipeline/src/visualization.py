import numpy as np
import matplotlib.pyplot as plt
import os


UNITS = {
    "discharge": "CMS",
    "TN": "mg/L",
    "TP": "mg/L",
}

LABELS = {
    "discharge": "Discharge",
    "TN": "Total Nitrogen",
    "TP": "Total Phosphorus",
}


def plot_comparison(time_idx, obs_phys, openloop_phys, rean_mean_phys,
                    variable, station_name, save_dir):
    """Three-line comparison: Observed vs Open-Loop vs Reanalysis Mean."""
    unit = UNITS.get(variable, "")
    label = LABELS.get(variable, variable)

    fig, ax = plt.subplots(figsize=(14, 5))

    # For sparse obs, only plot non-NaN points as scatter
    obs_valid = ~np.isnan(obs_phys)
    if obs_valid.sum() < len(obs_phys) * 0.5:
        # Sparse: scatter
        ax.scatter(time_idx[obs_valid], obs_phys[obs_valid],
                   s=12, color="#d62728", alpha=0.7, zorder=3, label="Observed")
    else:
        # Dense: line
        ax.plot(time_idx, obs_phys, label="Observed", linewidth=0.9, alpha=0.85)

    ax.plot(time_idx, openloop_phys, label="Open-Loop (LSTM, no DA)",
            linewidth=0.9, alpha=0.7)
    ax.plot(time_idx, rean_mean_phys, label="Reanalysis Mean (LSTM+EnKF)",
            linewidth=1.5)

    ax.set_xlabel("Date")
    ax.set_ylabel(f"{label} ({unit})")
    ax.set_title(f"{label}: Observed vs Open-Loop vs Reanalysis — {station_name}")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    plt.tight_layout()

    path = os.path.join(save_dir, f"{variable}_Comparison.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {path}")


def plot_ci_area(time_idx, ci_lower, ci_upper, rean_mean_phys,
                 ci_integral, variable, station_name, save_dir):
    """Shaded 95% CI with reanalysis mean overlay."""
    unit = UNITS.get(variable, "")
    label = LABELS.get(variable, variable)

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.fill_between(time_idx, ci_lower, ci_upper,
                    color="#7FB3D8", alpha=0.55, edgecolor="none",
                    label="95% CI Region")
    ax.plot(time_idx, rean_mean_phys, color="#8B0000", linewidth=1.2,
            label="Reanalysis Mean")

    start_yr = time_idx.min().year
    end_yr = time_idx.max().year
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(f"{label} ({unit})", fontsize=12)
    ax.set_title(
        f"{label}: 95% Confidence Interval ({start_yr}–{end_yr}) — {station_name}\n"
        f"∫ (Upper − Lower) dx = {ci_integral:,.2f} {unit}·days",
        fontsize=13, fontweight="bold",
    )
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = os.path.join(save_dir, f"CI_Area_{variable}.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {path}")


def plot_model_vs_observed(time_idx, model_phys, obs_phys,
                           variable, station_name, save_dir):
    """Model simulation line vs observation scatter dots."""
    unit = UNITS.get(variable, "")
    label = LABELS.get(variable, variable)

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(time_idx, model_phys, color="#1f77b4", linewidth=0.9,
            label="Model Simulation")

    obs_valid = ~np.isnan(obs_phys)
    ax.scatter(time_idx[obs_valid], obs_phys[obs_valid],
               s=4, color="#d62728", alpha=0.6, zorder=3, label="Observed")

    start_yr = time_idx.min().year
    end_yr = time_idx.max().year
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel(f"{label} ({unit})", fontsize=12)
    ax.set_title(
        f"Model Simulation vs Observed {label} ({start_yr}–{end_yr}) — {station_name}",
        fontsize=13, fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = os.path.join(save_dir, f"Model_vs_Observed_{variable}.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved → {path}")
