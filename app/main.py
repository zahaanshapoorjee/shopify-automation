from contextlib import asynccontextmanager
from typing import Union
from fastapi import FastAPI
from app.api.routes import router
from app.state.store import init_database, postgres_store
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    await init_database()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await postgres_store.close()

app = FastAPI(lifespan=lifespan)
app.include_router(router)

@app.get("/")
def read_root():
    return {
        "message": "Hello World!",
        "database": "Connected to Neon PostgreSQL"
    }

