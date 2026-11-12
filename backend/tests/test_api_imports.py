import io
import zipfile

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import Order, Shipment, Zone
from app.quality import stage_import, validate_record


@pytest.mark.parametrize(
    "path",
    [
        "overview",
        "delivery/kpis",
        "delivery/trends",
        "delivery/analysis",
        "zones",
        "partners",
        "inventory/overview",
        "models/performance",
        "predictions/high-risk",
        "forecast",
        "data-quality",
        "scenarios",
        "imports",
    ],
)
def test_main_api_endpoints(client, path):
    response = client.get("/api/v1/" + path)
    assert response.status_code == 200, response.text[:200]


def test_filters_and_pagination(client, db):
    response = client.get("/api/v1/shipments?city=Bengaluru&page_size=7").json()
    assert len(response["rows"]) == 7 and all(r["city"] == "Bengaluru" for r in response["rows"])
    assert response["total"] == db.scalar(
        select(func.count()).select_from(Order).join(Zone).where(Zone.city == "Bengaluru")
    )
    assert client.get("/api/v1/shipments?page_size=101").status_code == 422
    assert client.get("/api/v1/overview?start=2026-11-12&end=2026-01-01").status_code == 422
    assert client.get("/api/v1/shipments/missing").status_code == 404


def test_empty_cohort_returns_null_rates(client):
    result = client.get("/api/v1/overview?city=NoSuchCity")
    assert result.status_code == 200
    assert (
        result.json()["kpis"]["total_orders"] == 0
        and result.json()["kpis"]["on_time"]["value"] is None
    )


def test_prediction_validation_and_roundtrip(client):
    good = client.post("/api/v1/predictions/delay", json={})
    assert good.status_code == 200 and 0 <= good.json()["delay_probability"] <= 1
    assert client.post("/api/v1/predictions/delay", json={"zone_id": "bad"}).status_code == 422
    assert (
        client.post("/api/v1/predictions/delay", json={"distance_band_km": -1}).status_code == 422
    )


def test_scenario_saving_revisit_and_export(client):
    response = client.post(
        "/api/v1/scenarios",
        json={
            "scenario_name": "Test pilot",
            "scenario_type": "dispatch_improvement",
            "percentage": 50,
            "hours_reduced": 2,
        },
    )
    assert response.status_code == 201
    run = response.json()
    assert run["assumptions"]["projection_only"]
    assert any(
        r["scenario_id"] == run["scenario_id"]
        for r in client.get("/api/v1/scenarios").json()["rows"]
    )
    assert b"Test pilot" in client.get("/api/v1/exports/scenarios").content


def test_import_auth_and_unknown_columns(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "test-key")
    assert (
        client.post(
            "/api/v1/imports?table=zones", files={"file": ("x.csv", "zone_id\nZ999")}
        ).status_code
        == 401
    )
    response = client.post(
        "/api/v1/imports?table=zones",
        headers={"X-Admin-Key": "test-key"},
        files={"file": ("x.csv", "customer_phone\n123")},
    )
    assert response.status_code == 422


def test_csv_staging_atomic_insert_and_audit(db):
    header = "zone_id,zone_code,city,region,latitude,longitude,serviceability_category,estimated_distance_band\n"
    good = "Z999,SYN-TEST,Test city,South,13,77,CORE,20\n"
    bad = "Z000,SYN-DUP,Test city,South,13,77,CORE,20\n"
    log = stage_import(db, "zones", (header + good + bad).encode(), "mixed.csv")
    assert log.records_accepted == 0 and log.records_rejected == 2 and db.get(Zone, "Z999") is None
    assert log.error_details
    accepted = stage_import(db, "zones", (header + good).encode(), "valid.csv")
    assert accepted.records_accepted == 1 and db.get(Zone, "Z999")


def test_invalid_data_rules():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    assert validate_record("inventory_batches", {"quantity_available": -1})
    assert validate_record("order_items", {"quantity_ordered": 1, "quantity_fulfilled": 2})
    assert validate_record("shipments", {"shipment_status": "DELIVERED", "delivered_at": now})
    assert validate_record("shipment_events", {"event_type": "UNKNOWN"})


def test_database_foreign_key_enforcement(db):
    try:
        with db.begin_nested():
            db.add(
                Shipment(
                    shipment_id="BAD",
                    order_id="missing-order",
                    delivery_partner_id="LP1",
                    delivery_attempt_count=0,
                    shipment_status="PENDING",
                    distance_band_km=10,
                    shipping_cost=0,
                    backlog_at_dispatch=0,
                    picking_hours=0,
                    packing_hours=0,
                )
            )
            db.flush()
    except IntegrityError:
        pass
    else:
        pytest.fail("Foreign-key violation was not rejected")


def test_csv_and_powerbi_exports_reconcile(client, db):
    response = client.get("/api/v1/exports/shipments?city=Chennai")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    df = pd.read_csv(io.BytesIO(response.content))
    assert set(df.city) == {"Chennai"}
    archive = zipfile.ZipFile(io.BytesIO(client.get("/api/v1/exports/powerbi").content))
    assert {
        "DimDate.csv",
        "FactOrders.csv",
        "FactShipments.csv",
        "FactInventory.csv",
        "FactPredictions.csv",
        "FactScenarioRuns.csv",
    } <= set(archive.namelist())
    orders = pd.read_csv(archive.open("FactOrders.csv"))
    assert len(orders) == db.scalar(select(func.count()).select_from(Order))


def test_missing_event_defects_are_visible(client):
    report = client.get("/api/v1/data-quality").json()
    assert (
        next(r for r in report["checks"] if r["code"] == "missing_delivery_events")[
            "affected_records"
        ]
        > 0
    )
    assert (
        next(r for r in report["checks"] if r["code"] == "duplicate_orders")["affected_records"]
        == 0
    )
