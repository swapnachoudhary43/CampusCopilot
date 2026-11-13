"""CampusCopilot HTTP API."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import require_roles
from app.database.session import init_db
from app.routes import agent, analytics, auth, chat, complaints, crawl, documents, events, ml, notices, users
from app.services.ml.predict import model_path
from app.services.rag.vector_store import indexed_count


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.app_env.strip().lower() == "production" and settings.secret_key in {
        "dev-only-change-me",
        "replace-with-a-long-random-string",
        "campuscopilot-local-dev-secret-change-me",
    }:
        raise RuntimeError("Set a unique SECRET_KEY before starting in production.")
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CampusCopilot API",
        version="1.0.0",
        description=(
            "Academic demonstration API for campus RAG, controlled workflow tools, "
            "and complaint classification. Sample records are fictional."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(documents.router)
    app.include_router(crawl.router)
    app.include_router(chat.router)
    app.include_router(agent.router)
    app.include_router(complaints.router)
    app.include_router(events.router)
    app.include_router(notices.router)
    app.include_router(analytics.router)
    app.include_router(ml.router)

    @app.get("/")
    def root():
        return {"name": settings.app_name, "docs": "/docs"}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/health/diagnostics")
    def diagnostics(_user=Depends(require_roles("admin"))):
        return {
            "status": "ok",
            "embedding_backend": settings.embedding_backend,
            "embedding_model": settings.embedding_model,
            "llm_mode": settings.resolved_llm_mode(),
            "gemini_configured": settings.gemini_configured,
            "indexed_chunks": indexed_count(),
            "classifier_available": model_path().exists(),
        }

    return app


app = create_app()
