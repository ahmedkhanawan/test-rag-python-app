import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, documents, evaluation, health, retrieval
from app.core.config import check_startup_configuration, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    # Raises ConfigurationError (listing variable names only) in production.
    for problem in check_startup_configuration(settings):
        logger.warning("Configuration: %s", problem)

    app = FastAPI(title=settings.app_name)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(retrieval.router, prefix="/api")
    app.include_router(evaluation.router, prefix="/api")

    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:  # added last so it is outermost and also covers early rejections
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,  # the JWT travels in the Authorization header
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )
    logger.info("Application created (environment=%s)", settings.environment)
    return app


app = create_app()
