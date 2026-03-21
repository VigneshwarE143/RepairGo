import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from pymongo.errors import DuplicateKeyError

from utils.logger import logger
from utils.response_utils import error_response

logger_instance = logging.getLogger("repairgo")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = 500
    message = "Internal server error"
    data = None

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        message = exc.detail
    elif isinstance(exc, DuplicateKeyError):
        status_code = 400
        message = "Duplicate entry: email already exists"
    else:
        logger_instance.error(f"Exception: {exc}", exc_info=True)

    logger_instance.error(f"Error {status_code}: {message}")
    return JSONResponse(
        status_code=status_code,
        content=error_response(message=message, data=data),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Exception, global_exception_handler)
