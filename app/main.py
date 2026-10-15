from fastapi import FastAPI

from app.routes.query import router as query_router

app = FastAPI(
    title="Company Brain API",
    description="Permission-aware organisational knowledge assistant starter API.",
    version="0.1.0",
)
app.include_router(query_router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
