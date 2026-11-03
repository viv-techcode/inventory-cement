"""Validated request bodies for the HTTP API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inventory_app.inventory import local_today


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SiteCreate(InputModel):
    identifier: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    project_type: str | None = Field(default=None, max_length=60)
    notes: str | None = None


class SiteUpdate(InputModel):
    identifier: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    project_type: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None
    notes: str | None = None


class MaterialCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=40)
    default_lead_time_days: int | None = Field(default=None, ge=1, le=365)
    safety_stock_days: int = Field(default=7, ge=0, le=90)
    minimum_order_qty: Decimal = Field(default=Decimal("0"), ge=0)
    order_multiple: Decimal = Field(default=Decimal("0"), ge=0)
    maximum_stock_qty: Decimal | None = Field(default=None, ge=0)
    benchmark_unit_price_inr: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class MaterialUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    is_active: bool | None = None
    default_lead_time_days: int | None = Field(default=None, ge=1, le=365)
    safety_stock_days: int | None = Field(default=None, ge=0, le=90)
    minimum_order_qty: Decimal | None = Field(default=None, ge=0)
    order_multiple: Decimal | None = Field(default=None, ge=0)
    maximum_stock_qty: Decimal | None = Field(default=None, ge=0)
    benchmark_unit_price_inr: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class CustomerCreate(InputModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=60)
    notes: str | None = None


class CustomerUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None
    notes: str | None = None


TransactionKind = Literal["opening_balance", "receipt", "consumption", "adjustment"]


class InventoryTransactionCreate(InputModel):
    idempotency_key: str = Field(min_length=1, max_length=120)
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    transaction_type: TransactionKind
    quantity: Decimal
    unit: str = Field(min_length=1, max_length=40)
    transaction_date: date
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    reason: str | None = None
    unit_cost_inr: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_transaction(self):
        if self.transaction_type == "adjustment":
            if self.quantity == 0:
                raise ValueError("Adjustment quantity must be non-zero.")
            if not (self.reason or "").strip():
                raise ValueError("A reason is required for every stock adjustment.")
            if self.quantity < 0 and self.unit_cost_inr is not None:
                raise ValueError("A negative adjustment cannot carry an inbound unit cost.")
        elif self.quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if self.transaction_type == "consumption" and self.unit_cost_inr is not None:
            raise ValueError("Use the Sales page to record a priced sale; ordinary consumption cannot set a cost.")
        if self.transaction_date > local_today():
            raise ValueError("Inventory transactions cannot be dated in the future.")
        return self


class SaleCreate(InputModel):
    idempotency_key: str = Field(min_length=1, max_length=110)
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    unit_sale_price_inr: Decimal = Field(ge=0)
    sale_date: date
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    @model_validator(mode="after")
    def date_must_not_be_future(self):
        if self.sale_date > local_today():
            raise ValueError("Sales cannot be dated in the future.")
        return self


class ReorderRuleInput(InputModel):
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    reorder_point_qty: Decimal = Field(ge=0)
    lead_time_days: int | None = Field(default=None, ge=1, le=365)
    safety_stock_days: int | None = Field(default=None, ge=0, le=90)
    minimum_order_qty: Decimal | None = Field(default=None, ge=0)
    order_multiple: Decimal | None = Field(default=None, ge=0)
    maximum_stock_qty: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True
    notes: str | None = None


class ForecastRequest(InputModel):
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    frequency: Literal["weekly", "monthly"] = "weekly"
    horizon_days: int = Field(default=30, ge=1, le=90)
    source: Literal["auto", "historical_csv", "operational_sales"] = "auto"

    @model_validator(mode="after")
    def horizon_matches_frequency(self):
        choices = {7, 14, 30, 60, 90} if self.frequency == "weekly" else {30, 60, 90}
        if self.horizon_days not in choices:
            raise ValueError(f"Horizon must be one of {sorted(choices)} days for {self.frequency} forecasting.")
        return self


class ReplenishmentCalculate(InputModel):
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    lead_time_days: int | None = Field(default=None, ge=1, le=365)
    safety_stock_days: int | None = Field(default=None, ge=0, le=90)
    service_level: float = Field(default=0.95, gt=0, lt=1)
    source: Literal["auto", "historical_csv", "operational_sales"] = "auto"
    incoming_quantity: Decimal | None = Field(default=None, ge=0)
    incoming_date: date | None = None
    incoming_reference: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def incoming_scenario_is_consistent(self):
        if self.incoming_quantity is not None and self.incoming_quantity > 0 and self.incoming_date is None:
            raise ValueError("An expected date is required when a confirmed incoming quantity is entered.")
        if self.incoming_date is not None and self.incoming_date < local_today():
            raise ValueError("Scenario incoming date cannot be in the past.")
        return self


class SupplierCreate(InputModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    notes: str | None = None


class PurchaseOrderFromRecommendation(InputModel):
    idempotency_key: str = Field(min_length=1, max_length=120)
    supplier_id: int = Field(gt=0)
    site_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    unit_price_inr: Decimal = Field(default=Decimal("0"), ge=0)
    expected_delivery_date: date | None = None
    notes: str | None = None


class PurchaseOrderStatusUpdate(InputModel):
    status: Literal["Pending approval", "Approved", "Cancelled"]


class ReceiptCreate(InputModel):
    idempotency_key: str = Field(min_length=1, max_length=120)
    receipt_reference: str = Field(min_length=1, max_length=120)
    purchase_order_line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    receipt_date: date
    notes: str | None = None
