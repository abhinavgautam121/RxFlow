"""Dispatch-time classifiers with embargoed chronological label availability."""

import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import settings
from app.data import frame
from app.db import SessionLocal

NUMERIC = [
    "distance_band_km",
    "order_to_dispatch_hours",
    "picking_hours",
    "packing_hours",
    "backlog_at_dispatch",
    "order_hour",
    "order_weekday",
    "remaining_promise_hours",
]
CATEGORICAL = [
    "zone_id",
    "fulfillment_center_id",
    "delivery_partner_id",
    "promised_service_level",
]
FEATURES = NUMERIC + CATEGORICAL


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Explicit allowlist: no delivery events, attempts, outcomes or future aggregates."""
    x = df.copy()
    local = x.order_created_at.dt.tz_convert("Asia/Kolkata")
    x["order_hour"] = local.dt.hour
    x["order_weekday"] = local.dt.dayofweek
    x["remaining_promise_hours"] = (
        x.promised_delivery_at - x.dispatch_at
    ).dt.total_seconds() / 3600
    return x[FEATURES]


def chronological_split(df):
    data = df[df.eligible].sort_values("dispatch_at").copy()
    if len(data) < 300:
        raise ValueError("At least 300 eligible delivered shipments required")
    val_start = data.dispatch_at.iloc[int(len(data) * 0.6)]
    test_start = data.dispatch_at.iloc[int(len(data) * 0.8)]
    train = data[(data.dispatch_at < val_start) & (data.delivered_at < val_start)]
    validation = data[
        (data.dispatch_at >= val_start)
        & (data.dispatch_at < test_start)
        & (data.delivered_at < test_start)
    ]
    test = data[data.dispatch_at >= test_start]
    if min(len(train), len(validation), len(test)) < 30 or any(
        d.late.nunique() < 2 for d in [train, validation, test]
    ):
        raise ValueError("Insufficient chronological class coverage")
    return train, validation, test


def metrics(y, p, threshold=0.5):
    p = np.clip(np.asarray(p, dtype=float), 0, 1)
    predicted = p >= threshold
    fraction, mean = calibration_curve(y, p, n_bins=8, strategy="quantile")
    return {
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None,
        "pr_auc": float(average_precision_score(y, p)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "brier_score": float(brier_score_loss(y, p)),
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        "threshold": threshold,
        "sample_size": len(y),
        "positive_count": int(np.sum(y)),
        "positive_share": float(np.mean(y)),
        "calibration": [
            {"predicted": float(a), "observed": float(b)} for a, b in zip(mean, fraction)
        ],
    }


def train_models(df=None):
    if df is None:
        with SessionLocal() as db:
            df = frame(db)
    train, val, test = chronological_split(df)
    x = feature_frame(train)
    xv = feature_frame(val)
    xt = feature_frame(test)
    preprocess = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                CATEGORICAL,
            ),
        ]
    )
    models = {
        "logistic_regression": LogisticRegression(max_iter=1500, random_state=42),
        "random_forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=15,
            n_jobs=-1,
            random_state=42,
        ),
    }
    fitted = {}
    report = {}
    validation_scores = {}
    for name, estimator in models.items():
        model = Pipeline([("features", preprocess), ("model", estimator)])
        # Each pipeline receives a separate transformer instance.
        from sklearn.base import clone

        model = clone(model)
        model.fit(x, train.late.astype(int))
        p = model.predict_proba(xv)[:, 1]
        threshold = float(
            max(
                np.arange(0.2, 0.81, 0.05),
                key=lambda t: f1_score(val.late, p >= t, zero_division=0),
            )
        )
        validation_scores[name] = float(average_precision_score(val.late, p))
        report[name] = {
            "validation": metrics(val.late, p, threshold),
            "test": metrics(test.late, model.predict_proba(xt)[:, 1], threshold),
        }
        fitted[name] = model
    selected = max(validation_scores, key=validation_scores.get)
    rule = ((test.order_to_dispatch_hours > 6) | (test.distance_band_km >= 55)).astype(
        float
    ) * 0.7 + 0.1
    report["rule_baseline"] = {"test": metrics(test.late, rule)}
    importance = permutation_importance(
        fitted[selected],
        xv.iloc[:1500],
        val.late.iloc[:1500],
        n_repeats=3,
        random_state=42,
        scoring="average_precision",
        n_jobs=1,
    )
    signature = hashlib.sha256(
        pd.util.hash_pandas_object(x, index=False).values.tobytes()
        + train.late.to_numpy().tobytes()
    ).hexdigest()[:10]
    version = f"rxflow-{selected}-v1-{signature}"
    result = {
        "version": version,
        "selected_model": selected,
        "selection_reason": "Highest validation PR-AUC; decision threshold maximises validation F1. Test set was not used for selection.",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "models": report,
        "split": {
            "train": len(train),
            "validation": len(val),
            "test": len(test),
            "train_label_end": train.delivered_at.max().isoformat(),
            "validation_dispatch_start": val.dispatch_at.min().isoformat(),
            "validation_label_end": val.delivered_at.max().isoformat(),
            "test_dispatch_start": test.dispatch_at.min().isoformat(),
        },
        "importance": sorted(
            [
                {"feature": f, "importance": round(float(v), 5)}
                for f, v in zip(FEATURES, importance.importances_mean)
            ],
            key=lambda r: r["importance"],
            reverse=True,
        ),
        "limitations": [
            "Fictional operations; no evidence of real-world performance.",
            "No causal explanations; permutation importance is global validation association.",
            "Probabilities are uncalibrated; inspect reliability curve and Brier score.",
            "Synthetic generating patterns may make evaluation optimistic.",
            "No historical partner aggregates are used; this avoids look-ahead feature leakage.",
        ],
    }
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"pipeline": fitted[selected], "report": result},
        settings.model_dir / "delay_model.joblib",
    )
    (settings.model_dir / "model_report.json").write_text(json.dumps(result, indent=2))
    return result


def load_model():
    path = settings.model_dir / "delay_model.joblib"
    if not path.exists():
        raise FileNotFoundError("Run python -m app.ml before requesting predictions")
    return joblib.load(path)


def predict(inputs: dict, low=0.3, high=0.6):
    bundle = load_model()
    x = pd.DataFrame([inputs])[FEATURES]
    probability = float(bundle["pipeline"].predict_proba(x)[0, 1])
    return {
        "delay_probability": probability,
        "risk_level": "HIGH" if probability >= high else "MEDIUM" if probability >= low else "LOW",
        "model_version": bundle["report"]["version"],
        "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        "input_factors": inputs,
        "global_factors": bundle["report"]["importance"][:5],
        "explanation": "Global permutation importance describes validation associations; it does not attribute causes to this shipment.",
    }


if __name__ == "__main__":
    print(json.dumps(train_models(), indent=2))
