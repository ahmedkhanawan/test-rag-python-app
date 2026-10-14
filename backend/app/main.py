import logging

from fastapi import FastAPI

from app.api import admin, auth, chat, health
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    logger.info("Application created (environment=%s)", settings.environment)
    return app


app = create_app()
