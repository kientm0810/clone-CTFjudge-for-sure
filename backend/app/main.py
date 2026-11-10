from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.providers import router as providers_router
from app.api.runs import router as runs_router
from app.api.workflows import router as workflows_router
from app.database import init_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database()
    yield


app = FastAPI(
    title="CTFJudge Workflow API",
    version="0.2.0",
    description="Minimal extensible workflow engine for golden-solution comparison.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(providers_router)
app.include_router(workflows_router)
app.include_router(runs_router)

