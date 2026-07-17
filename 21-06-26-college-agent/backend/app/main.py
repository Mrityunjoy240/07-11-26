import logging
from app.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from uuid import uuid4

from app.config import settings
from app.database import init_db
from app.api import qa, conversations, tts, stt, monitoring, auth_routes, admin, health

init_db()

app = FastAPI(title="College Voice Agent API", version="1.0.0")

@app.middleware("http")
async def add_session_id_middleware(request: Request, call_next):
    if not hasattr(request.state, 'session_id'):
        request.state.session_id = str(uuid4())
    response = await call_next(request)
    return response

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.temp_audio_dir, exist_ok=True)
app.mount("/audio", StaticFiles(directory=settings.temp_audio_dir), name="audio")

app.include_router(qa.router, prefix="/qa", tags=["qa"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(tts.router, prefix="/qa", tags=["tts"])
app.include_router(stt.router, prefix="/qa", tags=["stt"])
app.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth_routes.router, tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

possible_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"),
    os.path.join(os.getcwd(), "frontend", "dist"),
    "/app/frontend/dist"
]

frontend_path = None
for path in possible_paths:
    if os.path.exists(path):
        frontend_path = path
        break

if frontend_path:
    logger.info(f"Frontend found at: {frontend_path}")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"message": "College Voice Agent API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
