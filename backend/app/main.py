import hmac
import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import analytics
from app.config import settings
from app.data import as_of, frame, records
from app.db import get_db
from app.exports import csv_bytes, powerbi_zip
from app.forecast import forecast
from app.inventory import inventory
from app.ml import feature_frame, load_model, predict
from app.models import (
    IMPORTABLE,
    DeliveryPartner,
    FulfilmentCentre,
    ImportLog,
    Product,
    ScenarioRun,
    Shipment,
    ShipmentEvent,
    Zone,
)
from app.quality import quality_report, stage_import, template
from app.schemas import PredictionRequest, ScenarioRequest
from app.simulation import simulate

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("rxflow")
app = FastAPI(
    title="RxFlow Operations Intelligence API",
    version="1.0.0",
    description="Fictional pharmacy operations. All dates UTC; UI display Asia/Kolkata. No clinical data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


@app.middleware("http")
async def request_log(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        json.dumps(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    )
    return response


def filters(
    city: str | None = Query(None, max_length=50),
    center: str | None = Query(None, max_length=30),
    partner: str | None = Query(None, max_length=30),
    zone: str | None = Query(None, max_length=30),
    start: date | None = None,
    end: date | None = None,
):
    if start and end and start > end:
        raise HTTPException(422, "Start date must not exceed end date")
    tz = ZoneInfo("Asia/Kolkata")
    return dict(
        city=city,
        center=center,
        partner=partner,
        zone=zone,
        start=datetime.combine(start, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
        if start
        else None,
        end=datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(
            timezone.utc
        )
        if end
        else None,
    )


def dump(instance):
    return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}


def admin(x_admin_key: str = Header("")):
    if not settings.admin_api_key:
        raise HTTPException(503, "Imports are disabled until ADMIN_API_KEY is configured")
    if not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(401, "Valid X-Admin-Key required")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/meta")
def meta(db: Session = Depends(get_db)):
    return {
        "as_of": as_of(db),
        "synthetic": True,
        "cities": list(db.scalars(select(Zone.city).distinct().order_by(Zone.city))),
        "centers": [dump(x) for x in db.scalars(select(FulfilmentCentre))],
        "partners": [dump(x) for x in db.scalars(select(DeliveryPartner))],
        "zones": [dump(x) for x in db.scalars(select(Zone))],
        "import_tables": list(IMPORTABLE),
        "timezone": "Asia/Kolkata",
        "data_scope": "Reproducible fictional Indian e-pharmacy operation; no affiliation with any company.",
    }


@app.get("/api/v1/overview")
def overview(f: dict = Depends(filters), db: Session = Depends(get_db)):
    df = frame(db, **f)
    inv = inventory(db, center=f["center"], city=f["city"])
    return {
        "as_of": as_of(db),
        "kpis": analytics.kpis(df, as_of(db)),
        "trends": analytics.trends(df),
        "cities": analytics.cohort(df, "city"),
        "centers": analytics.cohort(df, "fulfillment_center_id"),
        "recommendations": analytics.recommendations(df, inv["kpis"]),
    }


@app.get("/api/v1/delivery/kpis")
def delivery_kpis(f: dict = Depends(filters), db: Session = Depends(get_db)):
    return analytics.kpis(frame(db, **f), as_of(db))


@app.get("/api/v1/delivery/trends")
def delivery_trends(
    f: dict = Depends(filters),
    frequency: str = Query("D", pattern="^(D|W|M)$"),
    db: Session = Depends(get_db),
):
    return analytics.trends(frame(db, **f), frequency)


@app.get("/api/v1/delivery/analysis")
def delivery_analysis(f: dict = Depends(filters), db: Session = Depends(get_db)):
    df = frame(db, **f)
    events = pd.read_sql(
        select(
            ShipmentEvent.shipment_id,
            ShipmentEvent.event_type,
            ShipmentEvent.event_timestamp,
        ),
        db.connection(),
    )
    events = events[events.shipment_id.isin(df.shipment_id)]
    distribution = pd.cut(
        df.loc[df.eligible, "fulfilment_hours"],
        [0, 12, 24, 36, 48, 72, 1000],
        right=True,
    ).value_counts(sort=False)
    data = df.copy()
    data["day_of_week"] = data.order_created_at.dt.tz_convert("Asia/Kolkata").dt.day_name()
    data["order_hour"] = data.order_created_at.dt.tz_convert("Asia/Kolkata").dt.hour
    data["backlog_band"] = pd.cut(
        data.backlog_at_dispatch,
        [0, 25, 50, 10000],
        labels=["0–25", "26–50", "51+"],
        include_lowest=True,
    ).astype(str)
    return {
        "kpis": analytics.kpis(df, as_of(db)),
        "lifecycle": analytics.lifecycle(df, events),
        "status": [
            {"status": str(k), "orders": int(v)}
            for k, v in df.shipment_status.value_counts().items()
        ],
        "distribution": [{"band": str(k), "orders": int(v)} for k, v in distribution.items()],
        "by_day": analytics.cohort(data, "day_of_week"),
        "by_hour": analytics.cohort(data, "order_hour"),
        "by_backlog": analytics.cohort(data, "backlog_band"),
        "by_distance": analytics.cohort(data, "distance_band_km"),
        "note": "Stage means use available valid event pairs with separate sample sizes; stage means need not sum to the mean total. Cohort differences are associations.",
    }


@app.get("/api/v1/orders")
@app.get("/api/v1/shipments")
def shipments(
    f: dict = Depends(filters),
    status: str | None = None,
    search: str = Query("", max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    df = frame(db, **f)
    if status == "OVERDUE":
        df = df[
            df.shipment_status.isin(["PENDING", "IN_TRANSIT"])
            & df.valid_promise
            & (df.promised_delivery_at < as_of(db))
        ]
    elif status:
        df = df[df.shipment_status == status]
    if search:
        df = df[
            df.order_id.str.contains(search, regex=False, case=False)
            | df.shipment_id.fillna("").str.contains(search, regex=False, case=False)
        ]
    return {
        "total": len(df),
        "page": page,
        "page_size": page_size,
        "rows": records(
            df.sort_values("order_created_at", ascending=False).iloc[
                (page - 1) * page_size : page * page_size
            ]
        ),
    }


@app.get("/api/v1/shipments/{shipment_id}")
def shipment_detail(shipment_id: str, db: Session = Depends(get_db)):
    shipment = db.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    return {
        "shipment": dump(shipment),
        "events": [
            dump(x)
            for x in db.scalars(
                select(ShipmentEvent)
                .where(ShipmentEvent.shipment_id == shipment_id)
                .order_by(ShipmentEvent.event_timestamp)
            )
        ],
    }


@app.get("/api/v1/zones")
def zones(
    f: dict = Depends(filters),
    volume: float = Query(0.2, ge=0, le=1),
    delay: float = Query(0.3, ge=0, le=1),
    impact: float = Query(0.2, ge=0, le=1),
    gap: float = Query(0.2, ge=0, le=1),
    feasibility: float = Query(0.1, ge=0, le=1),
    db: Session = Depends(get_db),
):
    weights = [volume, delay, impact, gap, feasibility]
    if sum(weights) <= 0:
        raise HTTPException(422, "At least one positive weight required")
    return {
        "rows": analytics.cohort(frame(db, **f), "zone_id", weights),
        "weights": weights,
        "note": "Opportunity score is a weighted average of volume, delay, late-order impact, SLA gap to 95%, and inverse-distance feasibility. All components are visible; this is a prioritisation heuristic.",
    }


@app.get("/api/v1/zones/{zone_id}/performance")
def zone_detail(zone_id: str, f: dict = Depends(filters), db: Session = Depends(get_db)):
    if not db.get(Zone, zone_id):
        raise HTTPException(404, "Zone not found")
    f["zone"] = zone_id
    data = frame(db, **f)
    return {
        "kpis": analytics.kpis(data, as_of(db)),
        "trends": analytics.trends(data),
        "partners": analytics.cohort(data, "delivery_partner_id"),
    }


@app.get("/api/v1/partners")
def partners(
    f: dict = Depends(filters),
    reliability: float = Query(0.45, ge=0, le=1),
    speed: float = Query(0.2, ge=0, le=1),
    first: float = Query(0.2, ge=0, le=1),
    cost: float = Query(0.15, ge=0, le=1),
    db: Session = Depends(get_db),
):
    weights = [reliability, speed, first, cost]
    if sum(weights) <= 0:
        raise HTTPException(422, "At least one positive weight required")
    return analytics.partner_scores(frame(db, **f), weights)


@app.get("/api/v1/partners/{partner_id}/scorecard")
def partner_detail(partner_id: str, f: dict = Depends(filters), db: Session = Depends(get_db)):
    if not db.get(DeliveryPartner, partner_id):
        raise HTTPException(404, "Partner not found")
    f["partner"] = partner_id
    df = frame(db, **f)
    return {
        "kpis": analytics.kpis(df, as_of(db)),
        "trends": analytics.trends(df),
        "zones": analytics.cohort(df, "zone_id"),
    }


@app.get("/api/v1/inventory/overview")
@app.get("/api/v1/inventory/risks")
@app.get("/api/v1/inventory/replenishment")
def inventory_overview(
    f: dict = Depends(filters),
    window: int = Query(30, ge=7, le=90),
    safety_stock: int = Query(20, ge=0, le=10000),
    target_days: int = Query(21, ge=1, le=180),
    lead_time: int | None = Query(None, ge=1, le=90),
    minimum: int = Query(10, ge=1, le=10000),
    pack_size: int = Query(10, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return inventory(
        db,
        center=f["center"],
        city=f["city"],
        window=window,
        safety_stock=safety_stock,
        target_days=target_days,
        lead_time=lead_time,
        minimum=minimum,
        pack_size=pack_size,
    )


@app.get("/api/v1/models/performance")
def model_performance():
    try:
        return load_model()["report"]
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/v1/predictions/delay")
def prediction(request: PredictionRequest, db: Session = Depends(get_db)):
    for model, identifier in [
        (Zone, request.zone_id),
        (FulfilmentCentre, request.fulfillment_center_id),
        (DeliveryPartner, request.delivery_partner_id),
    ]:
        if not db.get(model, identifier):
            raise HTTPException(422, "Unknown zone, centre or partner")
    try:
        return predict(
            request.model_dump(exclude={"low_threshold", "high_threshold"}),
            request.low_threshold,
            request.high_threshold,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/predictions/high-risk")
def high_risk(
    f: dict = Depends(filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        bundle = load_model()
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    df = frame(db, **f)
    df = df[df.shipment_status.eq("IN_TRANSIT") & df.dispatch_at.notna() & df.valid_promise].copy()
    if df.empty:
        return {
            "total": 0,
            "rows": [],
            "note": "Only shipments already dispatched are scored",
        }
    df["delay_probability"] = bundle["pipeline"].predict_proba(feature_frame(df))[:, 1]
    df["risk_level"] = df.delay_probability.map(
        lambda x: "HIGH" if x >= 0.6 else "MEDIUM" if x >= 0.3 else "LOW"
    )
    df["model_version"] = bundle["report"]["version"]
    return {
        "total": len(df),
        "rows": records(
            df.sort_values("delay_probability", ascending=False).iloc[
                (page - 1) * page_size : page * page_size
            ]
        ),
        "note": "Dispatch-time model estimates; thresholds 0.3 and 0.6 are illustrative",
    }


@app.get("/api/v1/forecast")
def demand_forecast(
    f: dict = Depends(filters),
    category: str | None = None,
    horizon: int = Query(14, ge=1, le=60),
    db: Session = Depends(get_db),
):
    df = frame(db, **f)
    if category:
        from app.models import OrderItem

        ids = list(
            db.scalars(
                select(OrderItem.order_id)
                .join(Product)
                .where(Product.product_category == category)
                .distinct()
            )
        )
        df = df[df.order_id.isin(ids)]
    return forecast(df, horizon)


@app.post("/api/v1/scenarios", status_code=201)
def create_scenario(
    request: ScenarioRequest, f: dict = Depends(filters), db: Session = Depends(get_db)
):
    df = frame(db, **f)
    inv = (
        inventory(db, center=f["center"], city=f["city"])
        if request.scenario_type == "inventory_replenishment"
        else None
    )
    capacities = {
        c.fulfillment_center_id: c.capacity_per_day for c in db.scalars(select(FulfilmentCentre))
    }
    try:
        output = simulate(df, request.model_dump(), as_of(db), inv, capacities)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    output["assumptions"]["filters"] = {k: str(v) if v is not None else None for k, v in f.items()}
    output["assumptions"]["as_of"] = as_of(db).isoformat()
    scenario = ScenarioRun(
        scenario_id=str(uuid.uuid4()),
        scenario_name=request.scenario_name,
        scenario_type=request.scenario_type,
        created_at=datetime.now(timezone.utc),
        **output,
    )
    db.add(scenario)
    db.commit()
    return dump(scenario)


@app.get("/api/v1/scenarios")
def scenarios(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {
        "total": db.scalar(select(func.count()).select_from(ScenarioRun)),
        "rows": [
            dump(x)
            for x in db.scalars(
                select(ScenarioRun)
                .order_by(ScenarioRun.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ],
    }


@app.get("/api/v1/data-quality")
def quality(db: Session = Depends(get_db)):
    return quality_report(db)


@app.post("/api/v1/imports", dependencies=[Depends(admin)])
async def imports(table: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return dump(
            stage_import(
                db,
                table,
                await file.read(5 * 1024 * 1024 + 1),
                file.filename or "upload.csv",
            )
        )
    except ValueError as exc:
        log = ImportLog(
            import_id=str(uuid.uuid4()),
            filename=(file.filename or "upload.csv")[:255],
            source=f"CSV:{table}:INSERT_ONLY",
            import_date=datetime.now(timezone.utc),
            records_processed=0,
            records_accepted=0,
            records_rejected=0,
            error_details=[{"row": 0, "errors": [str(exc)]}],
            import_status="SCHEMA_REJECTED",
        )
        db.add(log)
        db.commit()
        raise HTTPException(422, f"{exc}; audit ID: {log.import_id}") from exc


@app.get("/api/v1/imports")
def import_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {
        "total": db.scalar(select(func.count()).select_from(ImportLog)),
        "rows": [
            dump(x)
            for x in db.scalars(
                select(ImportLog)
                .order_by(ImportLog.import_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ],
    }


@app.get("/api/v1/imports/{import_id}")
def import_detail(import_id: str, db: Session = Depends(get_db)):
    log = db.get(ImportLog, import_id)
    if not log:
        raise HTTPException(404, "Import not found")
    return dump(log)


@app.get("/api/v1/templates/{table}")
def csv_template(table: str):
    if table not in IMPORTABLE:
        raise HTTPException(404, "Unknown template")
    return Response(
        template(table),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}_template.csv"'},
    )


@app.get("/api/v1/exports/{dataset}")
def export(dataset: str, f: dict = Depends(filters), db: Session = Depends(get_db)):
    if dataset == "powerbi":
        return Response(
            powerbi_zip(db),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="rxflow-powerbi.zip"'},
        )
    if dataset == "shipments":
        df = frame(db, **f)
    elif dataset == "quality":
        df = pd.DataFrame(quality_report(db)["checks"])
    elif dataset == "inventory":
        df = pd.DataFrame(inventory(db, center=f["center"], city=f["city"])["rows"])
    elif dataset == "scenarios":
        df = pd.read_sql(select(ScenarioRun), db.connection())
    else:
        raise HTTPException(404, "Unknown export")
    return Response(
        csv_bytes(df),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="rxflow-{dataset}.csv"'},
    )
