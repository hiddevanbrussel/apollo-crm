import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    ai,
    apollo,
    auth,
    companies,
    contacts,
    dashboard,
    research,
    settings as settings_routes,
)
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Apollo CRM API",
    description="Self-hosted CRM that uses Apollo.io as an enrichment data source.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


api_prefix = ""
app.include_router(auth.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(companies.router, prefix=api_prefix)
app.include_router(contacts.router, prefix=api_prefix)
app.include_router(apollo.router, prefix=api_prefix)
app.include_router(settings_routes.router, prefix=api_prefix)
app.include_router(ai.router, prefix=api_prefix)
app.include_router(research.router, prefix=api_prefix)
