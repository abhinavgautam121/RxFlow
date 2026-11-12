from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Zone(Base):
    __tablename__ = "zones"
    zone_id: Mapped[str] = mapped_column(String, primary_key=True)
    zone_code: Mapped[str] = mapped_column(String, unique=True)
    city: Mapped[str] = mapped_column(String, index=True)
    region: Mapped[str] = mapped_column(String)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    serviceability_category: Mapped[str] = mapped_column(String)
    estimated_distance_band: Mapped[float] = mapped_column(Float)


class FulfilmentCentre(Base):
    __tablename__ = "fulfilment_centres"
    fulfillment_center_id: Mapped[str] = mapped_column(String, primary_key=True)
    center_name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    operational_status: Mapped[str] = mapped_column(String, default="ACTIVE")
    capacity_per_day: Mapped[int] = mapped_column(Integer)
    current_backlog: Mapped[int] = mapped_column(Integer)


class DeliveryPartner(Base):
    __tablename__ = "delivery_partners"
    delivery_partner_id: Mapped[str] = mapped_column(String, primary_key=True)
    partner_name: Mapped[str] = mapped_column(String)
    service_type: Mapped[str] = mapped_column(String)
    operational_status: Mapped[str] = mapped_column(String, default="ACTIVE")
    contracted_cost_model: Mapped[str] = mapped_column(String)


class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String)
    supplier_lead_time_days: Mapped[int] = mapped_column(Integer)
    reliability_metric: Mapped[float] = mapped_column(Float)
    supplier_status: Mapped[str] = mapped_column(String, default="ACTIVE")


class Product(Base):
    __tablename__ = "products"
    sku_id: Mapped[str] = mapped_column(String, primary_key=True)
    sku_code: Mapped[str] = mapped_column(String, unique=True)
    product_name: Mapped[str] = mapped_column(String)
    product_category: Mapped[str] = mapped_column(String)
    unit_of_measure: Mapped[str] = mapped_column(String)
    storage_category: Mapped[str] = mapped_column(String)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_reference: Mapped[str] = mapped_column(String, unique=True)
    order_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    order_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promised_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promised_service_level: Mapped[str] = mapped_column(String)
    fulfillment_center_id: Mapped[str] = mapped_column(
        ForeignKey("fulfilment_centres.fulfillment_center_id"), index=True
    )
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"), index=True)
    order_status: Mapped[str] = mapped_column(String, index=True)
    order_value: Mapped[float] = mapped_column(Float)
    shipping_fee: Mapped[float] = mapped_column(Float)
    cancellation_reason: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("order_value >= 0"),)


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), index=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer)
    quantity_fulfilled: Mapped[int] = mapped_column(Integer)
    item_status: Mapped[str] = mapped_column(String)
    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0 AND quantity_fulfilled >= 0 AND quantity_fulfilled <= quantity_ordered"
        ),
    )


class Shipment(Base):
    __tablename__ = "shipments"
    shipment_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), unique=True)
    delivery_partner_id: Mapped[str] = mapped_column(
        ForeignKey("delivery_partners.delivery_partner_id"), index=True
    )
    dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivery_attempt_count: Mapped[int] = mapped_column(Integer)
    first_attempt_success: Mapped[bool | None] = mapped_column(Boolean)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipment_status: Mapped[str] = mapped_column(String, index=True)
    distance_band_km: Mapped[float] = mapped_column(Float)
    shipping_cost: Mapped[float] = mapped_column(Float)
    backlog_at_dispatch: Mapped[int] = mapped_column(Integer)
    picking_hours: Mapped[float] = mapped_column(Float)
    packing_hours: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        CheckConstraint(
            "shipping_cost >= 0 AND distance_band_km >= 0 AND delivery_attempt_count >= 0"
        ),
    )


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.shipment_id"), index=True)
    event_type: Mapped[str] = mapped_column(String)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_location: Mapped[str] = mapped_column(String)
    event_description: Mapped[str] = mapped_column(String)
    __table_args__ = (Index("ix_events_ship_time", "shipment_id", "event_timestamp"),)


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"
    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("products.sku_id"), index=True)
    fulfillment_center_id: Mapped[str] = mapped_column(
        ForeignKey("fulfilment_centres.fulfillment_center_id"), index=True
    )
    batch_number: Mapped[str] = mapped_column(String, unique=True)
    quantity_received: Mapped[int] = mapped_column(Integer)
    quantity_available: Mapped[int] = mapped_column(Integer)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    quarantined_quantity: Mapped[int] = mapped_column(Integer, default=0)
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    unit_cost: Mapped[float] = mapped_column(Float)
    batch_status: Mapped[str] = mapped_column(String)
    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0 AND quantity_received >= quantity_available AND reserved_quantity >= 0 AND quarantined_quantity >= 0 AND reserved_quantity + quarantined_quantity <= quantity_available AND unit_cost >= 0"
        ),
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    movement_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("inventory_batches.batch_id"))
    source_center_id: Mapped[str | None] = mapped_column(
        ForeignKey("fulfilment_centres.fulfillment_center_id")
    )
    destination_center_id: Mapped[str | None] = mapped_column(
        ForeignKey("fulfilment_centres.fulfillment_center_id")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[str] = mapped_column(String)
    movement_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("quantity > 0"),)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    prediction_id: Mapped[str] = mapped_column(String, primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.shipment_id"), index=True)
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delay_probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    feature_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("delay_probability >= 0 AND delay_probability <= 1"),)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    scenario_id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_name: Mapped[str] = mapped_column(String)
    scenario_type: Mapped[str] = mapped_column(String)
    baseline_metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    simulated_metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ImportLog(Base):
    __tablename__ = "import_logs"
    import_id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    import_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    records_processed: Mapped[int] = mapped_column(Integer)
    records_accepted: Mapped[int] = mapped_column(Integer)
    records_rejected: Mapped[int] = mapped_column(Integer)
    error_details: Mapped[list] = mapped_column(JSON)
    import_status: Mapped[str] = mapped_column(String)


class DatasetMeta(Base):
    __tablename__ = "dataset_meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


IMPORTABLE = {
    c.__tablename__: c
    for c in [
        Zone,
        FulfilmentCentre,
        DeliveryPartner,
        Supplier,
        Product,
        Order,
        OrderItem,
        Shipment,
        ShipmentEvent,
        InventoryBatch,
    ]
}
