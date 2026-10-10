from fastapi import FastAPI
from app.service import run_improvement_cycle

app = FastAPI(title="Trace-Driven Agent Improver",
              description="A bounded, benchmark-driven agent improvement loop.", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/improve")
def improve():
    return run_improvement_cycle()
