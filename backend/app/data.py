from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DatasetMeta,
    DeliveryPartner,
    FulfilmentCentre,
    Order,
    Shipment,
    Zone,
)


def as_of(db: Session) -> datetime:
    meta = db.get(DatasetMeta, "as_of")
    return datetime.fromisoformat(meta.value) if meta else datetime.now(timezone.utc)


def frame(
    db: Session, city=None, center=None, start=None, end=None, partner=None, zone=None
) -> pd.DataFrame:
    stmt = (
        select(
            *Order.__table__.c,
            *[c for c in Shipment.__table__.c if c.name != "order_id"],
            Zone.city,
            Zone.zone_code,
            Zone.latitude,
            Zone.longitude,
            DeliveryPartner.partner_name,
            FulfilmentCentre.center_name,
        )
        .join(Shipment, Order.order_id == Shipment.order_id, isouter=True)
        .join(Zone, Order.zone_id == Zone.zone_id)
        .join(
            DeliveryPartner,
            Shipment.delivery_partner_id == DeliveryPartner.delivery_partner_id,
            isouter=True,
        )
        .join(
            FulfilmentCentre,
            Order.fulfillment_center_id == FulfilmentCentre.fulfillment_center_id,
        )
    )
    if city:
        stmt = stmt.where(Zone.city == city)
    if center:
        stmt = stmt.where(Order.fulfillment_center_id == center)
    if partner:
        stmt = stmt.where(Shipment.delivery_partner_id == partner)
    if zone:
        stmt = stmt.where(Order.zone_id == zone)
    if start:
        stmt = stmt.where(Order.order_created_at >= start)
    if end:
        stmt = stmt.where(Order.order_created_at < end)
    df = pd.read_sql(stmt, db.connection())
    for col in [
        "order_created_at",
        "order_confirmed_at",
        "promised_delivery_at",
        "dispatch_at",
        "delivered_at",
    ]:
        df[col] = pd.to_datetime(df[col], utc=True)
    df["order_to_dispatch_hours"] = (df.dispatch_at - df.order_created_at).dt.total_seconds() / 3600
    df["transit_hours"] = (df.delivered_at - df.dispatch_at).dt.total_seconds() / 3600
    df["fulfilment_hours"] = (df.delivered_at - df.order_created_at).dt.total_seconds() / 3600
    df["valid_promise"] = df.promised_delivery_at.notna() & (
        df.promised_delivery_at >= df.order_created_at
    )
    df["eligible"] = (
        df.shipment_status.eq("DELIVERED")
        & df.delivered_at.notna()
        & df.dispatch_at.notna()
        & df.valid_promise
        & (df.delivered_at >= df.dispatch_at)
        & (df.dispatch_at >= df.order_created_at)
    )
    df["late"] = df.eligible & (df.delivered_at > df.promised_delivery_at)
    return df


def records(df: pd.DataFrame) -> list[dict]:
    """JSON-safe records, replacing NaN/NaT rather than emitting non-standard JSON."""
    import json

    return json.loads(df.to_json(orient="records", date_format="iso"))
