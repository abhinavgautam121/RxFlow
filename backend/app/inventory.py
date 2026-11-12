"""Stock eligibility and illustrative replenishment; no stock movement writes."""

import math

import pandas as pd
from sqlalchemy import select

from app.data import as_of, records
from app.models import InventoryBatch, Order, OrderItem, Product, Supplier


def available_stock(on_hand: int, reserved: int, quarantined: int, eligible=True) -> int:
    return max(0, on_hand - reserved - quarantined) if eligible else 0


def days_cover(stock: float, demand: float):
    return round(stock / demand, 2) if demand > 0 else None


def replenishment(
    demand, lead_time, safety_stock, available, target_days=21, minimum=10, pack_size=10
):
    point = demand * lead_time + safety_stock
    need = max(0, demand * target_days + safety_stock - available) if available < point else 0
    qty = math.ceil(max(need, minimum) / pack_size) * pack_size if need > 0 else 0
    return {"reorder_point": round(point, 2), "suggested_quantity": qty}


def inventory(
    db,
    center=None,
    window=30,
    safety_stock=20,
    target_days=21,
    lead_time=None,
    minimum=10,
    pack_size=10,
    city=None,
):
    now = as_of(db)
    batches = pd.read_sql(select(InventoryBatch), db.connection())
    if center:
        batches = batches[batches.fulfillment_center_id == center]
    if city:
        from app.models import FulfilmentCentre

        centers = list(
            db.scalars(
                select(FulfilmentCentre.fulfillment_center_id).where(FulfilmentCentre.city == city)
            )
        )
        batches = batches[batches.fulfillment_center_id.isin(centers)]
    for col in ["received_date", "expiry_date"]:
        batches[col] = pd.to_datetime(batches[col], utc=True)
    batches["days_to_expiry"] = (batches.expiry_date - now).dt.total_seconds() / 86400
    batches["age_days"] = (now - batches.received_date).dt.days
    batches["sellable_units"] = [
        available_stock(
            r.quantity_available,
            r.reserved_quantity,
            r.quarantined_quantity,
            r.expiry_date > now and r.batch_status == "ACTIVE" and r.received_date <= now,
        )
        for r in batches.itertuples()
    ]
    batches["value"] = batches.quantity_available * batches.unit_cost
    products = pd.read_sql(
        select(
            Product.sku_id,
            Product.product_name,
            Product.product_category,
            Supplier.supplier_lead_time_days,
        ).join(Supplier),
        db.connection(),
    )
    stmt = (
        select(OrderItem.sku_id, Order.fulfillment_center_id, OrderItem.quantity_ordered)
        .join(Order)
        .where(
            Order.order_created_at >= now - pd.Timedelta(days=window),
            Order.order_created_at <= now,
            Order.order_status != "CANCELLED",
        )
    )
    demand = (
        pd.read_sql(stmt, db.connection())
        .groupby(["sku_id", "fulfillment_center_id"])
        .quantity_ordered.sum()
        / window
    )
    grouped = batches.groupby(["sku_id", "fulfillment_center_id"]).agg(
        available=("sellable_units", "sum"),
        on_hand=("quantity_available", "sum"),
        reserved=("reserved_quantity", "sum"),
        quarantined=("quarantined_quantity", "sum"),
        inventory_value=("value", "sum"),
    )
    index = grouped.index.union(demand.index)
    if center:
        index = index[index.get_level_values("fulfillment_center_id") == center]
    if city:
        index = index[index.get_level_values("fulfillment_center_id").isin(centers)]
    health = grouped.reindex(index, fill_value=0)
    health["avg_daily_demand"] = demand.reindex(index, fill_value=0)
    health = health.reset_index().merge(products, on="sku_id", how="left")
    health["days_of_cover"] = [
        days_cover(s, d) for s, d in zip(health.available, health.avg_daily_demand)
    ]
    health["demand_status"] = health.avg_daily_demand.map(
        lambda d: "NO_DEMAND" if d == 0 else "LOW_SAMPLE" if d * window < 10 else "AVAILABLE"
    )
    health["stockout_risk"] = (health.avg_daily_demand > 0) & (
        health.available
        < health.avg_daily_demand
        * (lead_time if lead_time is not None else health.supplier_lead_time_days)
    )
    suggestions = [
        replenishment(
            r.avg_daily_demand,
            lead_time if lead_time is not None else r.supplier_lead_time_days,
            safety_stock,
            r.available,
            target_days,
            minimum,
            pack_size,
        )
        for r in health.itertuples()
    ]
    health["reorder_point"] = [s["reorder_point"] for s in suggestions]
    health["suggested_quantity"] = [s["suggested_quantity"] for s in suggestions]
    near = (batches.days_to_expiry > 0) & (batches.days_to_expiry <= 30)
    k = {
        "sku_count": int(health.sku_id.nunique()),
        "total_inventory_units": int(batches.quantity_available.sum()),
        "available_inventory": int(batches.sellable_units.sum()),
        "reserved_inventory": int(batches.reserved_quantity.sum()),
        "quarantined_inventory": int(batches.quarantined_quantity.sum()),
        "expired_units": int(batches.loc[batches.days_to_expiry <= 0, "quantity_available"].sum()),
        "near_expiry_units": int(batches.loc[near, "quantity_available"].sum()),
        "near_expiry_value": round(float(batches.loc[near, "value"].sum()), 2),
        "inventory_value": round(float(batches.value.sum()), 2),
        "stockout_risk_skus": int(health.loc[health.stockout_risk, "sku_id"].nunique()),
        "risk_sku_center_pairs": int(health.stockout_risk.sum()),
        "units_expiring_60": int(
            batches.loc[
                (batches.days_to_expiry > 0) & (batches.days_to_expiry <= 60),
                "quantity_available",
            ].sum()
        ),
        "units_expiring_90": int(
            batches.loc[
                (batches.days_to_expiry > 0) & (batches.days_to_expiry <= 90),
                "quantity_available",
            ].sum()
        ),
        "inventory_turnover_proxy": round(
            float(health.avg_daily_demand.sum() * window / max(1, batches.sellable_units.sum())),
            3,
        ),
    }
    health = health.sort_values(["stockout_risk", "available"], ascending=[False, True])
    fefo = (
        batches[batches.sellable_units > 0]
        .sort_values("expiry_date")
        .merge(products, on="sku_id", how="left")
    )
    expiry = (
        batches.groupby("fulfillment_center_id")
        .apply(
            lambda g: pd.Series(
                {
                    "expired": int(g.loc[g.days_to_expiry <= 0, "quantity_available"].sum()),
                    "within_30": int(
                        g.loc[
                            (g.days_to_expiry > 0) & (g.days_to_expiry <= 30),
                            "quantity_available",
                        ].sum()
                    ),
                    "within_90": int(
                        g.loc[
                            (g.days_to_expiry > 0) & (g.days_to_expiry <= 90),
                            "quantity_available",
                        ].sum()
                    ),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    return {
        "kpis": k,
        "rows": records(health),
        "fefo": records(fefo),
        "expiry": records(expiry),
        "assumptions": {
            "as_of": now.isoformat(),
            "demand_window_days": window,
            "target_days": target_days,
            "safety_stock_units": safety_stock,
            "minimum_order": minimum,
            "pack_size": pack_size,
            "lead_time_override": lead_time,
            "note": "Demand excludes cancelled orders. Null cover means zero demand. Reorder suggestions require procurement validation. Turnover uses period demand / snapshot sellable stock, not accounting COGS.",
        },
    }
