"""Reusable operational metrics. All shares include explicit populations."""

import numpy as np
import pandas as pd


def ratio(n: int, d: int) -> dict:
    return {
        "value": round(100 * n / d, 2) if d else None,
        "numerator": int(n),
        "denominator": int(d),
    }


def avg(series: pd.Series):
    return round(float(series.mean()), 2) if series.notna().any() else None


def kpis(df: pd.DataFrame, now) -> dict:
    delivered = df[df.eligible]
    attempted = df[df.delivery_attempt_count.fillna(0) > 0]
    active = df.shipment_status.isin(["PENDING", "IN_TRANSIT"])
    overdue = active & df.valid_promise & (df.promised_delivery_at < now)
    return {
        "total_orders": len(df),
        "confirmed_orders": int(df.order_confirmed_at.notna().sum()),
        "dispatched_orders": int(df.dispatch_at.notna().sum()),
        "delivered_orders": int(df.shipment_status.eq("DELIVERED").sum()),
        "eligible_delivered": len(delivered),
        "excluded_delivered": int(df.shipment_status.eq("DELIVERED").sum() - len(delivered)),
        "pending_orders": int(active.sum()),
        "cancelled_orders": int(df.order_status.eq("CANCELLED").sum()),
        "delayed_delivered_orders": int(df.late.sum()),
        "currently_overdue": int(overdue.sum()),
        "not_yet_due": int((active & df.valid_promise & ~overdue).sum()),
        "active_invalid_promise": int((active & ~df.valid_promise).sum()),
        "on_time": ratio(int((~delivered.late).sum()), len(delivered)),
        "first_attempt_success": ratio(
            int(attempted.first_attempt_success.eq(True).sum()), len(attempted)
        ),
        "failed_first_attempts": int(attempted.first_attempt_success.eq(False).sum()),
        "cancellation_rate": ratio(int(df.order_status.eq("CANCELLED").sum()), len(df)),
        "delivery_failure_rate": ratio(
            int(df.shipment_status.eq("FAILED").sum()),
            int(df.dispatch_at.notna().sum()),
        ),
        "avg_order_to_dispatch_hours": avg(df.order_to_dispatch_hours),
        "avg_transit_hours": avg(delivered.transit_hours),
        "avg_fulfilment_hours": avg(delivered.fulfilment_hours),
        "median_delivery_hours": float(delivered.fulfilment_hours.median())
        if len(delivered)
        else None,
        "p90_delivery_hours": float(delivered.fulfilment_hours.quantile(0.9))
        if len(delivered)
        else None,
        "cost_per_successful_delivery": round(float(df.shipping_cost.sum() / len(delivered)), 2)
        if len(delivered)
        else None,
        "shipping_cost": round(float(df.shipping_cost.sum()), 2),
        "sla_mix": {
            level: ratio(int(df.promised_service_level.eq(level).sum()), len(df))
            for level in ["SDD", "NDD", "OTHER"]
        },
    }


def trends(df: pd.DataFrame, freq="D") -> list:
    if df.empty:
        return []
    data = df.copy()
    data["period"] = (
        data.order_created_at.dt.tz_convert("Asia/Kolkata")
        .dt.tz_localize(None)
        .dt.to_period(freq)
        .dt.start_time
    )
    output = []
    for period, g in data.groupby("period"):
        eligible = g[g.eligible]
        output.append(
            {
                "date": period.date().isoformat(),
                "orders": len(g),
                "on_time_rate": ratio(int((~eligible.late).sum()), len(eligible))["value"],
                "delayed": int(g.late.sum()),
                "first_attempt_success": ratio(
                    int(g.first_attempt_success.eq(True).sum()),
                    int((g.delivery_attempt_count > 0).sum()),
                )["value"],
            }
        )
    return output


def cohort(df: pd.DataFrame, key: str, weights=None) -> list:
    output = []
    for value, g in df.groupby(key):
        k = kpis(g, pd.Timestamp.now(tz="UTC"))
        e = g[g.eligible]
        r = {
            "id": str(value),
            "orders": len(g),
            "eligible": len(e),
            "delayed": int(g.late.sum()),
            "on_time_rate": k["on_time"]["value"],
            "avg_hours": k["avg_fulfilment_hours"],
            "median_hours": k["median_delivery_hours"],
            "p90_hours": k["p90_delivery_hours"],
            "first_attempt_success": k["first_attempt_success"]["value"],
            "failure_rate": k["delivery_failure_rate"]["value"],
            "cancellation_rate": k["cancellation_rate"]["value"],
            "return_rate": ratio(
                int(g.shipment_status.eq("RETURNED").sum()),
                int(g.dispatch_at.notna().sum()),
            )["value"],
            "cost_per_shipment": avg(g.loc[g.dispatch_at.notna(), "shipping_cost"]),
            "cost_per_successful_delivery": k["cost_per_successful_delivery"],
            "sdd_share": k["sla_mix"]["SDD"]["value"],
            "ndd_share": k["sla_mix"]["NDD"]["value"],
        }
        for col in [
            "city",
            "zone_code",
            "partner_name",
            "center_name",
            "latitude",
            "longitude",
            "distance_band_km",
        ]:
            r[col] = g.iloc[0][col] if col in g else None
        output.append(r)
    if key == "zone_id" and output:
        max_vol = max(r["orders"] for r in output)
        w = weights or [0.2, 0.3, 0.2, 0.2, 0.1]
        for r in output:
            delay = (100 - r["on_time_rate"]) if r["on_time_rate"] is not None else 0
            components = [
                100 * r["orders"] / max_vol,
                delay,
                100 * r["delayed"] / max(1, max(x["delayed"] for x in output)),
                max(0, 95 - (r["on_time_rate"] or 0)),
                100 * (1 - (r["distance_band_km"] or 0) / 100),
            ]
            r["score_components"] = dict(
                zip(["volume", "delay", "impact", "sla_gap", "feasibility"], components)
            )
            r["score"] = round(float(np.average(components, weights=w)), 1)
        output.sort(key=lambda r: r["score"], reverse=True)
    return output


