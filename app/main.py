from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.observability import initialize_neatlogs, shutdown_neatlogs
from app.service import run_improvement_cycle


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_neatlogs()
    try:
        yield
    finally:
        shutdown_neatlogs()


app = FastAPI(
    title="Trace-Driven Agent Improver",
    description="A bounded, benchmark-driven agent improvement loop.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/improve")
def improve():
    return run_improvement_cycle()
