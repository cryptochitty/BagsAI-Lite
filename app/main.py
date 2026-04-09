import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import tokens, analyze, simulate, portfolio, explain, trade

setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Autonomous Creator Intelligence Platform powered by the Bags API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Register routes
prefix = settings.API_PREFIX
app.include_router(tokens.router, prefix=prefix, tags=["Tokens"])
app.include_router(analyze.router, prefix=prefix, tags=["Analysis"])
app.include_router(simulate.router, prefix=prefix, tags=["Simulation"])
app.include_router(portfolio.router, prefix=prefix, tags=["Portfolio"])
app.include_router(explain.router, prefix=prefix, tags=["Explain & Chat"])
app.include_router(trade.router, prefix=prefix, tags=["Trade & Fee Share"])


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", tags=["UI"], include_in_schema=False)
async def root():
    return FileResponse("app/static/index.html")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
