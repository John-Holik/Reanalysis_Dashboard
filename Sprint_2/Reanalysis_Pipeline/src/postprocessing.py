import numpy as np
import pandas as pd
import os
from scipy import integrate


def inverse_transform(arr, scaler):
    """Inverse-transform a 1-D standardized array back to physical units."""
    return scaler.inverse_transform(arr.reshape(-1, 1)).flatten()


def compute_ci_bounds(ens_physical, lower_pct=2.5, upper_pct=97.5):
    """Compute confidence interval bounds from ensemble.

    Parameters
    ----------
    ens_physical : np.ndarray, shape (T, M)
    lower_pct, upper_pct : float

    Returns
    -------
    ci_lower, ci_upper : np.ndarray, shape (T,)
    """
    ci_lower = np.percentile(ens_physical, lower_pct, axis=1)
    ci_upper = np.percentile(ens_physical, upper_pct, axis=1)
    return ci_lower, ci_upper


def compute_ci_integral(ci_lower, ci_upper):
    """Compute CI area integral via trapezoidal rule.

    Returns
    -------
    dict with 'integral', 'mean_width', 'max_width', 'min_width'.
    """
    ci_width = ci_upper - ci_lower
    t_days = np.arange(len(ci_width), dtype=float)
    ci_integral = integrate.trapezoid(ci_width, x=t_days)
    return {
        "integral": ci_integral,
        "mean_width": float(ci_width.mean()),
        "max_width": float(ci_width.max()),
        "min_width": float(ci_width.min()),
    }


def export_results(time_idx, obs_phys, openloop_phys, rean_mean_phys,
                   ens_phys, output_dir, variable, n_ensemble):
    """Save observation, open-loop, reanalysis mean, and full ensemble CSVs.

    Parameters
    ----------
    time_idx : pd.DatetimeIndex
    obs_phys : np.ndarray, shape (T,) — may contain NaN for sparse obs
    openloop_phys, rean_mean_phys : np.ndarray, shape (T,)
    ens_phys : np.ndarray, shape (T, M)
    output_dir : str
    variable : str
    n_ensemble : int
    """
    os.makedirs(output_dir, exist_ok=True)

    # Observations
    obs_out = pd.DataFrame({"time": time_idx, variable: obs_phys}).set_index("time")
    obs_out.to_csv(os.path.join(output_dir, f"obs_{variable}.csv"))

    # Open-loop
    ol_out = pd.DataFrame({"time": time_idx, variable: openloop_phys}).set_index("time")
    ol_out.to_csv(os.path.join(output_dir, f"model_openloop_{variable}.csv"))

    # Reanalysis mean
    rean_out = pd.DataFrame({"time": time_idx, variable: rean_mean_phys}).set_index("time")
    rean_out.to_csv(os.path.join(output_dir, f"reanalysis_{variable}_mean.csv"))

    # Full ensemble (long format) — vectorized construction
    T, M = ens_phys.shape
    times_rep = np.tile(time_idx.values, M)
    members_rep = np.repeat(np.arange(M), T)
    values_rep = ens_phys.T.ravel()  # member-major order to match repeat
    ens_out = pd.DataFrame({"time": times_rep, "member": members_rep, variable: values_rep})
    ens_out.to_csv(os.path.join(output_dir, f"reanalysis_{variable}_ensemble.csv"), index=False)

    print(f"  Saved CSVs to {output_dir}")
