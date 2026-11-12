import numpy as np

from app.config import settings
from app.data import frame
from app.forecast import forecast
from app.ml import (
    FEATURES,
    chronological_split,
    feature_frame,
    load_model,
    metrics,
    predict,
    train_models,
)
from app.seed import generate


def test_generator_is_reproducible_and_structured():
    a = generate(500)
    b = generate(500)
    assert a == b
    assert a != generate(500, seed=7)
    from app.models import Order, Shipment, Zone

    assert len(a[Zone]) == 120 and len(a[Order]) == len(a[Shipment]) == 500
    assert all(r["zone_code"].startswith("SYN-") for r in a[Zone])


def test_temporal_split_label_availability(db):
    train, val, test = chronological_split(frame(db))
    assert train.dispatch_at.max() < val.dispatch_at.min() < test.dispatch_at.min()
    assert train.delivered_at.max() < val.dispatch_at.min()
    assert val.delivered_at.max() < test.dispatch_at.min()
    assert set(train.shipment_id).isdisjoint(test.shipment_id)


def test_future_outcomes_never_change_dispatch_features(db):
    df = frame(db).head(200)
    expected = feature_frame(df)
    changed = df.copy()
    changed["delivered_at"] = changed.order_created_at
    changed["delivery_attempt_count"] = 999
    changed["first_attempt_success"] = False
    changed["late"] = True
    assert feature_frame(changed).equals(expected)
    assert set(FEATURES).isdisjoint(
        {
            "delivered_at",
            "delivery_attempt_count",
            "first_attempt_success",
            "late",
            "shipment_status",
        }
    )


def test_model_roundtrip_missing_values_and_probability_bounds(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    df = frame(db).sort_values("dispatch_at").iloc[::12]
    report = train_models(df)
    bundle = load_model()
    x = feature_frame(df[df.eligible].head(2))
    x.loc[x.index[0], "packing_hours"] = np.nan
    p = bundle["pipeline"].predict_proba(x)[:, 1]
    assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
    assert report["version"] == bundle["report"]["version"]
    assert all("test" in r for r in report["models"].values())
    result = predict(feature_frame(df[df.eligible].head(1)).iloc[0].to_dict())
    assert result["model_version"] == report["version"] and 0 <= result["delay_probability"] <= 1


def test_forecast_holdout_never_uses_future_actuals(db):
    df = frame(db)
    result = forecast(df)
    assert result["sufficient"] and result["holdout_days"] == 28
    train_end = result["train_end"]
    # Duplicating only holdout observations changes errors, not a baseline's fixed-origin predictions.
    import pandas as pd

    cutoff = pd.Timestamp(train_end, tz="Asia/Kolkata") + pd.Timedelta(days=1)
    changed = pd.concat([df, df[df.order_created_at >= cutoff]])
    other = forecast(changed)
    assert result["train_end"] == other["train_end"]
    for method in result["evaluation"]:
        assert (
            result["evaluation"][method]["holdout_predictions"]
            == other["evaluation"][method]["holdout_predictions"]
        )
    assert set(result["evaluation"]) == {"moving_average", "day_of_week", "exponential_smoothing"}
    assert all(r["lower"] <= r["predicted"] <= r["upper"] for r in result["forecast"])


def test_evaluation_includes_confusion_and_calibration():
    result = metrics([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
    assert result["confusion_matrix"] == [[2, 0], [0, 2]]
    assert result["roc_auc"] == 1 and result["calibration"]
