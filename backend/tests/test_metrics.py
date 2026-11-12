import pandas as pd
import pytest
from sqlalchemy import text

from app.analytics import kpis, lifecycle, partner_scores, ratio
from app.data import as_of, frame
from app.inventory import available_stock, days_cover, inventory, replenishment
from app.schemas import PredictionRequest
from app.simulation import simulate


def test_late_overdue_and_not_due_are_separate(metric_df):
    k = kpis(metric_df, pd.Timestamp("2026-11-12", tz="UTC"))
    assert k["on_time"] == {"value": 50.0, "numerator": 1, "denominator": 2}
    assert k["delayed_delivered_orders"] == 1
    assert k["currently_overdue"] == 1 and k["not_yet_due"] == 1
    assert k["cancellation_rate"]["value"] == 20
    assert k["first_attempt_success"]["value"] == 50
    assert k["avg_fulfilment_hours"] == 26 and k["avg_transit_hours"] == 24
    assert k["p90_delivery_hours"] == pytest.approx(27.6)
    assert k["cost_per_successful_delivery"] == 50


def test_empty_denominator_is_null(metric_df):
    assert ratio(0, 0)["value"] is None
    assert kpis(metric_df.iloc[:0], pd.Timestamp.now(tz="UTC"))["on_time"]["value"] is None


def test_invalid_promise_is_not_silently_counted(metric_df):
    metric_df.loc[0, "eligible"] = False
    k = kpis(metric_df, pd.Timestamp.now(tz="UTC"))
    assert k["excluded_delivered"] == 1 and k["on_time"]["denominator"] == 1


@pytest.mark.parametrize(
    "stock,reserved,quarantined,eligible,expected",
    [(100, 10, 5, True, 85), (10, 8, 5, True, 0), (100, 0, 0, False, 0)],
)
def test_stock_eligibility(stock, reserved, quarantined, eligible, expected):
    assert available_stock(stock, reserved, quarantined, eligible) == expected


def test_cover_reorder_pack_rounding():
    assert days_cover(100, 5) == 20
    assert days_cover(100, 0) is None
    assert replenishment(5, 7, 10, 20, target_days=21, minimum=10, pack_size=12) == {
        "reorder_point": 45,
        "suggested_quantity": 96,
    }
    assert replenishment(5, 7, 10, 100)["suggested_quantity"] == 0


def test_lifecycle_excludes_negative_durations(metric_df):
    events = pd.DataFrame(
        {
            "shipment_id": ["s1", "s1", "s2", "s2"],
            "event_type": ["PICKING_COMPLETED", "PACKED"] * 2,
            "event_timestamp": pd.to_datetime(
                ["2026-11-10T01:00Z", "2026-11-10T01:30Z", "2026-11-10T01:00Z", "2026-11-10T00:30Z"]
            ),
        }
    )
    packing = next(r for r in lifecycle(metric_df, events) if r["stage"] == "Packing")
    assert packing["hours"] == 0.5 and packing["excluded"] == 1


def test_database_kpis_reconcile_to_sql(db):
    k = kpis(frame(db), as_of(db))
    row = db.execute(
        text(
            "SELECT SUM(total_orders),SUM(eligible_delivered),SUM(on_time_orders),SUM(late_deliveries) FROM vw_daily_delivery_kpis"
        )
    ).one()
    assert k["total_orders"] == row[0] and k["on_time"]["denominator"] == row[1]
    assert k["on_time"]["numerator"] == row[2] and k["delayed_delivered_orders"] == row[3]
    sql = db.execute(
        text("SELECT AVG(delivery_hours) FROM vw_delivery_base WHERE eligible")
    ).scalar()
    assert k["avg_fulfilment_hours"] == round(float(sql), 2)


def test_inventory_sellable_reconciles_to_sql(db):
    inv = inventory(db)
    sql = db.execute(text("SELECT SUM(sellable_units) FROM vw_inventory_health")).scalar()
    assert inv["kpis"]["available_inventory"] == sql
    assert all(r["sellable_units"] > 0 and r["days_to_expiry"] > 0 for r in inv["fefo"])
    assert inv["fefo"] == sorted(inv["fefo"], key=lambda r: r["expiry_date"])


def test_partner_cohort_normalisation_and_weights(db):
    df = frame(db)
    a = partner_scores(df)
    b = partner_scores(df, [1, 0, 0, 0])
    assert a["shared_cohorts"] > 0
    assert all(r["score"] is None or 0 <= r["score"] <= 100 for r in a["rows"])
    assert all(
        r["score"] is None or r["score"] == round(r["components"]["reliability"], 1)
        for r in b["rows"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "partner_allocation",
        "dispatch_improvement",
        "zone_pilot",
        "inventory_replenishment",
        "center_capacity",
    ],
)
def test_scenarios_are_reproducible_and_bounded(db, kind):
    df = frame(db)
    inv = inventory(db) if kind == "inventory_replenishment" else None
    params = {"scenario_type": kind, "percentage": 50, "hours_reduced": 2, "center_id": "FC1"}
    result = simulate(df, params, as_of(db), inv, {"FC1": 90})
    assert result == simulate(df, params, as_of(db), inv, {"FC1": 90})
    assert 0 <= result["simulated_metrics"]["on_time_rate"] <= 100
    if kind in ["dispatch_improvement", "zone_pilot"]:
        assert (
            result["simulated_metrics"]["average_hours"]
            <= result["baseline_metrics"]["average_hours"]
        )
    if kind == "inventory_replenishment":
        assert (
            result["simulated_metrics"]["on_time_rate"]
            == result["baseline_metrics"]["on_time_rate"]
        )


def test_probability_request_consistency():
    with pytest.raises(ValueError):
        PredictionRequest(low_threshold=0.8, high_threshold=0.4)
    with pytest.raises(ValueError):
        PredictionRequest(order_to_dispatch_hours=1, picking_hours=2)
