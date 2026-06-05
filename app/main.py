from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.db.session import init_db
from app.db.redis import init_redis, close_redis
from app.api.routes.main import router as api_router
from app.api.routes.dashboard import router as dash_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    await init_db()
    yield
    await close_redis()


app = FastAPI(
    title="Brooder Control API",
    description="سیستم کنترل گرم‌خانه جوجه اردک",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# داشبورد (صفحات HTML با لاگین)
app.include_router(dash_router)

# API (برای ESP و Swagger)
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(302)
async def redirect_handler(request: Request, exc):
    return RedirectResponse(url="/login")


@app.get("/health")
async def health():
    return {"status": "ok"}
