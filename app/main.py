from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.graph import GraphRepository
from app.settings import settings

from app.routes.query import router as query_router
from app.routes.profile import router as profile_router
from app.routes.admin import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = GraphRepository.from_settings(settings)
    yield
    if app.state.graph is not None:
        app.state.graph.close()


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
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(query_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
