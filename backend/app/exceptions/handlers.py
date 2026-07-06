from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import logger
from app.exceptions.custom_exceptions import (
    PaperNotFoundException,
    PaperPermissionDeniedException,
    ResearchNestException,
)


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(PaperNotFoundException)
    async def paper_not_found_handler(
        request: Request,
        exc: PaperNotFoundException,
    ):
        logger.warning(exc.message)

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": 404,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(PaperPermissionDeniedException)
    async def paper_permission_denied_handler(
        request: Request,
        exc: PaperPermissionDeniedException,
    ):
        logger.warning(exc.message)

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {
                    "code": 403,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(ResearchNestException)
    async def researchnest_exception_handler(
        request: Request,
        exc: ResearchNestException,
    ):
        logger.error(exc.message)

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": 400,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        logger.exception("Unhandled exception occurred.")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": 500,
                    "message": "Internal Server Error",
                },
            },
        )