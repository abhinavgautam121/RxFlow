"""Deterministic fictional operations with coherent geography, queues and lead times."""

import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, insert, select

from app.db import SessionLocal
from app.models import (
    DatasetMeta,
    DeliveryPartner,
    FulfilmentCentre,
    InventoryBatch,
    InventoryMovement,
    Order,
    OrderItem,
    Product,
    Shipment,
    ShipmentEvent,
    Supplier,
    Zone,
)

AS_OF = datetime(2026, 11, 12, tzinfo=timezone.utc)
CITIES = [
    ("Bengaluru", 12.97, 77.59, "South"),
    ("Delhi NCR", 28.61, 77.21, "North"),
    ("Mumbai", 19.08, 72.88, "West"),
    ("Hyderabad", 17.39, 78.49, "South"),
    ("Chennai", 13.08, 80.27, "South"),
    ("Pune", 18.52, 73.86, "West"),
    ("Kolkata", 22.57, 88.36, "East"),
    ("Jaipur", 26.91, 75.79, "North"),
]


def generate(n: int = 30000, seed: int = 42, days: int = 180) -> dict:
    if n < 100 or days < 60:
        raise ValueError("Use at least 100 orders and 60 days of history")
    rng = np.random.default_rng(seed)
    zones = []
    for z in range(120):
        city, lat, lon, region = CITIES[z // 15]
        zones.append(
            dict(
                zone_id=f"Z{z:03}",
                zone_code=f"SYN-{z:05}",
                city=city,
                region=region,
                latitude=round(lat + rng.normal(0, 0.12), 5),
                longitude=round(lon + rng.normal(0, 0.12), 5),
                serviceability_category="EXTENDED" if z % 5 == 0 else "CORE",
                estimated_distance_band=float(10 + z % 5 * 15),
            )
        )
    centres = [
        dict(
            fulfillment_center_id=f"FC{i + 1}",
            center_name=f"Demo {CITIES[i][0]} Hub",
            city=CITIES[i][0],
            zone_id=f"Z{i * 15:03}",
            latitude=CITIES[i][1],
            longitude=CITIES[i][2],
            capacity_per_day=[90, 80, 70, 60, 60][i],
            current_backlog=[22, 48, 15, 62, 19][i],
        )
        for i in range(5)
    ]
    partners = [
        dict(
            delivery_partner_id=f"LP{i + 1}",
            partner_name=f"Fictional {name}",
            service_type="EXPRESS" if i < 3 else "STANDARD",
            contracted_cost_model="Illustrative INR / shipment",
            operational_status="ACTIVE",
        )
        for i, name in enumerate(
            [
                "SwiftLane",
                "ParcelGrid",
                "BlueRoute",
                "LastMile",
                "UrbanLink",
                "EastWing",
                "RelayX",
                "MedTransit",
            ]
        )
    ]
    suppliers = [
        dict(
            supplier_id=f"SUP{i:02}",
            supplier_name=f"Fictional Supplier {i + 1:02}",
            supplier_lead_time_days=int(rng.integers(3, 15)),
            reliability_metric=round(float(rng.uniform(0.8, 0.99)), 3),
            supplier_status="ACTIVE",
        )
        for i in range(30)
    ]
    products = [
        dict(
            sku_id=f"SKU{i:03}",
            sku_code=f"DEMO-{i:04}",
            product_name=f"Fictional Product {i + 1:03}",
            product_category=[
                "Wellness",
                "Chronic care",
                "Seasonal care",
                "Personal care",
                "Essentials",
            ][i % 5],
            unit_of_measure="pack",
            storage_category="AMBIENT",
            supplier_id=f"SUP{i % 30:02}",
        )
        for i in range(300)
    ]
    dates = [AS_OF - timedelta(days=i) for i in range(days)]
    weights = np.array(
        [
            1 + 0.18 * (d.weekday() in [0, 5]) + 0.12 * np.sin(d.timetuple().tm_yday / 20)
            for d in dates
        ]
    )
    weights /= weights.sum()
    orders, shipments, items, events = [], [], [], []
    for i in range(n):
        z = int(rng.integers(120))
        fc = int(rng.choice(5, p=[0.3, 0.24, 0.19, 0.15, 0.12]))
        lp = int(rng.integers(8))
        created = dates[int(rng.choice(days, p=weights))] - timedelta(
            hours=float(rng.uniform(0, 24))
        )
        confirm = created + timedelta(minutes=float(rng.uniform(2, 25)))
        backlog = int(rng.poisson([22, 48, 15, 62, 19][fc]))
        picking = float(rng.gamma(2, 0.55) + backlog * 0.028)
        packing = float(rng.uniform(0.2, 1.3))
        dispatch = confirm + timedelta(hours=picking + packing + float(rng.uniform(0.2, 2.5)))
        distance = float(zones[z]["estimated_distance_band"])
        sla = str(rng.choice(["SDD", "NDD", "OTHER"], p=[0.22, 0.6, 0.18]))
        promise = created + timedelta(hours={"SDD": 14, "NDD": 30, "OTHER": 48}[sla])
        transit = max(
            1.0,
            4
            + distance * 0.24
            + [0, 2, 4, 6, 3, 5, 1, 7][lp]
            + (8 if z % 5 == 0 else 0)
            + (5 if lp == 4 and z // 15 == 1 else 0)
            + float(rng.normal(0, 4)),
        )
        first = bool(rng.random() > 0.09 - (0.02 if lp < 3 else -0.03))
        transit += 0 if first else 14
        delivery = dispatch + timedelta(hours=transit)
        cancelled = bool(rng.random() < 0.045)
        failure = bool(rng.random() < 0.02)
        returned = bool(rng.random() < 0.012)
        status = (
            "CANCELLED"
            if cancelled
            else "PENDING"
            if dispatch > AS_OF
            else "IN_TRANSIT"
            if delivery > AS_OF
            else "FAILED"
            if failure
            else "RETURNED"
            if returned
            else "DELIVERED"
        )
        dispatch_val = None if status in ["CANCELLED", "PENDING"] else dispatch
        delivered_val = delivery if status == "DELIVERED" else None
        oid = f"ORD{i + 1:06}"
        sid = f"SHP{i + 1:06}"
        orders.append(
            dict(
                order_id=oid,
                order_reference=f"SYN-{i + 1:07}",
                order_created_at=created,
                order_confirmed_at=None if cancelled else confirm,
                promised_delivery_at=promise,
                promised_service_level=sla,
                fulfillment_center_id=f"FC{fc + 1}",
                zone_id=f"Z{z:03}",
                order_status=status,
                order_value=round(float(rng.uniform(120, 2200)), 2),
                shipping_fee=round(float(rng.uniform(0, 49)), 2),
                cancellation_reason="Synthetic availability issue" if cancelled else None,
                created_at=created,
            )
        )
        shipments.append(
            dict(
                shipment_id=sid,
                order_id=oid,
                delivery_partner_id=f"LP{lp + 1}",
                dispatch_at=dispatch_val,
                delivered_at=delivered_val,
                delivery_attempt_count=0
                if status in ["CANCELLED", "PENDING", "IN_TRANSIT"]
                else 1
                if first
                else 2,
                first_attempt_success=first
                if status in ["DELIVERED", "FAILED", "RETURNED"]
                else None,
                shipment_status=status,
                distance_band_km=distance,
                shipping_cost=round(25 + distance * 0.4 + lp * 2 + float(rng.uniform(0, 10)), 2)
                if dispatch_val
                else 0.0,
                backlog_at_dispatch=backlog,
                picking_hours=picking,
                packing_hours=packing,
            )
        )
        for j in range(1 + int(rng.random() < 0.5)):
            sku = int(rng.integers(300))
            if created.month in [7, 8, 9] and rng.random() < 0.35:
                sku = (sku // 5) * 5 + 2
            qty = int(rng.integers(1, 4))
            items.append(
                dict(
                    order_item_id=f"{oid}-{j}",
                    order_id=oid,
                    sku_id=f"SKU{sku:03}",
                    quantity_ordered=qty,
                    quantity_fulfilled=qty if status == "DELIVERED" else 0,
                    item_status="FULFILLED" if status == "DELIVERED" else status,
                )
            )
        timeline = [("ORDER_CREATED", created)]
        if not cancelled:
            timeline += [("ORDER_CONFIRMED", confirm)]
        if dispatch_val:
            timeline += [
                ("PICKING_COMPLETED", confirm + timedelta(hours=picking)),
                ("PACKED", confirm + timedelta(hours=picking + packing)),
                ("DISPATCHED", dispatch),
            ]
        if delivered_val:
            timeline += [
                ("OUT_FOR_DELIVERY", max(dispatch, delivery - timedelta(hours=2))),
                ("DELIVERY_ATTEMPTED", delivery),
            ]
            if rng.random() > 0.012:
                timeline += [("DELIVERED", delivery)]
        elif status in ["FAILED", "RETURNED"]:
            timeline += [
                (
                    "DELIVERY_FAILED" if failure else "RETURN_COMPLETED",
                    min(delivery, AS_OF),
                )
            ]
        for j, (kind, ts) in enumerate(timeline):
            events.append(
                dict(
                    event_id=f"{sid}-E{j}",
                    shipment_id=sid,
                    event_type=kind,
                    event_timestamp=ts,
                    event_location=f"Z{z:03}",
                    event_description="Fictional operational event",
                )
            )
    batches = []
    movements = []
    for i in range(1000):
        qty = int(rng.integers(0, 800))
        reserved = int(qty * 0.08)
        quarantine = int(qty * 0.025)
        expiry = AS_OF + timedelta(days=int(rng.integers(-20, 365)))
        rec = AS_OF - timedelta(days=int(rng.integers(30, 160)))
        batch = dict(
            batch_id=f"B{i:04}",
            sku_id=f"SKU{i % 300:03}",
            fulfillment_center_id=f"FC{i % 5 + 1}",
            batch_number=f"DEMO-BATCH-{i:05}",
            quantity_received=qty + 100,
            quantity_available=qty,
            reserved_quantity=reserved,
            quarantined_quantity=quarantine,
            received_date=rec,
            expiry_date=expiry,
            unit_cost=round(float(rng.uniform(10, 180)), 2),
            batch_status="QUARANTINED" if i % 53 == 0 else "ACTIVE",
        )
        batches.append(batch)
        movements.append(
            dict(
                movement_id=f"M{i:04}",
                batch_id=batch["batch_id"],
                source_center_id=None,
                destination_center_id=batch["fulfillment_center_id"],
                quantity=qty + 100,
                movement_type="RECEIPT",
                movement_timestamp=rec,
            )
        )
    return {
        Zone: zones,
        FulfilmentCentre: centres,
        DeliveryPartner: partners,
        Supplier: suppliers,
        Product: products,
        Order: orders,
        Shipment: shipments,
        OrderItem: items,
        ShipmentEvent: events,
        InventoryBatch: batches,
        InventoryMovement: movements,
    }


def seed_database(n: int = 30000, seed: int = 42, days: int = 180):
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Order)):
            raise ValueError(
                "Database already contains orders; seed never overwrites existing data"
            )
        for model, records in generate(n, seed, days).items():
            for offset in range(0, len(records), 2000):
                db.execute(insert(model.__table__), records[offset : offset + 2000])
        db.add_all(
            [
                DatasetMeta(key="as_of", value=AS_OF.isoformat()),
                DatasetMeta(key="seed", value=str(seed)),
                DatasetMeta(key="synthetic", value="true"),
            ]
        )
        db.commit()
    print(f"Seeded {n:,} fictional orders with seed={seed}; snapshot={AS_OF.isoformat()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=30000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=180)
    args = parser.parse_args()
    seed_database(args.orders, args.seed, args.days)
