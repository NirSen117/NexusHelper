from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.graph import GraphRepository
from app.settings import settings

from app.routes.query import router as query_router
from app.routes.profile import router as profile_router
from app.routes.companies import router as companies_router
from app.routes.workspace import router as workspace_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production graphs are company-specific and are opened on demand. Avoid
    # blocking API startup on a remote graph handshake.
    app.state.graph = None if settings.app_env.lower() == "production" else GraphRepository.from_settings(settings)
    app.state.company_graphs = {}
    yield
    if app.state.graph is not None:
        app.state.graph.close()
    for graph in app.state.company_graphs.values():
        graph.close()


app = FastAPI(
    title="NexusHelper API",
    description="Permission-aware organisational knowledge assistant starter API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(set(settings.cors_allowed_origins + [settings.frontend_origin])),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Company-ID", "X-Demo-User"],
)
app.include_router(query_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(companies_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
