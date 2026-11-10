"""Catalogue and customer administration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from api.schemas import (
    CustomerCreate,
    CustomerUpdate,
    MaterialCreate,
    MaterialUpdate,
    SiteCreate,
    SiteUpdate,
)
from api.serializers import customer_payload, material_payload, site_payload
from inventory_app.catalog import CatalogError, create_material, create_site, update_material, update_site
from inventory_app.models import Customer, Material, ProjectSite
from inventory_app.sales import SalesError, create_customer

router = APIRouter(prefix="/api", tags=["catalogue"])


def _catalog_status(exc: Exception) -> APIProblem:
    message = str(exc)
    conflict = "already exists" in message.lower() or "cannot be changed" in message.lower()
    return APIProblem(409 if conflict else 422, "catalogue_conflict" if conflict else "catalogue_validation", message)


@router.get("/catalog")
def get_catalog(include_inactive: bool = Query(default=False), session: Session = Depends(get_session)):
    site_query = select(ProjectSite).order_by(ProjectSite.identifier)
    material_query = select(Material).order_by(Material.name)
    customer_query = select(Customer).order_by(Customer.name)
    if not include_inactive:
        site_query = site_query.where(ProjectSite.is_active.is_(True))
        material_query = material_query.where(Material.is_active.is_(True))
        customer_query = customer_query.where(Customer.is_active.is_(True))
    return {
        "sites": [site_payload(item) for item in session.scalars(site_query).all()],
        "materials": [material_payload(item) for item in session.scalars(material_query).all()],
        "customers": [customer_payload(item) for item in session.scalars(customer_query).all()],
    }


@router.get("/sites")
def list_sites(include_inactive: bool = Query(default=False), session: Session = Depends(get_session)):
    query = select(ProjectSite).order_by(ProjectSite.identifier)
    if not include_inactive:
        query = query.where(ProjectSite.is_active.is_(True))
    return {"items": [site_payload(item) for item in session.scalars(query).all()]}


@router.post("/sites", status_code=201)
def add_site(body: SiteCreate, session: Session = Depends(get_session)):
    try:
        site = create_site(session, **body.model_dump())
        session.commit()
        return {"item": site_payload(site)}
    except CatalogError as exc:
        raise _catalog_status(exc) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "duplicate_site", "A site with this identifier already exists.") from exc


@router.patch("/sites/{site_id}")
def edit_site(site_id: int, body: SiteUpdate, session: Session = Depends(get_session)):
    changes = body.model_dump(exclude_unset=True)
    try:
        site = update_site(session, site_id, **changes)
        session.commit()
        return {"item": site_payload(site)}
    except CatalogError as exc:
        raise _catalog_status(exc) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "site_conflict", "The site update conflicts with an existing identifier.") from exc


@router.get("/materials")
def list_materials(include_inactive: bool = Query(default=False), session: Session = Depends(get_session)):
    query = select(Material).order_by(Material.name)
    if not include_inactive:
        query = query.where(Material.is_active.is_(True))
    return {"items": [material_payload(item) for item in session.scalars(query).all()]}


@router.post("/materials", status_code=201)
def add_material(body: MaterialCreate, session: Session = Depends(get_session)):
    try:
        material = create_material(session, **body.model_dump())
        session.commit()
        return {"item": material_payload(material)}
    except CatalogError as exc:
        raise _catalog_status(exc) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "duplicate_material", "A material with this name already exists.") from exc


@router.patch("/materials/{material_id}")
def edit_material(material_id: int, body: MaterialUpdate, session: Session = Depends(get_session)):
    changes = body.model_dump(exclude_unset=True)
    try:
        material = update_material(session, material_id, **changes)
        session.commit()
        return {"item": material_payload(material)}
    except CatalogError as exc:
        raise _catalog_status(exc) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "material_conflict", "The material update conflicts with an existing catalogue entry.") from exc


@router.get("/customers")
def list_customers(include_inactive: bool = Query(default=False), session: Session = Depends(get_session)):
    query = select(Customer).order_by(Customer.name)
    if not include_inactive:
        query = query.where(Customer.is_active.is_(True))
    return {"items": [customer_payload(item) for item in session.scalars(query).all()]}


@router.post("/customers", status_code=201)
def add_customer(body: CustomerCreate, session: Session = Depends(get_session)):
    try:
        customer = create_customer(session, **body.model_dump())
        session.commit()
        return {"item": customer_payload(customer)}
    except SalesError as exc:
        conflict = "already exists" in str(exc).lower()
        raise APIProblem(409 if conflict else 422, "customer_conflict" if conflict else "customer_validation", str(exc)) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "duplicate_customer", "A customer with this name already exists.") from exc


@router.patch("/customers/{customer_id}")
def edit_customer(customer_id: int, body: CustomerUpdate, session: Session = Depends(get_session)):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise APIProblem(404, "customer_not_found", "Customer not found.")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        name = changes["name"].strip()
        duplicate = session.scalar(select(Customer.id).where(func.lower(Customer.name) == name.lower(), Customer.id != customer_id))
        if duplicate:
            raise APIProblem(409, "duplicate_customer", "A customer with this name already exists.")
        customer.name = name
    for key in ("contact_name", "email", "phone", "notes"):
        if key in changes:
            value = changes[key]
            setattr(customer, key, value.strip() if isinstance(value, str) and value.strip() else None)
    if "is_active" in changes and changes["is_active"] is not None:
        customer.is_active = changes["is_active"]
    try:
        session.commit()
        return {"item": customer_payload(customer)}
    except IntegrityError as exc:
        raise APIProblem(409, "customer_conflict", "The customer update conflicts with an existing entry.") from exc
