"""Idempotent first-run demo setup; existing operational data is preserved."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.config import settings
from app.data import frame
from app.db import SessionLocal
from app.ml import feature_frame, load_model, train_models
from app.models import Order, RiskPrediction
from app.seed import seed_database


def bootstrap():
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(Order)) == 0
    if empty:
        seed_database(settings.seed_orders)
    if not (settings.model_dir / "delay_model.joblib").exists():
        train_models()
    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(RiskPrediction)):
            df = frame(db)
            active = df[
                df.shipment_status.eq("IN_TRANSIT") & df.valid_promise & df.dispatch_at.notna()
            ]
            if len(active):
                model = load_model()
                features = feature_frame(active)
                probabilities = model["pipeline"].predict_proba(features)[:, 1]
                for (_, r), (_, x), p in zip(active.iterrows(), features.iterrows(), probabilities):
                    db.add(
                        RiskPrediction(
                            prediction_id=str(uuid.uuid4()),
                            shipment_id=r.shipment_id,
                            prediction_timestamp=datetime.now(timezone.utc),
                            delay_probability=float(p),
                            risk_level="HIGH" if p >= 0.6 else "MEDIUM" if p >= 0.3 else "LOW",
                            model_version=model["report"]["version"],
                            feature_snapshot=x.to_dict(),
                        )
                    )
                db.commit()
        # Views are installed by the migration; a SELECT verifies expected database state.
        db.execute(text("SELECT COUNT(*) FROM vw_daily_delivery_kpis"))


if __name__ == "__main__":
    bootstrap()
