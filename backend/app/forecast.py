import numpy as np
import pandas as pd


def forecast(df, horizon=14):
    """Fixed-origin holdout: every holdout prediction uses only the training prefix."""
    if df.empty:
        return {
            "sufficient": False,
            "warning": "No history in the selected cohort",
            "history": [],
            "forecast": [],
        }
    dates = df.order_created_at.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()
    series = dates.value_counts().sort_index().asfreq("D", fill_value=0).astype(float)
    if len(series) < 60 or series.sum() < 100:
        return {
            "sufficient": False,
            "warning": "At least 60 days and 100 orders required",
            "history": [],
            "forecast": [],
        }
    holdout = min(28, len(series) // 4)
    training = series.iloc[:-holdout]
    actual = series.iloc[-holdout:]

    def values(s, idx, method):
        if method == "moving_average":
            return np.repeat(s.iloc[-28:].mean(), len(idx))
        if method == "exponential_smoothing":
            return np.repeat(s.ewm(alpha=0.2, adjust=False).mean().iloc[-1], len(idx))
        profile = s.iloc[-56:].groupby(s.iloc[-56:].index.dayofweek).mean()
        return np.array([profile.get(d.dayofweek, s.mean()) for d in idx])

    results = {}
    for method in ["moving_average", "day_of_week", "exponential_smoothing"]:
        p = values(training, actual.index, method)
        error = np.abs(actual.values - p)
        results[method] = {
            "mae": float(error.mean()),
            "wape": float(error.sum() / actual.sum()) if actual.sum() else None,
            "holdout_predictions": p.tolist(),
        }
    best = min(results, key=lambda k: results[k]["mae"])
    held = values(training, actual.index, best)
    width = float(np.quantile(np.abs(actual - held), 0.9))
    future = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon)
    predicted = values(series, future, best)
    return {
        "sufficient": True,
        "selected_method": best,
        "evaluation": results,
        "train_end": training.index.max().date().isoformat(),
        "holdout_days": holdout,
        "history": [
            {"date": d.date().isoformat(), "actual": float(y), "predicted": float(p)}
            for d, y, p in zip(actual.index, actual, held)
        ],
        "forecast": [
            {
                "date": d.date().isoformat(),
                "predicted": round(float(p), 1),
                "lower": round(max(0, float(p) - width), 1),
                "upper": round(float(p) + width, 1),
            }
            for d, p in zip(future, predicted)
        ],
        "weekly": [
            {"week": str(k), "orders": float(v)}
            for k, v in series.resample("W-MON").sum().tail(12).items()
        ],
        "warning": "Fixed-origin holdout; uncertainty band uses empirical absolute holdout errors and has no guaranteed coverage. Recent final day may be partial.",
    }
