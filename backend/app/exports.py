import csv
import io
import zipfile

import pandas as pd
from sqlalchemy import select

from app.models import (
    DeliveryPartner,
    FulfilmentCentre,
    InventoryBatch,
    Order,
    Product,
    RiskPrediction,
    ScenarioRun,
    Shipment,
    ShipmentEvent,
    Zone,
)


def csv_bytes(df):
    safe = df.copy()
    for col in safe.select_dtypes(include=["object", "string"]).columns:
        safe[col] = safe[col].map(
            lambda v: "'" + v
            if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
            else v
        )
    return safe.to_csv(index=False, quoting=csv.QUOTE_MINIMAL).encode("utf-8-sig")


def powerbi_frames(db):
    mapping = {
        "DimZone": Zone,
        "DimFulfilmentCentre": FulfilmentCentre,
        "DimDeliveryPartner": DeliveryPartner,
        "DimSKU": Product,
        "FactOrders": Order,
        "FactShipments": Shipment,
        "FactShipmentEvents": ShipmentEvent,
        "FactInventory": InventoryBatch,
        "FactPredictions": RiskPrediction,
        "FactScenarioRuns": ScenarioRun,
    }
    frames = {name: pd.read_sql(select(model), db.connection()) for name, model in mapping.items()}
    orders = frames["FactOrders"]
    shipments = frames["FactShipments"]
    local = pd.to_datetime(orders.order_created_at, utc=True).dt.tz_convert("Asia/Kolkata")
    orders["DateKey"] = local.dt.strftime("%Y%m%d").astype(int)
    joined = shipments.merge(
        orders[
            [
                "order_id",
                "promised_delivery_at",
                "order_created_at",
                "DateKey",
                "zone_id",
                "fulfillment_center_id",
            ]
        ],
        on="order_id",
    )
    delivered = pd.to_datetime(joined.delivered_at, utc=True)
    promise = pd.to_datetime(joined.promised_delivery_at, utc=True)
    dispatch = pd.to_datetime(joined.dispatch_at, utc=True)
    created = pd.to_datetime(joined.order_created_at, utc=True)
    joined["EligibleDelivered"] = (
        joined.shipment_status.eq("DELIVERED")
        & delivered.notna()
        & promise.notna()
        & (promise >= created)
        & (delivered >= dispatch)
        & (dispatch >= created)
    )
    joined["OnTime"] = joined.EligibleDelivered & (delivered <= promise)
    joined["DeliveryHours"] = (delivered - created).dt.total_seconds() / 3600
    frames["FactShipments"] = joined
    inventory = frames["FactInventory"]
    from app.data import as_of

    now = as_of(db)
    expiry = pd.to_datetime(inventory.expiry_date, utc=True)
    received = pd.to_datetime(inventory.received_date, utc=True)
    inventory["SellableUnits"] = (
        (
            inventory.quantity_available
            - inventory.reserved_quantity
            - inventory.quarantined_quantity
        )
        .clip(lower=0)
        .where((expiry > now) & (received <= now) & inventory.batch_status.eq("ACTIVE"), 0)
    )
    inventory["NearExpiryValue"] = (inventory.quantity_available * inventory.unit_cost).where(
        (expiry > now) & (expiry <= now + pd.Timedelta(days=30)), 0
    )
    dates = pd.date_range(local.min().date(), local.max().date())
    frames["DimDate"] = pd.DataFrame(
        {
            "DateKey": dates.strftime("%Y%m%d").astype(int),
            "Date": dates.strftime("%Y-%m-%d"),
            "Year": dates.year,
            "Month": dates.month,
            "Weekday": dates.dayofweek,
        }
    )
    from app.inventory import inventory as health

    frames["FactInventoryHealth"] = pd.DataFrame(health(db)["rows"])
    return frames


def powerbi_zip(db):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, df in powerbi_frames(db).items():
            archive.writestr(name + ".csv", csv_bytes(df))
    return output.getvalue()


if __name__ == "__main__":
    from pathlib import Path

    from app.db import SessionLocal

    folder = Path("../powerbi/exports")
    folder.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        for name, df in powerbi_frames(db).items():
            (folder / (name + ".csv")).write_bytes(csv_bytes(df))
    print(f"Exported Power BI star schema to {folder.resolve()}")
