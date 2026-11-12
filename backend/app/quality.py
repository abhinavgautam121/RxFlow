"""CSV staging and quality checks. Inserts are atomic and never overwrite rows."""

import csv
import io
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import Boolean, DateTime, Float, Integer, select
from sqlalchemy.exc import IntegrityError

from app.data import as_of, frame
from app.models import (
    IMPORTABLE,
    ImportLog,
    InventoryBatch,
    Order,
    Product,
    Shipment,
    ShipmentEvent,
)

EVENT_ORDER = {
    "ORDER_CREATED": 0,
    "ORDER_CONFIRMED": 1,
    "PICKING_STARTED": 2,
    "PICKING_COMPLETED": 3,
    "PACKED": 4,
    "DISPATCHED": 5,
    "OUT_FOR_DELIVERY": 6,
    "DELIVERY_ATTEMPTED": 7,
    "DELIVERED": 8,
    "DELIVERY_FAILED": 8,
    "RETURN_INITIATED": 9,
    "RETURN_COMPLETED": 10,
}


def validate_record(table, row):
    errors = []

    def error(message):
        errors.append(message)

    for col, value in row.items():
        if (
            isinstance(value, (int, float))
            and (
                col.startswith("quantity")
                or col
                in [
                    "shipping_cost",
                    "order_value",
                    "shipping_fee",
                    "distance_band_km",
                    "unit_cost",
                    "reserved_quantity",
                    "quarantined_quantity",
                    "picking_hours",
                    "packing_hours",
                    "backlog_at_dispatch",
                    "delivery_attempt_count",
                    "capacity_per_day",
                    "current_backlog",
                    "supplier_lead_time_days",
                ]
            )
            and value < 0
        ):
            error(f"{col} must be nonnegative")

    def ordered(a, b):
        if row.get(a) and row.get(b) and row[b] < row[a]:
            error(f"{b} precedes {a}")

    if table == "orders":
        ordered("order_created_at", "promised_delivery_at")
        ordered("order_created_at", "order_confirmed_at")
        if row.get("order_status") not in [
            "PENDING",
            "IN_TRANSIT",
            "DELIVERED",
            "CANCELLED",
            "FAILED",
            "RETURNED",
        ]:
            error("Invalid order_status")
        if row.get("promised_service_level") not in ["SDD", "NDD", "OTHER"]:
            error("Invalid service level")
    if table == "shipments":
        ordered("dispatch_at", "delivered_at")
        if row.get("shipment_status") not in [
            "PENDING",
            "IN_TRANSIT",
            "DELIVERED",
            "CANCELLED",
            "FAILED",
            "RETURNED",
        ]:
            error("Invalid shipment_status")
        if row.get("shipment_status") == "DELIVERED" and (
            not row.get("delivered_at") or not row.get("dispatch_at")
        ):
            error("Delivered shipment requires dispatch and delivery timestamps")
        if (
            row.get("delivered_at")
            and row.get("dispatch_at")
            and (row["delivered_at"] - row["dispatch_at"]).total_seconds() > 720 * 3600
        ):
            error("Delivery duration exceeds 720h")
    if table == "order_items" and (
        row.get("quantity_ordered", 0) <= 0
        or row.get("quantity_fulfilled", 0) > row.get("quantity_ordered", 0)
    ):
        error("Invalid item quantity")
    if table == "shipment_events" and row.get("event_type") not in EVENT_ORDER:
        error("Invalid event type")
    if table == "inventory_batches":
        ordered("received_date", "expiry_date")
        if row.get("quantity_available", 0) > row.get("quantity_received", 0):
            error("On hand exceeds received")
        if row.get("reserved_quantity", 0) + row.get("quarantined_quantity", 0) > row.get(
            "quantity_available", 0
        ):
            error("Reserved + quarantined exceeds on hand")
        if row.get("batch_status") not in ["ACTIVE", "QUARANTINED", "UNAVAILABLE"]:
            error("Invalid batch_status")
    return errors


def template(table):
    model = IMPORTABLE[table]
    output = io.StringIO()
    csv.writer(output).writerow([c.name for c in model.__table__.columns])
    return output.getvalue()


