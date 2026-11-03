"""CSV inspection, validation and idempotent historical-data imports."""
from __future__ import annotations

import hashlib
import io
import json
import re
from statistics import median
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from inventory_app.database import Database
from inventory_app.levels import add_series_levels
from inventory_app.models import (
    HistoricalObservation,
    ImportRun,
    Material,
    ProjectSite,
    RejectedRow,
)

EXPECTED_COLUMNS = (
    "date",
    "project_site_id",
    "city",
    "state",
    "project_type",
    "project_phase",
    "material",
    "unit",
    "consumption_qty",
    "opening_stock_qty",
    "incoming_qty",
    "unit_price_inr",
    "supplier_lead_time_days",
    "wpi_reference_month",
)
NUMERIC_COLUMNS = (
    "consumption_qty",
    "opening_stock_qty",
    "incoming_qty",
    "unit_price_inr",
    "supplier_lead_time_days",
)


@dataclass(frozen=True)
class ImportResult:
    run_id: int | None
    file_hash: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    duplicate_rows: int
    duplicate_file: bool = False
    message: str = ""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    """Read a CSV while preserving values for explicit validation downstream."""
    try:
        return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(raw), encoding="latin-1")


def default_column_mapping(columns: list[str]) -> dict[str, str | None]:
    normalized = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): str(c) for c in columns}
    return {expected: normalized.get(re.sub(r"[^a-z0-9]+", "", expected.lower())) for expected in EXPECTED_COLUMNS}


def validate_schema(columns: list[str], mapping: dict[str, str | None] | None = None) -> list[str]:
    mapping = mapping or default_column_mapping(columns)
    errors: list[str] = []
    used: dict[str, str] = {}
    for expected in EXPECTED_COLUMNS:
        actual = mapping.get(expected)
        if not actual or actual not in columns:
            errors.append(f"Required field '{expected}' has no source column mapping.")
            continue
        if actual in used:
            errors.append(f"Source column '{actual}' is mapped to both '{used[actual]}' and '{expected}'.")
        used[actual] = expected
    return errors


def _decimal(value: Any, field: str) -> Decimal:
    if pd.isna(value):
        raise ValueError(f"{field} is missing")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError(f"{field} is not numeric") from None
    if not parsed.is_finite():
        raise ValueError(f"{field} is not finite")
    return parsed


def _canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in EXPECTED_COLUMNS:
        value = row[name]
        if isinstance(value, datetime):
            result[name] = value.isoformat(timespec="seconds")
        elif isinstance(value, Decimal):
            result[name] = format(value.normalize(), "f")
        else:
            result[name] = value
    return result


