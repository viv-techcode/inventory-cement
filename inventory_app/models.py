"""SQLAlchemy models for historical observations and the operational ledger."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    benchmark_unit_price_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_basis: Mapped[str] = mapped_column(String(60), default="not configured", nullable=False)
    default_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    safety_stock_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    minimum_order_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    order_multiple: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    maximum_stock_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("safety_stock_days >= 0", name="ck_material_safety_days_nonnegative"),
        CheckConstraint("minimum_order_qty >= 0", name="ck_material_min_order_nonnegative"),
        CheckConstraint("order_multiple >= 0", name="ck_material_order_multiple_nonnegative"),
    )


class ProjectSite(Base):
    __tablename__ = "project_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), default="uploaded_csv", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    report_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class RejectedRow(Base):
    __tablename__ = "rejected_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)


class HistoricalObservation(Base):
    """Immutable imported source record; distinct from operational transactions."""

    __tablename__ = "historical_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    natural_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    observation_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    project_site_id: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    project_type: Mapped[str] = mapped_column(String(60), nullable=False)
    project_phase: Mapped[str] = mapped_column(String(60), nullable=False)
    material: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    consumption_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    opening_stock_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    incoming_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit_price_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    demand_level: Mapped[str] = mapped_column(String(10), nullable=False, default="Medium", server_default="Medium")
    price_level: Mapped[str] = mapped_column(String(10), nullable=False, default="Medium", server_default="Medium")
    supplier_lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    wpi_reference_month: Mapped[str] = mapped_column(String(7), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("observation_datetime", "project_site_id", "material", name="uq_historical_natural_observation"),
        Index("ix_historical_site_material_date", "project_site_id", "material", "observation_datetime"),
        CheckConstraint("consumption_qty >= 0", name="ck_history_consumption_nonnegative"),
        CheckConstraint("opening_stock_qty >= 0", name="ck_history_opening_nonnegative"),
        CheckConstraint("incoming_qty >= 0", name="ck_history_incoming_nonnegative"),
        CheckConstraint("unit_price_inr >= 0", name="ck_history_price_nonnegative"),
    )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("project_sites.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    transaction_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    source_tag: Mapped[str] = mapped_column(String(40), default="operator", server_default="operator", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity >= 0 OR transaction_type = 'adjustment'", name="ck_txn_signed_adjustment_only"),
        CheckConstraint("transaction_type IN ('opening_balance','receipt','consumption','adjustment')", name="ck_txn_type"),
        Index("ix_txn_site_material_date", "site_id", "material_id", "transaction_date"),
    )


class Customer(Base):
    """Optional customer directory for operational sales."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    source_tag: Mapped[str] = mapped_column(String(40), default="operator", server_default="operator", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SalesRecord(Base):
    """A priced operational sale, linked to its stock-decreasing ledger event."""

    __tablename__ = "sales_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("project_sites.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    inventory_transaction_id: Mapped[int] = mapped_column(ForeignKey("inventory_transactions.id"), unique=True, nullable=False)
    sale_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_sale_price_inr: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    revenue_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit_cost_basis_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    cost_of_goods_sold_inr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    gross_margin_inr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    source_tag: Mapped[str] = mapped_column(String(40), default="operator", server_default="operator", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_quantity_positive"),
        CheckConstraint("unit_sale_price_inr >= 0", name="ck_sale_price_nonnegative"),
        CheckConstraint("revenue_inr >= 0", name="ck_sale_revenue_nonnegative"),
        CheckConstraint("cost_of_goods_sold_inr IS NULL OR cost_of_goods_sold_inr >= 0", name="ck_sale_cogs_nonnegative"),
    )


class ReorderRule(Base):
    """Reorder thresholds and planning overrides for one site/material pair."""

    __tablename__ = "reorder_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("project_sites.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    reorder_point_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    safety_stock_days: Mapped[int | None] = mapped_column(Integer)
    minimum_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    order_multiple: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    maximum_stock_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source_tag: Mapped[str] = mapped_column(String(40), default="operator", server_default="operator", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("site_id", "material_id", name="uq_reorder_rule_site_material"),
        CheckConstraint("reorder_point_qty >= 0", name="ck_reorder_point_nonnegative"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days > 0", name="ck_reorder_lead_positive"),
        CheckConstraint("safety_stock_days IS NULL OR safety_stock_days >= 0", name="ck_reorder_safety_nonnegative"),
        CheckConstraint("minimum_order_qty IS NULL OR minimum_order_qty >= 0", name="ck_reorder_minimum_nonnegative"),
        CheckConstraint("order_multiple IS NULL OR order_multiple >= 0", name="ck_reorder_multiple_nonnegative"),
        CheckConstraint("maximum_stock_qty IS NULL OR maximum_stock_qty >= 0", name="ck_reorder_maximum_nonnegative"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(60))
    city: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("project_sites.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="Draft", nullable=False)
    order_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('Draft','Pending approval','Approved','Partially received','Received','Cancelled')", name="ck_po_status"),
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price_inr: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=Decimal("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_po_line_quantity_positive"),
        CheckConstraint("quantity_received >= 0", name="ck_po_line_received_nonnegative"),
        CheckConstraint("unit_price_inr >= 0", name="ck_po_line_price_nonnegative"),
    )


class ReceiptRecord(Base):
    __tablename__ = "receipt_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    receipt_reference: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    receipt_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    inventory_transaction_id: Mapped[int] = mapped_column(ForeignKey("inventory_transactions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_receipt_quantity_positive"),)


class ForecastArtifact(Base):
    __tablename__ = "forecast_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    site_identifier: Mapped[str] = mapped_column(String(160), nullable=False)
    material_name: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    training_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    training_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    training_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_start: Mapped[datetime | None] = mapped_column(DateTime)
    evaluation_end: Mapped[datetime | None] = mapped_column(DateTime)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    feature_config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ReplenishmentReview(Base):
    __tablename__ = "replenishment_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("project_sites.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    accepted_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    calculation_json: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('Accepted','Adjusted','Rejected')", name="ck_replenishment_review_status"),
    )


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