def stage_import(db, table, payload: bytes, filename: str):
    if table not in IMPORTABLE:
        raise ValueError("Unsupported table")
    if len(payload) > 5 * 1024 * 1024:
        raise ValueError("File exceeds 5 MiB")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Use a UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    model = IMPORTABLE[table]
    columns = {c.name: c for c in model.__table__.columns}
    errors = []
    staged = []
    seen = set()
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Missing or duplicate CSV headers")
    unknown = set(reader.fieldnames) - set(columns)
    if unknown:
        raise ValueError(
            "Unknown columns are rejected; do not upload personal or health information"
        )
    missing = [
        c.name
        for c in columns.values()
        if not c.nullable and c.default is None and c.name not in reader.fieldnames
    ]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    pk = next(iter(model.__table__.primary_key.columns)).name
    rows = list(reader)
    if not rows or len(rows) > 10000:
        raise ValueError("Use 1–10,000 records per import")
    for number, raw in enumerate(rows, 2):
        row = {}
        try:
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError("Column count does not match header")
            for name, value in raw.items():
                column = columns[name]
                if value == "":
                    if column.nullable:
                        row[name] = None
                        continue
                    if column.default is not None:
                        continue
                    raise ValueError(f"{name} cannot be empty")
                if isinstance(column.type, DateTime):
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError(f"{name} requires timezone")
                    row[name] = parsed.astimezone(timezone.utc)
                elif isinstance(column.type, Boolean):
                    if value.lower() not in ["true", "false", "0", "1"]:
                        raise ValueError(f"{name} requires true/false")
                    row[name] = value.lower() in ["true", "1"]
                elif isinstance(column.type, Integer):
                    row[name] = int(value)
                elif isinstance(column.type, Float):
                    import math

                    row[name] = float(value)
                    if not math.isfinite(row[name]):
                        raise ValueError(f"{name} must be finite")
                else:
                    row[name] = value
            row_errors = validate_record(table, row)
            identifier = row[pk]
            if identifier in seen or db.get(model, identifier):
                row_errors.append("Duplicate primary key; insert-only policy")
            seen.add(identifier)
            for c in model.__table__.columns:
                for fk in c.foreign_keys:
                    if row.get(c.name) is not None:
                        target = next(
                            m
                            for m in IMPORTABLE.values()
                            if m.__tablename__ == fk.column.table.name
                        )
                        if not db.get(target, row[c.name]):
                            row_errors.append(f"Missing foreign key: {c.name}")
            if table == "shipments" and row.get("order_id"):
                order = db.get(Order, row["order_id"])
                if (
                    order
                    and row.get("dispatch_at")
                    and row["dispatch_at"] < pd.Timestamp(order.order_created_at)
                ):
                    row_errors.append("Dispatch precedes order creation")
            if (
                table == "shipment_events"
                and row.get("shipment_id")
                and row.get("event_type") in EVENT_ORDER
            ):
                existing = list(
                    db.scalars(
                        select(ShipmentEvent).where(ShipmentEvent.shipment_id == row["shipment_id"])
                    )
                )
                for event in existing:
                    if (
                        EVENT_ORDER.get(event.event_type, -1) > EVENT_ORDER[row["event_type"]]
                        and pd.Timestamp(event.event_timestamp) < row["event_timestamp"]
                    ):
                        row_errors.append("Invalid event transition")
                    if (
                        EVENT_ORDER.get(event.event_type, -1) < EVENT_ORDER[row["event_type"]]
                        and pd.Timestamp(event.event_timestamp) > row["event_timestamp"]
                    ):
                        row_errors.append("Invalid event transition")
                for previous in staged:
                    if (
                        previous.get("shipment_id") == row["shipment_id"]
                        and previous.get("event_type") in EVENT_ORDER
                        and previous.get("event_timestamp")
                    ):
                        delta_rank = (
                            EVENT_ORDER[row["event_type"]] - EVENT_ORDER[previous["event_type"]]
                        )
                        delta_time = (
                            row["event_timestamp"] - previous["event_timestamp"]
                        ).total_seconds()
                        if delta_rank * delta_time < 0:
                            row_errors.append("Invalid staged event transition")
            if row_errors:
                errors.append({"row": number, "errors": row_errors})
            staged.append(row)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"row": number, "errors": [str(exc)]})
    accepted = 0
    if not errors:
        try:
            with db.begin_nested():
                db.add_all([model(**r) for r in staged])
                db.flush()
            accepted = len(staged)
        except IntegrityError:
            errors.append(
                {
                    "row": 0,
                    "errors": ["Database integrity constraint failed; entire import rolled back"],
                }
            )
    log = ImportLog(
        import_id=str(uuid.uuid4()),
        filename=filename[:255],
        source=f"CSV:{table}:INSERT_ONLY",
        import_date=datetime.now(timezone.utc),
        records_processed=len(rows),
        records_accepted=accepted,
        records_rejected=len(rows) - accepted,
        error_details=errors[:100],
        import_status="COMPLETED" if accepted else "REJECTED",
    )
    db.add(log)
    db.commit()
    return log


