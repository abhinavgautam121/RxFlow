"""Deterministic, explicit historical projections. Never execute operational actions."""

from app.analytics import kpis


def simulate(df, params, now, inventory=None, centers=None):
    baseline = kpis(df, now)
    e = df[df.eligible]
    total = len(e)
    if total == 0:
        raise ValueError("No eligible delivered shipments in selected cohort")
    base = {
        "on_time_rate": baseline["on_time"]["value"],
        "average_hours": baseline["avg_fulfilment_hours"],
        "delay_rate": 100 - baseline["on_time"]["value"],
        "shipping_cost": float(e.shipping_cost.sum()),
        "orders_affected": 0,
    }
    result = base.copy()
    assumptions = {
        "projection_only": True,
        "method": "Historical replay; projections are not measured improvements",
        "parameters": params,
    }
    kind = params["scenario_type"]
    fraction = params.get("percentage", 20) / 100
    if kind == "partner_allocation":
        source = params.get("source_partner", "LP4")
        target = params.get("target_partner", "LP1")
        if source == target:
            raise ValueError("Source and target partners must differ")
        from_rows = e[e.delivery_partner_id == source]
        to_rows = e[e.delivery_partner_id == target]
        affected = 0
        on_delta = 0.0
        hour_delta = 0.0
        cost_delta = 0.0
        for (zone, distance, sla), g in from_rows.groupby(
            ["zone_id", "distance_band_km", "promised_service_level"]
        ):
            comparison = to_rows[
                (to_rows.zone_id == zone)
                & (to_rows.distance_band_km == distance)
                & (to_rows.promised_service_level == sla)
            ]
            if len(comparison) < 5:
                continue
            shift = int(len(g) * fraction)
            affected += shift
            on_delta += shift * (g.late.mean() - comparison.late.mean())
            hour_delta += shift * (comparison.fulfilment_hours.mean() - g.fulfilment_hours.mean())
            cost_delta += shift * (comparison.shipping_cost.mean() - g.shipping_cost.mean())
        result.update(
            on_time_rate=base["on_time_rate"] + on_delta / total * 100,
            average_hours=base["average_hours"] + hour_delta / total,
            shipping_cost=base["shipping_cost"] + cost_delta,
            orders_affected=affected,
        )
        assumptions.update(
            comparable_cohort="Same zone, distance and SLA; target n≥5",
            capacity="Target daily capacity is unknown; projected shifts require capacity validation",
            unmatched_source_orders=int(len(from_rows) - affected / max(fraction, 0.0001)),
        )
    elif kind in ["dispatch_improvement", "zone_pilot"]:
        hours = params.get("hours_reduced", 2)
        eligible = (
            e if kind == "dispatch_improvement" else e[e.zone_id == params.get("zone_id", "Z000")]
        )
        count = int(len(eligible) * fraction)
        selected = eligible.sort_values("shipment_id").head(count)
        # Reduction cannot exceed elapsed pre-dispatch processing.
        reduction = selected.order_to_dispatch_hours.clip(upper=hours)
        import pandas as pd

        new_delivery = selected.delivered_at - pd.to_timedelta(reduction, unit="h")
        recovered = int(
            (new_delivery <= selected.promised_delivery_at).sum() - (~selected.late).sum()
        )
        result.update(
            on_time_rate=base["on_time_rate"] + recovered / total * 100,
            average_hours=base["average_hours"] - float(reduction.sum()) / total,
            orders_affected=count,
        )
        assumptions.update(
            assumption="Every hour removed before dispatch moves arrival earlier one-for-one; last-mile time is held constant",
            selection="Deterministic shipment ID order",
            risk="Delay rate is historical replay, not an ML probability or causal effect",
        )
    elif kind == "inventory_replenishment":
        if not inventory:
            raise ValueError("Inventory snapshot required")
        stock = inventory["kpis"]
        result["orders_affected"] = 0
        base.update(
            stockout_sku_center_pairs=stock["risk_sku_center_pairs"],
            sellable_units=stock["available_inventory"],
            inventory_holding_value=stock["inventory_value"],
        )
        multiplier = params.get("stock_multiplier", 1.2)
        lead = params.get("lead_time_days", 7)
        safety = params.get("safety_stock", 20)
        target = params.get("target_days", 21)
        rows = inventory["rows"]
        risk = sum(
            r["avg_daily_demand"] > 0
            and r["available"] * multiplier < r["avg_daily_demand"] * lead + safety
            for r in rows
        )
        base["stockout_sku_center_pairs"] = sum(
            r["avg_daily_demand"] > 0 and r["available"] < r["avg_daily_demand"] * lead + safety
            for r in rows
        )
        target_need = sum(
            max(0, r["avg_daily_demand"] * target + safety - r["available"] * multiplier)
            for r in rows
        )
        result.update(
            stockout_sku_center_pairs=risk,
            sellable_units=round(stock["available_inventory"] * multiplier),
            inventory_holding_value=round(stock["inventory_value"] * multiplier, 2),
            target_coverage_gap_units=round(target_need),
        )
        assumptions.update(
            assumption="Uniform stock scaling, constant demand and average unit costs; expiry timing held constant. Delivery KPIs are unchanged.",
            target_days=target,
            lead_time_days=lead,
            safety_stock=safety,
        )
    elif kind == "center_capacity":
        center = params.get("center_id", "FC1")
        g = df[df.fulfillment_center_id == center]
        if g.empty or not centers or center not in centers:
            raise ValueError("No centre data for selection")
        days = max(
            1,
            (g.order_created_at.max() - g.order_created_at.min()).total_seconds() / 86400,
        )
        daily = len(g) / days
        capacity = centers[center]
        multiplier = params.get("capacity_multiplier", 1.2)
        base.update(
            daily_capacity=capacity,
            daily_load=round(daily, 2),
            daily_overflow=round(max(0, daily - capacity), 2),
        )
        result.update(
            daily_capacity=round(capacity * multiplier, 2),
            daily_load=round(daily, 2),
            daily_overflow=round(max(0, daily - capacity * multiplier), 2),
            orders_affected=len(g),
        )
        assumptions.update(
            assumption="Uniform historical mean daily load; capacity is illustrative. Delivery KPI effects are not identified, so they remain unchanged."
        )
    else:
        raise ValueError("Unknown scenario")
    result["delay_rate"] = 100 - result["on_time_rate"]
    return {
        "baseline_metrics": base,
        "simulated_metrics": result,
        "assumptions": assumptions,
    }
