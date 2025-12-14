import os
import sys
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # parent = backend
PARENT = os.path.dirname(BASE_DIR)                     # project root

for p in (BASE_DIR, PARENT):
    if p not in sys.path:
        sys.path.append(p)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app import routes
from backend.data.database import Base, engine, SessionLocal
from backend.pipelines.cleanup_old_articles import delete_old_articles
from backend.app.utils import sanitize_floats
from backend.app.scheduler import scheduler, start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    db = SessionLocal()
    try:
        deleted = delete_old_articles(db, days=2)
        print(f"Cleanup complete: deleted {deleted} old articles.")
    finally:
        db.close()
    print("Starting scheduled pipeline...")
    start_scheduler()
    yield

app = FastAPI(lifespan=lifespan)

origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def sanitize_json_responses(request: Request, call_next):
    response = await call_next(request)
    if isinstance(response, JSONResponse) and isinstance(response.body, (bytes, bytearray)):
        try:
            import json
            content = json.loads(response.body)
            sanitized = sanitize_floats(content)
            return JSONResponse(sanitized, status_code=response.status_code)
        except Exception:
            # fall back to original response if parsing fails
            return response
    return response

app.include_router(routes.router)

Base.metadata.create_all(bind=engine)