from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(title="LLM Gateway")


@app.get("/")
async def root():
    return {"name": "LLM Gateway", "version": "0.1.0"}


app.include_router(health_router)
