from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.container import Container
from src.interfaces.api.health_router import router as health_router


def create_app() -> FastAPI:
    container = Container()

    application = FastAPI(
        title="Agentic RAG Customer Service",
        version="0.1.0",
    )

    application.container = container  # type: ignore[attr-defined]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)

    return application


app = create_app()