def _row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(_canonical_row(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _natural_key(row: dict[str, Any]) -> str:
    payload = "|".join(
        [row["date"].isoformat(timespec="seconds"), row["project_site_id"], row["material"]]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_frame(
    frame: pd.DataFrame,
    mapping: dict[str, str | None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return normalized valid rows, row-level rejections and preview metadata.

    No row is silently dropped. Each rejected record carries its original values and
    a readable reason; column mapping is explicit and the source is never mutated.
    """
    mapping = mapping or default_column_mapping(list(frame.columns))
    schema_errors = validate_schema(list(frame.columns), mapping)
    if schema_errors:
        return [], [], {"schema_errors": schema_errors, "total_rows": int(len(frame)), "valid_rows": 0}

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    unit_by_material: dict[str, set[str]] = {}
    site_meta: dict[str, set[tuple[str, str, str]]] = {}

    for position, (_, source) in enumerate(frame.iterrows(), start=2):
        raw = {str(c): (None if pd.isna(v) else v) for c, v in source.to_dict().items()}
        row_no = position
        row: dict[str, Any] = {}
        issues: list[str] = []
        try:
            raw_date = source[mapping["date"]]
            parsed_date = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(parsed_date):
                raise ValueError("date is missing or invalid")
            if getattr(parsed_date, "tzinfo", None) is not None:
                parsed_date = parsed_date.tz_localize(None)
            row["date"] = parsed_date.to_pydatetime().replace(microsecond=0)
        except Exception as exc:
            issues.append(str(exc) if str(exc) else "date is invalid")

        for field in ("project_site_id", "city", "state", "project_type", "project_phase", "material", "unit", "wpi_reference_month"):
            raw_value = source[mapping[field]]
            value = "" if pd.isna(raw_value) else str(raw_value).strip()
            if not value:
                issues.append(f"{field} is missing")
            row[field] = value

        for field in NUMERIC_COLUMNS:
            try:
                value = _decimal(source[mapping[field]], field)
                if value < 0:
                    issues.append(f"{field} cannot be negative")
                if field == "supplier_lead_time_days" and (value < 1 or value != value.to_integral_value()):
                    issues.append("supplier_lead_time_days must be a whole number greater than zero")
                if field == "unit_price_inr" and value == 0:
                    issues.append("unit_price_inr must be greater than zero for cost analysis")
                row[field] = int(value) if field == "supplier_lead_time_days" else value
            except ValueError as exc:
                issues.append(str(exc))

        month = row.get("wpi_reference_month", "")
        if month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            issues.append("wpi_reference_month must use YYYY-MM format")

        if issues:
            rejected.append({"row_number": row_no, "reason": "; ".join(dict.fromkeys(issues)), "raw": raw})
            continue

        unit_by_material.setdefault(row["material"], set()).add(row["unit"])
        site_meta.setdefault(row["project_site_id"], set()).add((row["city"], row["state"], row["project_type"]))
        row["_raw"] = raw
        row["_source_key"] = _row_hash(row)
        row["_natural_key"] = _natural_key(row)
        row["_row_number"] = row_no
        valid.append(row)

    conflicted_materials = {name: units for name, units in unit_by_material.items() if len(units) > 1}
    conflicted_sites = {name: values for name, values in site_meta.items() if len(values) > 1}
    if conflicted_materials or conflicted_sites:
        kept: list[dict[str, Any]] = []
        for row in valid:
            conflict_messages: list[str] = []
            if row["material"] in conflicted_materials:
                conflict_messages.append(f"material '{row['material']}' appears with incompatible units {sorted(conflicted_materials[row['material']])}")
            if row["project_site_id"] in conflicted_sites:
                conflict_messages.append(f"site '{row['project_site_id']}' has conflicting city/state/project type values")
            if conflict_messages:
                rejected.append({"row_number": row["_row_number"], "reason": "; ".join(conflict_messages), "raw": row["_raw"]})
            else:
                kept.append(row)
        valid = kept

    if valid:
        level_frame = pd.DataFrame.from_records([
            {
                "date": row["date"],
                "project_site_id": row["project_site_id"],
                "material": row["material"],
                "consumption_qty": float(row["consumption_qty"]),
                "unit_price_inr": float(row["unit_price_inr"]),
            }
            for row in valid
        ])
        level_frame = add_series_levels(level_frame)
        for position, row in enumerate(valid):
            row["demand_level"] = str(level_frame.iloc[position]["demand_level"])
            row["price_level"] = str(level_frame.iloc[position]["price_level"])

    summary = {
        "schema_errors": [],
        "total_rows": int(len(frame)),
        "valid_rows": len(valid),
        "rejected_rows": len(rejected),
        "unit_distribution": frame[mapping["unit"]].astype(str).value_counts(dropna=False).to_dict(),
    }
    return valid, rejected, summary


def ensure_catalogs_from_history(session: Session) -> None:
    """Create missing catalog entries from accepted source values, never overwrite user edits."""
    rows = session.execute(
        select(
            HistoricalObservation.material,
            HistoricalObservation.unit,
            HistoricalObservation.project_site_id,
            HistoricalObservation.city,
            HistoricalObservation.state,
            HistoricalObservation.project_type,
            HistoricalObservation.unit_price_inr,
            HistoricalObservation.supplier_lead_time_days,
        )
    ).all()
    if not rows:
        return
    materials: dict[str, dict[str, Any]] = {}
    sites: dict[str, dict[str, Any]] = {}
    for name, unit, identifier, city, state, project_type, price, lead in rows:
        entry = materials.setdefault(name, {"unit": unit, "prices": [], "leads": []})
        if entry["unit"] == unit:
            entry["prices"].append(Decimal(price))
            entry["leads"].append(int(lead))
        site = sites.setdefault(identifier, {"city": city, "state": state, "project_types": set()})
        site["project_types"].add(project_type)

    for name, values in materials.items():
        material = session.scalar(select(Material).where(Material.name == name))
        prices = sorted(values["prices"])
        median_price = median(prices) if prices else None
        lead_days = sorted(values["leads"])
        median_lead = int(median(lead_days)) if lead_days else None
        if material is None:
            material = Material(
                name=name,
                unit=values["unit"],
                benchmark_unit_price_inr=median_price,
                price_basis="historical dataset median (estimate)",
                default_lead_time_days=median_lead,
            )
            session.add(material)
        elif material.unit != values["unit"]:
            # Catalog unit is authoritative for operational transactions; import rows
            # with a mismatch are rejected before reaching this point.
            continue
        else:
            if material.benchmark_unit_price_inr is None:
                material.benchmark_unit_price_inr = median_price
                material.price_basis = "historical dataset median (estimate)"
            if material.default_lead_time_days is None:
                material.default_lead_time_days = median_lead

    for identifier, values in sites.items():
        site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == identifier))
        inferred_type = next(iter(values["project_types"])) if len(values["project_types"]) == 1 else None
        if site is None:
            session.add(
                ProjectSite(
                    identifier=identifier,
                    name=identifier,
                    city=values["city"],
                    state=values["state"],
                    project_type=inferred_type,
                    notes="Seeded from imported historical source; verify operational site details.",
                )
            )


def import_dataframe(
    db: Database,
    frame: pd.DataFrame,
    *,
    file_name: str,
    file_bytes: bytes,
    mapping: dict[str, str | None] | None = None,
    source_kind: str = "uploaded_csv",
    source_tag: str | None = None,
) -> ImportResult:
    """Validate then persist a CSV once. History is immutable; conflicts are logged."""
    observation_tag = source_tag or source_kind
    if not observation_tag.strip() or len(observation_tag) > 40:
        raise ValueError("source_tag must contain 1–40 characters.")
    fingerprint = sha256_bytes(file_bytes)
    with db.session() as session:
        prior = session.scalar(select(ImportRun).where(ImportRun.file_hash == fingerprint))
        if prior is not None:
            return ImportResult(
                prior.id,
                fingerprint,
                prior.total_rows,
                prior.accepted_rows,
                prior.rejected_rows,
                prior.duplicate_rows,
                duplicate_file=True,
                message="This exact file has already been imported; no records were added.",
            )

        valid, rejected, validation_summary = validate_frame(frame, mapping)
        run = ImportRun(
            file_name=file_name,
            file_hash=fingerprint,
            source_kind=source_kind,
            total_rows=int(len(frame)),
            accepted_rows=0,
            rejected_rows=0,
            duplicate_rows=0,
            status="validating",
            report_json="{}",
        )
        session.add(run)
        session.flush()

        if validation_summary.get("schema_errors"):
            report = {"schema_errors": validation_summary["schema_errors"], "total_rows": int(len(frame))}
            run.status = "rejected_schema"
            run.rejected_rows = int(len(frame))
            run.report_json = json.dumps(report, ensure_ascii=False)
            for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
                raw = {str(k): (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
                session.add(RejectedRow(import_id=run.id, source_row_number=row_number, reason="; ".join(report["schema_errors"]), raw_json=json.dumps(raw, ensure_ascii=False, default=str)))
            session.commit()
            return ImportResult(run.id, fingerprint, len(frame), 0, len(frame), 0, message="Schema validation failed.")

        # Load unique constraints and catalog lookups in batches; the source may contain
        # thousands of rows, so validation must not issue a database query per record.
        existing_source_keys = set(session.scalars(select(HistoricalObservation.source_key)).all())
        existing_natural_keys = set(session.scalars(select(HistoricalObservation.natural_key)).all())
        materials_by_name = {item.name: item for item in session.scalars(select(Material)).all()}
        sites_by_identifier = {item.identifier: item for item in session.scalars(select(ProjectSite)).all()}
        seen_natural: set[str] = set()
        seen_source: set[str] = set()
        duplicate_count = 0
        accepted_count = 0
        new_records: list[HistoricalObservation] = []
        row_rejections = list(rejected)

        for row in valid:
            source_key = row["_source_key"]
            natural_key = row["_natural_key"]
            reason: str | None = None
            if source_key in seen_source or source_key in existing_source_keys:
                reason = "Exact source row already exists."
            elif natural_key in seen_natural or natural_key in existing_natural_keys:
                reason = "A historical observation already exists for this site, material and timestamp; changed values were not overwritten."
            else:
                material = materials_by_name.get(row["material"])
                if material is not None and material.unit != row["unit"]:
                    reason = f"Catalog unit mismatch: '{row['material']}' is configured as '{material.unit}', not '{row['unit']}'."
                site = sites_by_identifier.get(row["project_site_id"])
                if site is not None and (
                    site.city != row["city"] or site.state != row["state"]
                    or (site.project_type is not None and site.project_type != row["project_type"])
                ):
                    reason = f"Site catalogue conflict for '{row['project_site_id']}'; source values do not match the configured site."

            if reason:
                if reason.startswith("Exact source row") or "observation already exists" in reason.lower():
                    duplicate_count += 1
                row_rejections.append({"row_number": row["_row_number"], "reason": reason, "raw": row["_raw"]})
                continue

            seen_source.add(source_key)
            seen_natural.add(natural_key)
            new_records.append(HistoricalObservation(
                import_id=run.id,
                source_row_number=row["_row_number"],
                source_key=source_key,
                natural_key=natural_key,
                observation_datetime=row["date"],
                project_site_id=row["project_site_id"],
                city=row["city"],
                state=row["state"],
                project_type=row["project_type"],
                project_phase=row["project_phase"],
                material=row["material"],
                unit=row["unit"],
                consumption_qty=row["consumption_qty"],
                opening_stock_qty=row["opening_stock_qty"],
                incoming_qty=row["incoming_qty"],
                unit_price_inr=row["unit_price_inr"],
                demand_level=row["demand_level"],
                price_level=row["price_level"],
                supplier_lead_time_days=row["supplier_lead_time_days"],
                wpi_reference_month=row["wpi_reference_month"],
                raw_json=json.dumps(row["_raw"], ensure_ascii=False, default=str),
            ))
            accepted_count += 1
        if new_records:
            session.add_all(new_records)

        duplicate_count = min(duplicate_count, len(row_rejections))
        for item in row_rejections:
            session.add(
                RejectedRow(
                    import_id=run.id,
                    source_row_number=int(item["row_number"]),
                    reason=str(item["reason"]),
                    raw_json=json.dumps(item["raw"], ensure_ascii=False, default=str),
                )
            )
        run.accepted_rows = accepted_count
        run.rejected_rows = len(row_rejections)
        run.duplicate_rows = duplicate_count
        run.status = "completed" if not row_rejections else ("completed_with_rejections" if accepted_count else "rejected_rows")
        run.report_json = json.dumps(
            {
                **validation_summary,
                "rejected_count": len(row_rejections),
                "duplicate_count": duplicate_count,
                "source_file_sha256": fingerprint,
                "column_mapping": mapping or default_column_mapping(list(frame.columns)),
            },
            ensure_ascii=False,
            default=str,
        )
        try:
            session.flush()
            ensure_catalogs_from_history(session)
            session.commit()
        except IntegrityError:
            session.rollback()
            raise
        return ImportResult(run.id, fingerprint, int(len(frame)), accepted_count, len(row_rejections), duplicate_count, message=run.status)


def ensure_primary_dataset_import(db: Database, path: str) -> ImportResult | None:
    """One-time first-run load. Subsequent restarts are a no-op."""
    from pathlib import Path

    source_path = Path(path)
    if not source_path.exists():
        return None
    raw = source_path.read_bytes()
    fingerprint = sha256_bytes(raw)
    with db.session() as session:
        prior = session.scalar(select(ImportRun).where(ImportRun.file_hash == fingerprint))
        if prior is not None:
            return ImportResult(prior.id, fingerprint, prior.total_rows, prior.accepted_rows, prior.rejected_rows, prior.duplicate_rows, duplicate_file=True, message="Primary source was previously imported.")
    frame = read_csv_bytes(raw)
    # Record the canonical file fingerprint when its observations already exist.
    if len(frame) == 8940:
        valid, rejected, summary = validate_frame(frame)
        if not rejected and len(valid) == len(frame) and not summary.get("schema_errors"):
            incoming_keys = {row["_natural_key"] for row in valid}
            with db.session() as session:
                existing_keys = set(session.scalars(select(HistoricalObservation.natural_key)).all())
                if incoming_keys and incoming_keys == existing_keys:
                    run = ImportRun(
                        file_name=source_path.name,
                        file_hash=fingerprint,
                        source_kind="construction_materials_dehradun_dataset",
                        total_rows=len(frame),
                        accepted_rows=len(frame),
                        rejected_rows=0,
                        duplicate_rows=0,
                        status="completed",
                        report_json=json.dumps({"reconciled_existing_observations": True}),
                    )
                    session.add(run)
                    session.commit()
                    return ImportResult(run.id, fingerprint, len(frame), len(frame), 0, 0, message="Dataset matched the observations already stored.")
    return import_dataframe(
        db,
        frame,
        file_name=source_path.name,
        file_bytes=raw,
        source_kind="construction_materials_dehradun_dataset",
    )
