import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def db():
    """Every database test rolls back even when application code calls commit."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def metric_df():
    now = pd.Timestamp("2026-11-12", tz="UTC")
    created = now - pd.Timedelta(days=2)
    promise = now - pd.Timedelta(days=1)
    df = pd.DataFrame(
        {
            "order_id": ["a", "b", "c", "d", "e"],
            "shipment_id": ["s1", "s2", "s3", "s4", "s5"],
            "order_created_at": [created] * 5,
            "order_confirmed_at": [created] * 4 + [pd.NaT],
            "dispatch_at": [created + pd.Timedelta(hours=2)] * 4 + [pd.NaT],
            "promised_delivery_at": [
                promise,
                promise,
                now - pd.Timedelta(hours=2),
                now + pd.Timedelta(hours=2),
                promise,
            ],
            "delivered_at": [promise, promise + pd.Timedelta(hours=4), pd.NaT, pd.NaT, pd.NaT],
            "shipment_status": ["DELIVERED", "DELIVERED", "IN_TRANSIT", "IN_TRANSIT", "CANCELLED"],
            "order_status": ["DELIVERED", "DELIVERED", "IN_TRANSIT", "IN_TRANSIT", "CANCELLED"],
            "delivery_attempt_count": [1, 2, 0, 0, 0],
            "first_attempt_success": [True, False, None, None, None],
            "shipping_cost": [10.0, 20.0, 30.0, 40.0, 0.0],
            "promised_service_level": ["SDD", "NDD", "OTHER", "NDD", "NDD"],
            "eligible": [True, True, False, False, False],
            "valid_promise": [True] * 5,
            "late": [False, True, False, False, False],
        }
    )
    df["order_to_dispatch_hours"] = (df.dispatch_at - df.order_created_at).dt.total_seconds() / 3600
    df["transit_hours"] = (df.delivered_at - df.dispatch_at).dt.total_seconds() / 3600
    df["fulfilment_hours"] = (df.delivered_at - df.order_created_at).dt.total_seconds() / 3600
    return df