def partner_scores(df: pd.DataFrame, weights=None) -> dict:
    """Direct standardisation on shared city × distance × service-level cohorts."""
    e = df[df.eligible].copy()
    e["cohort"] = e.city + " / " + e.distance_band_km.astype(str) + " / " + e.promised_service_level
    partners = sorted(e.delivery_partner_id.unique())
    counts = e.groupby(["cohort", "delivery_partner_id"]).size().unstack(fill_value=0)
    shared = counts.index[(counts >= 3).all(axis=1)] if len(partners) > 1 else counts.index
    pooled = e[e.cohort.isin(shared)].groupby("cohort").size()
    common_weights = pooled / pooled.sum() if len(pooled) else pooled
    raw = cohort(df, "delivery_partner_id")
    w = weights or [0.45, 0.2, 0.2, 0.15]
    for r in raw:
        g = e[(e.delivery_partner_id == r["id"]) & e.cohort.isin(shared)]
        r["matched_n"] = len(g)
        r["matched_share"] = round(len(g) / max(1, r["eligible"]) * 100, 1)
        if g.empty:
            r.update(score=None, components={}, adjusted_on_time=None)
            continue
        grouped = g.groupby("cohort")
        agg = grouped.agg(
            on_time=("late", lambda s: 100 * (1 - s.mean())),
            hours=("fulfilment_hours", "mean"),
            cost=("shipping_cost", "mean"),
            first=("first_attempt_success", lambda s: 100 * s.eq(True).mean()),
        )
        adjusted = agg.mul(common_weights, axis=0).sum()
        components = {
            "reliability": float(adjusted.on_time),
            "speed": float(np.clip(100 - adjusted.hours * 1.5, 0, 100)),
            "first_attempt": float(adjusted["first"]),
            "cost_efficiency": float(np.clip(100 - adjusted.cost, 0, 100)),
        }
        r.update(
            score=round(float(np.average(list(components.values()), weights=w)), 1),
            components=components,
            adjusted_on_time=round(float(adjusted.on_time), 2),
        )
    raw.sort(key=lambda r: r["score"] if r["score"] is not None else -1, reverse=True)
    return {
        "rows": raw,
        "weights": w,
        "shared_cohorts": len(shared),
        "warning": "Scores standardise shared city × distance × SLA cohorts with at least 3 deliveries per partner. Coverage may be small; raw KPIs have different operating mixes. Associations are not causal.",
    }


def lifecycle(df: pd.DataFrame, events: pd.DataFrame) -> list:
    if events.empty:
        return []
    pivot = events.pivot_table(
        index="shipment_id",
        columns="event_type",
        values="event_timestamp",
        aggfunc="min",
    )
    joined = df.set_index("shipment_id").join(pivot)
    stages = [
        ("Confirmation", "order_created_at", "order_confirmed_at"),
        ("Picking", "order_confirmed_at", "PICKING_COMPLETED"),
        ("Packing", "PICKING_COMPLETED", "PACKED"),
        ("Dispatch queue", "PACKED", "dispatch_at"),
        ("Last mile", "dispatch_at", "delivered_at"),
    ]
    result = []
    for name, a, b in stages:
        if a not in joined or b not in joined:
            continue
        duration = (
            pd.to_datetime(joined[b], utc=True) - pd.to_datetime(joined[a], utc=True)
        ).dt.total_seconds() / 3600
        valid = duration[(duration >= 0) & (duration <= 720)]
        result.append(
            {
                "stage": name,
                "hours": avg(valid),
                "sample_size": len(valid),
                "excluded": int(duration.notna().sum() - len(valid)),
            }
        )
    return result


def recommendations(df, inventory) -> list:
    output = []
    for r in cohort(df, "zone_id"):
        if r["eligible"] >= 30 and r["on_time_rate"] is not None and r["on_time_rate"] < 80:
            output.append(
                {
                    "priority": "High",
                    "problem": f"Investigate {r['zone_code']} · {r['city']}",
                    "evidence": f"{r['on_time_rate']}% on time across {r['eligible']} delivered orders; {r['delayed']} late",
                    "action": "Review comparable partner cohorts and dispatch stages; evaluate a zone pilot.",
                    "impact": "Delivery reliability",
                    "confidence": "Moderate: synthetic sample ≥30",
                    "limitations": "Associational evidence; no causal attribution.",
                }
            )
    if inventory.get("near_expiry_units", 0):
        output.insert(
            0,
            {
                "priority": "High",
                "problem": "Review batches approaching expiry",
                "evidence": f"{inventory['near_expiry_units']:,} units expire within 30 days",
                "action": "Review FEFO eligibility, allocation and demand before moving stock.",
                "impact": "Inventory exposure",
                "confidence": "High: recorded batch dates",
                "limitations": "Synthetic stock snapshot; no procurement action is executed.",
            },
        )
    return output[:8]
