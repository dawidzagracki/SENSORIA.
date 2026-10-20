"""FastAPI application factory and application lifecycle."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from sensoria.config import Settings, get_settings
from sensoria.database import engine
from sensoria.modules.accounts.privacy import privacy_job_scheduler
from sensoria.modules.accounts.router import auth_router
from sensoria.modules.accounts.router import router as accounts_router
from sensoria.modules.admin.router import router as admin_router
from sensoria.modules.catalog.router import (
    products_router,
)
from sensoria.modules.catalog.router import (
    router as catalog_router,
)
from sensoria.modules.catalog.samples import router as product_samples_router
from sensoria.modules.library.router import router as library_router
from sensoria.modules.orders.cleanup import cleanup_scheduler
from sensoria.modules.orders.reorder import cart_reorder_router
from sensoria.modules.orders.reorder import router as reorder_router
from sensoria.modules.orders.router import router as orders_router
from sensoria.modules.payments.router import router as payments_router
from sensoria.modules.vouchers.reminders import voucher_reminder_scheduler
from sensoria.modules.vouchers.router import router as vouchers_router
from sensoria.shared.exception_handlers import register_exception_handlers
from sensoria.shared.health import router as health_router
from sensoria.version import APP_VERSION


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run periodic guest-cart cleanup and dispose the shared engine on shutdown."""

    cleanup_task = asyncio.create_task(cleanup_scheduler(_app.state.settings))
    reminder_task = asyncio.create_task(voucher_reminder_scheduler())
    privacy_task = asyncio.create_task(privacy_job_scheduler())
    try:
        yield
    finally:
        cleanup_task.cancel()
        reminder_task.cancel()
        privacy_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        with suppress(asyncio.CancelledError):
            await reminder_task
        with suppress(asyncio.CancelledError):
            await privacy_task
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API application without opening a database connection."""

    selected_settings = settings or get_settings()
    is_development = selected_settings.ENVIRONMENT == "development"
    logging.getLogger("sensoria").setLevel(logging.DEBUG if is_development else logging.INFO)
    app = FastAPI(
        title="Sensoria Shop API",
        version=APP_VERSION,
        debug=is_development,
        docs_url="/docs" if is_development else None,
        redoc_url="/redoc" if is_development else None,
        openapi_url="/openapi.json" if is_development else None,
        lifespan=lifespan,
    )
    app.state.settings = selected_settings
    register_exception_handlers(app, development=is_development)
    app.include_router(health_router)
    for router in (
        catalog_router,
        products_router,
        product_samples_router,
        orders_router,
        reorder_router,
        cart_reorder_router,
        payments_router,
        library_router,
        vouchers_router,
        accounts_router,
        auth_router,
        admin_router,
    ):
        app.include_router(router)
    return app


app = create_app()
