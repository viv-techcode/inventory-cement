"""FastAPI + static frontend entry point.

Run from the project root with ``uvicorn api.main:app --reload``.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import APIProblem
from api.routes_catalog import router as catalog_router
from api.routes_dashboard import router as dashboard_router
from api.routes_data import router as data_router
from api.routes_forecasting import router as forecasting_router
from api.routes_inventory import router as inventory_router
from api.routes_replenishment import router as replenishment_router
from api.routes_reports import router as reports_router
from api.routes_procurement import router as procurement_router
from api.routes_sales import router as sales_router
from inventory_app import config
from inventory_app.database import SCHEMA_VERSION, Database, initialize_database
from inventory_app.ingestion import ensure_primary_dataset_import
from inventory_app.models import Base, HistoricalObservation, SchemaVersion

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
REQUIRED_TABLES = set(Base.metadata.tables)


def _configure_file_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    target = (config.LOGS_DIR / "app.log").resolve()
    if not any(getattr(handler, "baseFilename", None) == str(target) for handler in logger.handlers):
        handler = logging.FileHandler(target, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _self_check(database: Database) -> dict:
    inspector = inspect(database.engine)
    tables = set(inspector.get_table_names())
    missing = sorted(REQUIRED_TABLES - tables)
    with database.session() as session:
        version_record = session.get(SchemaVersion, 1)
        schema_version = version_record.version if version_record else None
        history_rows = session.scalar(select(HistoricalObservation.id).limit(1))
        if history_rows is None:
            observed_rows = 0
        else:
            observed_rows = session.query(HistoricalObservation).count()
    dataset_rows = None
    if config.SOURCE_CSV.exists():
        with config.SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
            dataset_rows = max(sum(1 for _ in stream) - 1, 0)
    return {
        "schema_version": schema_version,
        "expected_schema_version": SCHEMA_VERSION,
        "schema_current": schema_version == SCHEMA_VERSION,
        "required_tables_present": not missing,
        "missing_tables": missing,
        "historical_rows": observed_rows,
        "dataset_rows": dataset_rows,
        "dataset_row_count_matches": dataset_rows is not None and observed_rows == dataset_rows,
    }


def create_app(*, database_url: str | None = None, auto_import_source: bool = True) -> FastAPI:
    """Create an app; tests can supply an isolated database and disable bundled import."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _configure_file_logging()
        if database_url is None:
            config.ensure_runtime_directories()
        database = Database(database_url or config.DATABASE_URL)
        try:
            initialize_database(database)
            if auto_import_source and config.SOURCE_CSV.exists():
                ensure_primary_dataset_import(database, str(config.SOURCE_CSV))
            app.state.database = database
            app.state.startup_diagnostics = _self_check(database)
            logger.info("Startup self-check: %s", app.state.startup_diagnostics)
            yield
        except Exception:
            logger.exception("Application startup failed")
            raise
        finally:
            database.dispose()

    application = FastAPI(
        title="Construction Materials Operations",
        version="2.0.0",
        description="Offline-first stock, sales, forecasting, replenishment, and reporting API.",
        lifespan=lifespan,
    )
    for router in (
        catalog_router,
        dashboard_router,
        data_router,
        inventory_router,
        sales_router,
        forecasting_router,
        replenishment_router,
        reports_router,
        procurement_router,
    ):
        application.include_router(router)

    @application.get("/api/health", tags=["system"])
    def health(request: Request):
        database: Database = request.app.state.database
        with database.session() as session:
            session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "service": "construction-materials-operations",
            "checks": _self_check(database),
        }

    @application.get("/api/diagnostics", tags=["system"])
    def diagnostics(request: Request):
        database: Database = request.app.state.database
        current = _self_check(database)
        current["startup"] = request.app.state.startup_diagnostics
        return current

    @application.exception_handler(APIProblem)
    async def api_problem_handler(_request: Request, exc: APIProblem):
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            }),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        details = [
            {
                "location": list(error.get("loc", ())),
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": details,
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail),
                    "details": None,
                }
            }),
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled request error at %s",
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed. Check the server log for details.",
                    "details": None,
                }
            },
        )

    # Mount last so /api routes always take precedence. The directory is served as-is:
    # no npm build, CDN, remote font, or runtime dependency fetch is required.
    application.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return application


app = create_app()
