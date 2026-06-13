from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin_router, router
from app.core.config import get_settings
from app.core.responses import now_iso

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="World Cup prediction API for mini program clients.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Unexpected server error",
                "details": {"path": str(request.url.path)},
            }
        },
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "time": now_iso(),
    }


app.include_router(router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/admin")
