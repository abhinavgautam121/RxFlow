from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ScenarioRequest(BaseModel):
    scenario_name: str = Field(default="Operations pilot", min_length=1, max_length=100)
    scenario_type: Literal[
        "partner_allocation",
        "dispatch_improvement",
        "zone_pilot",
        "inventory_replenishment",
        "center_capacity",
    ]
    percentage: float = Field(default=20, ge=0, le=100)
    hours_reduced: float = Field(default=2, ge=0, le=24)
    source_partner: str = Field(default="LP4", max_length=30)
    target_partner: str = Field(default="LP1", max_length=30)
    zone_id: str = Field(default="Z000", max_length=30)
    center_id: str = Field(default="FC1", max_length=30)
    stock_multiplier: float = Field(default=1.2, ge=0, le=5)
    capacity_multiplier: float = Field(default=1.2, gt=0, le=5)
    lead_time_days: int = Field(default=7, ge=1, le=90)
    safety_stock: int = Field(default=20, ge=0, le=10000)
    target_days: int = Field(default=21, ge=1, le=180)


class PredictionRequest(BaseModel):
    zone_id: str = Field(default="Z000", max_length=30)
    fulfillment_center_id: str = Field(default="FC1", max_length=30)
    delivery_partner_id: str = Field(default="LP1", max_length=30)
    promised_service_level: Literal["SDD", "NDD", "OTHER"] = "NDD"
    distance_band_km: float = Field(default=25, ge=0, le=500)
    order_to_dispatch_hours: float = Field(default=5, ge=0, le=240)
    picking_hours: float = Field(default=2, ge=0, le=120)
    packing_hours: float = Field(default=1, ge=0, le=120)
    backlog_at_dispatch: int = Field(default=30, ge=0, le=10000)
    order_hour: int = Field(default=10, ge=0, le=23)
    order_weekday: int = Field(default=1, ge=0, le=6)
    remaining_promise_hours: float = Field(default=25, ge=-240, le=240)
    low_threshold: float = Field(default=0.3, ge=0, lt=1)
    high_threshold: float = Field(default=0.6, gt=0, le=1)

    @model_validator(mode="after")
    def check_consistency(self):
        if self.low_threshold >= self.high_threshold:
            raise ValueError("Low threshold must be below high threshold")
        if self.picking_hours + self.packing_hours > self.order_to_dispatch_hours:
            raise ValueError("Picking + packing cannot exceed processing time")
        return self