def quality_report(db):
    df = frame(db)
    now = as_of(db)
    shipments = pd.read_sql(select(Shipment), db.connection())
    events = pd.read_sql(select(ShipmentEvent), db.connection())
    batches = pd.read_sql(select(InventoryBatch), db.connection())
    checks = []

    def check(code, description, count, severity="Error", sample=None):
        checks.append(
            {
                "code": code,
                "description": description,
                "affected_records": int(count),
                "severity": severity,
                "sample": sample or [],
            }
        )

    check("duplicate_orders", "Duplicate order IDs", df.order_id.duplicated().sum())
    check(
        "duplicate_shipments",
        "Duplicate shipment IDs",
        shipments.shipment_id.duplicated().sum(),
    )
    check("missing_shipments", "Orders without a shipment", df.shipment_id.isna().sum())
    check(
        "invalid_promise",
        "Missing or invalid delivery promises",
        (~df.valid_promise).sum(),
    )
    check(
        "invalid_timestamps",
        "Dispatch before creation or delivery before dispatch",
        ((df.dispatch_at < df.order_created_at) | (df.delivered_at < df.dispatch_at)).sum(),
    )
    check(
        "impossible_duration",
        "Delivery duration exceeds 720 hours",
        (df.fulfilment_hours > 720).sum(),
    )
    delivered_ids = set(df.loc[df.shipment_status.eq("DELIVERED"), "shipment_id"])
    event_delivered = set(events.loc[events.event_type.eq("DELIVERED"), "shipment_id"])
    missing = sorted(delivered_ids - event_delivered)
    check(
        "missing_delivery_events",
        "Delivered shipments missing a DELIVERED event",
        len(missing),
        "Warning",
        missing[:10],
    )
    check(
        "missing_events",
        "Shipments without any events",
        len(set(shipments.shipment_id) - set(events.shipment_id)),
    )
    if len(events):
        events["ts"] = pd.to_datetime(events.event_timestamp, utc=True)
        events["rank"] = events.event_type.map(EVENT_ORDER)
        transitions = (
            events.sort_values(["shipment_id", "ts", "rank"]).groupby("shipment_id")["rank"].diff()
            < 0
        )
        check("invalid_transitions", "Event sequence moves backwards", transitions.sum())
    check(
        "negative_inventory",
        "Invalid inventory quantities",
        (
            (batches.quantity_available < 0)
            | (
                batches.reserved_quantity + batches.quarantined_quantity
                > batches.quantity_available
            )
        ).sum(),
    )
    check(
        "expired_inventory",
        "Expired batches excluded from sellable inventory",
        (pd.to_datetime(batches.expiry_date, utc=True) <= now).sum(),
        "Warning",
    )
    check(
        "missing_partner",
        "Missing logistics partner",
        df.delivery_partner_id.isna().sum(),
    )
    check(
        "missing_center",
        "Missing centre assignment",
        df.fulfillment_center_id.isna().sum(),
    )
    product_ids = set(db.scalars(select(Product.sku_id)))
    check(
        "missing_sku",
        "Batches with missing product metadata",
        (~batches.sku_id.isin(product_ids)).sum(),
    )
    total = len(df) + len(shipments) + len(events) + len(batches)
    return {
        "as_of": now.isoformat(),
        "total_records_scanned": total,
        "issue_occurrences": sum(c["affected_records"] for c in checks),
        "checks": checks,
        "note": "Issue counts can overlap and are not a count of distinct invalid rows. Database constraints reject duplicates, negative quantities and orphan keys. Missing events are intentionally injected in the synthetic dataset.",
    }
