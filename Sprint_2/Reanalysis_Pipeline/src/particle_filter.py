import numpy as np


def _systematic_resample(weights, n):
    """O(N) systematic resampling.

    Generates n evenly-spaced positions on [0, 1] with a single random
    offset, then maps each to a particle index via the cumulative weight
    CDF. Produces lower variance than multinomial resampling.

    Parameters
    ----------
    weights : np.ndarray, shape (n,)
        Normalized particle weights (sum to 1).
    n : int
        Number of particles to draw.

    Returns
    -------
    indices : np.ndarray[int], shape (n,)
    """
    positions = (np.arange(n) + np.random.uniform()) / n
    cumsum = np.cumsum(weights)
    return np.searchsorted(cumsum, positions)


def run_particle_filter(forecast_model, obs_std, mdl_std, Q, R, lookback,
                        n_particles=500, n_state=1, seed=42):
    """Run Sequential Importance Resampling (SIR) Particle Filter.

    Handles intermittent (sparse) observations: the weight/resample step
    only fires on time steps where obs_std is non-NaN. On other steps
    the particles propagate forward without correction.

    Performance notes
    -----------------
    - All process noise and jitter arrays are pre-generated upfront.
    - Log-space weight normalization prevents numerical underflow.
    - Systematic resampling is O(N) via np.searchsorted.
    - Adaptive resampling: skips resampling when ESS >= n_particles/2,
      which covers nearly all steps for monthly TN/TP observations.
    - History reindexing after resampling is a single numpy fancy-index.

    Parameters
    ----------
    forecast_model : ForecastModel
        Any model satisfying the ForecastModel protocol.
        Called via forecast_model.predict_batch(X) where X has shape
        (n_particles, lookback, n_state).
    obs_std : np.ndarray, shape (T, 1)
        Standardized observations. NaN on days without data.
    mdl_std : np.ndarray, shape (T, 1)
        Standardized model data (used for history initialization).
    Q : float
        Process noise variance.
    R : float
        Observation error variance.
    lookback : int
    n_particles : int
    n_state : int
    seed : int

    Returns
    -------
    ens_analysis : np.ndarray, shape (T, n_particles)
    ens_forecast : np.ndarray, shape (T, n_particles)
    """
    np.random.seed(seed)
    T = len(obs_std)

    ens_forecast = np.zeros((T, n_particles))
    ens_analysis = np.zeros((T, n_particles))

    # Initialize particles around first valid observation (or model value)
    first_obs = obs_std[0, 0] if not np.isnan(obs_std[0, 0]) else mdl_std[0, 0]
    particles = first_obs + np.random.normal(0, 0.01, size=n_particles)
    ens_analysis[0, :] = particles

    # History buffer per particle: (n_particles, lookback, n_state)
    histories = np.tile(mdl_std[:lookback].T, (n_particles, 1, 1)).transpose(0, 2, 1)

    # Pre-compute constants
    sqrt_Q = np.sqrt(Q)
    inv_2R = 0.5 / R

    # Pre-generate all noise upfront — avoids per-step RNG calls
    proc_noise_all = np.random.normal(0, sqrt_Q, size=(T, n_particles))
    # Jitter applied after resampling to prevent sample impoverishment
    jitter_all = np.random.normal(0, sqrt_Q * 0.1, size=(T, n_particles))

    # Flatten obs and pre-compute mask for fast per-step lookup
    obs_flat = obs_std[:, 0]
    has_obs_mask = ~np.isnan(obs_flat)

    resample_count = 0

    # Particle filter loop
    for t in range(lookback, T):
        # -- Forecast step --
        preds = forecast_model.predict_batch(histories)  # (N, 1)
        x_f = preds[:, 0] + proc_noise_all[t]           # (N,)
        ens_forecast[t, :] = x_f

        # -- Analysis step --
        if has_obs_mask[t]:
            # Log-space Gaussian likelihood (prevents underflow)
            diff = obs_flat[t] - x_f                    # (N,)
            log_w = -inv_2R * (diff ** 2)               # (N,)
            log_w -= log_w.max()                        # shift for stability
            w = np.exp(log_w)
            w /= w.sum()

            ess = 1.0 / (w ** 2).sum()

            if ess < n_particles * 0.5:
                # Resample + jitter to restore diversity
                idx = _systematic_resample(w, n_particles)
                x_a = x_f[idx] + jitter_all[t]
                histories = histories[idx]              # reindex all buffers
                resample_count += 1
            else:
                # ESS healthy — keep particles as-is
                x_a = x_f
        else:
            ess = float(n_particles)
            x_a = x_f

        ens_analysis[t, :] = x_a

        # -- Update history buffers (vectorized shift) --
        histories[:, :-1, 0] = histories[:, 1:, 0]
        histories[:, -1, 0] = x_a

        if (t + 1) % 2000 == 0:
            status = f"ESS={ess:.0f}/{n_particles}" if has_obs_mask[t] else "no obs"
            print(f"  t = {t+1:,}/{T:,}  |  {status}")

    print(f"  Resampled {resample_count} time(s) over {T - lookback} steps.")

    # Fill first LOOKBACK rows (no filter has run yet)
    for t in range(lookback):
        if has_obs_mask[t]:
            ens_analysis[t, :] = obs_flat[t]
        else:
            ens_analysis[t, :] = mdl_std[t, 0]
        ens_forecast[t, :] = mdl_std[t, 0]

    return ens_analysis, ens_forecast
